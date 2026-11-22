#!/usr/bin/env python3
"""FB: real schema-v1-to-v2 synthetic SHADOW + native Swift metadata copy bridge.

LAB ONLY. Requires preexisting marked disposable root, a seeded full v1 and
fresh migrated v2 shadow. Never consumes the user's sqlite or iPad files.
Operations are copy-only, never delete source, purge snapshots, retire SQLite,
or modify downloaded/read progress. Review is non-destructive.
"""
from __future__ import annotations
import os
from pathlib import Path
import re
import sqlite3
import stat
import subprocess
import uuid
from dataclasses import dataclass
from contextlib import closing
from typing import Callable

from build70_ey_shadow_schema_migration import _root, validate_v2, EYUnsafe
from build70_fa_full_schema_shadow import TABLES, validate_full_schema
from build70_fa_copy_only_router import FACopyOnlyRouter

class FBUnsafe(RuntimeError): pass
class FBInterrupted(RuntimeError): pass

COPY_DDL = '''
CREATE TABLE offline_copy_journal (
    operation_id TEXT PRIMARY KEY CHECK(length(operation_id)=32 AND operation_id NOT GLOB '*[^0-9a-f]*'),
    chapter_id INTEGER NOT NULL UNIQUE REFERENCES chapters(internal_id) ON DELETE RESTRICT,
    source_id TEXT NOT NULL,
    source_manga_id TEXT NOT NULL,
    source_chapter_id TEXT NOT NULL,
    snapshot_name TEXT NOT NULL UNIQUE CHECK(
        length(snapshot_name)=35 AND substr(snapshot_name,1,3)='ev_' AND
        substr(snapshot_name,4) NOT GLOB '*[^0-9a-f]*'),
    source_device TEXT NOT NULL,
    source_inode TEXT NOT NULL,
    state TEXT NOT NULL CHECK(state IN ('prepared','copy_verified','needs_review')),
    consent TEXT NOT NULL CHECK(consent='synthetic_confirmation'),
    reason TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX offline_copy_state_idx ON offline_copy_journal(state);
'''

@dataclass(frozen=True)
class FBPlan:
    chapter_id: int
    source: str
    manga: str
    leaf: str
    device: str
    inode: str

class FBShadowCopyBridge:
    def __init__(self, root: Path, native_binary: Path, *, running_ids=(), pending_ids=(), sealed_only=False):
        self.sealed_only=bool(sealed_only)
        self.root=Path(root)
        app, _, shadow = _root(self.root)
        self.app=app
        self.native_binary=Path(native_binary)
        if (self.native_binary.is_symlink() or not self.native_binary.is_file() or
                not os.access(self.native_binary,os.X_OK)):
            raise FBUnsafe('native test binary unavailable')
        if shadow.is_symlink() or not shadow.is_file() or shadow.stat().st_nlink!=1:
            raise FBUnsafe('existing safe shadow-v2 fixture required')
        self.db=sqlite3.connect(shadow.as_uri()+'?mode=rw',uri=True,isolation_level=None,timeout=1.5)
        try:
            self.db.execute('PRAGMA foreign_keys=ON')
            self.db.execute('PRAGMA synchronous=FULL')
            self.db.execute('PRAGMA busy_timeout=1500')
            tables={r[0] for r in self.db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
            extras=tables-(set(TABLES)|{'offline_deletion_journal'})
            if extras not in (set(),{'offline_copy_journal'}):
                raise FBUnsafe('unexpected schema extras in lab')
            # Revalidate *every* legacy table on reopen, not merely the journal.
            validate_full_schema(self.db,version=2,allow_copy_journal=bool(extras))
            if not extras:
                self.db.execute('BEGIN IMMEDIATE')
                try:
                    for sql in COPY_DDL.split(';'):
                        if sql.strip():self.db.execute(sql)
                    self.db.execute('COMMIT')
                except BaseException:
                    self.db.execute('ROLLBACK');raise
            self.running_ids=frozenset(running_ids)
            self.pending_ids=frozenset(pending_ids)
            if (app/'Downloads').is_symlink() or (app/'Quarantine').is_symlink():
                raise FBUnsafe('unsafe synthetic parent')
        except BaseException:
            self.db.close()
            raise

    def close(self):self.db.close()
    def __enter__(self):return self
    def __exit__(self,*_):self.close()

    def _native(self,action,source,manga,leaf,dest,identity=None):
        if self.sealed_only:
            action={"inspectmeta":"inspectsealed", "snapshotmeta":"snapshotsealed",
                    "verifycopymeta":"verifycopysealed"}.get(action, action)
        args=[str(self.native_binary),action,str(self.root),source,manga,leaf,dest]
        if identity is not None:args.extend(identity)
        r=subprocess.run(args,capture_output=True,text=True,timeout=18)
        if r.returncode or len(r.stdout)>2048:raise FBUnsafe('native operation rejected: preserve originals')
        import json
        try:data=json.loads(r.stdout)
        except ValueError as exc:raise FBUnsafe('invalid Swift result') from exc
        if data.get('status') not in ('observed','copy_verified'):
            raise FBUnsafe('Swift returned unexpected state')
        if (not isinstance(data.get('device'),str) or not data['device'].isdigit() or
                not isinstance(data.get('inode'),str) or not data['inode'].isdigit()):
            raise FBUnsafe('invalid native identity')
        return data

    def _rows(self):
        return self.db.execute('''SELECT c.internal_id,m.source_id,m.source_manga_id,
                c.source_chapter_id,d.state,c.downloaded
                FROM downloads d JOIN chapters c ON c.internal_id=d.chapter_id
                JOIN manga m ON m.internal_id=c.manga_id
                ORDER BY c.internal_id''').fetchall()

    def _by_id(self,chapter):
        return next((row for row in self._rows() if row[0]==chapter),None)

    def _journal(self,chapter):
        return self.db.execute('''SELECT operation_id,chapter_id,source_id,source_manga_id,
            source_chapter_id,snapshot_name,source_device,source_inode,state
            FROM offline_copy_journal WHERE chapter_id=?''',(chapter,)).fetchone()

    @staticmethod
    def _components(source,manga,leaf):
        for c in (source,manga,leaf):
            if not isinstance(c,str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,80}',c) or c in ('.','..'):
                raise FBUnsafe('unsafe canonical component')
        return source,manga,leaf

    def _plan(self,selected,*,bulk=False):
        if any(type(i) is not int or i<=0 for i in selected) or len(selected)!=len(set(selected)):
            raise FBUnsafe('invalid chapter selections')
        if any(i in self.running_ids or i in self.pending_ids for i in selected):
            raise FBUnsafe('active or pending worker')
        if bulk and (self.running_ids or self.pending_ids):raise FBUnsafe('bulk requires idle worker')
        rows=self._rows();byid={r[0]:r for r in rows}
        if len(rows)!=len(byid) or set(selected)-set(byid):raise FBUnsafe('unknown download')
        identities=[FACopyOnlyRouter._identity(*r[1:4]) for r in rows]
        if len(set(identities))!=len(identities):raise FBUnsafe('canonical identity collision')
        planned=[]
        for chapter in selected:
            row=byid[chapter]
            if row[4] not in ('completed','failed','paused') or row[5] != (1 if row[4]=='completed' else 0):
                raise FBUnsafe('unexpected chapter state')
            if self.sealed_only and row[4] != 'completed':
                raise FBUnsafe('sealed snapshot requires completed chapter')
            if self._journal(chapter):raise FBUnsafe('preexisting journal requires review')
            source,manga,leaf=self._components(*row[1:4])
            observed=self._native('inspectmeta',source,manga,leaf,'ev_'+uuid.uuid4().hex)
            if observed['status']!='observed':raise FBUnsafe('unexpected native admission')
            planned.append(FBPlan(chapter,source,manga,leaf,observed['device'],observed['inode']))
        return planned

    def _persist_intent(self,plan,dest):
        op=dest[3:]
        self.db.execute('BEGIN IMMEDIATE')
        try:
            current=self._by_id(plan.chapter_id)
            if (current is None or current[1:4]!=(plan.source,plan.manga,plan.leaf)
                    or self._journal(plan.chapter_id) or
                    (self.sealed_only and (current[4],current[5]) != ('completed',1))):
                raise FBUnsafe('owner changed before intent commit')
            self.db.execute('''INSERT INTO offline_copy_journal
                (operation_id,chapter_id,source_id,source_manga_id,source_chapter_id,
                 snapshot_name,source_device,source_inode,state,consent)
                VALUES (?,?,?,?,?,?,?,?,?,?)''',
                (op,plan.chapter_id,plan.source,plan.manga,plan.leaf,dest,
                 plan.device,plan.inode,'prepared','synthetic_confirmation'))
            self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK');raise

    def _owner_still_matches(self,row):
        current=self._by_id(row[1])
        return (current is not None and current[1:4]==row[2:5] and
                current[4] in ('completed','failed','paused') and
                current[5] == (1 if current[4]=='completed' else 0) and
                (not self.sealed_only or current[4]=='completed'))

    def _transition(self,row,old,new,reason=''):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            if not self._owner_still_matches(row):raise FBUnsafe('owner changed before state update')
            updated=self.db.execute('''UPDATE offline_copy_journal SET state=?,reason=?,updated_at=CURRENT_TIMESTAMP
               WHERE operation_id=? AND state=?''',(new,reason[:100],row[0],old))
            if updated.rowcount!=1:raise FBUnsafe('CAS conflict')
            self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK');raise

    def _execute(self,plans,*,crash_at=None):
        completed=[]
        for plan in plans:
            # Pre-copy revalidation, while retaining source bytes if drift.
            observed=self._native('inspectmeta',plan.source,plan.manga,plan.leaf,'ev_'+uuid.uuid4().hex)
            if observed['status']!='observed':raise FBUnsafe('unexpected recheck result')
            if (observed['device'],observed['inode'])!=(plan.device,plan.inode):
                raise FBUnsafe('source changed since batch preflight')
            dest='ev_'+uuid.uuid4().hex
            self._persist_intent(plan,dest)
            if crash_at=='after_intent':raise FBInterrupted('after_intent')
            row=self._journal(plan.chapter_id)
            snapshot=self._native('snapshotmeta',plan.source,plan.manga,plan.leaf,dest,(plan.device,plan.inode))
            if snapshot['status']!='copy_verified':raise FBUnsafe('snapshot was not verified')
            if crash_at=='after_snapshot':raise FBInterrupted('after_snapshot')
            copied=self._native('verifycopymeta',plan.source,plan.manga,plan.leaf,dest,(plan.device,plan.inode))
            if copied.get('status')!='copy_verified' or copied.get('pages',0)<1 or copied.get('bytes',0)<1:
                raise FBUnsafe('empty or unverified copy')
            self._transition(row,'prepared','copy_verified')
            if crash_at=='after_commit':raise FBInterrupted('after_commit')
            completed.append(plan.chapter_id)
        return tuple(completed)

    def prepare_single(self,chapter,*,confirmed=False,crash_at=None):
        if confirmed is not True:raise FBUnsafe('explicit synthetic consent required')
        return self._execute(self._plan((chapter,)),crash_at=crash_at)

    def prepare_bulk(self,*,confirmed=False,crash_at=None):
        if confirmed is not True:raise FBUnsafe('explicit synthetic consent required')
        chapters=tuple(r[0] for r in self._rows())
        if not chapters:return ()
        return self._execute(self._plan(chapters,bulk=True),crash_at=crash_at)

    def recover(self):
        """Read native files; only allow safe SQLite *journal* status updates."""
        outcomes=[]
        rows=self.db.execute('''SELECT operation_id,chapter_id,source_id,source_manga_id,
           source_chapter_id,snapshot_name,source_device,source_inode,state
           FROM offline_copy_journal ORDER BY chapter_id''').fetchall()
        for row in rows:
            if row[8]=='needs_review':outcomes.append((row[1],'needs_review'));continue
            try:
                if not self._owner_still_matches(row):raise FBUnsafe('owner drift')
                verified=self._native('verifycopymeta',row[2],row[3],row[4],row[5],(row[6],row[7]))
                if verified.get('pages',0)<1:raise FBUnsafe('empty copy')
                if row[8]=='prepared':self._transition(row,'prepared','copy_verified')
                outcomes.append((row[1],'copy_verified'))
            except (FBUnsafe,sqlite3.Error,subprocess.SubprocessError,OSError):
                # Idempotent, non-destructive review. No automatic restore/purge.
                current=self._journal(row[1])
                if current and current[8]!='needs_review':
                    self.db.execute('''UPDATE offline_copy_journal SET state='needs_review',
                         reason='ambiguous_or_missing_copy' WHERE operation_id=? AND state=?''',
                                    (row[0],row[8]))
                outcomes.append((row[1],'needs_review'))
        return tuple(outcomes)

    def reindex_preview(self):
        rows=self._rows(); identities=[FACopyOnlyRouter._identity(*r[1:4]) for r in rows]
        collisions={i for i in identities if identities.count(i)>1}
        result=[]
        for row in rows:
            chapter,source,manga,leaf,*_=row
            if FACopyOnlyRouter._identity(source,manga,leaf) in collisions:
                result.append((chapter,'needs_review'));continue
            journal=self._journal(chapter)
            if journal:
                try:
                    if journal[8]!='copy_verified' or not self._owner_still_matches(journal):
                        raise FBUnsafe('unverified copy')
                    self._native('verifycopymeta',source,manga,leaf,journal[5],(journal[6],journal[7]))
                    result.append((chapter,'copy_verified'))
                except (FBUnsafe,subprocess.SubprocessError,OSError):
                    result.append((chapter,'needs_review'))
            else:
                try:
                    probe=self._native('inspectmeta',source,manga,leaf,'ev_'+uuid.uuid4().hex)
                    result.append((chapter,'source_present' if probe['status']=='observed' else 'needs_review'))
                except (FBUnsafe,subprocess.SubprocessError,OSError):
                    result.append((chapter,'needs_review'))
        return tuple(result)

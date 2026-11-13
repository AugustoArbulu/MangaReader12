#!/usr/bin/env python3
"""EZ copy-only journal for a separately marked disposable Swift/SQLite lab.

This intentionally does NOT retire downloads, change chapters.downloaded,
restore originals or purge snapshots. It is not production WebReader code.
"""
from pathlib import Path
import json
import re
import sqlite3
import subprocess
import uuid

from build70_ex_persistent_journal_bridge import EXJournalLab, EXUnsafe


class EZUnsafe(EXUnsafe):
    pass


class EZInterrupted(RuntimeError):
    pass


class EZSnapshotJournal:
    def __init__(self, root: Path, swift_binary: Path):
        self.lab = EXJournalLab(root, swift_binary)
        self.db = self.lab.db
        self.db.execute('PRAGMA foreign_keys=ON;')
        self.db.execute('PRAGMA synchronous=FULL;')
        self.db.execute('PRAGMA busy_timeout=2000;')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS ez_snapshot_journal (
                op TEXT PRIMARY KEY CHECK (length(op)=32 AND op NOT GLOB '*[^0-9a-f]*'),
                chapter_id INTEGER NOT NULL,
                source TEXT NOT NULL,
                manga TEXT NOT NULL,
                leaf TEXT NOT NULL,
                dest TEXT NOT NULL UNIQUE CHECK (
                    length(dest)=35 AND substr(dest,1,3)='ev_' AND
                    substr(dest,4) NOT GLOB '*[^0-9a-f]*'),
                device TEXT NOT NULL,
                inode TEXT NOT NULL,
                state TEXT NOT NULL CHECK (state IN (
                    'prepared', 'copy_verified', 'needs_review')),
                reason TEXT NOT NULL DEFAULT '',
                confirmed TEXT NOT NULL CHECK (confirmed='synthetic_explicit_confirm'),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE UNIQUE INDEX IF NOT EXISTS ez_one_operation_per_chapter
                ON ez_snapshot_journal (chapter_id);
        ''')

    def close(self): self.lab.close()
    def __enter__(self): return self
    def __exit__(self, exc_type, exc, tb): self.close()

    def _native(self, action, row):
        _,_,source,manga,leaf,dest,device,inode,*_ = row
        args=[str(self.lab.swift_binary),action,str(self.lab.root),source,manga,leaf,dest,device,inode]
        r=subprocess.run(args,capture_output=True,text=True,timeout=15,check=False)
        if r.returncode or len(r.stdout)>2048:
            raise EZUnsafe('native copy or verification rejected; preserve data')
        try:
            j=json.loads(r.stdout)
        except (ValueError,TypeError) as exc:
            raise EZUnsafe('bad native response') from exc
        if j.get('status')!='copy_verified' or j.get('device')!=device or j.get('inode')!=inode:
            raise EZUnsafe('native copy identity mismatch')
        if not isinstance(j.get('pages'),int) or j['pages']<1 or not isinstance(j.get('bytes'),int) or j['bytes']<1:
            raise EZUnsafe('bad verified copy size')
        return j

    def _download(self,chapter):
        return self.db.execute('SELECT source,manga,leaf FROM downloads WHERE chapter_id=?',(chapter,)).fetchone()

    def _select(self,chapter):
        return self.db.execute('''SELECT op,chapter_id,source,manga,leaf,dest,device,inode,state
            FROM ez_snapshot_journal WHERE chapter_id=?''',(chapter,)).fetchone()

    def _owner_matches(self,row):
        return self._download(row[1]) == (row[2],row[3],row[4]) and self.db.execute(
            'SELECT downloaded FROM chapters WHERE id=?',(row[1],)).fetchone() == (1,)

    def _transition(self,op,expected,next_state,reason=''):
        cursor=self.db.execute('''UPDATE ez_snapshot_journal
            SET state=?,reason=?,updated_at=CURRENT_TIMESTAMP
            WHERE op=? AND state=?''',(next_state,reason[:120],op,expected))
        if cursor.rowcount!=1:raise EZUnsafe('journal CAS rejected')

    def start(self,chapter,*,confirmed=False,crash_at=None):
        if confirmed is not True or not isinstance(chapter,int) or isinstance(chapter,bool) or chapter<=0:
            raise EZUnsafe('explicit synthetic confirmation and chapter id required')
        if self._select(chapter):raise EZUnsafe('existing copy operation requires review')
        source,manga,leaf=self._download(chapter) or (None,None,None)
        if not all([source,manga,leaf]):raise EZUnsafe('exact download owner missing')
        op=uuid.uuid4().hex;dest='ev_'+op
        observed=self.lab._native('inspect',source,manga,leaf,dest)
        if observed['status']!='observed':raise EZUnsafe('native preflight rejected')
        device,inode=self.lab._validated_identity(observed)
        self.db.execute('BEGIN IMMEDIATE')
        try:
            if self._select(chapter) or self._download(chapter)!=(source,manga,leaf):
                raise EZUnsafe('owner or journal changed before insert')
            self.db.execute('''INSERT INTO ez_snapshot_journal
                (op,chapter_id,source,manga,leaf,dest,device,inode,state,confirmed)
                VALUES(?,?,?,?,?,?,?,?,?,?)''',(op,chapter,source,manga,leaf,dest,device,inode,
                                                 'prepared','synthetic_explicit_confirm'))
            self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK');raise
        if crash_at=='after_intent':raise EZInterrupted('after persistent intent')
        row=self._select(chapter)
        self._native('snapshot',row)
        if crash_at=='after_snapshot':raise EZInterrupted('after snapshot, before journal commit')
        verified=self._native('verifycopy',row)
        self.db.execute('BEGIN IMMEDIATE')
        try:
            if not self._owner_matches(row):raise EZUnsafe('owner drift before verification commit')
            self._transition(op,'prepared','copy_verified')
            self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK');raise
        if crash_at=='after_verification_commit':raise EZInterrupted('after journal commit')
        return verified

    def recover_readonly(self):
        """Reads pages only; never creates, deletes, restores or retires files/rows."""
        outcome=[]
        rows=self.db.execute('''SELECT op,chapter_id,source,manga,leaf,dest,device,inode,state
            FROM ez_snapshot_journal ORDER BY op''').fetchall()
        for row in rows:
            op,chapter,*_=row
            if row[8]=='needs_review':outcome.append((chapter,'needs_review'));continue
            try:
                if not self._owner_matches(row):raise EZUnsafe('metadata drift')
                self._native('verifycopy',row)
                if row[8]=='prepared':
                    self._transition(op,'prepared','copy_verified')
                outcome.append((chapter,'copy_verified'))
            except (EZUnsafe,EXUnsafe,subprocess.SubprocessError,OSError):
                # Even a crash before native copy leads to a conservative
                # review, not automatic cleanup of a possibly partial folder.
                self._transition(op,row[8],'needs_review','missing_or_ambiguous_copy')
                outcome.append((chapter,'needs_review'))
        return outcome

    def reindex_safe(self):
        if self.db.execute("SELECT count(*) FROM ez_snapshot_journal WHERE state!='copy_verified'").fetchone()[0]:
            raise EZUnsafe('unresolved snapshot; block prototype reindex')
        # This is intentionally never calling app reindex, even when verified.
        return True

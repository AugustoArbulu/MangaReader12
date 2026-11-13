#!/usr/bin/env python3
"""FA: one *copy-only* coordination layer for three mock UI routes.

Never call the real ChapterDownloadManager, StorageManager, DownloadRepository
or SQLiteDatabase. Only preexisting marked synthetic roots and Swift fd lab.
No route deletes originals, retires SQLite downloads, or purges snapshots.
"""
from __future__ import annotations
import json
import os
import stat
import hashlib
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import uuid

from build70_ez_copy_journal_bridge import EZSnapshotJournal, EZUnsafe

class FARouteUnsafe(EZUnsafe): pass

@dataclass(frozen=True)
class SafePlan:
    chapter_id: int
    source: str
    manga: str
    leaf: str
    device: str
    inode: str
    fingerprint: str

@dataclass(frozen=True)
class ReindexObservation:
    chapter_id: int
    status: str
    detail: str

class FACopyOnlyRouter:
    def __init__(self, root: Path, binary: Path, *, running_ids=(), pending_ids=()):
        self.snapshots=EZSnapshotJournal(root,binary)
        self.db=self.snapshots.db
        self.running_ids=frozenset(running_ids)
        self.pending_ids=frozenset(pending_ids)

    def close(self):self.snapshots.close()
    def __enter__(self):return self
    def __exit__(self,*_):self.close()

    @staticmethod
    def _identity(source,manga,leaf):
        def safe(value):
            if not isinstance(value,str):raise FARouteUnsafe('non-string owner')
            # Mirrors the app conservative collision check without using a
            # user path. Native Swift only accepts ASCII safe components.
            value=''.join(c if (c.isalnum() or c in '._-') else '_' for c in value)
            if value in ('','.','..'):value='item'
            return unicodedata.normalize('NFKD',value).casefold()
        return (safe(source),safe(manga),safe(leaf))

    def _page_fingerprint(self,source,manga,leaf):
        """Bounded read-only manifest; each component opened NOFOLLOW by fd.

        This is synthetic lab safety evidence, not a production-ready
        filesystem trust primitive. Concurrent writers can still race between
        this admission and the Swift copy; native verification handles its own
        pre/post checks and leaves all files if ambiguous.
        """
        root=self.snapshots.lab.root
        fds=[]
        try:
            fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
            fds.append(fd)
            for c in ('synthetic_app','Downloads',source,manga,leaf):
                if not isinstance(c,str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,80}',c) or c in ('.','..'):
                    raise FARouteUnsafe('untrusted component')
                fd=os.open(c,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fds[-1])
                fds.append(fd)
            names=sorted(os.listdir(fds[-1]))
            if not 1<=len(names)<=1000:raise FARouteUnsafe('bounded fixture chapter expected')
            hasher=hashlib.sha256()
            total=0
            for name in names:
                if not re.fullmatch(r'page-[0-9]{5}\.bin',name):raise FARouteUnsafe('foreign file in fixture')
                f=os.open(name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=fds[-1])
                try:
                    before=os.fstat(f)
                    if (not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or
                            not 0<before.st_size<=20*1024*1024):
                        raise FARouteUnsafe('unsafe page')
                    hasher.update(name.encode('ascii')+b'\0')
                    total+=before.st_size
                    if total>256*1024*1024:raise FARouteUnsafe('synthetic bounded total exceeded')
                    while True:
                        block=os.read(f,65536)
                        if not block:break
                        hasher.update(block)
                    after=os.fstat(f)
                    if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)!=(
                        after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns):
                        raise FARouteUnsafe('concurrent page mutation')
                finally:os.close(f)
            return hasher.hexdigest()
        except OSError as exc:
            raise FARouteUnsafe('unsafe synthetic source path or page') from exc
        finally:
            for fd in reversed(fds):os.close(fd)

    def _records(self):
        return self.db.execute('SELECT chapter_id,source,manga,leaf FROM downloads ORDER BY chapter_id').fetchall()

    def _preflight_all(self, requested, *,bulk=False):
        rows=self._records()
        if len({r[0] for r in rows})!=len(rows):raise FARouteUnsafe('ambiguous DB IDs')
        # Batch preflight performs all checks before first journal/FS write.
        if not all(type(c) is int and c>0 for c in requested):
            raise FARouteUnsafe('positive integer chapter IDs required')
        if len(set(requested))!=len(requested):raise FARouteUnsafe('duplicate batch chapter')
        if any(c in self.running_ids or c in self.pending_ids for c in requested):
            raise FARouteUnsafe('active or pending job')
        if bulk and (self.running_ids or self.pending_ids):
            raise FARouteUnsafe('bulk requires completely idle mock worker')
        byid={r[0]:r for r in rows}
        if set(requested)-set(byid):raise FARouteUnsafe('unknown chapter')
        # As in EQ, reject ambiguous mapping of identities to physical path.
        identities=[self._identity(*r[1:]) for r in rows]
        if len(set(identities))!=len(identities):raise FARouteUnsafe('canonical path collision')
        plans=[]
        for chapter in requested:
            _,source,manga,leaf=byid[chapter]
            if self.snapshots._select(chapter):raise FARouteUnsafe('existing journal; manual review')
            observed=self.snapshots.lab._native('inspect',source,manga,leaf,'ev_'+uuid.uuid4().hex)
            if observed.get('status')!='observed':raise FARouteUnsafe('inspection failed')
            device,inode=self.snapshots.lab._validated_identity(observed)
            plans.append(SafePlan(chapter,source,manga,leaf,device,inode,
                                      self._page_fingerprint(source,manga,leaf)))
        return tuple(plans)

    def _execute(self,plans):
        completed=[]
        for plan in plans:
            # Compare source identity at use-time, not just at batch admission.
            current=self.snapshots.lab._native('inspect',plan.source,plan.manga,plan.leaf,'ev_'+uuid.uuid4().hex)
            if (current.get('status'),*self.snapshots.lab._validated_identity(current))!=('observed',plan.device,plan.inode):
                raise FARouteUnsafe(f'identity drift; {len(completed)} copies preserved')
            if self._page_fingerprint(plan.source,plan.manga,plan.leaf)!=plan.fingerprint:
                raise FARouteUnsafe(f'page contents changed; {len(completed)} copies preserved')
            if self.snapshots._download(plan.chapter_id)!=(plan.source,plan.manga,plan.leaf):
                raise FARouteUnsafe(f'owner drift; {len(completed)} copies preserved')
            try:
                self.snapshots.start(plan.chapter_id,confirmed=True)
            except Exception as exc:
                raise FARouteUnsafe(f'copy failed; {len(completed)} copies remain, originals unchanged') from exc
            completed.append(plan.chapter_id)
        return tuple(completed)

    def prepare_single(self,chapter_id: int,*,confirmed=False):
        if confirmed is not True: raise FARouteUnsafe('explicit synthetic consent required')
        return self._execute(self._preflight_all((chapter_id,)))

    def prepare_bulk(self,*,confirmed=False):
        if confirmed is not True: raise FARouteUnsafe('explicit synthetic bulk consent required')
        ids=tuple(r[0] for r in self._records())
        if not ids:return ()
        return self._execute(self._preflight_all(ids,bulk=True))

    def reindex_preview(self):
        """Read-only. Missing or ambiguous files must not retire metadata."""
        rows=self._records()
        identities=[self._identity(*r[1:]) for r in rows]
        collided={x for x in identities if identities.count(x)>1}
        results=[]
        for chapter,source,manga,leaf in rows:
            if self._identity(source,manga,leaf) in collided:
                results.append(ReindexObservation(chapter,'needs_review','ambiguous path collision'))
                continue
            row=self.snapshots._select(chapter)
            if row:
                try:
                    if row[8]!='copy_verified' or not self.snapshots._owner_matches(row):
                        raise FARouteUnsafe('unverified journal')
                    self.snapshots._native('verifycopy',row)
                    results.append(ReindexObservation(chapter,'copy_verified','source and copy readable'))
                except Exception:
                    results.append(ReindexObservation(chapter,'needs_review','unresolved copy journal'))
                continue
            try:
                r=self.snapshots.lab._native('inspect',source,manga,leaf,'ev_'+uuid.uuid4().hex)
                results.append(ReindexObservation(chapter,'source_present' if r.get('status')=='observed' else 'needs_review','no metadata mutation'))
            except Exception:
                results.append(ReindexObservation(chapter,'needs_review','source unavailable or unsafe'))
        return tuple(results)

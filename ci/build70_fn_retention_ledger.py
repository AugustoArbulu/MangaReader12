#!/usr/bin/env python3
"""FN: durable *synthetic* retention accounting, with no filesystem purge.

The ledger records advisory quota obligations even when a copy becomes
unverifiable or a process crashes. It MUST NOT be imported by the iOS app or
be run against a real library. Its operations NEVER delete/move pages, retire
SQLite owner rows, release reserved bytes automatically, or grant authority.
"""
from __future__ import annotations

from collections import Counter
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
import os
import sqlite3
import stat
from typing import Callable

from build70_fi_readonly_shadow_audit import _safe_root, FIUnsafe
from build70_fj_paired_readonly_reconciliation import _readonly_rows, _eligible, FJUnsafe, OPERATION
from build70_fl_monotonic_shadow import (
    FLUnsafe, inspect_disposable_version_clock, same_cooperative_generation,
)
from build70_fm_held_recovery_budget import (
    FMUnsafe, _binary, _clock_matches_v2_row, audit_held_recovery,
    _call_native, _valid_numbers, CHAPTER_QUOTA, BATCH_QUOTA, MIN_RESERVE,
)

NAME = 'fn_retention_v1.sqlite'
MAX_TICKETS = 16
STATES = frozenset({'reserved', 'retained', 'needs_review', 'release_requested'})
TABLES = frozenset({'fn_retention', 'fn_retention_event'})
TRIGGERS = frozenset({
    'fn_immutable_identity', 'fn_no_ticket_delete', 'fn_event_on_update',
    'fn_no_event_update', 'fn_no_event_delete',
})

class FNUnsafe(RuntimeError):
    """Stop and retain all prior obligations for manual owner review."""

class FNInterrupted(FNUnsafe):
    """Injected test-only crash after SQLite atomic commit or before it."""

@dataclass(frozen=True)
class FNStatus:
    entries: int
    accounted_bytes: int
    event_ceiling: int
    event_count: int
    reasons: tuple[tuple[str, int], ...]
    # A shadow ledger is accounting, not proof of any durable FS operation.
    can_delete: bool = False
    can_purge: bool = False
    can_restore: bool = False
    can_release_bytes: bool = False
    can_mark_downloaded: bool = False
    can_copy: bool = False

DDL = (
    '''CREATE TABLE fn_retention (
        operation_id TEXT PRIMARY KEY CHECK(
            length(operation_id)=32 AND operation_id NOT GLOB '*[^0-9a-f]*'),
        chapter_id INTEGER NOT NULL UNIQUE CHECK(chapter_id>0),
        snapshot_name TEXT NOT NULL UNIQUE CHECK(
            snapshot_name='ev_'||operation_id),
        source_device TEXT NOT NULL,
        source_inode TEXT NOT NULL,
        budget_bytes INTEGER NOT NULL CHECK(budget_bytes>0 AND budget_bytes<=536870912),
        state TEXT NOT NULL CHECK(
            state IN ('reserved','retained','needs_review','release_requested')),
        generation INTEGER NOT NULL DEFAULT 0 CHECK(generation>=0)
    )''',
    '''CREATE TABLE fn_retention_event (
        sequence INTEGER PRIMARY KEY AUTOINCREMENT,
        operation_id TEXT NOT NULL REFERENCES fn_retention(operation_id),
        kind TEXT NOT NULL CHECK(kind IN ('reserved','transition')),
        old_state TEXT,
        new_state TEXT NOT NULL
    )''',
    '''CREATE TRIGGER fn_immutable_identity BEFORE UPDATE ON fn_retention
       WHEN OLD.operation_id != NEW.operation_id OR OLD.chapter_id != NEW.chapter_id
         OR OLD.snapshot_name != NEW.snapshot_name
         OR OLD.source_device != NEW.source_device OR OLD.source_inode != NEW.source_inode
         OR OLD.budget_bytes != NEW.budget_bytes
         OR NEW.generation != OLD.generation+1
       BEGIN SELECT RAISE(ABORT,'FN immutable reservation or generation'); END''',
    '''CREATE TRIGGER fn_no_ticket_delete BEFORE DELETE ON fn_retention
       BEGIN SELECT RAISE(ABORT,'FN retention cannot be deleted'); END''',
    '''CREATE TRIGGER fn_event_on_update AFTER UPDATE ON fn_retention
       BEGIN INSERT INTO fn_retention_event(operation_id,kind,old_state,new_state)
            VALUES(NEW.operation_id,'transition',OLD.state,NEW.state); END''',
    '''CREATE TRIGGER fn_no_event_update BEFORE UPDATE ON fn_retention_event
       BEGIN SELECT RAISE(ABORT,'FN synthetic events immutable'); END''',
    '''CREATE TRIGGER fn_no_event_delete BEFORE DELETE ON fn_retention_event
       BEGIN SELECT RAISE(ABORT,'FN synthetic events cannot be deleted'); END''',
)


def _ledger_path(root: Path, *, create: bool) -> Path:
    """Require the existing EV marker and v2 DB; create only synthetic ledger."""
    try:
        v2 = _safe_root(Path(root))
    except (FIUnsafe, OSError) as exc:
        raise FNUnsafe('FN accepts marked disposable synthetic roots only') from exc
    app = v2.parent
    path = app / NAME
    if create and not path.exists() and not path.is_symlink():
        parent_fd = os.open(app, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0) |
                            getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_CLOEXEC', 0))
        try:
            try:
                fd = os.open(NAME, os.O_CREAT | os.O_EXCL | os.O_RDWR |
                             getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_CLOEXEC', 0),
                             0o600, dir_fd=parent_fd)
            except FileExistsError:
                pass
            else:
                os.close(fd)
        finally:
            os.close(parent_fd)
    try:
        before = path.lstat()
    except OSError as exc:
        raise FNUnsafe('retention ledger absent') from exc
    if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or
            before.st_size > 16*1024*1024):
        raise FNUnsafe('retention ledger is linked, special or unexpectedly large')
    return path


def _connect(path: Path, *, readonly: bool):
    db = sqlite3.connect(path.as_uri()+('?mode=ro' if readonly else '?mode=rw'),
                         uri=True, isolation_level=None, timeout=1.0)
    try:
        db.execute('PRAGMA busy_timeout=1000')
        db.execute('PRAGMA foreign_keys=ON')
        if readonly:
            db.execute('PRAGMA query_only=ON')
            if db.execute('PRAGMA query_only').fetchone() != (1,):
                raise FNUnsafe('SQLite query-only unavailable')
        else:
            db.execute('PRAGMA synchronous=FULL')
        return db
    except BaseException:
        db.close()
        raise


def _validate(db):
    if db.execute('PRAGMA user_version').fetchone() != (1,):
        raise FNUnsafe('unknown retention ledger version')
    tables = frozenset(r[0] for r in db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"))
    if tables != TABLES:
        raise FNUnsafe('retention table schema mismatch')
    triggers = frozenset(r[0] for r in db.execute(
        "SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE 'fn_%'"))
    if triggers != TRIGGERS:
        raise FNUnsafe('retention guard triggers missing')
    expected = {'operation_id','chapter_id','snapshot_name','source_device','source_inode',
                'budget_bytes','state','generation'}
    columns = {r[1] for r in db.execute('PRAGMA table_info(fn_retention)')}
    if columns != expected:
        raise FNUnsafe('retention ledger columns drift')
    if db.execute('PRAGMA foreign_key_check').fetchone() is not None:
        raise FNUnsafe('retention ledger foreign keys corrupt')
    if db.execute('PRAGMA quick_check').fetchone() != ('ok',):
        raise FNUnsafe('retention ledger corrupt')


def _ticket_rows(db):
    rows = db.execute('''SELECT operation_id,chapter_id,snapshot_name,
        source_device,source_inode,budget_bytes,state,generation
        FROM fn_retention ORDER BY operation_id LIMIT ?''',(MAX_TICKETS+1,)).fetchall()
    if len(rows) > MAX_TICKETS:
        raise FNUnsafe('too many accounting obligations')
    total = 0
    for op,chapter,snap,dev,ino,bytes_,state,gen in rows:
        if (not isinstance(op,str) or OPERATION.fullmatch(op) is None or
            snap!='ev_'+op or type(chapter) is not int or chapter<=0 or
            not isinstance(dev,str) or not dev.isascii() or not dev.isdecimal() or
            not isinstance(ino,str) or not ino.isascii() or not ino.isdecimal() or
            int(dev)<=0 or int(ino)<=0 or
            type(bytes_) is not int or not 0<bytes_<=CHAPTER_QUOTA or
            state not in STATES or type(gen) is not int or gen<0):
            raise FNUnsafe('invalid immutable retention obligation')
        total += bytes_
    if total > BATCH_QUOTA:
        raise FNUnsafe('retention ledger over aggregate accounting budget')
    return rows,total


def _events(db,rows):
    seq,count = db.execute('SELECT COALESCE(MAX(sequence),0),COUNT(*) FROM fn_retention_event').fetchone()
    if count > 100_000 or seq < count or count < len(rows):
        raise FNUnsafe('missing or implausible retention history')
    latest = dict(db.execute('''SELECT e.operation_id,e.new_state
       FROM fn_retention_event e
       WHERE sequence=(SELECT MAX(sequence) FROM fn_retention_event
                       WHERE operation_id=e.operation_id)''').fetchall())
    for op,_,_,_,_,_,state,generation in rows:
        n=db.execute('SELECT COUNT(*) FROM fn_retention_event WHERE operation_id=?',(op,)).fetchone()[0]
        if n != generation+1 or latest.get(op)!=state:
            raise FNUnsafe('retention event clock inconsistent')
    return seq,count


def init_synthetic_ledger(root: Path) -> Path:
    path = _ledger_path(root,create=True)
    with closing(_connect(path,readonly=False)) as db:
        version = db.execute('PRAGMA user_version').fetchone()[0]
        if version==1:
            _validate(db)
            existing,_=_ticket_rows(db)
            _events(db,existing)
        elif version==0:
            others = db.execute("SELECT COUNT(*) FROM sqlite_master WHERE type IN ('table','trigger') AND name NOT LIKE 'sqlite_%'").fetchone()[0]
            if others:
                raise FNUnsafe('partial or foreign retention ledger; manual review')
            db.execute('BEGIN IMMEDIATE')
            try:
                for statement in DDL: db.execute(statement)
                db.execute('PRAGMA user_version=1')
                db.execute('COMMIT')
            except BaseException:
                db.execute('ROLLBACK')
                raise
            _validate(db)
        else:
            raise FNUnsafe('unsupported retention ledger version')
    return path


def inspect_retention(root: Path) -> FNStatus:
    path = _ledger_path(root,create=False)
    try:
        with closing(_connect(path,readonly=True)) as db:
            db.execute('BEGIN')
            try:
                _validate(db)
                rows,total=_ticket_rows(db)
                seq,count=_events(db,rows)
                counts=tuple(sorted(Counter(r[6] for r in rows).items()))
                db.execute('COMMIT')
            finally:
                if db.in_transaction:db.execute('ROLLBACK')
        return FNStatus(len(rows),total,seq,count,counts)
    except sqlite3.Error as exc:
        raise FNUnsafe('retention ledger unavailable for read-only audit') from exc


def _evidence(root: Path, binary: Path, operation_id: str):
    if not isinstance(operation_id,str) or OPERATION.fullmatch(operation_id) is None:
        raise FNUnsafe('bad operation id')
    rows = _readonly_rows(root)
    row = rows.get(operation_id)
    if row is None or not _eligible(row):
        raise FNUnsafe('verified source journal owner missing')
    clock = inspect_disposable_version_clock(root)
    by_id={r[0]:r for r in clock.row_state}
    if row[0] not in by_id or not _clock_matches_v2_row(row,by_id[row[0]]):
        raise FNUnsafe('v2/v3 shadow state mismatch')
    report = audit_held_recovery(root,binary)
    if report.entries != report.held_matches or report.needs_review or report.observed_snapshot_bytes<=0:
        raise FNUnsafe('native held snapshot not proven for all entries')
    device,inode=row[6],row[7]
    raw=_call_native(binary,root,'holdverifysealed',row[2],row[3],row[4],row[5],(device,inode))
    if not _valid_numbers(raw,status='copy_verified',expected=(device,inode)):
        raise FNUnsafe('native snapshot budget/identity rejected')
    if raw['bytes'] > report.observed_snapshot_bytes:
        raise FNUnsafe('snapshot accounting inconsistent')
    quota=_call_native(binary,root,'budgetsealed',row[2],row[3],row[4],row[5])
    if not _valid_numbers(quota,status='observed',expected=(device,inode)) or quota['bytes'] != raw['bytes']:
        raise FNUnsafe('source budget mismatch')
    if type(quota.get('free_bytes')) is not int or quota['free_bytes']<0:
        raise FNUnsafe('free capacity unavailable')
    return row,clock,raw['bytes'],quota['free_bytes']


def _transition(db,op: str,old: str,new: str) -> bool:
    if new not in STATES:
        raise FNUnsafe('unknown retention transition')
    result=db.execute('''UPDATE fn_retention SET state=?,generation=generation+1
       WHERE operation_id=? AND state=?''',(new,op,old))
    return result.rowcount==1


def reserve_snapshot(root: Path, binary: Path, operation_id: str,
                     *, crash_at: str|None=None,
                     after_admission: Callable[[],None]|None=None) -> FNStatus:
    """Records a durable synthetic obligation; never copies/removes pages."""
    root=Path(root);binary=_binary(binary)
    path=_ledger_path(root,create=False)  # explicit preinitialized ledger required
    row,clock,bytes_,free=_evidence(root,binary,operation_id)
    if after_admission is not None: after_admission()
    if crash_at=='before_begin':raise FNInterrupted('before ledger transaction')
    try:
        with closing(_connect(path,readonly=False)) as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                _validate(db)
                tickets,total=_ticket_rows(db)
                _events(db,tickets)
                if len(tickets)>=MAX_TICKETS or any(t[0]==operation_id or t[1]==row[1] for t in tickets):
                    raise FNUnsafe('duplicate or full retention ledger')
                if bytes_>BATCH_QUOTA-total:
                    raise FNUnsafe('aggregate budget exhausted (no release allowed)')
                # Capacity is advisory; it may change after this read. Never
                # interpret it as proof that a subsequent copy can fit.
                if free < (total+bytes_)*2+MIN_RESERVE:
                    raise FNUnsafe('observed free capacity below conservative margin')
                if _readonly_rows(root).get(operation_id)!=row or not same_cooperative_generation(
                        clock,inspect_disposable_version_clock(root)):
                    raise FNUnsafe('source journal changed before reservation')
                db.execute('''INSERT INTO fn_retention
                  (operation_id,chapter_id,snapshot_name,source_device,source_inode,budget_bytes,state)
                  VALUES(?,?,?,?,?,?,'reserved')''',
                  (operation_id,row[1],row[5],row[6],row[7],bytes_))
                db.execute('''INSERT INTO fn_retention_event
                  (operation_id,kind,old_state,new_state) VALUES(?,'reserved',NULL,'reserved')''',(operation_id,))
                if crash_at=='before_commit':raise FNInterrupted('rolled back uncommitted ticket')
                db.execute('COMMIT')
            except BaseException:
                if db.in_transaction:db.execute('ROLLBACK')
                raise
    except sqlite3.Error as exc:
        raise FNUnsafe('retention reservation failed') from exc
    if crash_at=='after_commit':raise FNInterrupted('durable synthetic reservation already committed')
    return inspect_retention(root)


def recover_retention(root: Path,binary: Path,*,
                      after_first:Callable[[],None]|None=None) -> FNStatus:
    """Idempotently mark retained or needs_review; NEVER frees a reservation."""
    root=Path(root); binary=_binary(binary)
    path=_ledger_path(root,create=False)
    with closing(_connect(path,readonly=True)) as reader:
        reader.execute('BEGIN')
        _validate(reader)
        tickets,_=_ticket_rows(reader)
        _events(reader,tickets)
        reader.execute('COMMIT')
    for i,ticket in enumerate(tickets):
        op,_,_,_,_,bytes_,state,_=ticket
        if state not in ('reserved','retained'):
            continue  # review/release remain reserved, never auto-deleted
        try:
            row,_,observed,_=_evidence(root,binary,op)
            ok=(observed==bytes_ and ticket[1:5]==(row[1],row[5],row[6],row[7]))
        except (FNUnsafe,FMUnsafe,FJUnsafe,FLUnsafe,OSError,sqlite3.Error):
            ok=False
        target='retained' if ok else 'needs_review'
        if target==state:
            pass
        else:
            try:
                with closing(_connect(path,readonly=False)) as db:
                    db.execute('BEGIN IMMEDIATE')
                    try:
                        _validate(db)
                        if not _transition(db,op,state,target):
                            raise FNUnsafe('concurrent retention transition; review')
                        db.execute('COMMIT')
                    except BaseException:
                        if db.in_transaction:db.execute('ROLLBACK')
                        raise
            except sqlite3.Error as exc:
                raise FNUnsafe('retention crash recovery failed') from exc
        if after_first is not None and i==0:after_first()
    return inspect_retention(root)


def request_manual_release(root: Path,operation_id: str) -> FNStatus:
    """Only mark intent for human review; does NOT free accounting or bytes."""
    path=_ledger_path(root,create=False)
    if not isinstance(operation_id,str) or OPERATION.fullmatch(operation_id) is None:
        raise FNUnsafe('invalid operation')
    with closing(_connect(path,readonly=False)) as db:
        db.execute('BEGIN IMMEDIATE')
        try:
            _validate(db)
            rows,_=_ticket_rows(db)
            _events(db,rows)
            if not _transition(db,operation_id,'retained','release_requested'):
                raise FNUnsafe('only retained tickets can request release')
            db.execute('COMMIT')
        except BaseException:
            if db.in_transaction:db.execute('ROLLBACK')
            raise
    return inspect_retention(root)

#!/usr/bin/env python3
"""FL: disposable shadow-v3 event log proving COOPERATIVE SQLite ABA detection.

Synthetic marker REQUIRED. Never modifies source v2, application SQLite,
production Swift sources, original pages, or any live device. No deletion API.
Trigger/event table is NOT tamper proof against hostile database writers.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
import os
import sqlite3
import stat

from build70_fi_readonly_shadow_audit import _safe_root, FIUnsafe

NAME = 'fl_shadow_v3.sqlite'
MAX_OPERATIONS = 16

class FLUnsafe(RuntimeError):
    """Conservative failure: no mutation permission or implicit recovery."""

@dataclass(frozen=True)
class FLObservation:
    operations: int
    event_ceiling: int
    event_count: int
    row_state: tuple[tuple, ...]
    # These remain false even after an apparently consistent observation.
    can_delete: bool = False
    can_restore: bool = False
    can_purge: bool = False
    can_retire_database_rows: bool = False
    is_source_inode_locked: bool = False

EVENT_DDL = (
    '''CREATE TABLE fl_journal_event (
         seq INTEGER PRIMARY KEY AUTOINCREMENT,
         operation_id TEXT NOT NULL,
         kind TEXT NOT NULL CHECK(kind IN ('baseline','insert','update','delete')),
         old_state TEXT,
         new_state TEXT
       )''',
    '''CREATE TRIGGER fl_journal_on_insert AFTER INSERT ON offline_copy_journal
       BEGIN INSERT INTO fl_journal_event(operation_id,kind,old_state,new_state)
            VALUES (NEW.operation_id,'insert',NULL,NEW.state); END''',
    '''CREATE TRIGGER fl_journal_on_update AFTER UPDATE ON offline_copy_journal
       BEGIN INSERT INTO fl_journal_event(operation_id,kind,old_state,new_state)
            VALUES (NEW.operation_id,'update',OLD.state,NEW.state); END''',
    '''CREATE TRIGGER fl_journal_on_delete AFTER DELETE ON offline_copy_journal
       BEGIN INSERT INTO fl_journal_event(operation_id,kind,old_state,new_state)
            VALUES (OLD.operation_id,'delete',OLD.state,NULL); END''',
    '''CREATE TRIGGER fl_event_no_update BEFORE UPDATE ON fl_journal_event
       BEGIN SELECT RAISE(ABORT, 'FL synthetic event is immutable'); END''',
    '''CREATE TRIGGER fl_event_no_delete BEFORE DELETE ON fl_journal_event
       BEGIN SELECT RAISE(ABORT, 'FL synthetic event is immutable'); END''',
)

REQUIRED_TRIGGERS = frozenset({
    'fl_journal_on_insert', 'fl_journal_on_update', 'fl_journal_on_delete',
    'fl_event_no_update', 'fl_event_no_delete',
})


def _paths(root: Path) -> tuple[Path, Path]:
    try:
        v2 = _safe_root(root)
    except FIUnsafe as exc:
        raise FLUnsafe('unmarked, absent or unsafe synthetic v2') from exc
    return v2, v2.with_name(NAME)


def migrate_disposable_copy(root: Path) -> Path:
    """Creates a new EXCLUSIVE shadow-v3 fixture; never overwrites v2/v3."""
    v2, v3 = _paths(root)
    app = v2.parent
    appfd = os.open(app, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0) |
                    getattr(os, 'O_NOFOLLOW', 0))
    try:
        fd = os.open(NAME, os.O_CREAT | os.O_EXCL | os.O_RDWR |
                     getattr(os, 'O_NOFOLLOW', 0), 0o600, dir_fd=appfd)
        os.close(fd)
    finally:
        os.close(appfd)
    # In an interrupted test the incomplete shadow remains for human review.
    with closing(sqlite3.connect(v2.as_uri()+'?mode=ro',uri=True,
                                 isolation_level=None)) as src:
        if src.execute('PRAGMA user_version').fetchone() != (2,):
            raise FLUnsafe('source must be synthetic v2')
        with closing(sqlite3.connect(v3.as_uri()+'?mode=rw',uri=True,
                                     isolation_level=None)) as dst:
            src.backup(dst)
            if dst.execute('PRAGMA user_version').fetchone() != (2,):
                raise FLUnsafe('backup version mismatch')
            dst.execute('PRAGMA foreign_keys=ON')
            dst.execute('BEGIN IMMEDIATE')
            try:
                for statement in EVENT_DDL:
                    dst.execute(statement)
                dst.execute('''INSERT INTO fl_journal_event
                    (operation_id,kind,old_state,new_state)
                    SELECT operation_id,'baseline',NULL,state
                    FROM offline_copy_journal ORDER BY operation_id''')
                dst.execute('PRAGMA user_version=3')
                dst.execute('COMMIT')
            except BaseException:
                dst.execute('ROLLBACK')
                raise
            dst.execute('PRAGMA journal_mode=WAL')
            dst.execute('PRAGMA synchronous=FULL')
    return v3


def inspect_disposable_version_clock(root: Path) -> FLObservation:
    """Single read-only SQLite snapshot with monotonic event watermark.

    The watermark only detects updates by cooperating trigger-enabled writers;
    external writers can disable/drop triggers or rewrite a fixture. Never
    feed the result into a destructive operation.
    """
    _, v3 = _paths(root)
    try:
        st = v3.lstat()
    except OSError as exc:
        raise FLUnsafe('shadow v3 missing') from exc
    if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
        raise FLUnsafe('unsafe shadow v3 inode')
    try:
        with closing(sqlite3.connect(v3.as_uri()+'?mode=ro', uri=True,
                                     isolation_level=None, timeout=.3)) as db:
            db.execute('PRAGMA query_only=ON')
            if db.execute('PRAGMA query_only').fetchone() != (1,):
                raise FLUnsafe('query-only policy unavailable')
            db.execute('BEGIN')
            try:
                if db.execute('PRAGMA user_version').fetchone() != (3,):
                    raise FLUnsafe('unexpected synthetic clock schema')
                names = {r[0] for r in db.execute(
                    "SELECT name FROM sqlite_master WHERE type='trigger'")}
                if not REQUIRED_TRIGGERS.issubset(names):
                    raise FLUnsafe('event tracking triggers absent')
                row_state = tuple(db.execute('''
                    SELECT operation_id,chapter_id,source_id,source_manga_id,
                           source_chapter_id,snapshot_name,source_device,source_inode,
                           state,consent,reason,created_at,updated_at
                    FROM offline_copy_journal ORDER BY operation_id
                    LIMIT ?''',(MAX_OPERATIONS+1,)))
                if len(row_state) > MAX_OPERATIONS:
                    raise FLUnsafe('bounded witness limit exceeded')
                seq, count = db.execute(
                    'SELECT COALESCE(MAX(seq),0),COUNT(*) FROM fl_journal_event'
                ).fetchone()
                if count > 100_000 or (count and seq < count):
                    raise FLUnsafe('event history unexpectedly large or inconsistent')
                db.execute('COMMIT')
                return FLObservation(len(row_state), seq, count, row_state)
            finally:
                if db.in_transaction:
                    db.execute('ROLLBACK')
    except sqlite3.Error as exc:
        raise FLUnsafe('synthetic read-only event observation failed') from exc


def same_cooperative_generation(a: FLObservation, b: FLObservation) -> bool:
    """Detects ABA from cooperating triggers, *never* authorizes deletion."""
    return (a.event_ceiling == b.event_ceiling and
            a.event_count == b.event_count and a.row_state == b.row_state)

#!/usr/bin/env python3
"""EY — synthetic, offline shadow migration prototype, never an app DB migrator.

The only accepted legacy database is <marked_root>/synthetic_app/legacy_library_v1.sqlite.
A NEW, separate shadow_library_v2.sqlite is created with O_EXCL and populated
via SQLite's online backup API. The original is opened mode=ro. All DDL / the
user_version bump are one BEGIN IMMEDIATE transaction on the *shadow* file.

Do not import this module into the iOS app or point it at a user's database.
"""
from __future__ import annotations

import os
from pathlib import Path
import sqlite3
import stat
from typing import Literal

MARKER = b'EV_SYNTHETIC_ONLY\n'
LEGACY_NAME = 'legacy_library_v1.sqlite'
SHADOW_NAME = 'shadow_library_v2.sqlite'
VERSION = 2


class EYUnsafe(RuntimeError):
    pass


class EYInjectedFault(RuntimeError):
    pass


JOURNAL_DDL = """
CREATE TABLE offline_deletion_journal (
    operation_id TEXT PRIMARY KEY NOT NULL
        CHECK(length(operation_id)=32 AND operation_id NOT GLOB '*[^0-9a-f]*'),
    chapter_id INTEGER NOT NULL REFERENCES chapters(internal_id) ON DELETE RESTRICT,
    source_id TEXT NOT NULL,
    source_manga_id TEXT NOT NULL,
    source_chapter_id TEXT NOT NULL,
    quarantine_name TEXT NOT NULL UNIQUE
        CHECK(length(quarantine_name)=35 AND substr(quarantine_name,1,3)='ev_'
              AND substr(quarantine_name,4) NOT GLOB '*[^0-9a-f]*'),
    source_device TEXT NOT NULL,
    source_inode TEXT NOT NULL,
    state TEXT NOT NULL CHECK(state IN (
        'prepared','quarantined','retired_quarantined','aborted','needs_review'
    )),
    owner_confirmation TEXT NOT NULL
        CHECK(owner_confirmation='explicit_confirmation_required'),
    reason TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE UNIQUE INDEX offline_one_unresolved_chapter
ON offline_deletion_journal(chapter_id)
WHERE state IN ('prepared','quarantined','needs_review');
CREATE INDEX offline_deletion_state_idx ON offline_deletion_journal(state);
"""


def _regular_nofollow(path: Path) -> bool:
    try:
        s = path.lstat()
    except OSError:
        return False
    return stat.S_ISREG(s.st_mode) and s.st_nlink == 1


def _root(root: Path) -> tuple[Path, Path, Path]:
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise EYUnsafe('not a real preexisting synthetic root')
    marker = root / '.webreader_ev_disposable_marker'
    if not _regular_nofollow(marker) or marker.read_bytes() != MARKER:
        raise EYUnsafe('synthetic marker absent or invalid')
    app = root / 'synthetic_app'
    if app.is_symlink() or not app.is_dir():
        raise EYUnsafe('synthetic_app must be an existing real directory')
    return app, app / LEGACY_NAME, app / SHADOW_NAME


def _connect(path: Path, readonly: bool) -> sqlite3.Connection:
    if not _regular_nofollow(path):
        raise EYUnsafe('database absent, linked or non-regular')
    suffix = '?mode=ro' if readonly else '?mode=rw'
    conn = sqlite3.connect(path.as_uri() + suffix, uri=True, isolation_level=None, timeout=1)
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('PRAGMA busy_timeout=1000')
    return conn


def _check_legacy(conn: sqlite3.Connection) -> None:
    version = conn.execute('PRAGMA user_version').fetchone()[0]
    if version != 1:
        raise EYUnsafe(f'expected schema v1 only, got {version}')
    if conn.execute('PRAGMA quick_check').fetchone() != ('ok',):
        raise EYUnsafe('SQLite quick_check failed')
    if conn.execute('PRAGMA foreign_key_check').fetchone() is not None:
        raise EYUnsafe('foreign-key violation in legacy fixture')
    required = {
        'manga': {'internal_id', 'source_id', 'source_manga_id'},
        'chapters': {'internal_id', 'manga_id', 'source_chapter_id', 'downloaded'},
        'downloads': {'internal_id', 'chapter_id', 'state', 'local_path'},
    }
    for table, columns in required.items():
        cols = {row[1] for row in conn.execute(f'PRAGMA table_info({table})')}
        if not columns.issubset(cols):
            raise EYUnsafe(f'legacy table {table} missing required fields')
    fk_chapters = {(row[2], row[3], row[4]) for row in conn.execute('PRAGMA foreign_key_list(chapters)')}
    fk_downloads = {(row[2], row[3], row[4]) for row in conn.execute('PRAGMA foreign_key_list(downloads)')}
    if ('manga','manga_id','internal_id') not in fk_chapters or (
        'chapters','chapter_id','internal_id') not in fk_downloads:
        raise EYUnsafe('legacy foreign-key contract mismatch')
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name='offline_deletion_journal'").fetchone():
        raise EYUnsafe('unexpected preexisting deletion journal')


def make_shadow(root: Path) -> Path:
    """Consistent SQLite backup from read-only v1 to O_EXCL, never overwrite."""
    _, legacy, shadow = _root(root)
    source = _connect(legacy, readonly=True)
    try:
        _check_legacy(source)
        try:
            # Creating the named file this way prevents accidental clobbering.
            fd = os.open(shadow, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os,'O_NOFOLLOW',0), 0o600)
        except FileExistsError as e:
            raise EYUnsafe('shadow already exists; never overwrite') from e
        os.close(fd)
        try:
            dest = _connect(shadow, readonly=False)
            try:
                source.backup(dest)
                if dest.execute('PRAGMA user_version').fetchone()[0] != 1:
                    raise EYUnsafe('shadow backup did not retain v1')
                _check_legacy(dest)
            finally:
                dest.close()
        except BaseException:
            # Failed shadow is intentionally left for manual inspection; do not
            # remove or rename an unfamiliar file in an unsafe root.
            raise
    finally:
        source.close()
    return shadow


def validate_v2(conn: sqlite3.Connection) -> None:
    if conn.execute('PRAGMA user_version').fetchone()[0] != VERSION:
        raise EYUnsafe('not schema version 2')
    cols = {row[1] for row in conn.execute('PRAGMA table_info(offline_deletion_journal)')}
    if not {'operation_id','chapter_id','quarantine_name','source_device','source_inode',
            'owner_confirmation','state','created_at','updated_at'}.issubset(cols):
        raise EYUnsafe('journal schema incomplete')
    existing = {row[0] for row in conn.execute('SELECT name FROM sqlite_master WHERE type="index"')}
    if 'offline_one_unresolved_chapter' not in existing or 'offline_deletion_state_idx' not in existing:
        raise EYUnsafe('journal indexes absent')
    if conn.execute('PRAGMA foreign_key_check').fetchone() is not None:
        raise EYUnsafe('foreign key violation')
    if conn.execute('PRAGMA quick_check').fetchone() != ('ok',):
        raise EYUnsafe('failed quick_check')


def migrate_shadow(root: Path, fault: str | None = None) -> Literal['migrated', 'already_v2']:
    """Fail-closed and transactional on a disposable shadow database ONLY."""
    _, _, shadow = _root(root)
    db = _connect(shadow, readonly=False)
    try:
        version = db.execute('PRAGMA user_version').fetchone()[0]
        if version == VERSION:
            validate_v2(db)
            return 'already_v2'
        if version != 1:
            raise EYUnsafe(f'unsupported shadow version: {version}')
        _check_legacy(db)
        db.execute('BEGIN IMMEDIATE')
        try:
            if fault == 'before_create':
                raise EYInjectedFault('before_create')
            # executescript() would COMMIT an open transaction implicitly.
            # Explicit individual execute calls keep DDL and user_version atomic.
            stmts = [s.strip() for s in JOURNAL_DDL.split(';') if s.strip()]
            db.execute(stmts[0])
            if fault == 'after_table':
                raise EYInjectedFault('after_table')
            db.execute(stmts[1])
            if fault == 'after_unique_index':
                raise EYInjectedFault('after_unique_index')
            db.execute(stmts[2])
            db.execute('PRAGMA user_version=2')
            if fault == 'after_version':
                raise EYInjectedFault('after_version')
            if fault == 'process_exit':
                os._exit(86)  # synthetic interruption; uncommitted SQLite tx
            db.execute('COMMIT')
        except BaseException:
            if db.in_transaction:
                db.execute('ROLLBACK')
            raise
        validate_v2(db)
        return 'migrated'
    finally:
        db.close()


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(description='EY synthetic shadow migration (no real library)')
    p.add_argument('root', type=Path, help='existing marked synthetic lab fixture')
    p.add_argument('--create-shadow', action='store_true')
    p.add_argument('--migrate-shadow', action='store_true')
    p.add_argument('--fault', choices=('before_create','after_table','after_unique_index','after_version','process_exit'))
    a = p.parse_args()
    if not (a.create_shadow ^ a.migrate_shadow):
        p.error('choose exactly one operation')
    print(make_shadow(a.root) if a.create_shadow else migrate_shadow(a.root, fault=a.fault))

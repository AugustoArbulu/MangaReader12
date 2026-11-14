#!/usr/bin/env python3
"""FI read-only snapshot of a *synthetic* v2 SQLite copy journal.

Never opens the user's WebReader database. Requires the EV synthetic marker and
existing shadow v2. This is a metadata inspector, not a file-verification,
retirement, restoration, purge, or ownership-authority mechanism.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import os
import re
import sqlite3
import stat

MARKER = b'EV_SYNTHETIC_ONLY\n'
REQUIRED = frozenset({
    'operation_id', 'chapter_id', 'source_id', 'source_manga_id',
    'source_chapter_id', 'snapshot_name', 'source_device', 'source_inode',
    'state', 'consent', 'reason', 'created_at', 'updated_at',
})
STATES = frozenset({'prepared', 'copy_verified', 'needs_review'})
SNAPSHOT_RE = re.compile(r'ev_[0-9a-f]{32}\Z')
OPERATION_RE = re.compile(r'[0-9a-f]{32}\Z')
MAX_ROWS = 5000


class FIUnsafe(RuntimeError):
    """Fail closed: no data is changed and no verdict can authorize deletion."""


@dataclass(frozen=True)
class FISummary:
    entries: int
    copy_verified_metadata_only: int
    requires_review: int
    state_counts: tuple[tuple[str, int], ...]
    missing_journal: bool
    # FI *never* certifies a source or a snapshot, even if all statuses match.
    can_delete: bool = False
    can_restore: bool = False
    can_purge: bool = False


def _safe_root(root: Path) -> Path:
    root = Path(root)
    marker = root / '.webreader_ev_disposable_marker'
    if root.is_symlink() or not root.is_dir():
        raise FIUnsafe('lab root missing or linked')
    if marker.is_symlink() or not marker.is_file() or marker.read_bytes() != MARKER:
        raise FIUnsafe('EV synthetic marker absent')
    app = root / 'synthetic_app'
    if app.is_symlink() or not app.is_dir():
        raise FIUnsafe('lab synthetic_app absent or linked')
    shadow = app / 'shadow_library_v2.sqlite'
    try:
        s = shadow.lstat()
    except FileNotFoundError as e:
        raise FIUnsafe('synthetic shadow database not found') from e
    if not stat.S_ISREG(s.st_mode) or s.st_nlink != 1:
        raise FIUnsafe('unsafe shadow inode')
    return shadow


def inspect_synthetic_shadow(root: Path) -> FISummary:
    """Snapshot aggregate statuses; do not leak owner IDs, URLs or paths.

    SQLite may need to read/write WAL/-shm coordination files; no byte-level
    sidecar immutability is promised. No SQL statement changes schema or rows.
    """
    path = _safe_root(root)
    db = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True,
                         isolation_level=None, timeout=0.3)
    try:
        db.execute('PRAGMA query_only=ON')
        if db.execute('PRAGMA query_only').fetchone() != (1,):
            raise FIUnsafe('SQLite read-only policy inactive')
        db.execute('BEGIN')
        if db.execute('PRAGMA user_version').fetchone() != (2,):
            raise FIUnsafe('expected synthetic shadow v2')
        # Treat missing table as a reason to review, never as a successful scan.
        tables = {row[0] for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name IN "
            "('chapters','manga','downloads','offline_copy_journal')")}
        if not {'chapters', 'manga', 'downloads'}.issubset(tables):
            raise FIUnsafe('missing legacy owner schema')
        if 'offline_copy_journal' not in tables:
            return FISummary(0, 0, 1, (), True)
        actual = {r[1] for r in db.execute('PRAGMA table_info(offline_copy_journal)')}
        if actual != REQUIRED:
            raise FIUnsafe('copy journal schema drift')
        rows = db.execute('''
            SELECT j.operation_id, j.chapter_id, j.source_id, j.source_manga_id,
                   j.source_chapter_id, j.snapshot_name, j.source_device,
                   j.source_inode, j.state, j.consent,
                   m.source_id, m.source_manga_id, c.source_chapter_id,
                   d.state, c.downloaded
            FROM offline_copy_journal j
            LEFT JOIN chapters c ON c.internal_id=j.chapter_id
            LEFT JOIN manga m ON m.internal_id=c.manga_id
            LEFT JOIN downloads d ON d.chapter_id=c.internal_id
            ORDER BY j.operation_id LIMIT ?
        ''', (MAX_ROWS + 1,)).fetchall()
        if len(rows) > MAX_ROWS:
            raise FIUnsafe('journal row limit exceeded')
        counts: Counter[str] = Counter()
        verified = 0
        review = 0
        for r in rows:
            op, chapter, source, manga, leaf, snapshot, device, inode, state, consent, \
                owner_source, owner_manga, owner_leaf, download_state, downloaded = r
            if state not in STATES:
                raise FIUnsafe('unexpected journal state')
            counts[state] += 1
            matches = (isinstance(op, str) and OPERATION_RE.fullmatch(op) and
                       isinstance(snapshot, str) and SNAPSHOT_RE.fullmatch(snapshot) and
                       isinstance(device, str) and device.isdecimal() and
                       isinstance(inode, str) and inode.isdecimal() and
                       consent == 'synthetic_confirmation' and
                       (source, manga, leaf) ==
                       (owner_source, owner_manga, owner_leaf) and
                       download_state == 'completed' and downloaded == 1)
            if state == 'copy_verified' and matches:
                verified += 1  # Still only untrusted metadata, no filesystem proof.
            else:
                review += 1
        return FISummary(len(rows), verified, review,
                         tuple(sorted(counts.items())), False)
    except sqlite3.Error as e:
        raise FIUnsafe('SQLite read-only inspection failed') from e
    finally:
        try:
            if db.in_transaction:
                db.execute('ROLLBACK')
        finally:
            db.close()

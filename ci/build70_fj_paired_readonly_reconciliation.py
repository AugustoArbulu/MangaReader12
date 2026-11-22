#!/usr/bin/env python3
"""FJ: paired SQLite + native FD evidence, only in EV-marked disposable lab.

This auditor reads an existing synthetic shadow-v2 journal and asks the
standalone Swift binary to compare original and copied bytes by opened file
descriptors. It never writes the SQLite DB, creates/quarantines/deletes files,
or grants permission to delete, purge, restore, or mark downloaded=0.

Every positive result is transient *observation*, not an atomic FS+SQLite
snapshot. An adversary can mutate state after return. Production prohibited.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import json
import os
import re
import sqlite3
import stat
import subprocess
from typing import Callable

from build70_fi_readonly_shadow_audit import _safe_root, FIUnsafe, REQUIRED

OPERATION = re.compile(r"[0-9a-f]{32}\Z")
SNAPSHOT = re.compile(r"ev_[0-9a-f]{32}\Z")
COMPONENT = re.compile(r"[A-Za-z0-9_.-]{1,80}\Z")
MAX_ROWS = 5_000
MAX_NATIVE_CHECKS = 64  # two native checks per entry, bounded host CPU usage
MAX_NATIVE_OUTPUT = 2_048


class FJUnsafe(RuntimeError):
    """The audit cannot safely classify this synthetic fixture."""


@dataclass(frozen=True)
class FJReport:
    entries: int
    paired_observations: int
    requires_review: int
    reasons: tuple[tuple[str, int], ...]
    # Invariant: matching evidence NEVER authorizes an operation.
    can_delete: bool = False
    can_restore: bool = False
    can_purge: bool = False
    can_mark_downloaded: bool = False


def _readonly_rows(root: Path) -> dict[str, tuple]:
    """Read all relevant state together in one SQLite read transaction."""
    try:
        shadow = _safe_root(root)
    except FIUnsafe as exc:
        raise FJUnsafe("unsafe disposable shadow") from exc
    db = None
    try:
        db = sqlite3.connect(shadow.as_uri() + '?mode=ro', uri=True,
                             timeout=0.5, isolation_level=None)
        db.execute('PRAGMA query_only=ON')
        if db.execute('PRAGMA query_only').fetchone() != (1,):
            raise FJUnsafe('SQLite query-only policy unavailable')
        db.execute('BEGIN')
        if db.execute('PRAGMA user_version').fetchone() != (2,):
            raise FJUnsafe('unexpected synthetic shadow schema')
        present = {r[0] for r in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name IN ('offline_copy_journal','manga','chapters','downloads')")}
        if present != {'offline_copy_journal', 'manga', 'chapters', 'downloads'}:
            raise FJUnsafe('missing required synthetic tables')
        columns = {r[1] for r in db.execute('PRAGMA table_info(offline_copy_journal)')}
        if columns != REQUIRED:
            raise FJUnsafe('unexpected journal columns')
        records = db.execute('''
            SELECT j.operation_id, j.chapter_id, j.source_id, j.source_manga_id,
                j.source_chapter_id, j.snapshot_name, j.source_device,
                j.source_inode, j.state, j.consent,
                m.source_id, m.source_manga_id, c.source_chapter_id,
                d.state, c.downloaded, j.reason, j.updated_at, j.created_at
            FROM offline_copy_journal j
            LEFT JOIN chapters c ON c.internal_id=j.chapter_id
            LEFT JOIN manga m ON m.internal_id=c.manga_id
            LEFT JOIN downloads d ON d.chapter_id=c.internal_id
            ORDER BY j.operation_id
            LIMIT ?
        ''', (MAX_ROWS + 1,)).fetchall()
        if len(records) > MAX_ROWS:
            raise FJUnsafe('journal exceeds bounded audit size')
        if any(not isinstance(r[0], str) for r in records):
            raise FJUnsafe('corrupt journal operation identifiers')
        if len({r[0] for r in records}) != len(records):
            raise FJUnsafe('nonunique journal operation ids')
        return {r[0]: r for r in records}
    except sqlite3.Error as exc:
        raise FJUnsafe('SQLite read-only journal audit failed') from exc
    finally:
        if db is not None:
            try:
                if db.in_transaction:
                    db.execute('ROLLBACK')
            finally:
                db.close()


def _eligible(row: tuple) -> bool:
    op, chapter, source, manga, leaf, snapshot, device, inode, state, consent, \
        msource, mmanga, cleaf, dstate, downloaded, reason, updated_at, created_at = row
    return (isinstance(op, str) and OPERATION.fullmatch(op) is not None and
            isinstance(chapter, int) and chapter > 0 and
            isinstance(snapshot, str) and SNAPSHOT.fullmatch(snapshot) is not None and
            snapshot[3:] == op and
            all(isinstance(c, str) and COMPONENT.fullmatch(c) is not None and
                c not in ('.', '..') for c in (source, manga, leaf)) and
            all(isinstance(n, str) and len(n) < 22 and n.isascii() and
                n.isdecimal() and int(n) > 0 for n in (device, inode)) and
            state == 'copy_verified' and consent == 'synthetic_confirmation' and
            (source, manga, leaf) == (msource, mmanga, cleaf) and
            dstate == 'completed' and downloaded == 1 and reason == '')


def _native_verify(binary: Path, root: Path, row: tuple) -> bool:
    # Fixed argv and no shell. Never pass DB row in command log or stderr.
    op, _, source, manga, leaf, snapshot, device, inode, *_ = row
    args = [str(binary), 'verifycopysealed', str(root),
            source, manga, leaf, snapshot, device, inode]
    try:
        result = subprocess.run(args, capture_output=True, text=True,
                                timeout=20, check=False)
        if result.returncode != 0 or len(result.stdout) > MAX_NATIVE_OUTPUT:
            return False
        data = json.loads(result.stdout)
    except (ValueError, OSError, UnicodeError, subprocess.SubprocessError):
        return False
    return (isinstance(data, dict) and data.get('status') == 'copy_verified' and
            data.get('device') == device and data.get('inode') == inode and
            type(data.get('pages')) is int and 1 <= data['pages'] <= 5000 and
            type(data.get('bytes')) is int and 1 <= data['bytes'] <= 5000 * 20 * 1024 * 1024)


def paired_audit(root: Path, native_binary: Path,
                 *, between_checks: Callable[[str], None] | None = None,
                 after_first_native: Callable[[str], None] | None = None,
                 after_second_sql: Callable[[str], None] | None = None) -> FJReport:
    """Two DB snapshots + two independent Swift FD comparisons.

    Hooks are **only** for deterministic race injection with disposable
    fixtures. The method returns aggregate counts, never user identities.
    """
    root = Path(root)
    binary = Path(native_binary)
    try:
        bs = binary.lstat()
    except OSError as exc:
        raise FJUnsafe('standalone native verifier absent') from exc
    if not stat.S_ISREG(bs.st_mode) or bs.st_nlink != 1 or not os.access(binary, os.X_OK):
        raise FJUnsafe('standalone native verifier unsafe')
    rows = _readonly_rows(root)
    counts: Counter[str] = Counter()
    accepted = 0
    checks = 0
    for operation, old in rows.items():
        reason = 'requires_review'
        if not _eligible(old):
            reason = 'metadata_untrusted'
        elif checks >= MAX_NATIVE_CHECKS:
            reason = 'audit_budget_exceeded'
        else:
            checks += 1
            try:
                if between_checks is not None:
                    between_checks(operation)
                if not _native_verify(binary, root, old):
                    reason = 'first_fd_verification_failed'
                else:
                    if after_first_native is not None:
                        after_first_native(operation)
                    fresh = _readonly_rows(root)
                    if fresh.get(operation) != old:
                        reason = 'journal_or_owner_changed'
                    else:
                        if after_second_sql is not None:
                            after_second_sql(operation)
                        if _native_verify(binary, root, old):
                            reason = 'paired_observation_only'
                            accepted += 1
                        else:
                            reason = 'second_fd_verification_failed'
            except (FJUnsafe, FIUnsafe, OSError, sqlite3.Error):
                reason = 'audit_interrupted_or_inconsistent'
        counts[reason] += 1
    # Check for rows inserted or removed during iteration. Never accept a
    # positive observation when journal membership has changed.
    try:
        final_rows = _readonly_rows(root)
        if final_rows != rows:
            counts['journal_membership_or_state_changed'] += 1
            accepted = 0
    except FJUnsafe:
        counts['journal_final_read_failed'] += 1
        accepted = 0
    return FJReport(entries=len(rows), paired_observations=accepted,
                    requires_review=len(rows) - accepted,
                    reasons=tuple(sorted(counts.items())))

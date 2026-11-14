#!/usr/bin/env python3
"""FK: read-only late-window challenge of FJ's synthetic evidence.

This module deliberately DOES NOT supply a safe delete API. It runs on a
previously EV-marked disposable fixture, adds another series of SQLite/FD
observations after FJ, and demonstrates the unavoidable *subsequent* race.
None of these reads creates a binding between an inode and a path for a
future rename/unlink. Every public verdict permanently denies mutation.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
import os
import stat

from build70_fj_paired_readonly_reconciliation import (
    FJUnsafe, _eligible, _native_verify, _readonly_rows, paired_audit,
)

MAX_FK_ENTRIES = 16  # 4+ independent native scans per accepted entry


@dataclass(frozen=True)
class FKWitness:
    entries: int
    observations: int
    requires_review: int
    reasons: tuple[tuple[str, int], ...]
    late_race_window_remains: bool = True
    source_inode_cas_available: bool = False
    # An observation can never confer mutation authority, even if valid now.
    can_delete: bool = False
    can_purge: bool = False
    can_restore: bool = False
    can_mark_downloaded: bool = False


def _native_is_safely_executable(binary: Path) -> bool:
    try:
        info = binary.lstat()
        return stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and os.access(binary, os.X_OK)
    except OSError:
        return False


def late_window_audit(
    root: Path, native_binary: Path, *,
    after_paired: Callable[[str], None] | None = None,
    after_first_late_fd: Callable[[str], None] | None = None,
    after_late_sql: Callable[[str], None] | None = None,
    after_last_native: Callable[[str], None] | None = None,
) -> FKWitness:
    """Revalidate paired read-only evidence and refuse all physical mutation.

    Hooks are deterministic **synthetic fixture** race injections only.
    If an uncooperative writer swaps a basename after our final FD check,
    nothing can rule out that race. Therefore even a successful observation
    always has can_delete=False. No operation here uses unlink/rename.
    """
    root, native_binary = Path(root), Path(native_binary)
    if not _native_is_safely_executable(native_binary):
        raise FJUnsafe('unsafe synthetic Swift verifier')

    before = _readonly_rows(root)
    prior = paired_audit(root, native_binary)
    reasons: Counter[str] = Counter()
    count = len(before)
    if not before:
        return FKWitness(0, 0, 1, (('no_copy_journal_evidence', 1),))
    if count > MAX_FK_ENTRIES:
        return FKWitness(count, 0, count, (('late_audit_budget_exceeded', count),))
    if prior.entries != count or prior.paired_observations != count or prior.requires_review:
        return FKWitness(count, 0, count, (('prior_evidence_untrusted', count),))

    observed = 0
    for op, row in before.items():
        reason = 'late_observation_only'
        try:
            if after_paired is not None:
                after_paired(op)
            fresh = _readonly_rows(root)
            if fresh != before or not _eligible(row):
                reason = 'journal_drift_after_pair'
            elif not _native_verify(native_binary, root, row):
                reason = 'late_first_fd_rejected'
            else:
                if after_first_late_fd is not None:
                    after_first_late_fd(op)
                next_db = _readonly_rows(root)
                if next_db != before:
                    reason = 'late_journal_drift'
                else:
                    if after_late_sql is not None:
                        after_late_sql(op)
                    if not _native_verify(native_binary, root, row):
                        reason = 'late_second_fd_rejected'
                    elif _readonly_rows(root) != before:
                        reason = 'late_final_db_drift'
                    else:
                        # This hook deliberately demonstrates an event *after*
                        # the last file read: no scan can close this window.
                        if after_last_native is not None:
                            after_last_native(op)
                        observed += 1
        except (FJUnsafe, OSError, ValueError):
            reason = 'late_inconsistent_or_interrupted'
        reasons[reason] += 1

    try:
        if _readonly_rows(root) != before:
            reasons['last_journal_revalidation_failed'] += 1
            observed = 0
    except (FJUnsafe, OSError):
        reasons['last_journal_read_failed'] += 1
        observed = 0
    # All positive observations remain nonauthoritative. Nothing is locked.
    return FKWitness(count, observed, count - observed, tuple(sorted(reasons.items())))

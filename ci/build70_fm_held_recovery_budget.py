#!/usr/bin/env python3
"""FM: FD-held recoverability observations and conservative quota previews.

ONLY pre-marked synthetic EV lab fixtures. No write, delete, restore, path
rename, database migration, or mutation authorization. A held FD proves which
inode was read *during this process*, not the future target of a pathname.
"""
from __future__ import annotations
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
import json
import os
import stat
import subprocess

from build70_fj_paired_readonly_reconciliation import (
    FJUnsafe, _readonly_rows, _eligible, COMPONENT, SNAPSHOT,
)
from build70_fk_late_window_evidence import _native_is_safely_executable
from build70_fl_monotonic_shadow import (
    inspect_disposable_version_clock, same_cooperative_generation, FLUnsafe,
)

MAX_OPERATIONS = 16
CHAPTER_QUOTA = 512 * 1024 * 1024
BATCH_QUOTA = 1024 * 1024 * 1024
MIN_RESERVE = 64 * 1024 * 1024
MAX_OUTPUT = 2048

class FMUnsafe(RuntimeError):
    """Untrusted fixture or verifier: manual review required."""

@dataclass(frozen=True)
class FMRecovery:
    entries: int
    held_matches: int
    needs_review: int
    observed_snapshot_bytes: int
    reasons: tuple[tuple[str, int], ...]
    # These NEVER become True even when all observations match.
    can_delete: bool = False
    can_restore: bool = False
    can_purge: bool = False
    can_retire_downloads: bool = False
    source_inode_cas_available: bool = False
    source_stays_pinned_after_return: bool = False

@dataclass(frozen=True)
class FMQuota:
    entries: int
    estimate_bytes: int
    free_bytes_at_observation: int
    within_advisory_budget: bool
    # A budget preview does not reserve bytes or authorize copying.
    can_copy: bool = False
    can_delete: bool = False


def _binary(binary: Path) -> Path:
    binary = Path(binary)
    if not _native_is_safely_executable(binary):
        raise FMUnsafe('untrusted native verifier executable')
    return binary


def _call_native(binary: Path, root: Path, action: str,
                 source: str, manga: str, leaf: str,
                 destination: str, identity: tuple[str, str] | None = None) -> dict:
    args = [str(binary), action, str(root), source, manga, leaf, destination]
    if identity is not None:
        args.extend(identity)
    try:
        r = subprocess.run(args, capture_output=True, text=True,
                           timeout=25, check=False)
        if r.returncode or len(r.stdout) > MAX_OUTPUT:
            raise FMUnsafe('native FD admission rejected')
        data = json.loads(r.stdout)
    except (OSError, UnicodeError, ValueError, subprocess.SubprocessError) as exc:
        raise FMUnsafe('native FD verification failed') from exc
    if not isinstance(data, dict):
        raise FMUnsafe('native verifier returned non-object')
    return data


def _valid_numbers(data: dict, *, status: str, expected: tuple[str,str] | None = None) -> bool:
    return (data.get('status') == status and
            all(isinstance(data.get(k), str) and
                data[k].isascii() and data[k].isdecimal() and
                0 < int(data[k]) for k in ('device','inode')) and
            (expected is None or (data['device'], data['inode']) == expected) and
            type(data.get('pages')) is int and 1 <= data['pages'] <= 5000 and
            type(data.get('bytes')) is int and 0 < data['bytes'] <= CHAPTER_QUOTA)


def _clock_matches_v2_row(v2: tuple, v3: tuple) -> bool:
    # FL v3: op, chapter, source, manga, chapter, snapshot, dev, inode,
    # state, consent, reason, created_at, updated_at.
    return (v2[:10] + (v2[15], v2[17], v2[16])) == v3


def audit_held_recovery(root: Path, binary: Path, *,
                        after_hold: Callable[[str], None] | None = None,
                        after_budget: Callable[[str], None] | None = None,
                        after_final: Callable[[str], None] | None = None,
                        ) -> FMRecovery:
    """Read v2/v3 clock and inspect BOTH original and snapshot by held FD.

    v3 is a separate synthetic shadow backup: if v2/v3 diverge, review. The
    two connections are NOT an atomic cross-file SQLite transaction. Hooked
    races are fixture-only. No verification survives process exit.
    """
    root, binary = Path(root), _binary(binary)
    before = _readonly_rows(root)
    clock_before = inspect_disposable_version_clock(root)
    if len(before) > MAX_OPERATIONS or clock_before.operations > MAX_OPERATIONS:
        return FMRecovery(len(before), 0, len(before), 0,
                          (('operation_count_exceeded', len(before)),))
    if not before:
        return FMRecovery(0, 0, 1, 0, (('no_journal_rows',1),))
    v3 = {r[0]: r for r in clock_before.row_state}
    reasons: Counter[str] = Counter()
    matches = 0
    cumulative = 0
    for op, row in before.items():
        reason = 'requires_manual_review'
        try:
            if not _eligible(row) or op not in v3 or not _clock_matches_v2_row(row,v3[op]):
                reason = 'journal_owner_or_shadow_mismatch'
            else:
                source, manga, leaf, dest = row[2],row[3],row[4],row[5]
                identity = (row[6],row[7])
                hold = _call_native(binary,root,'holdverifysealed',source,manga,leaf,dest,identity)
                if after_hold is not None:
                    after_hold(op)
                budget = _call_native(binary,root,'budgetsealed',source,manga,leaf,dest)
                if after_budget is not None:
                    after_budget(op)
                hold_after = _call_native(binary,root,'holdverifysealed',source,manga,leaf,dest,identity)
                if not (_valid_numbers(hold,status='copy_verified',expected=identity) and
                        _valid_numbers(budget,status='observed',expected=identity) and
                        _valid_numbers(hold_after,status='copy_verified',expected=identity) and
                        hold['bytes']==budget['bytes']==hold_after['bytes'] and
                        hold['pages']==budget['pages']==hold_after['pages']):
                    reason = 'fd_bytes_identity_or_budget_mismatch'
                elif hold['bytes'] > BATCH_QUOTA - cumulative:
                    reason = 'aggregate_copy_quota_exceeded'
                else:
                    matches += 1
                    cumulative += hold['bytes']
                    reason = 'held_inodes_transiently_match'
        except (FMUnsafe, FJUnsafe, FLUnsafe, OSError, ValueError):
            reason = 'native_or_schema_review'
        reasons[reason] += 1
    # If anything changed while our two processes were checking pages, the
    # entire observation is withdrawn, but still there can be a final race.
    try:
        after = _readonly_rows(root)
        clock_after = inspect_disposable_version_clock(root)
        if (before != after or not same_cooperative_generation(clock_before,clock_after)):
            reasons['journal_or_cooperative_generation_drift'] += 1
            matches = 0
            cumulative = 0
    except (FMUnsafe,FJUnsafe,FLUnsafe,OSError):
        reasons['final_sql_snapshot_unavailable'] += 1
        matches = 0
        cumulative = 0
    # A test may mutate immediately after the last native/SQL read.
    if after_final is not None:
        after_final('synthetic_exit')
    return FMRecovery(len(before), matches, len(before)-matches,
                      cumulative, tuple(sorted(reasons.items())))


def preview_quota(root: Path, binary: Path,
                  chapters: tuple[tuple[str,str,str], ...]) -> FMQuota:
    """Advisory new-copy budget, using pinned source FDs, no reservations.

    The snapshot name is a constant valid dummy name and is NEVER created.
    The caller must still separately prove DB ownership and obtain consent.
    """
    root, binary = Path(root), _binary(binary)
    if not isinstance(chapters,tuple) or len(chapters) > MAX_OPERATIONS or any(
            not isinstance(c,tuple) for c in chapters) or len(set(chapters)) != len(chapters):
        raise FMUnsafe('quota list exceeds operation bound or has duplicates')
    total = 0
    min_free: int | None = None
    for chapter in chapters:
        if (len(chapter)!=3 or any(
                not isinstance(c,str) or not COMPONENT.fullmatch(c) or c in ('.','..')
                for c in chapter)):
            raise FMUnsafe('invalid synthetic owner components')
        raw = _call_native(binary,root,'budgetsealed',*chapter,'ev_'+'0'*32)
        if not _valid_numbers(raw,status='observed'):
            raise FMUnsafe('native quota evidence invalid')
        if type(raw.get('free_bytes')) is not int or raw['free_bytes'] < 0:
            raise FMUnsafe('native free-space evidence invalid')
        if raw['bytes'] > BATCH_QUOTA - total:
            return FMQuota(len(chapters),total,raw['free_bytes'],False)
        total += raw['bytes']
        min_free = min(min_free,raw['free_bytes']) if min_free is not None else raw['free_bytes']
    free = min_free if min_free is not None else 0
    # 2x covers a second simultaneous copy; reserves 64 MiB conservatively.
    # This is NOT an atomic capacity reservation, even if within budget.
    enough = bool(chapters) and total <= BATCH_QUOTA and free >= total*2 + MIN_RESERVE
    return FMQuota(len(chapters),total,free,enough)

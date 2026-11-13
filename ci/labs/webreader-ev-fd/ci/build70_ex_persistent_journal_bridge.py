#!/usr/bin/env python3
"""Build70 EX — disposable Python/SQLite -> REAL Swift fd laboratory bridge.

This is deliberately NOT application code. An explicit synthetic fixture marker,
and the standalone Swift tool, and a disposable SQLite DB are required.
No real app paths, no network, no purge, no automatic restoration, no iPad.
The only filesystem mutation on chapter bytes is the explicit, guarded
Swift stage (exclusive rename to synthetic quarantine).

Important: stage's source inode is NOT atomically pinned by renameatx_np or
renameat2. Fail closed and never auto-restore or purge on mismatches.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import uuid

MARKER = '.webreader_ev_disposable_marker'
PREFIX = 'ev_'
IDENTITY = re.compile(r'^([1-9][0-9]*)$')


class EXUnsafe(RuntimeError):
    pass


class EXInjectedInterruption(RuntimeError):
    pass


class EXJournalLab:
    """Drive a native Swift fd-only probe and journal its results into SQLite.

    The journal uses the existing synthetic lab.sqlite, NOT the WebReader
    schema. Its methods do not call the old EV Python recover/rename path.
    """

    def __init__(self, root: Path, swift_binary: Path):
        self.root = Path(root)
        self.swift_binary = Path(swift_binary)
        # Never create a root, a DB or an app tree during admission.
        if self.root.is_symlink() or not self.root.is_dir():
            raise EXUnsafe('synthetic root is not an existing real directory')
        marker = self.root / MARKER
        if marker.is_symlink() or not marker.is_file() or marker.read_bytes() != b'EV_SYNTHETIC_ONLY\n':
            raise EXUnsafe('synthetic root marker not valid')
        self.app = self.root / 'synthetic_app'
        if self.app.is_symlink() or not self.app.is_dir():
            raise EXUnsafe('synthetic app not valid')
        self.db_path = self.app / 'lab.sqlite'
        if self.db_path.is_symlink() or not self.db_path.is_file():
            raise EXUnsafe('preexisting synthetic SQLite DB required')
        if self.swift_binary.is_symlink() or not self.swift_binary.is_file() or not os.access(self.swift_binary, os.X_OK):
            raise EXUnsafe('precompiled native Swift probe required')
        self.db = sqlite3.connect(str(self.db_path), isolation_level=None, timeout=2.0)
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.execute('PRAGMA busy_timeout=2000')
        # No changes to existing download tables, and NEVER auto-migrate app DB.
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS ex_delete_journal (
              op TEXT PRIMARY KEY,
              chapter_id INTEGER NOT NULL,
              source TEXT NOT NULL,
              manga TEXT NOT NULL,
              leaf TEXT NOT NULL,
              dest TEXT NOT NULL UNIQUE,
              device TEXT NOT NULL,
              inode TEXT NOT NULL,
              state TEXT NOT NULL CHECK (state IN (
                'prepared','quarantined','retired_quarantined','aborted','needs_review')),
              reason TEXT NOT NULL DEFAULT '',
              approved TEXT NOT NULL CHECK (approved='synthetic_explicit_confirm'),
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE UNIQUE INDEX IF NOT EXISTS ex_one_unresolved_chapter
            ON ex_delete_journal(chapter_id)
            WHERE state IN ('prepared','quarantined','needs_review');
        ''')

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    @staticmethod
    def _validated_identity(result):
        if not isinstance(result, dict) or result.get('status') not in ('observed', 'at_source', 'in_quarantine', 'needs_review'):
            raise EXUnsafe('unexpected native response state')
        device = result.get('device')
        inode = result.get('inode')
        if not isinstance(device, str) or not isinstance(inode, str) or not IDENTITY.fullmatch(device) or not IDENTITY.fullmatch(inode):
            raise EXUnsafe('invalid native identity')
        return device, inode

    def _native(self, action, source, manga, leaf, dest, identity=None):
        args = [str(self.swift_binary), action, str(self.root), source, manga, leaf, dest]
        if identity is not None:
            args.extend(identity)
        try:
            result = subprocess.run(args, capture_output=True, text=True, timeout=15, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise EXUnsafe('native descriptor probe unavailable') from exc
        if result.returncode or len(result.stdout) > 2048:
            raise EXUnsafe('native descriptor operation refused')
        try:
            parsed = json.loads(result.stdout)
            self._validated_identity(parsed)
            return parsed
        except (ValueError, KeyError, TypeError) as exc:
            raise EXUnsafe('invalid native response') from exc

    def _download(self, chapter_id):
        row = self.db.execute(
            'SELECT source,manga,leaf FROM downloads WHERE chapter_id=?',
            (chapter_id,)).fetchone()
        if row is None:
            raise EXUnsafe('download owner missing')
        return row

    def _assert_no_outstanding(self, chapter_id):
        if self.db.execute(
            "SELECT 1 FROM ex_delete_journal WHERE chapter_id=? AND state IN ('prepared','quarantined','needs_review')",
            (chapter_id,)).fetchone():
            raise EXUnsafe('unresolved deletion intent: review required')

    def preflight(self, chapter_id):
        if not isinstance(chapter_id, int) or isinstance(chapter_id, bool) or chapter_id <= 0:
            raise EXUnsafe('invalid chapter ID')
        self._assert_no_outstanding(chapter_id)
        source, manga, leaf = self._download(chapter_id)
        dest = PREFIX + uuid.uuid4().hex
        result = self._native('inspect', source, manga, leaf, dest)
        if result['status'] != 'observed':
            raise EXUnsafe('unsafe preflight state')
        return (chapter_id, source, manga, leaf, dest, self._validated_identity(result))

    def _transition(self, op, expected, new_state, reason=''):
        # Compare-and-swap: never overwrite a state changed by another actor.
        cursor = self.db.execute('''
            UPDATE ex_delete_journal SET state=?, reason=?, updated_at=CURRENT_TIMESTAMP
            WHERE op=? AND state=?''', (new_state, reason[:180], op, expected))
        if cursor.rowcount != 1:
            raise EXUnsafe('journal transition rejected')

    def stage_confirmed(self, chapter_id, *, confirmed=False, fail_at=None, checked=None, fault_hook=None):
        if confirmed is not True:
            raise EXUnsafe('explicit synthetic confirmation required')
        checked = self.preflight(chapter_id) if checked is None else checked
        _, source, manga, leaf, dest, identity = checked
        # Compare preplanned identity/owner again rather than trusting caller.
        if checked[0] != chapter_id or self._download(chapter_id) != (source, manga, leaf):
            raise EXUnsafe('preflight ownership changed')
        observed = self._native('inspect', source, manga, leaf, dest)
        if observed['status'] != 'observed' or self._validated_identity(observed) != identity:
            raise EXUnsafe('preflight identity changed')
        op = dest[len(PREFIX):]
        self.db.execute('BEGIN IMMEDIATE')
        try:
            self._assert_no_outstanding(chapter_id)
            if self._download(chapter_id) != (source, manga, leaf):
                raise EXUnsafe('owner changed in transaction')
            self.db.execute('''
              INSERT INTO ex_delete_journal(op,chapter_id,source,manga,leaf,dest,device,inode,state,approved)
              VALUES(?,?,?,?,?,?,?,?,?,?)''',
                (op,chapter_id,source,manga,leaf,dest,*identity,'prepared','synthetic_explicit_confirm'))
            self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK')
            raise
        if fail_at == 'after_intent':
            raise EXInjectedInterruption('after_intent')
        # The native stage never deletes a chapter. An error leaves intent
        # persisted for safe, read-only reconciliation at next startup.
        moved = self._native('stage',source,manga,leaf,dest,identity)
        if moved['status'] != 'in_quarantine' or self._validated_identity(moved) != identity:
            raise EXUnsafe('unexpected result after stage')
        if fail_at == 'after_stage':
            raise EXInjectedInterruption('after_stage')
        self._transition(op, 'prepared', 'quarantined')
        if fail_at == 'after_quarantine_state':
            raise EXInjectedInterruption('after_quarantine_state')
        # Injection hook is for a hostile synthetic test ONLY, before the
        # final pre-retirement read-only native inode check.
        if fault_hook is not None:
            fault_hook(op)
        final = self._native('classify', source, manga, leaf, dest, identity)
        if final['status'] != 'in_quarantine' or self._validated_identity(final) != identity:
            raise EXUnsafe('quarantine identity drift before SQLite retirement')
        # This remains TOCTOU: no cross-system atomic commit or source-inode
        # conditional rename exists here. NEVER enable for real library data.
        # SQLite metadata and journal state change together; no FS changes.
        self.db.execute('BEGIN IMMEDIATE')
        try:
            if self.db.execute(
                'SELECT source,manga,leaf FROM downloads WHERE chapter_id=?',
                (chapter_id,)).fetchone() != (source,manga,leaf):
                raise EXUnsafe('owner drift before metadata retirement')
            self._transition(op,'quarantined','retired_quarantined')
            deleted = self.db.execute('''
                DELETE FROM downloads WHERE chapter_id=? AND source=? AND manga=? AND leaf=?
            ''',(chapter_id,source,manga,leaf))
            if deleted.rowcount != 1:
                raise EXUnsafe('exact download owner vanished')
            changed = self.db.execute('UPDATE chapters SET downloaded=0 WHERE id=?',(chapter_id,))
            if changed.rowcount != 1:
                raise EXUnsafe('chapter status missing')
            self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK')
            raise
        if fail_at == 'after_sqlite_commit':
            raise EXInjectedInterruption('after_sqlite_commit')
        return op

    def stage_bulk_confirmed(self, chapter_ids, *, confirmed=False):
        """Preflight ALL before FIRST intent/move, same individual policy."""
        if confirmed is not True:
            raise EXUnsafe('explicit synthetic bulk confirmation required')
        ids = list(chapter_ids)
        if len(set(ids)) != len(ids) or not ids or len(ids)>128:
            raise EXUnsafe('duplicate, empty, or oversized batch')
        checked = [self.preflight(chapter_id) for chapter_id in ids]
        return [self.stage_confirmed(p[0], confirmed=True, checked=p) for p in checked]

    def startup_reconcile(self):
        """Read-only on filesystem. Retains bytes, and never auto-restores.

        Repeated calls produce the same durable state. Any uncertainty goes to
        needs_review; an already committed retirement is checked, not undone.
        """
        outcomes = []
        rows = self.db.execute('''
            SELECT op,chapter_id,source,manga,leaf,dest,device,inode,state
            FROM ex_delete_journal ORDER BY created_at,op''').fetchall()
        for op,chapter_id,source,manga,leaf,dest,dev,ino,state in rows:
            if state in ('aborted', 'needs_review'):
                outcomes.append((op,state))
                continue
            try:
                observed = self._native('classify',source,manga,leaf,dest,(dev,ino))
                location = observed['status']
            except EXUnsafe:
                location = 'needs_review'
            owner = self.db.execute('''SELECT source,manga,leaf FROM downloads WHERE chapter_id=?''',
                                    (chapter_id,)).fetchone()
            chapter = self.db.execute('SELECT downloaded FROM chapters WHERE id=?',(chapter_id,)).fetchone()
            if state == 'prepared' and location == 'at_source' and owner == (source,manga,leaf) and chapter == (1,):
                self._transition(op,'prepared','aborted','interrupted_before_native_move')
                state='aborted'
            elif state == 'retired_quarantined' and location == 'in_quarantine' and owner is None and chapter == (0,):
                # Completed journal entry, quarantine remains held for review.
                pass
            elif state in ('prepared','quarantined','retired_quarantined'):
                self._transition(op,state,'needs_review','interrupted_or_ambiguous_' + location)
                state='needs_review'
            outcomes.append((op,state))
        return outcomes

    def reindex_guard(self):
        """The prototype reindex operation is a non-mutating safety gate.

        The actual app reindex code is NOT called or modified.
        """
        blockers=self.db.execute('''
            SELECT COUNT(*) FROM ex_delete_journal
            WHERE state IN ('prepared','quarantined','needs_review')''').fetchone()[0]
        if blockers:
            raise EXUnsafe('reindex blocked by outstanding journal review')
        return True

    def journal_row(self, op):
        return self.db.execute('''SELECT chapter_id,state,reason FROM ex_delete_journal WHERE op=?''',(op,)).fetchone()

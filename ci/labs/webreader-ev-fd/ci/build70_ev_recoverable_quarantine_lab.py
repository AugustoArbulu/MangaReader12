#!/usr/bin/env python3
"""Fase EV: PROTOTYPE ONLY. Synthetic host filesystem + SQLite quarantine.

Not imported by WebReader, no iOS app integration, no production deletion, no
purging, no network, no appinst. All callers must supply a disposable lab root.
A conditional/inode-bound rename cannot be guaranteed by POSIX renameat alone:
review mismatches after rename, and NEVER purge on uncertain identity.
"""
import errno
import os
from pathlib import Path
import re
import sqlite3
import stat
import uuid

O_DIR = os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0) | getattr(os, 'O_NOFOLLOW', 0)
PART = re.compile(r'^[A-Za-z0-9_-]{1,40}$')
PAGE = re.compile(r'^page-[0-9]{5}\.bin$')


class Unsafe(Exception):
    pass


class InjectedCrash(Exception):
    pass


def _component(s):
    if not PART.fullmatch(s) or s in ('.', '..'):
        raise Unsafe('invalid component')
    return s


def _opendir(parent_fd, component):
    return os.open(_component(component), O_DIR, dir_fd=parent_fd)


def _inode_at(parent, name):
    try:
        return os.stat(name, dir_fd=parent, follow_symlinks=False)
    except FileNotFoundError:
        return None


def _same(a, b):
    return a is not None and b is not None and (a.st_dev, a.st_ino, a.st_mode) == (b.st_dev, b.st_ino, b.st_mode)


class QuarantineLab:
    def __init__(self, root):
        self.root = Path(root)
        if self.root.is_symlink() or not self.root.is_dir():
            raise Unsafe('lab root must be a real existing directory')
        marker = self.root / '.webreader_ev_disposable_marker'
        if marker.is_symlink() or not marker.is_file() or marker.read_text() != 'EV_SYNTHETIC_ONLY\n':
            raise Unsafe('explicit synthetic-lab marker required')
        self.app = self.root / 'synthetic_app'
        if self.app.is_symlink():
            raise Unsafe('synthetic app root may not be a symlink')
        self.app.mkdir(exist_ok=True)
        (self.app / 'Downloads').mkdir(exist_ok=True)
        (self.app / 'Quarantine').mkdir(exist_ok=True)
        self.db = sqlite3.connect(str(self.app / 'lab.sqlite'), isolation_level=None)
        self.db.executescript('''
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS chapters (id INTEGER PRIMARY KEY, downloaded INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS downloads (
            chapter_id INTEGER PRIMARY KEY, source TEXT NOT NULL, manga TEXT NOT NULL,
            leaf TEXT NOT NULL, UNIQUE(source,manga,leaf));
        CREATE TABLE IF NOT EXISTS delete_intents (
            op TEXT PRIMARY KEY, chapter_id INTEGER NOT NULL, source TEXT NOT NULL,
            manga TEXT NOT NULL, leaf TEXT NOT NULL, dest TEXT NOT NULL UNIQUE,
            device TEXT NOT NULL, inode TEXT NOT NULL, state TEXT NOT NULL,
            reason TEXT NOT NULL DEFAULT '');
        ''')

    def close(self):
        self.db.close()

    def seed(self, chapter_id=1, source='s', manga='m', leaf='c'):
        for name in (source, manga, leaf):
            _component(name)
        path = self.app / 'Downloads' / source / manga / leaf
        path.mkdir(parents=True)
        (path / 'page-00000.bin').write_bytes(b'page-content-preserve')
        with self.db:
            self.db.execute('INSERT INTO chapters VALUES(?,1)', (chapter_id,))
            self.db.execute('INSERT INTO downloads VALUES(?,?,?,?)', (chapter_id,source,manga,leaf))
        return path

    def _fds(self, source, manga):
        app_fd = os.open(self.app, O_DIR)
        try:
            d_fd = _opendir(app_fd, 'Downloads')
            try:
                s_fd = _opendir(d_fd, source)
                try:
                    m_fd = _opendir(s_fd, manga)
                except BaseException:
                    os.close(s_fd)
                    raise
            except BaseException:
                os.close(d_fd)
                raise
            q_fd = _opendir(app_fd, 'Quarantine')
            if os.fstat(m_fd).st_dev != os.fstat(q_fd).st_dev:
                raise Unsafe('different filesystems')
            return app_fd,d_fd,s_fd,m_fd,q_fd
        except BaseException:
            # Called only on fixtures; cleanup open fds upon early failures.
            for name in ('m_fd','s_fd','d_fd'):
                if name in locals():
                    try: os.close(locals()[name])
                    except OSError: pass
            os.close(app_fd)
            raise

    @staticmethod
    def _close_fds(fds):
        for fd in reversed(fds):
            os.close(fd)

    def _preflight(self, parent_fd, leaf):
        info = _inode_at(parent_fd, leaf)
        if info is None or not stat.S_ISDIR(info.st_mode):
            raise Unsafe('chapter is absent or not a real directory')
        fd = _opendir(parent_fd, leaf)
        try:
            if not _same(info, os.fstat(fd)):
                raise Unsafe('folder identity changed')
            names = os.listdir(fd)
            if not names or len(names) > 100000:
                raise Unsafe('unexpected chapter inventory')
            for name in names:
                if not PAGE.fullmatch(name):
                    raise Unsafe('foreign file')
                item = _inode_at(fd, name)
                if item is None or not stat.S_ISREG(item.st_mode) or item.st_nlink != 1 or not 0 < item.st_size <= 20*1024*1024:
                    raise Unsafe('unsafe page')
            if not _same(info, _inode_at(parent_fd, leaf)):
                raise Unsafe('folder swapped during preflight')
            return info
        finally:
            os.close(fd)

    def stage(self, chapter_id=1, fail_at=None):
        row = self.db.execute('SELECT source,manga,leaf FROM downloads WHERE chapter_id=?', (chapter_id,)).fetchone()
        if row is None:
            raise Unsafe('no exact persisted owner')
        source,manga,leaf = map(_component,row)
        fds = self._fds(source,manga)
        try:
            m_fd, q_fd = fds[3],fds[4]
            info = self._preflight(m_fd,leaf)
            op = uuid.uuid4().hex
            dest = 'ev_'+op
            self.db.execute('BEGIN IMMEDIATE')
            try:
                if self.db.execute("SELECT 1 FROM delete_intents WHERE chapter_id=? AND state NOT IN ('aborted')", (chapter_id,)).fetchone():
                    raise Unsafe('outstanding intent')
                self.db.execute('INSERT INTO delete_intents(op,chapter_id,source,manga,leaf,dest,device,inode,state) VALUES(?,?,?,?,?,?,?,?,?)',
                    (op,chapter_id,source,manga,leaf,dest,str(info.st_dev),str(info.st_ino),'prepared'))
                self.db.execute('COMMIT')
            except BaseException:
                self.db.execute('ROLLBACK')
                raise
            if fail_at == 'after_intent':
                raise InjectedCrash('after_intent')
            if not _same(info,_inode_at(m_fd,leaf)):
                raise Unsafe('identity changed before rename')
            if _inode_at(q_fd,dest) is not None:
                raise Unsafe('quarantine collision')
            # POSIX renameat; a concurrent final-component substitution is
            # possible, therefore post-rename identity must be verified.
            os.rename(leaf,dest,src_dir_fd=m_fd,dst_dir_fd=q_fd)
            os.fsync(m_fd)
            os.fsync(q_fd)
            if fail_at == 'after_rename':
                raise InjectedCrash('after_rename')
            if not _same(info,_inode_at(q_fd,dest)):
                self.db.execute("UPDATE delete_intents SET state='needs_review',reason='inode mismatch after rename' WHERE op=?", (op,))
                raise Unsafe('identity mismatch; quarantine preserved for review')
            self.db.execute("UPDATE delete_intents SET state='quarantined' WHERE op=?", (op,))
            if fail_at == 'after_quarantine_record':
                raise InjectedCrash('after_quarantine_record')
            # Retire SQLite metadata and ledger stage in ONE SQLite transaction.
            self.db.execute('BEGIN IMMEDIATE')
            try:
                self.db.execute('DELETE FROM downloads WHERE chapter_id=?', (chapter_id,))
                self.db.execute('UPDATE chapters SET downloaded=0 WHERE id=?', (chapter_id,))
                self.db.execute("UPDATE delete_intents SET state='retired_quarantined' WHERE op=?", (op,))
                self.db.execute('COMMIT')
            except BaseException:
                self.db.execute('ROLLBACK')
                raise
            if fail_at == 'after_sqlite_commit':
                raise InjectedCrash('after_sqlite_commit')
            return op
        finally:
            self._close_fds(fds)

    def recover(self):
        """Fail closed: rollback only while download row exists. Never purge."""
        outcomes=[]
        rows=self.db.execute("SELECT op,chapter_id,source,manga,leaf,dest,device,inode,state FROM delete_intents WHERE state != 'aborted'").fetchall()
        for op,chapter_id,source,manga,leaf,dest,dev,ino,state in rows:
            if state in ('retired_quarantined','needs_review'):
                outcomes.append((op,state))
                continue
            try:
                fds=self._fds(source,manga)
                try:
                    m_fd,q_fd=fds[3],fds[4]
                    src=_inode_at(m_fd,leaf); quarantined=_inode_at(q_fd,dest)
                    matching=lambda v: v is not None and str(v.st_dev)==dev and str(v.st_ino)==ino and stat.S_ISDIR(v.st_mode)
                    owned=self.db.execute('SELECT 1 FROM downloads WHERE chapter_id=? AND source=? AND manga=? AND leaf=?', (chapter_id,source,manga,leaf)).fetchone()
                    if not owned:
                        raise Unsafe('owner vanished before retirement')
                    if matching(src) and quarantined is None:
                        outcome='aborted' # crashed before rename
                    elif src is None and matching(quarantined):
                        # EX conservative revision: never restore via plain rename,
                        # which could overwrite a newly created source directory.
                        # Preserve quarantine and exact SQLite ownership for review.
                        outcome='needs_review'
                    else:
                        raise Unsafe('ambiguous or foreign content')
                finally:
                    self._close_fds(fds)
            except (Unsafe,OSError) as exc:
                outcome='needs_review'
                reason=str(exc)[:200]
                self.db.execute('UPDATE delete_intents SET state=?,reason=? WHERE op=?',(outcome,reason,op))
            else:
                self.db.execute('UPDATE delete_intents SET state=?,reason=? WHERE op=?',(outcome, 'quarantine_held_for_manual_review' if outcome == 'needs_review' else '', op))
            outcomes.append((op,outcome))
        return outcomes

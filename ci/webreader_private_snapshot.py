#!/usr/bin/env python3
"""Offline, host-only protected-copy rehearsal. Never invoke an installer.

The caller is assumed to supply trustworthy source/private directory roots and
independently signed expected metadata. Neither assumption is demonstrated by
this helper. On-device IPC credentials, release signatures, full ZIP inspection
and the appinst re-copy behavior remain separate UNRESOLVED gates.
"""
import hashlib
import hmac
import os
from pathlib import Path
import re
import secrets
import stat

from webreader_helper_file_preflight import (
    MAX_IPA_BYTES, NAME_RE, SHA_RE, BLOCK, FilePreflightRejected,
)


class SnapshotRejected(FilePreflightRejected):
    """No protected snapshot can be provided to a future validator."""


def _id(s):
    return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)


class PrivateSnapshot:
    """Holds the same read-only fd used for a second hash verification.

    This does NOT authorize installation. Cleanup is caller-controlled in this
    host prototype. Real privileged storage must not be writable by the app.
    """
    def __init__(self, fd, root_fd, leaf, size, digest, dev, ino):
        self._fd = fd
        self._root_fd = root_fd
        self._leaf = leaf
        self.size = size
        self.sha256 = digest
        self._identity = (dev, ino)

    @property
    def installer_authorized(self):
        return False

    def verify_snapshot(self):
        if self._fd is None:
            raise SnapshotRejected("snapshot handle closed")
        st_before = os.fstat(self._fd)
        if not stat.S_ISREG(st_before.st_mode) or st_before.st_size != self.size:
            raise SnapshotRejected("snapshot no longer regular or same size")
        os.lseek(self._fd, 0, os.SEEK_SET)
        digest = hashlib.sha256()
        consumed = 0
        while True:
            chunk = os.read(self._fd, BLOCK)
            if not chunk:
                break
            consumed += len(chunk)
            if consumed > self.size:
                raise SnapshotRejected("snapshot size grew")
            digest.update(chunk)
        st_after = os.fstat(self._fd)
        if (_id(st_before) != _id(st_after) or consumed != self.size or
                not hmac.compare_digest(digest.hexdigest(), self.sha256)):
            raise SnapshotRejected("snapshot content changed")
        return True

    def close(self):
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None

    def remove_for_test(self):
        self.close()
        if self._root_fd is not None:
            try:
                named = os.stat(self._leaf, dir_fd=self._root_fd,
                                follow_symlinks=False)
                if (named.st_dev, named.st_ino) == self._identity:
                    os.unlink(self._leaf, dir_fd=self._root_fd)
            except FileNotFoundError:
                pass
            finally:
                os.close(self._root_fd)
                self._root_fd = None

    def __enter__(self):
        if self._fd is None:
            raise SnapshotRejected("snapshot handle closed")
        return self

    def __exit__(self, *_):
        self.remove_for_test()


def prepare_private_snapshot(source_root: Path, staged_leaf: str,
                             private_root: Path, *, expected_build: int,
                             expected_size: int, expected_sha256: str,
                             _test_after_first_chunk=None):
    """Copy one verified source fd to a private root and return a held RO fd.

    All expected metadata is TEST INPUT. A production process must derive it
    from its own verified publisher signature, never directly from an IPC msg.
    """
    if (type(expected_build) is not int or not 1 <= expected_build <= 2_147_483_647 or
            type(expected_size) is not int or not 4 <= expected_size <= MAX_IPA_BYTES or
            type(expected_sha256) is not str or not SHA_RE.fullmatch(expected_sha256)):
        raise SnapshotRejected("invalid purported signed metadata")
    if (type(staged_leaf) is not str or not NAME_RE.fullmatch(staged_leaf) or
            int(NAME_RE.fullmatch(staged_leaf).group(1)) != expected_build):
        raise SnapshotRejected("unexpected staged filename")
    if (not isinstance(source_root, Path) or not isinstance(private_root, Path) or
            not source_root.is_absolute() or not private_root.is_absolute()):
        raise SnapshotRejected("directories must be trusted absolute Path objects")

    src_dfd = dst_dfd = src_fd = new_fd = verified_fd = None
    tmp_leaf = final_leaf = None
    installed_final_link = False
    created_tmp = False
    succeeded = False
    try:
        src_dfd = os.open(source_root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        dst_dfd = os.open(private_root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        src_st = os.fstat(src_dfd)
        dst_st = os.fstat(dst_dfd)
        if ((src_st.st_dev, src_st.st_ino) == (dst_st.st_dev, dst_st.st_ino) or
                not stat.S_ISDIR(src_st.st_mode) or not stat.S_ISDIR(dst_st.st_mode) or
                src_st.st_mode & 0o022 or dst_st.st_mode & 0o077 or
                dst_st.st_uid != os.geteuid()):
            raise SnapshotRejected("unsafe source or supposedly private directory")
        src_fd = os.open(staged_leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                         dir_fd=src_dfd)
        before = os.fstat(src_fd)
        if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or
                before.st_uid != src_st.st_uid or before.st_mode & 0o022 or
                before.st_size != expected_size):
            raise SnapshotRejected("unsafe original staged IPA")

        token = secrets.token_hex(16)
        if type(token) is not str or not re.fullmatch(r"[0-9a-f]{32}", token):
            raise SnapshotRejected("invalid internal snapshot token")
        tmp_leaf = ".incoming-" + token + ".tmp"
        final_leaf = "verified-" + token + ".ipa"
        new_fd = os.open(tmp_leaf, os.O_CREAT | os.O_EXCL | os.O_RDWR | os.O_NOFOLLOW,
                         0o600, dir_fd=dst_dfd)
        created_tmp = True
        hasher = hashlib.sha256()
        total = 0
        zip_prefix = b""
        while True:
            chunk = os.read(src_fd, BLOCK)
            if not chunk:
                break
            if total == 0:
                zip_prefix = chunk[:4]
            total += len(chunk)
            if total > expected_size:
                raise SnapshotRejected("source file grew during protected copy")
            hasher.update(chunk)
            view = memoryview(chunk)
            while view:
                count = os.write(new_fd, view)
                if count <= 0:
                    raise SnapshotRejected("snapshot write stalled")
                view = view[count:]
            if _test_after_first_chunk is not None and total == len(chunk):
                _test_after_first_chunk()
        after = os.fstat(src_fd)
        by_name = os.stat(staged_leaf, dir_fd=src_dfd, follow_symlinks=False)
        if (_id(before) != _id(after) or
                (after.st_dev, after.st_ino) != (by_name.st_dev, by_name.st_ino) or
                total != expected_size or zip_prefix != b"PK\x03\x04" or
                not hmac.compare_digest(hasher.hexdigest(), expected_sha256)):
            raise SnapshotRejected("source identity or checksum changed")
        written = os.fstat(new_fd)
        if not stat.S_ISREG(written.st_mode) or written.st_size != total:
            raise SnapshotRejected("snapshot was incomplete")
        os.fchmod(new_fd, 0o400)
        os.fsync(new_fd)
        # Atomic no-clobber publication: final pathname must not preexist.
        os.link(tmp_leaf, final_leaf, src_dir_fd=dst_dfd,
                dst_dir_fd=dst_dfd, follow_symlinks=False)
        installed_final_link = True
        os.unlink(tmp_leaf, dir_fd=dst_dfd)
        tmp_leaf = None
        os.fsync(dst_dfd)
        verified_fd = os.open(final_leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                              dir_fd=dst_dfd)
        final_st = os.fstat(verified_fd)
        if (not stat.S_ISREG(final_st.st_mode) or final_st.st_nlink != 1 or
                final_st.st_uid != dst_st.st_uid or final_st.st_size != expected_size or
                (final_st.st_dev, final_st.st_ino) != (written.st_dev, written.st_ino)):
            raise SnapshotRejected("private snapshot identity changed")
        # Independent second SHA over the exact fd returned to the caller.
        second = hashlib.sha256()
        while True:
            block = os.read(verified_fd, BLOCK)
            if not block:
                break
            second.update(block)
        if not hmac.compare_digest(second.hexdigest(), expected_sha256):
            raise SnapshotRejected("private copy hash mismatch")
        os.lseek(verified_fd, 0, os.SEEK_SET)
        snapshot = PrivateSnapshot(verified_fd, dst_dfd, final_leaf,
                                   total, expected_sha256,
                                   final_st.st_dev, final_st.st_ino)
        verified_fd = None
        dst_dfd = None  # Ownership transferred to the held snapshot.
        succeeded = True
        return snapshot
    except OSError as exc:
        raise SnapshotRejected("snapshot filesystem operation failed") from exc
    finally:
        if verified_fd is not None:
            os.close(verified_fd)
        if new_fd is not None:
            os.close(new_fd)
        if dst_dfd is not None:
            if created_tmp and tmp_leaf is not None:
                try: os.unlink(tmp_leaf, dir_fd=dst_dfd)
                except OSError: pass
            if installed_final_link and not succeeded:
                try: os.unlink(final_leaf, dir_fd=dst_dfd)
                except OSError: pass
            os.close(dst_dfd)
        if src_fd is not None:
            os.close(src_fd)
        if src_dfd is not None:
            os.close(src_dfd)

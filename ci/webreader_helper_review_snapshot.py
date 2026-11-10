#!/usr/bin/env python3
"""CK: host-only protected *review* copy of a downloaded IPA.

This is NEVER an installation handle. An owner-writable file can still be
mutated later; chmod 0400 is NOT immutable (root/same owner can chmod it).
The future helper needs authenticated IPC, independent publisher/codesign
verification, durable replay state, local user consent and a way to pass the
EXACT immutable reviewed bytes to appinst instead of a mutable path.

No device access, network, application installation, appinst, code signing,
or privilege is used. Only a preexisting 0700 staging directory is accepted.
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
import stat

_RE_SHA = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_MAX_SIZE = 512 * 1024 * 1024
_MIN_SIZE = 4
_MAX_BUILD = 2_147_483_647
_CHUNK = 128 * 1024


class ReviewSnapshotRejected(ValueError):
    pass


@dataclass(frozen=True)
class ReviewSnapshotReceipt:
    requested_build: int
    checked_sha256: str
    checked_size: int
    review_basename: str
    independent_signature_verified: bool = False
    publisher_identity_verified: bool = False
    immutable_installer_handle_issued: bool = False
    peer_authenticated: bool = False
    user_consent_verified: bool = False
    install_authorized: bool = False
    installation_performed: bool = False


def _flags():
    if not all(hasattr(os, name) for name in
               ("O_NOFOLLOW", "O_DIRECTORY", "O_CLOEXEC")):
        raise ReviewSnapshotRejected("required POSIX fd protections unsupported")
    return os.O_NOFOLLOW | os.O_CLOEXEC


def _identity(st):
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)


def _validate_regular(st, *, expected_size):
    if (not stat.S_ISREG(st.st_mode) or st.st_nlink != 1
            or st.st_uid != os.getuid()
            or st.st_mode & 0o022
            or st.st_size != expected_size):
        raise ReviewSnapshotRejected("source regular file, owner, hardlink, mode or size denied")


def protected_review_snapshot(*, source_path: Path, staging_directory: Path,
                              expected_sha256: str, expected_size: int,
                              requested_build: int, on_first_chunk=None) -> ReviewSnapshotReceipt:
    if (type(expected_sha256) is not str or not _RE_SHA.fullmatch(expected_sha256)
            or type(expected_size) is not int
            or not _MIN_SIZE <= expected_size <= _MAX_SIZE
            or type(requested_build) is not int
            or not 1 <= requested_build <= _MAX_BUILD):
        raise ReviewSnapshotRejected("invalid previously checked release facts")
    if type(source_path) is not Path or type(staging_directory) is not Path:
        raise ReviewSnapshotRejected("explicit filesystem paths required")
    if (not source_path.is_absolute() or not staging_directory.is_absolute()
            or ".." in source_path.parts or ".." in staging_directory.parts
            or source_path == staging_directory):
        raise ReviewSnapshotRejected("unsafe file or directory location")
    flags = _flags()
    directory_fd = -1
    source_fd = -1
    output_fd = -1
    basename = "WebReader-review-build" + str(requested_build) + "-" + expected_sha256[:20] + ".ipa"
    created = False
    try:
        # Open directory by FD; all subsequent writes occur relative to it.
        # Ancestor directories are NOT proven trustworthy by this prototype.
        directory_fd = os.open(staging_directory, os.O_RDONLY | os.O_DIRECTORY | flags)
        folder = os.fstat(directory_fd)
        if (not stat.S_ISDIR(folder.st_mode) or folder.st_uid != os.getuid()
                or stat.S_IMODE(folder.st_mode) != 0o700):
            raise ReviewSnapshotRejected("destination is not preexisting 0700 owner-only directory")
        source_fd = os.open(source_path, os.O_RDONLY | os.O_NONBLOCK | flags)
        before = os.fstat(source_fd)
        _validate_regular(before, expected_size=expected_size)
        named = os.stat(source_path, follow_symlinks=False)
        if _identity(before) != _identity(named):
            raise ReviewSnapshotRejected("source filename changed before copy")
        outflags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | flags
        output_fd = os.open(basename, outflags, 0o600, dir_fd=directory_fd)
        created = True
        copied = 0
        sha = hashlib.sha256()
        first = True
        while True:
            chunk = os.read(source_fd, _CHUNK)
            if not chunk:
                break
            copied += len(chunk)
            if copied > expected_size:
                raise ReviewSnapshotRejected("file grew during review copy")
            sha.update(chunk)
            mv = memoryview(chunk)
            while mv:
                count = os.write(output_fd, mv)
                if count <= 0:
                    raise ReviewSnapshotRejected("short copy write")
                mv = mv[count:]
            if first and on_first_chunk is not None:
                on_first_chunk()
            first = False
        after = os.fstat(source_fd)
        name_after = os.stat(source_path, follow_symlinks=False)
        if (_identity(before) != _identity(after)
                or _identity(before) != _identity(name_after)
                or copied != expected_size
                or sha.hexdigest() != expected_sha256):
            raise ReviewSnapshotRejected("source changed or verified digest mismatched")
        # A second digest of the copied file (not just input) catches errors
        # from the copy path. This is STILL NOT a durable immutable handle.
        os.fsync(output_fd)
        out_stat = os.fstat(output_fd)
        if (not stat.S_ISREG(out_stat.st_mode) or out_stat.st_size != expected_size
                or out_stat.st_uid != os.getuid() or out_stat.st_nlink != 1):
            raise ReviewSnapshotRejected("review output identity failed")
        os.close(output_fd)
        output_fd = -1
        readback_fd = os.open(basename, os.O_RDONLY | flags, dir_fd=directory_fd)
        try:
            image = hashlib.sha256()
            while True:
                part = os.read(readback_fd, _CHUNK)
                if not part: break
                image.update(part)
            if image.hexdigest() != expected_sha256:
                raise ReviewSnapshotRejected("copied output digest mismatch")
            os.fchmod(readback_fd, 0o400)
            os.fsync(readback_fd)
        finally:
            os.close(readback_fd)
        os.fsync(directory_fd)
        return ReviewSnapshotReceipt(
            requested_build, expected_sha256, copied, basename
        )
    except (OSError, ReviewSnapshotRejected) as exc:
        # Leave a created partial output as a spent tombstone. Never delete
        # by pathname after loss of the original opened file identity.
        # A new review requires a new isolated directory and human inspection.
        if isinstance(exc, ReviewSnapshotRejected):
            raise
        raise ReviewSnapshotRejected("protected review snapshot I/O failure") from exc
    finally:
        if output_fd >= 0: os.close(output_fd)
        if source_fd >= 0: os.close(source_fd)
        if directory_fd >= 0: os.close(directory_fd)

#!/usr/bin/env python3
"""Host-only read-only file preflight prototype for a future WebReader helper.

This is not an installer, an IPA/ZIP validator, an IPC service or an entitlement.
The trusted root directory and signed metadata MUST be established independently
by a future native helper. Passing this preflight NEVER authorizes installation.
"""
from dataclasses import dataclass
import hashlib
import hmac
import os
from pathlib import Path
import re
import stat

MAX_IPA_BYTES = 512 * 1024 * 1024
BLOCK = 256 * 1024
UUID_RE = r"[0-9A-Fa-f]{8}(?:-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}"
NAME_RE = re.compile(r"WebReader-build([1-9][0-9]{0,9})-(" + UUID_RE + r")\.ipa\Z", re.ASCII)
SHA_RE = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)


class FilePreflightRejected(ValueError):
    """Untrusted candidate or missing/different staged IPA file."""


@dataclass(frozen=True)
class FilePreflightReport:
    build: int
    file_size: int
    sha256: str
    file_was_regular: bool
    no_link_at_open: bool

    @property
    def installer_authorized(self):
        return False


def _identity(st):
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)


def inspect_prepared_ipa(directory: Path, leaf_name: str, *, expected_build: int,
                         expected_size: int, expected_sha256: str,
                         _test_after_first_chunk=None) -> FilePreflightReport:
    """Reject untrusted file names/links and audit one fd without extraction.

    This confirms only current byte identity relative to supplied metadata. The
    independently pinned signed-release verification and the native ZIP/Info.plist
    audit are NOT performed here. A future installer must retain the verified fd
    or make a protected immutable copy then revalidate immediately before use.
    """
    if type(expected_build) is not int or not 1 <= expected_build <= 2_147_483_647:
        raise FilePreflightRejected("invalid expected build")
    if type(expected_size) is not int or not 4 <= expected_size <= MAX_IPA_BYTES:
        raise FilePreflightRejected("invalid expected IPA size")
    if type(expected_sha256) is not str or SHA_RE.fullmatch(expected_sha256) is None:
        raise FilePreflightRejected("invalid expected digest")
    if type(leaf_name) is not str:
        raise FilePreflightRejected("invalid leaf filename")
    name = NAME_RE.fullmatch(leaf_name)
    if name is None or int(name.group(1)) != expected_build:
        raise FilePreflightRejected("unapproved staged filename")
    if not isinstance(directory, Path):
        raise FilePreflightRejected("root must be a trusted absolute Path")
    if not directory.is_absolute():
        raise FilePreflightRejected("root must be absolute")

    dir_fd = None
    file_fd = None
    try:
        dir_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        ds = os.fstat(dir_fd)
        if not stat.S_ISDIR(ds.st_mode) or ds.st_mode & 0o022:
            raise FilePreflightRejected("unsafe staging directory permissions")
        file_fd = os.open(leaf_name,
                          os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                          dir_fd=dir_fd)
        before = os.fstat(file_fd)
        if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or
                before.st_uid != ds.st_uid or before.st_mode & 0o022):
            raise FilePreflightRejected("unsafe staged file identity")
        if before.st_size != expected_size:
            raise FilePreflightRejected("file size mismatch")
        digest = hashlib.sha256()
        read = 0
        first_four = b""
        while True:
            block = os.read(file_fd, BLOCK)
            if not block:
                break
            if read == 0:
                first_four = block[:4]
            read += len(block)
            if read > expected_size:
                raise FilePreflightRejected("file grew during audit")
            digest.update(block)
            if _test_after_first_chunk is not None and read == len(block):
                _test_after_first_chunk()
        after = os.fstat(file_fd)
        try:
            by_name = os.stat(leaf_name, dir_fd=dir_fd, follow_symlinks=False)
        except OSError as error:
            raise FilePreflightRejected("staged filename disappeared") from error
        if (_identity(before) != _identity(after) or
                (after.st_dev, after.st_ino) != (by_name.st_dev, by_name.st_ino) or
                read != expected_size):
            raise FilePreflightRejected("staged file changed during audit")
        if first_four != b"PK\x03\x04":
            raise FilePreflightRejected("missing ZIP local-header prefix")
        actual = digest.hexdigest()
        if not hmac.compare_digest(actual, expected_sha256):
            raise FilePreflightRejected("staged file SHA-256 mismatch")
        return FilePreflightReport(
            build=expected_build,
            file_size=read,
            sha256=actual,
            file_was_regular=True,
            no_link_at_open=True,
        )
    except OSError as error:
        raise FilePreflightRejected("file open or read rejected") from error
    finally:
        if file_fd is not None:
            os.close(file_fd)
        if dir_fd is not None:
            os.close(dir_fd)

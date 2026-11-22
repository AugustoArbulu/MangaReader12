#!/usr/bin/env python3
"""Phase CU: read-only, nonprivileged, anchored host file-custody inspection.

A local test root is supplied as a trust *assumption*, never authenticated.
The function inspects descendants relative to opened directory descriptors,
rejects links and insecure permissions, and hashes a bounded regular file.
Nothing here establishes a separate helper UID, tamper resistance after close,
the identity of the actual iOS installer input, or installation permission.
No network, subprocess, privileged operations or appinst.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import os
from pathlib import Path
import re
import stat

_MAX_FILE = 1024 * 1024
_MAX_DEPTH = 5
_BLOCK = 32768
_LEAF = re.compile(r"[a-z0-9][a-z0-9-]{0,63}\.fake\Z", re.ASCII)
_SUBDIR = re.compile(r"[a-z0-9][a-z0-9-]{0,31}\Z", re.ASCII)
_SHA = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)


class CustodyAuditRejected(ValueError):
    """Observed inputs or filesystem conditions fail the review-only policy."""


@dataclass(frozen=True)
class CustodyHostObservation:
    checked_sha256: str
    size: int
    ancestor_directory_descriptors_checked: int
    fd_and_filename_agreed_at_review: bool
    file_owned_by_lab_uid: bool
    chain_root_from_trusted_device_policy: bool = False
    separate_helper_uid_verified_on_device: bool = False
    client_write_access_excluded: bool = False
    future_inode_mutation_excluded: bool = False
    appinst_secondary_copy_protected: bool = False
    final_installer_bytes_bound_to_verified_fd: bool = False
    production_editor_identity_authenticated: bool = False
    consent_from_trusted_owner_ui: bool = False
    durable_antireplay_completed: bool = False
    ios12_runtime_verified: bool = False
    installation_authorized: bool = False
    installation_performed: bool = False


def _folder_stat(fd: int) -> None:
    info = os.fstat(fd)
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) != 0o700):
        raise CustodyAuditRejected("lab directory must be own 0700")


def _identity(info):
    return (info.st_dev, info.st_ino, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns)


def inspect_anchored_host_file(*, anchor: Path, components: tuple[str, ...],
                               leaf: str, expected_size: int, expected_sha256: str,
                               after_read=None) -> CustodyHostObservation:
    """Inspect one host fixture under a *caller-assumed* trusted anchor.

    The trusted status of anchor's ancestors is deliberately NOT inferred.
    No caller can supply an install path or get an installer authorization.
    """
    if (not isinstance(anchor, Path) or not anchor.is_absolute()
            or ".." in anchor.parts or anchor.is_symlink()
            or not all(hasattr(os, k) for k in ("O_DIRECTORY", "O_NOFOLLOW", "O_CLOEXEC"))):
        raise CustodyAuditRejected("absolute, pre-trusted non-symlink anchor required")
    if (type(components) is not tuple or len(components) > _MAX_DEPTH
            or not all(type(c) is str and _SUBDIR.fullmatch(c) for c in components)
            or type(leaf) is not str or _LEAF.fullmatch(leaf) is None):
        raise CustodyAuditRejected("invalid relative anchored file path")
    if (type(expected_size) is not int or not 4 <= expected_size <= _MAX_FILE
            or type(expected_sha256) is not str or _SHA.fullmatch(expected_sha256) is None):
        raise CustodyAuditRejected("expected review facts invalid")

    dir_fds: list[int] = []
    fd = -1
    try:
        base = os.open(anchor, os.O_RDONLY | os.O_DIRECTORY |
                       os.O_NOFOLLOW | os.O_CLOEXEC)
        dir_fds.append(base)
        _folder_stat(base)
        for part in components:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY |
                            os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=dir_fds[-1])
            dir_fds.append(child)
            _folder_stat(child)
        parent = dir_fds[-1]
        fd = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
                     dir_fd=parent)
        before = os.fstat(fd)
        if (not stat.S_ISREG(before.st_mode) or before.st_uid != os.geteuid()
                or before.st_nlink != 1 or before.st_mode & 0o022
                or before.st_size != expected_size):
            raise CustodyAuditRejected("unsafe fixture inode, mode, owner, links or size")
        digest = hashlib.sha256()
        total = 0
        while True:
            chunk = os.read(fd, _BLOCK)
            if not chunk:
                break
            total += len(chunk)
            if total > expected_size:
                raise CustodyAuditRejected("file grew during anchored read")
            digest.update(chunk)
        if after_read is not None:
            after_read()
        after = os.fstat(fd)
        named = os.stat(leaf, dir_fd=parent, follow_symlinks=False)
        if (_identity(before) != _identity(after)
                or _identity(before) != _identity(named)
                or total != expected_size
                or not hmac.compare_digest(digest.hexdigest(), expected_sha256)):
            raise CustodyAuditRejected("review bytes or anchored name changed")
        return CustodyHostObservation(
            checked_sha256=digest.hexdigest(), size=total,
            ancestor_directory_descriptors_checked=len(dir_fds),
            fd_and_filename_agreed_at_review=True, file_owned_by_lab_uid=True
        )
    except OSError as exc:
        raise CustodyAuditRejected("anchored host file unavailable or unsafe") from exc
    finally:
        if fd >= 0:
            os.close(fd)
        for dir_fd in reversed(dir_fds):
            os.close(dir_fd)


def main() -> int:
    import tempfile
    with tempfile.TemporaryDirectory(prefix="wr-cu-review-only-") as tmp:
        root = Path(tmp)
        root.chmod(0o700)
        child = root / "private"
        child.mkdir(mode=0o700)
        child.chmod(0o700)
        fake = child / "candidate.fake"
        contents = b"WEBREADER_CU_HOST_SYNTHETIC_NOT_IPA\n" * 32
        fake.write_bytes(contents)
        expected = hashlib.sha256(contents).hexdigest()
        observation = inspect_anchored_host_file(
            anchor=root, components=("private",), leaf="candidate.fake",
            expected_sha256=expected, expected_size=len(contents))
        assert observation.fd_and_filename_agreed_at_review
        assert not observation.separate_helper_uid_verified_on_device
        assert not observation.installation_authorized
        assert not observation.installation_performed
    print("PASS CU: anchored directory FD and synthetic file verified on host only")
    print("NO iOS trust proof, NO appinst, NO IPA, NO install")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

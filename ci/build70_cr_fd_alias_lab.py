#!/usr/bin/env python3
"""CR: host-only FD alias laboratory; never an installation authorization.

Proves only that a controlled Python child can consume a previously verified
open file description while the original pathname is replaced. On Linux use
/proc/self/fd/N, on macOS use /dev/fd/N. This does NOT establish that appinst
accepts descriptor aliases, or that the bytes cannot be changed via another
writable handle. No network, iOS, root, production keys or real IPA is used.
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile

GOOD = b"WEBREADER_CR_VERIFIED_FIXTURE\n" * 16
EVIL = b"WEBREADER_CR_REPLACEMENT_FIXTURE\n" * 16
CHILD = r'''
import hashlib, os, sys
alias = sys.argv[1]
with open(alias, "rb") as f:
    data = f.read()
print(hashlib.sha256(data).hexdigest())
'''

class FdAliasLabRejected(ValueError):
    pass

@dataclass(frozen=True)
class FdAliasObservation:
    original_sha256: str
    pathname_after_swap_sha256: str
    child_alias_sha256: str
    pathname_swap_resisted: bool
    host_fd_alias_supported: bool
    # The test DOES NOT establish any of these properties.
    ios12_verified: bool = False
    appinst_fd_alias_compatible: bool = False
    appinst_used: bool = False
    immutable_install_bytes_proven: bool = False
    publisher_authenticated: bool = False
    consent_verified: bool = False
    install_authorized: bool = False
    installation_performed: bool = False


def _alias(fd: int) -> str:
    if sys.platform == "darwin":
        return f"/dev/fd/{fd}"
    if sys.platform.startswith("linux"):
        return f"/proc/self/fd/{fd}"
    raise FdAliasLabRejected("lab supports only macOS and Linux")


def _spawn_fixture(alias: str, fd: int, *, forward_fd: bool) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-c", CHILD, alias],
        pass_fds=(fd,) if forward_fd else (),
        check=False, capture_output=True, text=True, timeout=15
    )


def observe_swapped_path(*, forward_fd: bool = True) -> FdAliasObservation:
    """Only in a fresh temporary lab. No caller-selected path or executable."""
    if os.name != "posix" or not hasattr(os, "O_NOFOLLOW"):
        raise FdAliasLabRejected("POSIX O_NOFOLLOW required")
    with tempfile.TemporaryDirectory(prefix="wr-cr-fd-fixture-") as temp:
        directory = Path(temp)
        original = directory / "candidate.fake"
        moved = directory / "previous.fake"
        original.write_bytes(GOOD)
        expected = hashlib.sha256(GOOD).hexdigest()
        fd = os.open(original, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0))
        try:
            first = os.fstat(fd)
            if not stat.S_ISREG(first.st_mode) or first.st_nlink != 1:
                raise FdAliasLabRejected("invalid test fixture")
            with os.fdopen(os.dup(fd), "rb") as review:
                digest = hashlib.sha256(review.read()).hexdigest()
            if digest != expected:
                raise FdAliasLabRejected("original descriptor digest mismatch")
            # Simulate an attacker replacing a *name*, not modifying the FD.
            original.rename(moved)
            original.write_bytes(EVIL)
            changed = hashlib.sha256(original.read_bytes()).hexdigest()
            if changed == expected:
                raise FdAliasLabRejected("attack fixture did not change pathname")
            # No untrusted name is passed to the child: only the FD alias.
            result = _spawn_fixture(_alias(fd), fd, forward_fd=forward_fd)
            if result.returncode != 0:
                raise FdAliasLabRejected("child cannot consume forwarded descriptor alias")
            child_digest = result.stdout.strip()
            if len(child_digest) != 64:
                raise FdAliasLabRejected("unexpected child digest")
            after = os.fstat(fd)
            if (first.st_dev, first.st_ino, first.st_size) != (after.st_dev, after.st_ino, after.st_size):
                raise FdAliasLabRejected("descriptor identity changed")
            if child_digest != expected:
                raise FdAliasLabRejected("child consumed different bytes")
            return FdAliasObservation(expected, changed, child_digest, True, True)
        finally:
            os.close(fd)


def main() -> int:
    result = observe_swapped_path()
    assert result.pathname_swap_resisted
    assert not any((result.ios12_verified, result.appinst_fd_alias_compatible,
                    result.immutable_install_bytes_proven, result.install_authorized,
                    result.installation_performed))
    print("PASS CR: host fixture FD alias preserved original bytes despite pathname swap")
    print("NO iOS verification; NO appinst compatibility claim; NO install")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

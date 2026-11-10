#!/usr/bin/env python3
"""CT host-only two-hop *review* simulation, NEVER an installer.

Models the extra path-to-path copy found in the public appinst reference:
source -> helper review copy -> second handoff copy. All three directories
must be pre-existing, owned by the test user and 0700. Explicit FD-based
copies and readbacks reject swapped names and altered bytes *at review time*.

This does NOT make a directory or file immutable; a same-UID or privileged
writer can still mutate bytes later. No appinst, IPA, iOS, network or shell.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import os
from pathlib import Path
import re
import stat
import tempfile

MAX_FIXTURE = 1024 * 1024
BLOCK = 32768
HEX = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
ORIGINAL = b"PK\x03\x04WEBREADER_CT_FAKE_ORIGINAL_NOT_AN_IPA\n" * 32
ALTERED = b"PK\x03\x04WEBREADER_CT_FAKE_ALTERED_NOT_AN_IPA\n" * 32


class CTReviewRejected(ValueError):
    pass


@dataclass(frozen=True)
class CTTwoHopObservation:
    expected_sha256: str
    helper_review_sha256: str
    second_copy_sha256: str
    both_copies_verified_at_review: bool
    source_dir_mode_0700: bool
    review_dir_mode_0700: bool
    second_dir_mode_0700: bool
    # Neither path may be described as a safe installer input.
    protection_from_later_same_uid_mutation: bool = False
    true_privilege_separation_proven: bool = False
    macos_native_code_signature_checked: bool = False
    exact_iOS_installer_consumption_proven: bool = False
    publisher_authenticated: bool = False
    owner_consent_verified: bool = False
    appinst_called: bool = False
    installation_authorized: bool = False
    installation_performed: bool = False


@dataclass(frozen=True)
class CTPostReviewMutation:
    verified_sha256: str
    later_sha256: str
    later_writes_remain_possible: bool
    installer_byte_identity_proven: bool = False
    installation_authorized: bool = False
    installation_performed: bool = False


def _folder_fd(folder: Path) -> int:
    if (not isinstance(folder, Path) or not folder.is_absolute()
            or ".." in folder.parts or folder.is_symlink()
            or not all(hasattr(os, k) for k in ("O_NOFOLLOW", "O_DIRECTORY", "O_CLOEXEC"))):
        raise CTReviewRejected("expected an absolute pre-existing non-link POSIX folder")
    try:
        fd = os.open(folder, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        info = os.fstat(fd)
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o700):
            raise CTReviewRejected("folder must be 0700 and owned by current user")
        return fd
    except OSError as exc:
        raise CTReviewRejected("folder open failed") from exc
    except CTReviewRejected:
        os.close(fd)
        raise


def _regular(info, expected_size: int):
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
            or info.st_nlink != 1 or info.st_mode & 0o022
            or info.st_size != expected_size):
        raise CTReviewRejected("unsafe source or output file identity")


def _copy_checked(src_dir: int, src_leaf: str, dest_dir: int, dest_leaf: str,
                  expected_sha: str, expected_size: int) -> str:
    """Copy once by descriptor and verify source *and* copy (review only)."""
    if not (type(src_leaf) is str and type(dest_leaf) is str
            and re.fullmatch(r"[a-z0-9-]{1,60}\.fake", src_leaf)
            and re.fullmatch(r"[a-z0-9-]{1,60}\.fake", dest_leaf)):
        raise CTReviewRejected("only fixed synthetic fixture leaf names")
    src_fd, dst_fd = -1, -1
    try:
        src_fd = os.open(src_leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
                         dir_fd=src_dir)
        before = os.fstat(src_fd)
        _regular(before, expected_size)
        # Exclusive creation: do not remove a partially created output on error.
        dst_fd = os.open(dest_leaf, os.O_CREAT | os.O_EXCL | os.O_WRONLY |
                         os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=dest_dir)
        sha = hashlib.sha256()
        copied = 0
        while True:
            chunk = os.read(src_fd, BLOCK)
            if not chunk:
                break
            copied += len(chunk)
            if copied > expected_size:
                raise CTReviewRejected("source grew while copied")
            sha.update(chunk)
            offset = 0
            while offset < len(chunk):
                written = os.write(dst_fd, chunk[offset:])
                if written <= 0:
                    raise CTReviewRejected("short second-copy write")
                offset += written
        after = os.fstat(src_fd)
        by_name = os.stat(src_leaf, dir_fd=src_dir, follow_symlinks=False)
        if ((before.st_dev, before.st_ino, before.st_mtime_ns, before.st_ctime_ns)
                != (after.st_dev, after.st_ino, after.st_mtime_ns, after.st_ctime_ns)
                or (before.st_dev, before.st_ino) != (by_name.st_dev, by_name.st_ino)
                or copied != expected_size
                or not hmac.compare_digest(sha.hexdigest(), expected_sha)):
            raise CTReviewRejected("source changed, renamed or digest differed")
        os.fsync(dst_fd)
        _regular(os.fstat(dst_fd), expected_size)
        os.close(dst_fd)
        dst_fd = -1
        # Independently check the destination by reopening inside the held
        # directory FD. This is NOT a guarantee about subsequent consumers.
        check_fd = os.open(dest_leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
                           dir_fd=dest_dir)
        try:
            check_stat = os.fstat(check_fd)
            _regular(check_stat, expected_size)
            h = hashlib.sha256()
            while True:
                b = os.read(check_fd, BLOCK)
                if not b:
                    break
                h.update(b)
            after_check = os.fstat(check_fd)
            by_dest_name = os.stat(dest_leaf, dir_fd=dest_dir, follow_symlinks=False)
            if (check_stat.st_dev, check_stat.st_ino, check_stat.st_size,
                check_stat.st_mtime_ns, check_stat.st_ctime_ns) != (
                after_check.st_dev, after_check.st_ino, after_check.st_size,
                after_check.st_mtime_ns, after_check.st_ctime_ns
            ) or (check_stat.st_dev, check_stat.st_ino) != (
                by_dest_name.st_dev, by_dest_name.st_ino
            ) or not hmac.compare_digest(h.hexdigest(), expected_sha):
                raise CTReviewRejected("second copy readback mismatch")
        finally:
            os.close(check_fd)
        os.fsync(dest_dir)
        return expected_sha
    except OSError as exc:
        raise CTReviewRejected("two-hop source/copy I/O rejected") from exc
    finally:
        if src_fd != -1:
            os.close(src_fd)
        if dst_fd != -1:
            os.close(dst_fd)


def two_hop_review(*, source_dir: Path, review_dir: Path, second_dir: Path,
                   expected_sha256: str, expected_size: int,
                   after_first_copy=None, after_second_copy=None) -> CTTwoHopObservation:
    if (type(expected_sha256) is not str or not HEX.fullmatch(expected_sha256)
            or type(expected_size) is not int
            or not 4 <= expected_size <= MAX_FIXTURE):
        raise CTReviewRejected("invalid fixed synthetic metadata")
    folders = (source_dir, review_dir, second_dir)
    if (not all(isinstance(f, Path) for f in folders)
            or len({f.resolve(strict=True) for f in folders}) != 3):
        raise CTReviewRejected("three separate existing folders required")
    fds = []
    try:
        for folder in folders:
            fds.append(_folder_fd(folder))
        src, review, second = fds
        name1 = "review-" + expected_sha256[:24] + ".fake"
        name2 = "handoff-" + expected_sha256[:24] + ".fake"
        _copy_checked(src, "candidate.fake", review, name1,
                      expected_sha256, expected_size)
        if after_first_copy is not None:
            after_first_copy(review_dir / name1)
        _copy_checked(review, name1, second, name2,
                      expected_sha256, expected_size)
        if after_second_copy is not None:
            after_second_copy(second_dir / name2)
        # Check final output after any injected lab mutation.
        final_fd = os.open(name2, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
                           dir_fd=second)
        try:
            stat_final = os.fstat(final_fd)
            _regular(stat_final, expected_size)
            h = hashlib.sha256()
            while True:
                piece = os.read(final_fd, BLOCK)
                if not piece:
                    break
                h.update(piece)
            now = os.fstat(final_fd)
            named = os.stat(name2, dir_fd=second, follow_symlinks=False)
            if ((stat_final.st_dev, stat_final.st_ino, stat_final.st_size,
                 stat_final.st_mtime_ns, stat_final.st_ctime_ns)
                != (now.st_dev, now.st_ino, now.st_size,
                    now.st_mtime_ns, now.st_ctime_ns)
                or (now.st_dev, now.st_ino) != (named.st_dev, named.st_ino)
                or not hmac.compare_digest(h.hexdigest(), expected_sha256)):
                raise CTReviewRejected("final readback failed")
        finally:
            os.close(final_fd)
        return CTTwoHopObservation(
            expected_sha256, expected_sha256, h.hexdigest(), True,
            True, True, True
        )
    except OSError as exc:
        raise CTReviewRejected("final review I/O rejected") from exc
    finally:
        for fd in reversed(fds):
            os.close(fd)


def same_uid_post_review_mutation() -> CTPostReviewMutation:
    """Counterexample: mode 0400 and 0700 do not imply immutability."""
    with tempfile.TemporaryDirectory(prefix="wr-ct-late-mutation-") as temp:
        root = Path(temp)
        root.chmod(0o700)
        leaf = root / "reviewed.fake"
        leaf.write_bytes(ORIGINAL)
        leaf.chmod(0o400)
        checked = hashlib.sha256(leaf.read_bytes()).hexdigest()
        # Same owner can re-enable write permission and overwrite the inode.
        leaf.chmod(0o600)
        leaf.write_bytes(ALTERED)
        later = hashlib.sha256(leaf.read_bytes()).hexdigest()
        if checked == later:
            raise CTReviewRejected("late mutation fixture not observed")
        return CTPostReviewMutation(checked, later, True)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="wr-ct-host-only-") as temp:
        root = Path(temp)
        directories = [root / name for name in ("source", "review", "second")]
        for directory in directories:
            directory.mkdir(mode=0o700)
            directory.chmod(0o700)
        (directories[0] / "candidate.fake").write_bytes(ORIGINAL)
        digest = hashlib.sha256(ORIGINAL).hexdigest()
        report = two_hop_review(
            source_dir=directories[0], review_dir=directories[1],
            second_dir=directories[2], expected_sha256=digest,
            expected_size=len(ORIGINAL)
        )
        assert report.both_copies_verified_at_review
        assert not report.installation_authorized
        late = same_uid_post_review_mutation()
        assert late.later_writes_remain_possible
        assert not late.installer_byte_identity_proven
    print("PASS CT: 2 synthetic copies checked; later same-UID mutation remains possible")
    print("NO IPA, NO appinst, NO installer, NO production trust, NO iPad changes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

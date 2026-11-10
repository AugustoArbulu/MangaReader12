#!/usr/bin/env python3
"""Phase DB: explicitly disposable host POSIX cross-UID custody *negative* probe.

A separate process runs this probe as the hypothetical client UID. It tries
to change ONLY a narrowly named synthetic fixture under wr-db-fixture-*/.
The test creates all fixture files itself. This module is not a production
helper, sandbox policy, installer, network client or signed-update verifier.

Passing a Linux cross-UID permission test is NOT iOS12 separation evidence.
A client with the same UID as the helper or a privileged/root process can
mutate host files despite 0700 directories and flock.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import stat
import sys

PRIVATE = "wr-db-helper-private"
MARKER = "wr-da-check.pending"
LOCK = "wr-da-review.lock"
CREATED = "wr-db-synthetic-created.fake"


class DBFixtureRejected(ValueError):
    pass


@dataclass(frozen=True)
class DBHostProbe:
    client_euid: int
    synthetic_directory_owner_uid: int
    distinct_host_uids_observed: bool
    protected_directory_mode: str
    directory_open_denied: bool
    marker_read_denied: bool
    marker_write_denied: bool
    marker_unlink_denied: bool
    lock_unlink_denied: bool
    extra_file_create_denied: bool
    # These facts NEVER come from a simulated iOS12 runtime.
    ios12_helper_uid_isolation_proven: bool = False
    ios12_entitlements_verified: bool = False
    ancestors_owned_by_independent_service: bool = False
    storage_rollback_resistance_proven: bool = False
    editor_trust_provisioned: bool = False
    owner_install_consent_verified: bool = False
    installation_authorized: bool = False
    installation_performed: bool = False


def _fixture(folder: Path) -> os.stat_result:
    if (not isinstance(folder, Path) or not folder.is_absolute()
            or folder.name != PRIVATE
            or not folder.parent.name.startswith("wr-db-fixture-")
            or ".." in folder.parts
            or folder.is_symlink() or folder.parent.is_symlink()):
        raise DBFixtureRejected("disposable test fixture path only")
    try:
        parent_info = folder.parent.stat()
        info = folder.stat()
    except OSError as exc:
        raise DBFixtureRejected("host fixture path inaccessible") from exc
    if (not stat.S_ISDIR(info.st_mode)
            or not stat.S_ISDIR(parent_info.st_mode)
            or stat.S_IMODE(parent_info.st_mode) != 0o755
            or info.st_uid == -1):
        raise DBFixtureRejected("invalid disposable fixture metadata")
    return info


def _try_open(path: Path, flags: int) -> bool:
    fd = -1
    try:
        fd = os.open(path, flags | os.O_NOFOLLOW | os.O_CLOEXEC)
        return True
    except OSError:
        return False
    finally:
        if fd != -1:
            os.close(fd)


def _try_unlink(path: Path) -> bool:
    try:
        path.unlink()
        return True
    except OSError:
        return False


def run_host_fixture_client_probe(folder: Path) -> DBHostProbe:
    """Attempt host fixture modifications ONLY; successful calls change fixture.

    When a different UID has no access to helper-private 0700, all six
    attempts fail. For same UID or mode 0777, some succeed deliberately,
    proving that chmod alone cannot substitute for identity separation.
    """
    info = _fixture(folder)
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
        raise DBFixtureRejected("required host POSIX flags absent")
    euid = os.geteuid()
    directory_open = _try_open(folder, os.O_RDONLY | os.O_DIRECTORY)
    marker_read = _try_open(folder / MARKER, os.O_RDONLY)
    marker_write = _try_open(folder / MARKER, os.O_WRONLY)
    marker_unlink = _try_unlink(folder / MARKER)
    lock_unlink = _try_unlink(folder / LOCK)
    extra_create = _try_open(folder / CREATED, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    return DBHostProbe(
        client_euid=euid,
        synthetic_directory_owner_uid=info.st_uid,
        distinct_host_uids_observed=euid != info.st_uid,
        protected_directory_mode=oct(stat.S_IMODE(info.st_mode)),
        directory_open_denied=not directory_open,
        marker_read_denied=not marker_read,
        marker_write_denied=not marker_write,
        marker_unlink_denied=not marker_unlink,
        lock_unlink_denied=not lock_unlink,
        extra_file_create_denied=not extra_create,
    )


def main() -> int:
    if len(sys.argv) != 2:
        print("DB host-only fixture client probe requires one path", file=sys.stderr)
        return 2
    try:
        result = run_host_fixture_client_probe(Path(sys.argv[1]))
    except DBFixtureRejected as exc:
        print("DB_REJECTED: " + str(exc), file=sys.stderr)
        return 3
    print(json.dumps(asdict(result), sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

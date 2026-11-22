#!/usr/bin/env python3
"""Phase CS — source-pinned, host-only appinst copy-boundary audit.

A public upstream appinst source REFERENCE is inspected, NOT the appinst
binary installed on a particular iPad. The executable is never run.
The host simulation only shows a pathname-copy race in a controlled toy flow.
This cannot authenticate a publisher, authorize an installer, or prove
exploitation on iOS12/Chimera.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, asdict
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile

UPSTREAM_URL = (
    "https://github.com/akemin-dayo/AppSync/blob/"
    "235aca6cddfbdc9fa87fcb5b2aec2df37ed6d65a/appinst/appinst.m"
)
PINNED_REVISION = "235aca6cddfbdc9fa87fcb5b2aec2df37ed6d65a"
PINNED_BLOB_SHA1 = "be0350e637c85da70b5cb1a573780bcb0d46d534"
MAX_SOURCE_BYTES = 250_000

# These are distinct actions in the reference implementation. In particular,
# file existence and ZIP inspection happen before the *second* pathname read.
STEPS = (
    ("source_file_existence", "[fileManager fileExistsAtPath:filePath]"),
    ("zip_open_path", "zip_open(argv[1], 0, &err)"),
    ("temporary_directory_world_writable_mode", "@0777 forKey:NSFilePosixPermissions"),
    ("copy_by_mutable_path", "copyItemAtPath:filePath toPath:installPath"),
    ("install_from_copied_path",
     "installApplication:[NSURL fileURLWithPath:installPath]"),
)

GOOD = b"WEBREADER_CS_ORIGINAL_NOT_IPA\n" * 24
EVIL = b"WEBREADER_CS_REPLACEMENT_NOT_IPA\n" * 24


class SourceAuditRejected(ValueError):
    """Fail closed when reference source is unknown or incomplete."""


@dataclass(frozen=True)
class SourceReferenceObservation:
    reference_revision: str
    source_blob_sha1: str
    source_matches_pinned_public_reference: bool
    sequential_path_based_reopen_observed: bool
    temporary_copy_by_path_observed: bool
    temp_directory_mode_0777_requested: bool
    exact_installed_appinst_binary_identified: bool = False
    ios12_runtime_verified: bool = False
    installer_consumes_verified_same_fd: bool = False
    immutable_installer_bytes_proven: bool = False
    publisher_authenticated: bool = False
    user_consent_verified: bool = False
    installation_authorized: bool = False
    installation_performed: bool = False


@dataclass(frozen=True)
class HostPathSwapObservation:
    checked_original_sha256: str
    final_named_source_sha256: str
    copied_file_sha256: str
    simulated_pathname_race_observed: bool
    source_code_executed_on_device: bool = False
    appinst_executed: bool = False
    ios12_runtime_verified: bool = False
    installation_authorized: bool = False
    installation_performed: bool = False


def git_blob_sha1(content: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(content)).encode("ascii") + b"\0" + content
    ).hexdigest()


def identify_reference_steps(content: str) -> tuple[str, ...]:
    """Ordered SOURCE-EVIDENCE parser, not an installation safety validator."""
    if type(content) is not str:
        raise SourceAuditRejected("source text required")
    last_position = -1
    found = []
    for name, marker in STEPS:
        position = content.find(marker, last_position + 1)
        if position < 0:
            raise SourceAuditRejected("missing/out-of-order reference step: " + name)
        found.append(name)
        last_position = position
    return tuple(found)


def audit_pinned_reference(raw: bytes) -> SourceReferenceObservation:
    """Only accepts the exact known upstream reference blob."""
    if (type(raw) is not bytes or not 1024 <= len(raw) <= MAX_SOURCE_BYTES
            or git_blob_sha1(raw) != PINNED_BLOB_SHA1):
        raise SourceAuditRejected("unknown upstream source: no device claim may be made")
    try:
        content = raw.decode("utf-8")
    except UnicodeError as exc:
        raise SourceAuditRejected("non UTF-8 reference source") from exc
    identify_reference_steps(content)
    return SourceReferenceObservation(
        reference_revision=PINNED_REVISION,
        source_blob_sha1=PINNED_BLOB_SHA1,
        source_matches_pinned_public_reference=True,
        sequential_path_based_reopen_observed=True,
        temporary_copy_by_path_observed=True,
        temp_directory_mode_0777_requested=True,
    )


def simulate_host_pathname_replacement() -> HostPathSwapObservation:
    """Demonstrate the boundary with fake bytes; does not execute appinst."""
    with tempfile.TemporaryDirectory(prefix="wr-cs-fake-path-") as temp:
        root = Path(temp)
        original_path = root / "candidate.NOT_AN_IPA"
        previously_checked = root / "earlier.NOT_AN_IPA"
        copied_path = root / "temporary-copy.NOT_AN_IPA"
        original_path.write_bytes(GOOD)

        # Source review opens, reads, and closes a descriptor.
        fd = os.open(original_path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise SourceAuditRejected("nonregular host fixture")
            h = hashlib.sha256()
            while True:
                chunk = os.read(fd, 65536)
                if not chunk:
                    break
                h.update(chunk)
            reviewed = h.hexdigest()
        finally:
            os.close(fd)
        if reviewed != hashlib.sha256(GOOD).hexdigest():
            raise SourceAuditRejected("fake initial source digest invalid")

        # Attacker controls only the filename in this toy model.
        original_path.rename(previously_checked)
        original_path.write_bytes(EVIL)
        # This second pathname open is precisely the boundary at issue.
        shutil.copyfile(original_path, copied_path)
        named = hashlib.sha256(original_path.read_bytes()).hexdigest()
        copied = hashlib.sha256(copied_path.read_bytes()).hexdigest()
        if copied == reviewed or copied != named:
            raise SourceAuditRejected("host replacement not observed")
        return HostPathSwapObservation(reviewed, named, copied, True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True,
                        help="locally fetched pinned upstream appinst.m, read only")
    args = parser.parse_args()
    source = args.source
    if not source.is_file() or source.is_symlink():
        raise SystemExit("REFUSED: source must be a normal local file")
    if source.stat().st_size > MAX_SOURCE_BYTES:
        raise SystemExit("REFUSED: source too large")
    try:
        evidence = audit_pinned_reference(source.read_bytes())
        swap = simulate_host_pathname_replacement()
    except SourceAuditRejected as exc:
        raise SystemExit("REFUSED: " + str(exc)) from exc
    print(json.dumps({
        "phase": "CS", "reference": asdict(evidence),
        "hostOnlySimulation": asdict(swap),
        "decision": "UNSAFE_TO_INFER_FD_BOUND_APPINST_INSTALL",
        "ownerDataTouched": False,
        "newIPAOrDebCreated": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

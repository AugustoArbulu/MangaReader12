#!/usr/bin/env python3
"""Compare a reported on-device appinst binary SHA-256 to a local DEB payload.

Read-only, offline, host-side only. Does not connect to the iPhone, export its
binary, run appinst, install DEBs/IPAs, or claim original publisher provenance.
A user-supplied SHA-256 is NOT a cryptographic attestation of the device.
"""
import argparse
import hashlib
import hmac
import json
from pathlib import Path
import re

from audit_appinst_deb import PackageRejected, audit_file


class FingerprintRejected(ValueError):
    """Malformed or unusable fingerprint input."""


def compare_fingerprint(audit: dict, installed_sha256: str) -> dict:
    if not isinstance(installed_sha256, str) or not re.fullmatch(
        r"[0-9a-fA-F]{64}", installed_sha256
    ):
        raise FingerprintRejected("expected exactly 64 hexadecimal SHA-256 digits")
    expected = audit.get("appinst_executable_sha256")
    if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise FingerprintRejected("archive has no audited executable fingerprint")
    actual = installed_sha256.lower()
    matched = hmac.compare_digest(expected, actual)
    return {
        "package": audit.get("package"),
        "package_version": audit.get("version"),
        "architecture": audit.get("architecture"),
        "package_sha256": audit.get("sha256"),
        "package_executable_sha256": expected,
        "reported_device_executable_sha256": actual,
        "reported_device_matches_supplied_deb_payload": matched,
        "device_binary_independently_attested": False,
        "original_publisher_provenance_verified": False,
        "privileged_installer_authorized": False,
        "installer_executed": False,
        "notice": (
            "Digest equality is only a byte identity check against the supplied "
            "DEB. It cannot authenticate an untrusted mirror, confirm that the "
            "reported hash came from the actual device, or authorize installation."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("deb", type=Path, help="Locally supplied .deb; not downloaded")
    parser.add_argument(
        "--installed-sha256", required=True,
        help="Read-only SHA-256 of /usr/bin/appinst reported from the iPhone"
    )
    args = parser.parse_args()
    try:
        report = compare_fingerprint(audit_file(args.deb), args.installed_sha256)
    except (PackageRejected, FingerprintRejected) as error:
        parser.error(str(error))
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if not report["reported_device_matches_supplied_deb_payload"]:
        raise SystemExit(2)
    # Exit 0 means only the supplied fingerprints match, NOT safe to install.


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Build66 Phase J: offline ONLY signed-release-to-manual-review handoff.

A successful signed manifest/IPA binding may help the user verify a file before
a MANUAL Filza installation. It does not connect to a jailbreak bridge or
execute appinst. The publisher's SPKI pin must be independently provisioned;
we do NOT derive it from release contents or put it in the iOS app.

This module is host-only. It never downloads, changes app state, opens sockets,
sends email, prints private paths, or invokes installer/privileged commands.
The release key is deliberately absent from production.
"""
from dataclasses import dataclass
from pathlib import Path
import re

from build66_release_key_pinning_gate import (
    ReleaseKeyUntrusted, verify_independently_pinned_v2
)

HEX = re.compile(r"[a-f0-9]{64}\Z")
NAME = re.compile(r"WebReader-Build([1-9][0-9]{0,8})-iOS12-adhoc\.ipa\Z")
MAX_BUILD = 2_147_483_647


class ManualReleaseRejected(ValueError):
    pass


@dataclass(frozen=True)
class ManualReviewReceipt:
    build: int
    asset_name: str
    expected_sha256: str
    independent_key_pin_match: bool = True
    signed_manifest_and_ipa_match: bool = True
    # This operation does not run native codesign or inspect the user's iPad.
    native_codesign_verified: bool = False
    publisher_authenticated_on_device: bool = False
    installed_app_identity_verified: bool = False
    user_approved_manual_install: bool = False
    installation_authorized: bool = False
    installation_performed: bool = False
    manual_rehash_required_after_transfer: bool = True
    user_should_keep_existing_app_and_data: bool = True
    # No user-specific path or untrusted release note is included in the
    # receipt that may be displayed or copied elsewhere.


def prepare_manual_review(envelope_json, public_pem, trusted_spki_sha256,
                          staged_ipa_path, *, installed_build=65):
    """Build a non-authorizing receipt from a host-selected signed v2 release.

    This function is NOT allowed to invoke install even if the user manually
    decides to proceed. A separate Filza action remains a user-controlled step.
    """
    if (type(installed_build) is not int or
            not 0 < installed_build < MAX_BUILD):
        raise ManualReleaseRejected("invalid installed build")
    if not isinstance(staged_ipa_path, (Path, str)):
        raise ManualReleaseRejected("invalid host-selected path")
    staged_path = Path(staged_ipa_path)
    # The local filename is not a trust anchor. This restriction is only a
    # conservative UI/QA check against wrong or ambiguous distribution naming.
    matched = NAME.fullmatch(staged_path.name)
    if not matched:
        raise ManualReleaseRejected("unexpected local artifact naming convention")
    name_build = int(matched.group(1))
    if name_build <= installed_build or name_build > MAX_BUILD:
        raise ManualReleaseRejected("wrong artifact build or downgrade")
    try:
        result = verify_independently_pinned_v2(
            envelope_json, public_pem, trusted_spki_sha256,
            staged_path, installed_build=installed_build
        )
    except (ReleaseKeyUntrusted, OSError, ValueError) as exc:
        raise ManualReleaseRejected("release or independently pinned key rejected") from exc
    if (result.get("build") != name_build or
            not result.get("signed_manifest_and_ipa_match") or
            not result.get("pinned_spki_fingerprint_match") or
            result.get("native_codesign_verified") is not False or
            result.get("installation_authorized") is not False or
            result.get("installation_performed") is not False):
        raise ManualReleaseRejected("unexpected host preflight security result")
    digest = result.get("ipa_sha256")
    if type(digest) is not str or HEX.fullmatch(digest) is None:
        raise ManualReleaseRejected("invalid verified digest")
    return ManualReviewReceipt(
        build=name_build, asset_name=staged_path.name,
        expected_sha256=digest
    )

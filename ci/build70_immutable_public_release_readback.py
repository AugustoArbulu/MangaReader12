#!/usr/bin/env python3
"""Phase CI: OFFLINE immutable public Release readback gate — NO publication.

The *supplied* copies of source signed IPA, independently downloaded public
IPA, signed v2 production manifest, published manifest, public owner key/pin,
and GitHub Release REST JSON must all agree. Requires native Apple codesign
preflight on macOS. A supplied JSON snapshot is NOT proof of actual GitHub
availability, identity, or owner publication consent.

No network, authentication tokens, write actions, appinst, private keys,
installer capability, releases, or main-branch changes.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import stat

from build69_production_release_preflight import (
    ProductionPreflightRejected, review_production_release, _read_external_regular
)
from webreader_update_manifest import ManifestRejected, validate

REPO = Path(__file__).resolve().parent.parent.resolve()
MANIFEST_NAME = "channel-production-v2.json"
MAX_API_JSON = 2 * 1024 * 1024


class PublicReadbackRejected(ValueError):
    pass


def _no_duplicate_json_keys(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise PublicReadbackRejected("duplicate REST JSON field")
        out[key] = value
    return out


def _public_snapshot(body: bytes, *, signed: dict) -> dict:
    if type(body) is not bytes or not 2 <= len(body) <= MAX_API_JSON:
        raise PublicReadbackRejected("missing or oversized GitHub Release response")
    try:
        release = json.loads(body.decode("utf-8"),
                             object_pairs_hook=_no_duplicate_json_keys)
    except (UnicodeError, ValueError, TypeError) as exc:
        raise PublicReadbackRejected("invalid GitHub Release response") from exc
    if type(release) is not dict:
        raise PublicReadbackRejected("GitHub release response is not an object")

    build = signed["build"]
    if (release.get("tag_name") != "build" + str(build)
            or release.get("html_url") !=
            "https://github.com/AugustoArbulu/MangaReader12/releases/tag/build" + str(build)
            or release.get("draft") is not False
            or release.get("prerelease") is not False
            or release.get("immutable") is not True):
        raise PublicReadbackRejected(
            "release tag, public state or immutable-protection policy denied"
        )
    published_at = release.get("published_at")
    if type(published_at) is not str or len(published_at) != 20:
        raise PublicReadbackRejected("missing release publication timestamp")
    try:
        datetime.strptime(published_at, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise PublicReadbackRejected("invalid release publication timestamp") from exc
    assets = release.get("assets")
    if not isinstance(assets, list) or len(assets) > 64:
        raise PublicReadbackRejected("missing or excessive release assets")

    expected_name = "WebReader-Build" + str(build) + "-iOS12-adhoc.ipa"
    matches = [x for x in assets if type(x) is dict and
               x.get("name") == expected_name]
    if len(matches) != 1:
        raise PublicReadbackRejected("release must expose one exact IPA asset")
    item = matches[0]
    if (item.get("state") != "uploaded" or
            type(item.get("size")) is not int or
            item["size"] != signed["ipaSize"] or
            item.get("digest") != "sha256:" + signed["sha256"] or
            item.get("browser_download_url") != signed["ipaUrl"] or
            item.get("content_type") not in (
                "application/octet-stream", "application/zip",
                "application/x-zip-compressed"
            )):
        raise PublicReadbackRejected(
            "GitHub asset URL, SHA-256, size, content type or upload state denied"
        )
    return {"tag": release["tag_name"], "immutable": True,
            "assetName": expected_name, "assetDigestMatched": True,
            "publicReleaseTimestamp": published_at}


def _file_identity(path: Path) -> tuple[int, int]:
    path = Path(path)
    if path.is_symlink():
        raise PublicReadbackRejected("symlinked IPA is forbidden")
    if path.resolve() == REPO or REPO in path.resolve().parents:
        raise PublicReadbackRejected("IPA files must be external to repository")
    st = path.stat()
    if not stat.S_ISREG(st.st_mode) or st.st_size <= 0:
        raise PublicReadbackRejected("regular IPA file required")
    return st.st_dev, st.st_ino


def review_public_readback(
    *, owner_public_pem: bytes, independent_pin: str,
    private_manifest: bytes, published_manifest: bytes,
    local_ipa: Path, readback_ipa: Path,
    release_rest_json: bytes, installed_build: int = 70
) -> dict:
    """Reject unless BOTH independently supplied IPA copies match v2 + seal.

    A positive receipt reflects consistency of *provided local files* only.
    It is NOT network proof nor a sufficient authorization to publish/install.
    """
    if type(installed_build) is not int or installed_build < 69:
        raise PublicReadbackRejected("Build69+ baseline mandatory; Build70 lab uses pre-upgrade Build69")
    if type(private_manifest) is not bytes or type(published_manifest) is not bytes:
        raise PublicReadbackRejected("exact manifest bytes required")
    if not private_manifest or private_manifest != published_manifest:
        raise PublicReadbackRejected("public channel differs from owner signed bytes")
    if _file_identity(local_ipa) == _file_identity(readback_ipa):
        raise PublicReadbackRejected(
            "release readback requires a distinct downloaded file, not source alias"
        )
    try:
        claims = validate(
            private_manifest, owner_public_pem,
            installed_build=installed_build, installed_ios="12.5.8",
            expected_channel="production"
        )
    except ManifestRejected as exc:
        raise PublicReadbackRejected("signed production manifest denied") from exc
    api = _public_snapshot(release_rest_json, signed=claims)
    try:
        approved = review_production_release(
            public_key_pem=owner_public_pem,
            independent_spki_sha256=independent_pin,
            manifest_v2=private_manifest,
            ipa_path=Path(local_ipa), installed_build=installed_build
        )
        downloaded = review_production_release(
            public_key_pem=owner_public_pem,
            independent_spki_sha256=independent_pin,
            manifest_v2=published_manifest,
            ipa_path=Path(readback_ipa), installed_build=installed_build
        )
    except (ProductionPreflightRejected, OSError) as exc:
        raise PublicReadbackRejected(
            "local or public-readback IPA signed code seal denied"
        ) from exc
    if (approved["ipaSHA256"] != claims["sha256"] or
            downloaded["ipaSHA256"] != approved["ipaSHA256"] or
            downloaded["ipaSize"] != approved["ipaSize"] or
            approved["releaseURL"] != claims["ipaUrl"] or
            downloaded["releaseURL"] != claims["ipaUrl"] or
            approved["publicSPKISHA256"] != independent_pin or
            downloaded["publicSPKISHA256"] != independent_pin or
            not approved["nativeCodeSealVerified"] or
            not downloaded["nativeCodeSealVerified"]):
        raise PublicReadbackRejected("signed manifest and downloaded IPA diverge")

    return {
        "schema": "WebReader-CI-Immutable-Release-Readback-v1",
        "state": "offline_supplied_files_consistent",
        "build": claims["build"],
        "installedBuildReviewed": installed_build,
        "assetName": api["assetName"],
        "releaseTag": api["tag"],
        "releaseImmutableFlagMatched": True,
        "assetAPISHA256MatchedSignedPayload": True,
        "readbackByteDigestMatched": True,
        "sourceAndReadbackNativeCodeSealsVerified": True,
        "manifestSHA256": hashlib.sha256(private_manifest).hexdigest(),
        "ipaSHA256": approved["ipaSHA256"],
        "ipaSize": approved["ipaSize"],
        "publicSPKISHA256": independent_pin,
        "releaseURL": claims["ipaUrl"],
        "publicationHappenedInThisTool": False,
        "githubAPILiveVerifiedByThisTool": False,
        "publicDownloadOriginAuthenticatedByThisTool": False,
        "ownerPublicationApprovalRecordedByThisTool": False,
        "publicRootProvisionedOnInstalledIPadByThisTool": False,
        "productionChannelActivatedByThisTool": False,
        "automaticInstallationAuthorized": False,
        "installationPerformed": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner-public-key", type=Path, required=True)
    parser.add_argument("--independent-spki-sha256", required=True)
    parser.add_argument("--signed-manifest", type=Path, required=True)
    parser.add_argument("--public-manifest", type=Path, required=True)
    parser.add_argument("--source-ipa", type=Path, required=True)
    parser.add_argument("--readback-ipa", type=Path, required=True)
    parser.add_argument("--release-rest-json", type=Path, required=True)
    parser.add_argument("--installed-build", type=int, default=70)
    args = parser.parse_args()
    try:
        report = review_public_readback(
            owner_public_pem=_read_external_regular(args.owner_public_key, 4096),
            independent_pin=args.independent_spki_sha256,
            private_manifest=_read_external_regular(args.signed_manifest, 64 * 1024),
            published_manifest=_read_external_regular(args.public_manifest, 64 * 1024),
            local_ipa=args.source_ipa, readback_ipa=args.readback_ipa,
            release_rest_json=_read_external_regular(args.release_rest_json, MAX_API_JSON),
            installed_build=args.installed_build
        )
    except ProductionPreflightRejected as exc:
        raise SystemExit("BLOCKED: unsafe external input") from exc
    print(json.dumps(report, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()

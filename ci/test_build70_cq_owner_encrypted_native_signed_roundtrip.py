#!/usr/bin/env python3
"""CQ: macOS-only end-to-end encrypted owner signer -> native WebReader readback.

Build an iOS12 ARM64 Mach-O *synthetic fixture*, sign it ad hoc, and package
a disposable fake WebReader IPA in a temporary OUT-OF-REPO directory.
Then sign a production-v2 manifest using a new EPHEMERAL encrypted P256 key,
cross-check with the existing macOS-native code-seal preflight and with real
Swift Security.framework + exact-descriptor ZIP verifier.

Important: the fixture executable is NOT WebReader application code.
It is a signature-protocol interoperability test, NEVER a shippable IPA.
NO owner production key, private key artifact, installation, appinst, network,
release, GitHub output or changes to main.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile

from cryptography.hazmat.primitives import serialization

from build68_release_public_key_handoff import prepare_public_key_handoff
from build69_production_release_preflight import (
    ProductionPreflightRejected, review_production_release
)
from webreader_owner_key_ceremony import (
    create_owner_identity, PRIVATE_NAME, PUBLIC_NAME, FINGERPRINT_NAME
)
from webreader_owner_offline_v2_signer import (
    OwnerManifestRejected, sign_owner_candidate
)
from webreader_update_manifest import ManifestRejected, validate

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "MangaReader12/Core"
SOURCES = [
    CORE / "WebReaderStrictJSON.swift",
    CORE / "WebReaderUpdateManifestVerifier.swift",
    CORE / "WebReaderSignedReleaseTrustGate.swift",
    CORE / "WebReaderNativeIPAAuditor.swift",
    CORE / "WebReaderSignedIPAReview.swift",
]
FIXTURE_BUILD = 71
IPA_NAME = "WebReader-Build71-iOS12-adhoc.ipa"
FAKE_NOT_WEBREADER_MESSAGE = "SYNTHETIC_CQ_FIXTURE_NOT_A_DISTRIBUTABLE_APP"

SWIFT = r'''
import Foundation

func ensure(_ yes: @autoclosure () -> Bool, _ why: String) {
    if !yes() { fatalError(why) }
}
func expectReject(_ description: String, _ f: () throws -> Void) {
    do { try f(); fatalError("unexpectedly accepted " + description) }
    catch is WebReaderSignedReleaseTrustError { }
    catch is WebReaderUpdateValidationError { }
    catch is WebReaderIPAAuditError { }
    catch is WebReaderSignedIPAReviewError { }
    catch { fatalError("unexpected error for " + description + ": " + String(describing: error)) }
}
let args = CommandLine.arguments
ensure(args.count == 7, "manifest x963 pin validIPA modifiedIPA modifiedManifest")
let envelope = try! Data(contentsOf: URL(fileURLWithPath: args[1]))
let pub = try! Data(contentsOf: URL(fileURLWithPath: args[2]))
let pin = args[3]
let file = URL(fileURLWithPath: args[4])
let alteredIPA = URL(fileURLWithPath: args[5])
let alteredEnvelope = try! Data(contentsOf: URL(fileURLWithPath: args[6]))
let ios = OperatingSystemVersion(majorVersion: 12, minorVersion: 5, patchVersion: 8)
func audit(
    _ manifest: Data, _ archive: URL, _ fingerprint: String? = pin,
    _ baseline: Int = 70, _ channel: String = "production"
) throws -> WebReaderSignedIPAReviewResult {
    return try WebReaderSignedIPAReview.inspectReadOnly(
        envelopeData: manifest, independentlyTrustedPublicKeyX963: pub,
        independentlyTrustedSPKISHA256: fingerprint,
        localIPAURL: archive, installedBuild: baseline,
        installedIOS: ios, expectedChannel: channel
    )
}
let good = try! audit(envelope, file)
ensure(good.build == 71, "synthetic Build71 signed metadata")
ensure(good.bundleID == "com.example.MangaReader12", "fixed bundle")
ensure(good.signedSHA256 == good.observedSHA256, "same IPA byte digest")
ensure(good.signedSPKISHA256 == pin, "SPKI independent test pin")
ensure(good.signedManifestChecked && good.localZIPAndDigestChecked, "both checks executed")
ensure(!good.nativeExecutableSignatureChecked && !good.fileLockedForLaterUse
       && !good.publisherIdentityProvenByDevice && !good.peerAuthenticated
       && !good.consentForInstallVerified && !good.installationAuthorized
       && !good.installationPerformed, "read-only result always negative")
expectReject("missing pin") { _ = try audit(envelope, file, nil) }
expectReject("wrong pin") { _ = try audit(envelope, file, String(repeating: "0", count: 64)) }
expectReject("downgrade") { _ = try audit(envelope, file, pin, 71) }
expectReject("wrong channel") { _ = try audit(envelope, file, pin, 70, "development") }
expectReject("changed file") { _ = try audit(envelope, alteredIPA) }
expectReject("forged signature") { _ = try audit(alteredEnvelope, file) }
print("PASS CQ: encrypted temporary owner key -> signed production v2 -> Swift Security.framework -> same-FD IPA hash/ZIP; all unsafe paths rejected; NO install")
'''


def run(*args, timeout=90):
    proc = subprocess.run([str(x) for x in args],
                          capture_output=True, text=True,
                          timeout=timeout, check=False)
    if proc.returncode != 0:
        raise RuntimeError(
            "CQ command rejected: " + str(args[0]) + " -> "
            + proc.stdout[-1400:] + proc.stderr[-1400:]
        )
    return proc


def make_fake_native_signed_ipa(root: Path) -> Path:
    if sys.platform != "darwin":
        raise RuntimeError("CQ synthetic codesigning must run only on macOS")
    app = root / "Payload" / "MangaReader12.app"
    app.mkdir(parents=True, exist_ok=False)
    (root / "main.c").write_text(
        'int main(void) { return 0; } /* CQ SYNTHETIC TEST ONLY */\n',
        encoding="ascii"
    )
    executable = app / "MangaReader12"
    run("xcrun", "--sdk", "iphoneos", "clang", "-std=c11", "-Os",
        "-Wall", "-Werror", "-arch", "arm64",
        "-miphoneos-version-min=12.0", root / "main.c",
        "-o", executable)
    info = {
        "CFBundleIdentifier": "com.example.MangaReader12",
        "CFBundleExecutable": "MangaReader12",
        "CFBundleDisplayName": "WebReader",
        "CFBundleName": "WebReader",
        "CFBundleVersion": str(FIXTURE_BUILD),
        "CFBundleShortVersionString": "0.0",
        "CFBundlePackageType": "APPL",
        "MinimumOSVersion": "12.0",
    }
    (app / "Info.plist").write_bytes(plistlib.dumps(info))
    entitlements = root / "owner-fixture-entitlements.plist"
    entitlements.write_bytes(plistlib.dumps({
        "application-identifier":
        "AR5SFJC432.com.example.MangaReader12.AR5SFJC432"
    }))
    run("codesign", "--force", "--sign", "-", "--timestamp=none",
        "--entitlements", entitlements, app)
    run("codesign", "--verify", "--verbose=2", app)
    ipa = root / IPA_NAME
    # No lazy ZIP re-compression of code signature resources; exact archive
    # is bound by the v2 manifest and validated before codesign extraction.
    with zipfile.ZipFile(ipa, "x", compression=zipfile.ZIP_STORED) as out:
        for item in (root / "Payload").rglob("*"):
            if item.is_file():
                out.write(item, arcname=item.relative_to(root).as_posix())
    if len(ipa.read_bytes()) < 1500:
        raise RuntimeError("unexpectedly small synthetic native fixture")
    return ipa


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--verify-fixture-only", action="store_true",
                   help="never produce a release; this is already the sole behavior")
    opts = p.parse_args()
    if sys.platform != "darwin":
        raise SystemExit("CQ requires macOS, native codesign and Swift")
    with tempfile.TemporaryDirectory(
        prefix="wr-cq-synthetic-not-release-",
        dir=Path(tempfile.gettempdir()).resolve(strict=True)
    ) as tmp:
        directory = Path(tmp)
        secret_dir = directory / "throwaway-owner-identity"
        secret_dir.mkdir(mode=0o700)
        secret_dir.chmod(0o700)
        password = "cq-temporary-test-only-never-a-production-password"
        identity = create_owner_identity(
            output_directory=secret_dir, passphrase=password
        )
        ipa = make_fake_native_signed_ipa(directory)
        notes = directory / "test-only-notes.json"
        notes.write_text(json.dumps(["CQ disposable synthetic iOS12 fixture"]))
        envelope = directory / "channel-production-v2.json"
        receipt = sign_owner_candidate(
            owner_directory=secret_dir, ipa_path=ipa, notes_path=notes,
            output=envelope, passphrase=password,
            independent_spki_sha256=identity.public_spki_sha256,
            published_at="2026-11-11T12:00:00Z", installed_build=70
        )
        if not (receipt["build"] == 71
                and receipt["nativeAppleIPACodeSealVerifiedByTool"] is False
                and receipt["installationAuthorized"] is False):
            raise RuntimeError("owner signer promoted false authority")
        public = (secret_dir / PUBLIC_NAME).read_bytes()
        pin = identity.public_spki_sha256
        assert (secret_dir / FINGERPRINT_NAME).read_text().strip() == pin
        handoff = prepare_public_key_handoff(public, pin)
        verified = validate(envelope.read_bytes(), public, installed_build=70,
                            installed_ios="12.5.8", expected_channel="production")
        if verified["build"] != 71 or verified["sha256"] != receipt["ipaSHA256"]:
            raise RuntimeError("manifest signed facts diverge from source IPA")
        # This separate gate makes its own native codesign / entitlement
        # validation on the same signed metadata and IPA snapshot.
        reviewed = review_production_release(
            public_key_pem=public,
            independent_spki_sha256=pin,
            manifest_v2=envelope.read_bytes(),
            ipa_path=ipa, installed_build=70
        )
        if (not reviewed["nativeCodeSealVerified"]
                or reviewed["ipaSHA256"] != receipt["ipaSHA256"]
                or reviewed["build"] != 71
                or reviewed["installationAuthorized"] is not False
                or reviewed["githubReleasePublished"] is not False):
            raise RuntimeError("native macOS production preflight rejected")
        print("PASS CQ: macOS native ad-hoc seal + installed application-identifier + encrypted temporary owner manifest, all read-only")

        # Mutation must cause rejection even if the signing key itself is valid.
        modified_ipa = directory / "tampered.ipa"
        payload = bytearray(ipa.read_bytes())
        payload[16] ^= 1
        modified_ipa.write_bytes(payload)
        try:
            review_production_release(
                public_key_pem=public,
                independent_spki_sha256=pin,
                manifest_v2=envelope.read_bytes(),
                ipa_path=modified_ipa, installed_build=70
            )
        except ProductionPreflightRejected:
            pass
        else:
            raise RuntimeError("macOS native reviewer accepted changed IPA")

        altered = json.loads(envelope.read_bytes())
        signature = bytearray(base64.b64decode(altered["signature"]))
        signature[len(signature)//2] ^= 1
        altered["signature"] = base64.b64encode(signature).decode()
        bad_envelope = directory / "altered-manifest.json"
        bad_envelope.write_text(json.dumps(altered, separators=(",", ":")))
        point = directory / "synthetic-public-X963.bin"
        point.write_bytes(bytes.fromhex(handoff.x963_public_key_hex))
        swift_main = directory / "main.swift"
        swift_main.write_text(SWIFT)
        native_binary = directory / "cq-native-review"
        run("swiftc", "-swift-version", "5", *SOURCES, swift_main,
            "-framework", "Security", "-o", native_binary,
            timeout=180)
        swift_result = run(native_binary, envelope, point, pin, ipa,
                           modified_ipa, bad_envelope, timeout=45)
        print(swift_result.stdout.strip())
        print("PASS CQ: real native Swift signature and ZIP checks use owner-encrypted synthetic manifest")
        print("NO production owner key / NO real WebReader IPA / NO release / NO install / NO appinst")


if __name__ == "__main__":
    main()

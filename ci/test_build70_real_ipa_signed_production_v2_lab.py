#!/usr/bin/env python3
"""Phase CE: native signed production-v2 metadata + REAL Build70 QA IPA audit.

This is a disposable lab, NOT the production WebReader updater:
- Opens a downloaded and externally checksum-checked Build70 QA IPA.
- Generates a throwaway P-256 key in a temp directory outside the repo.
- Uses this key to sign a fake production-channel v2 manifest referencing
  exactly the same IPA digest/size. NOTHING is published or provisioned.
- Rechecks with real iOS12 Swift Security.framework + same-FD ZIP auditor.
- Exercises wrong channel, pin, SHA, replay build, link, and altered signature.
- NO installation, appinst, permanent signing key, token export or Release.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tempfile
import zipfile

from build70_immutable_public_release_readback import review_public_readback
from build68_release_public_key_handoff import prepare_public_key_handoff
from build66_release_key_pinning_gate import public_key_spki_sha256
from build70_private_qa_ipa_preflight import preflight_private_qa_ipa
from prepare_signed_webreader_update import prepare
from webreader_update_manifest import validate

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "MangaReader12/Core"
SOURCES = [
    CORE / "WebReaderStrictJSON.swift",
    CORE / "WebReaderUpdateManifestVerifier.swift",
    CORE / "WebReaderSignedReleaseTrustGate.swift",
    CORE / "WebReaderNativeIPAAuditor.swift",
    CORE / "WebReaderSignedIPAReview.swift",
]
IPA_NAME = "WebReader-Build70-iOS12-adhoc.ipa"
CHECKSUM_NAME = IPA_NAME + ".sha256"

SWIFT = r'''
import Foundation

func ensure(_ condition: @autoclosure () -> Bool, _ reason: String) {
    if !condition() { fatalError(reason) }
}
func reject(_ reason: String, _ block: () throws -> Void) {
    do {
        try block()
        fatalError("unexpectedly accepted: " + reason)
    } catch is WebReaderSignedReleaseTrustError {
    } catch is WebReaderUpdateValidationError {
    } catch is WebReaderIPAAuditError {
    } catch is WebReaderSignedIPAReviewError {
    } catch {
        fatalError("wrong rejection category " + reason + ": " + String(describing: error))
    }
}
let args = CommandLine.arguments
ensure(args.count == 7, "manifest publicX963 pin IPA changedIPA alteredManifest")
let manifest = try! Data(contentsOf: URL(fileURLWithPath: args[1]))
let x963 = Data(try! Data(contentsOf: URL(fileURLWithPath: args[2])))
let pin = args[3]
let ipa = URL(fileURLWithPath: args[4])
let changed = URL(fileURLWithPath: args[5])
let alteredManifest = try! Data(contentsOf: URL(fileURLWithPath: args[6]))
let ios = OperatingSystemVersion(majorVersion: 12, minorVersion: 5, patchVersion: 8)
func inspect(
    _ envelope: Data, _ file: URL,
    _ expectedPin: String? = pin,
    _ channel: String = "production",
    _ installedBuild: Int = 69
) throws -> WebReaderSignedIPAReviewResult {
    return try WebReaderSignedIPAReview.inspectReadOnly(
        envelopeData: envelope,
        independentlyTrustedPublicKeyX963: x963,
        independentlyTrustedSPKISHA256: expectedPin,
        localIPAURL: file,
        installedBuild: installedBuild, installedIOS: ios,
        expectedChannel: channel
    )
}
let ok = try! inspect(manifest, ipa)
ensure(ok.build == 70 && ok.bundleID == "com.example.MangaReader12",
       "production signed metadata bound to Build70 application")
ensure(ok.minimumIOS == "12.0", "iOS12 minimum validated")
ensure(ok.signedSHA256 == ok.observedSHA256,
       "verified signed digest equals actual IPA bytes")
ensure(ok.signedSPKISHA256 == pin && ok.zipEntries >= 4,
       "independent key pin and ZIP checks verified")
ensure(ok.signedManifestChecked && ok.localZIPAndDigestChecked,
       "both native independent read-only checks complete")
ensure(!ok.nativeExecutableSignatureChecked && !ok.fileLockedForLaterUse,
       "no claim of a native executable seal or immutable installation handle")
ensure(!ok.publisherIdentityProvenByDevice && !ok.peerAuthenticated &&
       !ok.consentForInstallVerified && !ok.installationAuthorized &&
       !ok.installationPerformed, "no production authority derived from lab")

reject("default dev channel cannot accept production manifest") {
    _ = try WebReaderSignedIPAReview.inspectReadOnly(
        envelopeData: manifest, independentlyTrustedPublicKeyX963: x963,
        independentlyTrustedSPKISHA256: pin,
        localIPAURL: ipa, installedBuild: 69, installedIOS: ios
    )
}
reject("explicit dev channel cannot accept production manifest") {
    _ = try inspect(manifest, ipa, pin, "development")
}
reject("invalid channel never downgrades") {
    _ = try inspect(manifest, ipa, pin, "testing")
}
reject("wrong key fingerprint") {
    _ = try inspect(manifest, ipa, String(repeating: "f", count: 64))
}
reject("missing independently verified fingerprint") {
    _ = try inspect(manifest, ipa, nil)
}
reject("same or newer installed build") {
    _ = try inspect(manifest, ipa, pin, "production", 70)
}
reject("tampered ECDSA manifest signature") {
    _ = try inspect(alteredManifest, ipa)
}
reject("mutated downloaded IPA") {
    _ = try inspect(manifest, changed)
}
let symlink = URL(fileURLWithPath: args[4] + ".symlink")
reject("symlinked IPA") {
    _ = try inspect(manifest, symlink)
}
print("PASS CE: authentic native production-v2 signed envelope and REAL Build70 QA IPA same-FD audit; all negatives denied; NO install")
'''


def _run(args, **kwargs):
    return subprocess.run(
        args, check=True, capture_output=True, timeout=180, **kwargs
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ipa", type=Path, required=True)
    ap.add_argument("--checksum", type=Path, required=True)
    args = ap.parse_args()
    if sys.platform != "darwin":
        raise SystemExit("macOS native Security.framework is mandatory")
    if args.ipa.name != IPA_NAME or args.ipa.is_symlink():
        raise SystemExit("real Build70 IPA file required")
    expected = args.checksum.read_bytes()
    qa = preflight_private_qa_ipa(
        args.ipa, checksum_data=expected, baseline=69
    )
    if (qa["ipaSHA256"] != hashlib.sha256(args.ipa.read_bytes()).hexdigest()
            or qa["build"] != 70
            or qa["installedBuildBaseline"] != 69
            or qa["adHocSignatureIntegrityVerified"] is not True
            or qa["installedApplicationIdentifierMatch"] is not True):
        raise SystemExit("real Build70 IPA failed native QA preflight")

    with tempfile.TemporaryDirectory(prefix="wr70-real-signed-v2-lab-") as tmp:
        directory = Path(tmp)
        private = directory / "throwaway-private-p256.pem"
        public = directory / "throwaway-public-p256.pem"
        notes = directory / "test-notes.json"
        signed = directory / "test-production-v2-envelope.json"
        notes.write_text(json.dumps(["Ephemeral owner-key fixture; no publication"]))
        _run(["openssl", "ecparam", "-name", "prime256v1",
              "-genkey", "-noout", "-out", str(private)])
        private.chmod(0o600)
        _run(["openssl", "pkey", "-in", str(private),
              "-pubout", "-out", str(public)])
        pin = public_key_spki_sha256(public.read_bytes())
        handoff = prepare_public_key_handoff(public.read_bytes(), pin)
        x963 = directory / "throwaway-x963.bin"
        x963.write_bytes(bytes.fromhex(handoff.x963_public_key_hex))
        report = prepare(
            ipa=args.ipa, private_key=private, public_key=public,
            notes_file=notes, output=signed,
            published_at="2026-11-09T21:00:00Z",
            installed_build=69,
            schema_version=2, channel="production",
            independently_trusted_spki_sha256=pin
        )
        verified = validate(
            signed.read_bytes(), public.read_bytes(),
            installed_build=69, installed_ios="12.5.8",
            expected_channel="production"
        )
        if (verified["build"] != 70 or report["ipa_sha256"] != qa["ipaSHA256"]
                or verified["sha256"] != qa["ipaSHA256"]
                or verified["ipaSize"] != qa["ipaSize"]):
            raise RuntimeError("host signer did not bind exact Build70 archive")
        # Phase CI: simulate a public GitHub readback using TWO distinct
        # copies of the genuine signed Build70 IPA, while keeping ALL files
        # local. No Release, HTTP request, main commit or publication occurs.
        mirror_folder = directory / "simulated-public-asset"
        mirror_folder.mkdir()
        mirror_ipa = mirror_folder / IPA_NAME
        shutil.copyfile(args.ipa, mirror_ipa)
        fake_release = {
            "tag_name": "build70",
            "html_url": "https://github.com/AugustoArbulu/MangaReader12/releases/tag/build70",
            "draft": False, "prerelease": False, "immutable": True,
            "published_at": "2026-11-09T23:00:00Z",
            "assets": [{
                "name": IPA_NAME, "state": "uploaded",
                "content_type": "application/octet-stream",
                "size": qa["ipaSize"], "digest": "sha256:" + qa["ipaSHA256"],
                "browser_download_url": verified["ipaUrl"],
            }],
        }
        readback_report = review_public_readback(
            owner_public_pem=public.read_bytes(), independent_pin=pin,
            private_manifest=signed.read_bytes(),
            published_manifest=signed.read_bytes(),
            local_ipa=args.ipa, readback_ipa=mirror_ipa,
            release_rest_json=json.dumps(
                fake_release, sort_keys=True, separators=(",", ":")
            ).encode("utf-8"),
            installed_build=69
        )
        if not (readback_report["sourceAndReadbackNativeCodeSealsVerified"]
                and readback_report["assetAPISHA256MatchedSignedPayload"]
                and readback_report["readbackByteDigestMatched"]
                and not readback_report["githubAPILiveVerifiedByThisTool"]
                and not readback_report["publicationHappenedInThisTool"]
                and not readback_report["installationPerformed"]):
            raise RuntimeError("CI mocked public readback contract failed")
        print("PASS CI: REAL Build70 native code seals (2 files), immutable"
              " GitHub REST snapshot consistency and signed v2 envelope."
              " All readback data is LOCAL and simulated; NO publication.")
        mutated = directory / "mutated-qa.ipa"
        # A byte mutation is detected by signed-digest comparison before
        # the ZIP parser can treat the potentially damaged archive as valid.
        changed = bytearray(args.ipa.read_bytes())
        if len(changed) < 32:
            raise RuntimeError("IPA too small to mutate")
        changed[20] ^= 0x01
        mutated.write_bytes(changed)
        # A flipped signature byte must fail, even if metadata is unchanged.
        envelope = json.loads(signed.read_bytes())
        import base64
        signature = bytearray(base64.b64decode(envelope["signature"]))
        signature[len(signature)//2] ^= 0x01
        envelope["signature"] = base64.b64encode(signature).decode("ascii")
        bad = directory / "altered-signature.json"
        bad.write_text(json.dumps(envelope, sort_keys=True))
        alias = Path(str(args.ipa) + ".symlink")
        if alias.exists() or alias.is_symlink():
            raise RuntimeError("test symlink already exists")
        alias.symlink_to(args.ipa)
        try:
            runner = directory / "main.swift"
            executable = directory / "native-signed-v2-ipa"
            runner.write_text(SWIFT)
            _run(["swiftc", "-swift-version", "5",
                  *map(str, SOURCES), str(runner),
                  "-framework", "Security", "-o", str(executable)])
            result = _run([str(executable), str(signed), str(x963),
                           pin, str(args.ipa), str(mutated), str(bad)])
            message = result.stdout.decode("utf-8", errors="replace")
            if "PASS CE:" not in message:
                raise RuntimeError("native Swift cross-channel tests did not finish")
            print(message.strip())
            print("REAL_IPA_SHA256=" + qa["ipaSHA256"])
            print("LIMIT: the signing key was THROWAWAY; no editorial trust enrolled, "
                  "no public release URL populated, no Chimera installation attempted")
        finally:
            alias.unlink(missing_ok=True)


if __name__ == "__main__":
    main()

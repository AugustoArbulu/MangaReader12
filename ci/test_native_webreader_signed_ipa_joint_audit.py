#!/usr/bin/env python3
"""Real Swift Security.framework + one-descriptor IPA audit; no installations.

All PEM private keys are ephemeral test fixtures in a temporary directory.
The independently pinned public-key digest is a TEST-ONLY trusted input.
"""
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

from build66_release_key_pinning_gate import public_key_spki_sha256
from build68_release_public_key_handoff import prepare_public_key_handoff
from test_native_webreader_ipa_auditor import (
    make_ipa, make_plist, mutate_crc,
)

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "MangaReader12/Core"
SOURCES = [
    CORE / "WebReaderStrictJSON.swift",
    CORE / "WebReaderUpdateManifestVerifier.swift",
    CORE / "WebReaderSignedReleaseTrustGate.swift",
    CORE / "WebReaderNativeIPAAuditor.swift",
    CORE / "WebReaderSignedIPAReview.swift",
]
SWIFT = r'''
import Foundation

func ensure(_ yes: @autoclosure () -> Bool, _ label: String) {
    if !yes() { fatalError(label) }
}
let args = CommandLine.arguments
ensure(args.count == 12, "expected publickey pin manifest ipa altered wrongbundleEnv wrongbundle badsignature brokenEnv brokenIPA symlink")
let keyHex = Array(args[1].utf8)
var key = Data()
for i in stride(from: 0, to: keyHex.count, by: 2) {
    let hex = String(bytes: keyHex[i..<(i + 2)], encoding: .utf8)!
    key.append(UInt8(hex, radix: 16)!)
}
let pin = args[2]
func data(_ index: Int) -> Data {
    return try! Data(contentsOf: URL(fileURLWithPath: args[index]))
}
func file(_ index: Int) -> URL {
    return URL(fileURLWithPath: args[index])
}
let goodManifest = data(3)
let goodIPA = file(4)
let alteredIPA = file(5)
let badBundleManifest = data(6)
let badBundleIPA = file(7)
let badSignatureManifest = data(8)
let damagedZIPManifest = data(9)
let damagedZIPIPA = file(10)
let aliasIPA = file(11)
let ios = OperatingSystemVersion(majorVersion: 12, minorVersion: 5, patchVersion: 8)

func inspect(
    _ signed: Data, _ ipa: URL, pin selectedPin: String? = nil,
    installedBuild: Int = 66
) throws -> WebReaderSignedIPAReviewResult {
    return try WebReaderSignedIPAReview.inspectReadOnly(
        envelopeData: signed,
        independentlyTrustedPublicKeyX963: key,
        independentlyTrustedSPKISHA256: selectedPin ?? pin,
        localIPAURL: ipa,
        installedBuild: installedBuild,
        installedIOS: ios
    )
}
func rejects(
    _ signed: Data, _ ipa: URL, _ reason: String,
    pin selectedPin: String? = nil, installedBuild: Int = 66
) {
    do {
        _ = try inspect(signed, ipa, pin: selectedPin,
                        installedBuild: installedBuild)
        fatalError("security gate accepted invalid case: " + reason)
    } catch is WebReaderSignedReleaseTrustError {
        // Missing/wrong independently authenticated key fingerprint.
    } catch is WebReaderUpdateValidationError {
        // Bad signed ECDSA metadata, old build or wrong application.
    } catch is WebReaderIPAAuditError {
        // Unsafe archive, bad hash or unexpected embedded identity.
    } catch is WebReaderSignedIPAReviewError {
        // Internal fields do not agree.
    } catch {
        fatalError("wrong error category for: " + reason)
    }
}
let report = try! inspect(goodManifest, goodIPA)
ensure(report.build == 69, "verified build")
ensure(report.bundleID == "com.example.MangaReader12", "verified bundle")
ensure(report.minimumIOS == "12.0", "verified iOS")
ensure(report.signedSHA256 == report.observedSHA256, "signed bytes match same-FD IPA")
ensure(report.signedSPKISHA256 == pin, "independent publisher-key pin matched")
ensure(report.zipEntries >= 4, "central ZIP directory checked")
ensure(report.signedManifestChecked && report.localZIPAndDigestChecked,
       "independent signature + local archive checks ran")
ensure(!report.nativeExecutableSignatureChecked, "ad-hoc code signature not checked")
ensure(!report.publisherIdentityProvenByDevice, "publisher identity not attributed by kernel")
ensure(!report.fileLockedForLaterUse, "file not immutable after audit")
ensure(!report.peerAuthenticated && !report.consentForInstallVerified,
       "no installer peer or consent attestation")
ensure(!report.installationAuthorized && !report.installationPerformed,
       "NO automatic installation")
rejects(goodManifest, alteredIPA, "changed bytes same-size")
rejects(badBundleManifest, badBundleIPA, "wrong app identity signed by fixture")
rejects(badSignatureManifest, goodIPA, "tampered ECDSA signature")
rejects(damagedZIPManifest, damagedZIPIPA, "ZIP CRC damaged but correctly signed")
rejects(goodManifest, aliasIPA, "symbolic link to valid IPA")
rejects(goodManifest, goodIPA, "wrong independent trust pin",
        pin: String(repeating: "0", count: 64))
rejects(goodManifest, goodIPA, "build not newer", installedBuild: 69)
do {
    _ = try WebReaderSignedIPAReview.inspectReadOnly(
        envelopeData: goodManifest,
        independentlyTrustedPublicKeyX963: key,
        independentlyTrustedSPKISHA256: nil,
        localIPAURL: goodIPA,
        installedBuild: 66, installedIOS: ios
    )
    fatalError("accepted missing independent editorial pin")
} catch is WebReaderSignedReleaseTrustError {}
print("PASS signed-v2 manifest + exact IPA same-FD audit: positive/negative fixtures; installation DENIED")
'''

def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_claims(private, root, payload):
    body = root / "claims"
    sig = root / "claims.sig"
    data = encode(payload)
    body.write_bytes(data)
    subprocess.run(
        ["openssl", "dgst", "-sha256", "-sign", str(private),
         "-out", str(sig), str(body)], check=True,
        capture_output=True, timeout=20
    )
    return encode({
        "schemaVersion": 2,
        "algorithm": "ecdsa-p256-sha256",
        "payload": base64.b64encode(data).decode("ascii"),
        "signature": base64.b64encode(sig.read_bytes()).decode("ascii"),
    })


def manifest_for(path):
    raw = path.read_bytes()
    return {
        "schemaVersion": 2,
        "application": "WebReader",
        "bundleId": "com.example.MangaReader12",
        "applicationIdentifier":
            "AR5SFJC432.com.example.MangaReader12.AR5SFJC432",
        "channel": "development",
        "build": 69,
        "minimumIOS": "12.0",
        "ipaUrl": (
            "https://github.com/AugustoArbulu/MangaReader12/"
            "releases/download/build69/WebReader-Build69-iOS12-adhoc.ipa"
        ),
        "ipaSize": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "releaseNotes": ["ephemeral unit-test data only"],
        "publishedAt": "2026-11-08T05:30:00Z",
    }


with tempfile.TemporaryDirectory(prefix="wr68-signed-local-ipa-") as tmp:
    root = Path(tmp)
    private = root / "temporary.key"
    public = root / "temporary.pub"
    subprocess.run([
        "openssl", "ecparam", "-name", "prime256v1", "-genkey",
        "-noout", "-out", str(private)
    ], check=True, capture_output=True, timeout=20)
    subprocess.run([
        "openssl", "pkey", "-in", str(private),
        "-pubout", "-out", str(public)
    ], check=True, capture_output=True, timeout=20)
    pub = public.read_bytes()
    trusted_fixture_pin = public_key_spki_sha256(pub)
    receipt = prepare_public_key_handoff(pub, trusted_fixture_pin)
    assert receipt.installation_authorized is False

    good = root / "good.ipa"
    make_ipa(good, plist=make_plist(build="69"))
    altered = root / "altered-same-size.ipa"
    changed = bytearray(good.read_bytes())
    changed[5] ^= 1
    altered.write_bytes(changed)
    assert len(altered.read_bytes()) == len(good.read_bytes())

    bad_bundle = root / "wrongbundle.ipa"
    make_ipa(bad_bundle, plist=make_plist(build="69", bundle="com.example.Attacker"))
    damaged = root / "crc-corrupt.ipa"
    make_ipa(damaged, plist=make_plist(build="69"))
    mutate_crc(damaged)

    manifest_good = root / "manifest-signed.json"
    manifest_good.write_bytes(sign_claims(private, root, manifest_for(good)))
    manifest_bad_bundle = root / "manifest-wrongbundle.json"
    manifest_bad_bundle.write_bytes(sign_claims(private, root, manifest_for(bad_bundle)))
    manifest_bad_zip = root / "manifest-badzip.json"
    manifest_bad_zip.write_bytes(sign_claims(private, root, manifest_for(damaged)))
    bad_sign_bytes = json.loads(manifest_good.read_bytes())
    signature = bytearray(base64.b64decode(bad_sign_bytes["signature"]))
    signature[len(signature) // 2] ^= 0x01
    bad_sign_bytes["signature"] = base64.b64encode(signature).decode("ascii")
    manifest_bad_sig = root / "manifest-badsignature.json"
    manifest_bad_sig.write_bytes(encode(bad_sign_bytes))
    alias = root / "alias.ipa"
    alias.symlink_to(good)

    runner = root / "main.swift"
    runner.write_text(SWIFT)
    executable = root / "signed-ipa-joint-audit"
    subprocess.run([
        "swiftc", "-swift-version", "5", *map(str, SOURCES), str(runner),
        "-framework", "Security", "-o", str(executable)
    ], check=True, timeout=120)
    subprocess.run([
        str(executable), receipt.x963_public_key_hex, trusted_fixture_pin,
        str(manifest_good), str(good), str(altered),
        str(manifest_bad_bundle), str(bad_bundle), str(manifest_bad_sig),
        str(manifest_bad_zip), str(damaged), str(alias),
    ], check=True, timeout=90)

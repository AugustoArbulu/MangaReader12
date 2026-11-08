#!/usr/bin/env python3
"""Native Swift/Apple Security + CommonCrypto read-only signed-v2 trust tests.

All keys are ephemeral. This is NEVER a production key provisioning script;
does not run on the iPad, download releases, or install any IPA.
"""
import base64
import json
from pathlib import Path
import subprocess
import tempfile

from build66_release_key_pinning_gate import public_key_spki_sha256
from build68_release_public_key_handoff import prepare_public_key_handoff

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "MangaReader12/Core"
SOURCES = [
    CORE / "WebReaderStrictJSON.swift",
    CORE / "WebReaderUpdateManifestVerifier.swift",
    CORE / "WebReaderSignedReleaseTrustGate.swift",
    CORE / "WebReaderProductionPublisherTrust.swift",
]
SWIFT = r'''
import Foundation

// Actual running channel is nil until a separately reviewed owner build.
enum WebReaderUpdateChannel {
    static let productionPublicKeyX963: Data? = nil
}

func expect(_ condition: @autoclosure () -> Bool, _ label: String) {
    if !condition() { fatalError(label) }
}
let args = CommandLine.arguments
expect(args.count == 6, "expected key, pin, v2, v1, invalid-signature envelope")
let pointHex = args[1]
let pin = args[2]
let v2 = try! Data(contentsOf: URL(fileURLWithPath: args[3]))
let v1 = try! Data(contentsOf: URL(fileURLWithPath: args[4]))
let corruptedSignature = try! Data(contentsOf: URL(fileURLWithPath: args[5]))
var point = Data()
let hexBytes = Array(pointHex.utf8)
for index in stride(from: 0, to: hexBytes.count, by: 2) {
    let text = String(bytes: hexBytes[index..<(index + 2)], encoding: .utf8)!
    point.append(UInt8(text, radix: 16)!)
}
let ios = OperatingSystemVersion(majorVersion: 12, minorVersion: 5, patchVersion: 8)

func inspect(
    _ envelope: Data, _ suppliedKey: Data, _ trustedPin: String?,
    installedBuild: Int = 66
) throws -> WebReaderSignedReleasePreview {
    return try WebReaderSignedReleaseTrustGate.inspectReadOnlyV2(
        envelopeData: envelope,
        publicKeyX963: suppliedKey,
        independentlyTrustedSPKISHA256: trustedPin,
        installedBuild: installedBuild, installedIOS: ios
    )
}
func reject(
    _ envelope: Data, _ suppliedKey: Data, _ trustedPin: String?,
    _ name: String, installedBuild: Int = 66
) {
    do {
        _ = try inspect(envelope, suppliedKey, trustedPin,
                        installedBuild: installedBuild)
        fatalError("accepted invalid signed preview: " + name)
    } catch is WebReaderSignedReleaseTrustError {
        // Expected trusted-anchor or schema denial.
    } catch is WebReaderUpdateValidationError {
        // Expected signature / payload / application-version denial.
    } catch {
        fatalError("unexpected error type " + name)
    }
}
// A test key/pin can verify a fixture with the lab API, but cannot enroll
// production trust or enable a real in-app release channel.
expect(!WebReaderProductionPublisherTrust.isProvisioned,
       "production trust must be absent even with valid fixture key")
do {
    _ = try WebReaderProductionPublisherTrust.inspectProductionManifestReadOnly(
        envelopeData: v2, installedBuild: 66, installedIOS: ios
    )
    fatalError("developer fixture illegally configured production trust")
} catch WebReaderPublisherTrustError.noProvisionedOwnerTrust {
    // Expected: no production key and no independently installed key pin.
}

let preview = try! inspect(v2, point, pin)
expect(preview.update.build == 69, "signed v2 accepted")
expect(preview.update.provenance == .signedManifest, "signed origin")
expect(preview.observedSPKISHA256 == pin, "SPKI fingerprint exact")
expect(preview.signatureVerifiedAgainstSuppliedKey, "signature valid")
expect(!preview.ownerIdentityEstablishedByDevice, "device does not authenticate editor")
expect(!preview.nativeIPACodeSignatureVerified, "IPA code signature not audited")
expect(!preview.peerAuthenticated && !preview.userConsentVerified,
       "no authenticated peer or consent")
expect(!preview.installationAuthorized && !preview.installationPerformed,
       "read-only result never authorizes installation")

reject(v2, point, nil, "no trusted pin")
reject(v2, point, "", "empty pin")
reject(v2, point, pin.uppercased(), "noncanonical pin")
reject(v2, point, String(repeating: "0", count: 64), "wrong pin")
reject(v2, Data(), pin, "missing point")
reject(v2, Data([0x04, 0x01]), pin, "short point")
var invalidPoint = point
invalidPoint[0] = 0x03
reject(v2, invalidPoint, pin, "compressed/invalid prefix")
var changedPoint = point
changedPoint[1] ^= 0x01
reject(v2, changedPoint, pin, "mutated key")
reject(v1, point, pin, "v1 not allowed even when correctly signed")
reject(corruptedSignature, point, pin, "invalid ECDSA signature")
reject(v2, point, pin, "not newer than installed", installedBuild: 69)
reject(Data(), point, pin, "empty envelope")

let fakeEnvelope = Data(
    #"{"schemaVersion":true,"algorithm":"ecdsa-p256-sha256","payload":"QQ==","signature":"QQ=="}"#
        .utf8
)
reject(fakeEnvelope, point, pin, "bool schema version")
let fakeFloat = Data(
    #"{"schemaVersion":2.0,"algorithm":"ecdsa-p256-sha256","payload":"QQ==","signature":"QQ=="}"#
        .utf8
)
reject(fakeFloat, point, pin, "fractional schema")
print("PASS native iOS12 signed-v2 read-only gate: independent SPKI, valid ECDSA, v1/downgrade/tamper rejection; installation denied")
'''

def json_bytes(value):
    return json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf8")


def signed_envelope(payload, private_key, root):
    data = json_bytes(payload)
    body = root / "payload.json"
    body.write_bytes(data)
    signature = root / "signature.der"
    subprocess.run(
        ["openssl", "dgst", "-sha256", "-sign", str(private_key),
         "-out", str(signature), str(body)],
        check=True, capture_output=True, timeout=20
    )
    return json_bytes({
        "schemaVersion": payload["schemaVersion"],
        "algorithm": "ecdsa-p256-sha256",
        "payload": base64.b64encode(data).decode("ascii"),
        "signature": base64.b64encode(signature.read_bytes()).decode("ascii"),
    })


with tempfile.TemporaryDirectory(prefix="wr68-native-signed-v2-preview-") as tmp:
    root = Path(tmp)
    private = root / "ephemeral-private.pem"
    public = root / "ephemeral-public.pem"
    subprocess.run(
        ["openssl", "ecparam", "-name", "prime256v1", "-genkey",
         "-noout", "-out", str(private)],
        check=True, capture_output=True, timeout=15
    )
    subprocess.run(
        ["openssl", "pkey", "-in", str(private),
         "-pubout", "-out", str(public)],
        check=True, capture_output=True, timeout=15
    )
    public_bytes = public.read_bytes()
    independently_verified_fixture_pin = public_key_spki_sha256(public_bytes)
    key = prepare_public_key_handoff(
        public_bytes, independently_verified_fixture_pin
    )
    claims = {
        "schemaVersion": 2,
        "application": "WebReader",
        "bundleId": "com.example.MangaReader12",
        "applicationIdentifier":
            "AR5SFJC432.com.example.MangaReader12.AR5SFJC432",
        "channel": "development",
        "build": 69,
        "minimumIOS": "12.0",
        "ipaUrl":
            "https://github.com/AugustoArbulu/MangaReader12/"
            "releases/download/build69/WebReader-Build69-iOS12-adhoc.ipa",
        "ipaSize": 1024,
        "sha256": "a" * 64,
        "releaseNotes": ["offline native signed-v2 test"],
        "publishedAt": "2026-11-08T05:00:00Z",
    }
    envelope_v2 = root / "signed-v2.json"
    envelope_v2.write_bytes(signed_envelope(claims, private, root))
    old = dict(claims)
    old["schemaVersion"] = 1
    del old["applicationIdentifier"]
    old["ipaUrl"] = (
        "https://github.com/AugustoArbulu/MangaReader12/"
        "releases/download/build69/WebReader-iOS12-unsigned.ipa"
    )
    envelope_v1 = root / "signed-v1.json"
    envelope_v1.write_bytes(signed_envelope(old, private, root))
    tampered = json.loads(envelope_v2.read_bytes())
    signature = bytearray(base64.b64decode(tampered["signature"]))
    signature[len(signature) // 2] ^= 1
    tampered["signature"] = base64.b64encode(signature).decode("ascii")
    corrupt_path = root / "corrupted-signature.json"
    corrupt_path.write_bytes(json_bytes(tampered))
    harness = root / "main.swift"
    harness.write_text(SWIFT)
    executable = root / "native-v2-preview"
    subprocess.run(
        ["swiftc", "-swift-version", "5", *map(str, SOURCES),
         str(harness), "-framework", "Security", "-o", str(executable)],
        check=True, timeout=120
    )
    subprocess.run([
        str(executable), key.x963_public_key_hex,
        independently_verified_fixture_pin, str(envelope_v2),
        str(envelope_v1), str(corrupt_path)
    ], check=True, timeout=90)

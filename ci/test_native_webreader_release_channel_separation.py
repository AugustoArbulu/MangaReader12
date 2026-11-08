#!/usr/bin/env python3
"""Real Swift/Security tests: an ECDSA-signed QA manifest cannot become PROD.

Uses a fresh ephemeral P-256 signing key, an independently computed SPKI
fingerprint and two valid signed-v2 envelopes. No production enrollment,
GitHub access, IPA publication or installation occurs.
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
]
SWIFT = r'''
import Foundation

func ensure(_ good: @autoclosure () -> Bool, _ description: String) {
    if !good() { fatalError(description) }
}
let args = CommandLine.arguments
ensure(args.count == 5, "expected P256 point, SPKI SHA, dev, production")
let pin = args[2]
let binary = Array(args[1].utf8)
var point = Data()
for index in stride(from: 0, to: binary.count, by: 2) {
    let h = String(bytes: binary[index..<(index + 2)], encoding: .utf8)!
    point.append(UInt8(h, radix: 16)!)
}
let dev = try! Data(contentsOf: URL(fileURLWithPath: args[3]))
let prod = try! Data(contentsOf: URL(fileURLWithPath: args[4]))
let ios = OperatingSystemVersion(majorVersion: 12, minorVersion: 5, patchVersion: 8)
func inspect(_ body: Data, _ expectedChannel: String = "development")
    throws -> WebReaderSignedReleasePreview {
    return try WebReaderSignedReleaseTrustGate.inspectReadOnlyV2(
        envelopeData: body, publicKeyX963: point,
        independentlyTrustedSPKISHA256: pin, installedBuild: 68,
        installedIOS: ios, expectedChannel: expectedChannel
    )
}
func reject(_ body: Data, _ expectedChannel: String, _ label: String) {
    do {
        _ = try inspect(body, expectedChannel)
        fatalError("accepted a signed manifest from wrong channel: " + label)
    } catch WebReaderUpdateValidationError.wrongApplication {
        // Correct: the signature is valid but wrong signed channel.
    } catch {
        fatalError("unexpected channel rejection: " + label)
    }
}
let d = try! inspect(dev)
ensure(d.update.build == 69, "dev fixture valid")
ensure(d.signatureVerifiedAgainstSuppliedKey, "dev ECDSA authentic")
let p = try! inspect(prod, "production")
ensure(p.update.build == 69, "production fixture valid")
ensure(p.signatureVerifiedAgainstSuppliedKey, "prod ECDSA authentic")
ensure(!p.installationAuthorized && !p.installationPerformed,
       "production signature cannot authorize installation")
reject(dev, "production", "dev signed with true P256 key")
reject(prod, "development", "prod signed with same P256 key")
reject(prod, "releases", "unsupported arbitrary channel")
print("PASS native ECDSA signed-v2 channel binding: dev/prod do not cross, no install")
'''

def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")

with tempfile.TemporaryDirectory(prefix="wr69-channel-separation-") as tmp:
    root = Path(tmp)
    private = root / "fixture-ec-private.pem"
    public = root / "fixture-ec-public.pem"
    subprocess.run([
        "openssl", "ecparam", "-name", "prime256v1",
        "-genkey", "-noout", "-out", str(private)
    ], check=True, capture_output=True, timeout=20)
    subprocess.run([
        "openssl", "pkey", "-in", str(private),
        "-pubout", "-out", str(public)
    ], check=True, capture_output=True, timeout=20)
    pem = public.read_bytes()
    pin = public_key_spki_sha256(pem)
    trusted = prepare_public_key_handoff(pem, pin)
    def signed(channel):
        claims = {
            "schemaVersion": 2,
            "application": "WebReader",
            "bundleId": "com.example.MangaReader12",
            "applicationIdentifier": "AR5SFJC432.com.example.MangaReader12.AR5SFJC432",
            "channel": channel,
            "build": 69,
            "minimumIOS": "12.0",
            "ipaUrl": "https://github.com/AugustoArbulu/MangaReader12/releases/download/build69/WebReader-Build69-iOS12-adhoc.ipa",
            "ipaSize": 17800000,
            "sha256": "e" * 64,
            "releaseNotes": ["Ephemeral test only; nothing published"],
            "publishedAt": "2026-11-08T07:40:00Z",
        }
        source = root / ("payload-" + channel + ".json")
        sig = root / ("signature-" + channel + ".der")
        message = encode(claims)
        source.write_bytes(message)
        subprocess.run([
            "openssl", "dgst", "-sha256", "-sign",
            str(private), "-out", str(sig), str(source)
        ], check=True, capture_output=True, timeout=20)
        envelope = encode({
            "schemaVersion": 2,
            "algorithm": "ecdsa-p256-sha256",
            "payload": base64.b64encode(message).decode("ascii"),
            "signature": base64.b64encode(sig.read_bytes()).decode("ascii"),
        })
        out = root / ("envelope-" + channel + ".json")
        out.write_bytes(envelope)
        return out
    dev, prod = signed("development"), signed("production")
    harness = root / "main.swift"
    binary = root / "channel-test"
    harness.write_text(SWIFT)
    subprocess.run([
        "swiftc", "-swift-version", "5", *map(str, SOURCES),
        str(harness), "-framework", "Security", "-o", str(binary)
    ], check=True, timeout=120)
    subprocess.run([
        str(binary), trusted.x963_public_key_hex, pin, str(dev), str(prod)
    ], check=True, timeout=45)

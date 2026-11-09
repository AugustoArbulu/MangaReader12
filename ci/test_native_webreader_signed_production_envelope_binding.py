#!/usr/bin/env python3
"""CH: real Swift Security.framework signed-envelope->download metadata binding.

Temporary P-256 key / manifest fixtures only. No IPA, network, key enrollment
or installation. Includes wrong provenance, channel, build, SHA, URL and notes.
"""
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

from build66_release_key_pinning_gate import public_key_spki_sha256

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "MangaReader12/Core"
SOURCES = [
    CORE / "WebReaderStrictJSON.swift",
    CORE / "WebReaderUpdateManifestVerifier.swift",
    CORE / "WebReaderSignedReleaseTrustGate.swift",
    CORE / "WebReaderProductionPublisherTrust.swift",
    CORE / "WebReaderSignedProductionEnvelopeBinding.swift"
]
SWIFT = r'''
import Foundation
enum WebReaderUpdateChannel {
    // Exact public-root state of the currently shipped Build70:
    static let productionPublicKeyX963: Data? = nil
}
func ensure(_ condition: @autoclosure () -> Bool, _ why: String) {
    if !condition() { fatalError(why) }
}
let args = CommandLine.arguments
ensure(args.count == 5, "manifest, X9.63, pin, corrupted manifest")
let manifest = try! Data(contentsOf: URL(fileURLWithPath: args[1]))
let key = try! Data(contentsOf: URL(fileURLWithPath: args[2]))
let pin = args[3]
let altered = try! Data(contentsOf: URL(fileURLWithPath: args[4]))
let ios = OperatingSystemVersion(majorVersion: 12, minorVersion: 5, patchVersion: 8)
let baseline = 70
let verified = try! WebReaderUpdateManifestVerifier.verify(
    envelopeData: manifest, publicKeyX963: key,
    installedBuild: baseline, installedIOS: ios, expectedChannel: "production"
)
func matches(_ update: WebReaderVerifiedUpdate, _ data: Data = manifest,
             _ pinArg: String? = pin, _ base: Int = baseline) -> Bool {
    return WebReaderSignedProductionEnvelopeBinding.matchesReadOnly(
        envelopeData: data, update: update,
        installedBuild: base, installedIOS: ios,
        publicKeyX963: key, independentlyTrustedSPKISHA256: pinArg
    )
}
func alteredUpdate(
    build: Int? = nil, minimumIOS: String? = nil,
    url: URL? = nil, ipaSize: Int64? = nil,
    sha: String? = nil, publishedAt: String? = nil,
    notes: [String]? = nil, provenance: WebReaderUpdateProvenance = .signedManifest
) -> WebReaderVerifiedUpdate {
    var candidate = WebReaderVerifiedUpdate(
        build: build ?? verified.build,
        minimumIOS: minimumIOS ?? verified.minimumIOS,
        ipaURL: url ?? verified.ipaURL,
        ipaSize: ipaSize ?? verified.ipaSize,
        sha256: sha ?? verified.sha256,
        publishedAt: publishedAt ?? verified.publishedAt,
        releaseNotes: notes ?? verified.releaseNotes
    )
    candidate.provenance = provenance
    return candidate
}
ensure(matches(verified), "valid production-v2 envelope must bind exact claims")
ensure(!WebReaderSignedProductionEnvelopeBinding.matchesCompiledOwnerRootReadOnly(
    envelopeData: manifest, update: verified,
    installedBuild: baseline, installedIOS: ios
), "unprovisioned app must reject even valid throwaway ECDSA fixture")

let forged: [WebReaderVerifiedUpdate] = [
    alteredUpdate(build: 72),
    alteredUpdate(minimumIOS: "12.1"),
    alteredUpdate(url: URL(string: "https://example.com/app.ipa")!),
    alteredUpdate(ipaSize: verified.ipaSize + 1),
    alteredUpdate(sha: String(repeating: "f", count: 64)),
    alteredUpdate(publishedAt: "2026-11-10T00:00:00Z"),
    alteredUpdate(notes: ["Malicious release notes"]),
    alteredUpdate(provenance: .publicGitHubRelease),
    alteredUpdate(provenance: .manualLocalFile)
]
for (index, item) in forged.enumerated() {
    ensure(!matches(item), "forged metadata field accepted: " + String(index))
}
ensure(!matches(verified, altered), "changed signature rejected")
ensure(!matches(verified, manifest,
                pin == String(repeating: "0", count: 64) ?
                    String(repeating: "f", count: 64) :
                    String(repeating: "0", count: 64)),
       "wrong SPKI pin rejected")
ensure(!matches(verified, manifest, nil), "absent independently trusted SPKI pin rejected")
ensure(!matches(verified, manifest, pin, 71), "repeated/downgrade build rejected")
ensure(!matches(verified, Data()), "missing envelope rejected")

print("PASS CH: native production ECDSA/metadata binding and ten negative cases; compiled root absent; NO install")
'''

def command(argv):
    return subprocess.run(argv, check=True, capture_output=True, timeout=90)


def json_bytes(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


with tempfile.TemporaryDirectory(prefix="wr70-ch-ecdsa-metadata-") as tmp:
    folder = Path(tmp)
    private = folder / "test-private-ec.key"
    public = folder / "test-public.pem"
    command(["openssl", "ecparam", "-name", "prime256v1", "-genkey",
             "-noout", "-out", str(private)])
    command(["openssl", "pkey", "-in", str(private),
             "-pubout", "-out", str(public)])
    pem = public.read_bytes()
    pin = public_key_spki_sha256(pem)
    der = command(["openssl", "pkey", "-pubin", "-in", str(public),
                   "-outform", "DER"]).stdout
    assert len(der) == 91 and der[-65] == 4
    x963 = folder / "test-public-x963.bin"
    x963.write_bytes(der[-65:])
    payload = {
        "schemaVersion": 2,
        "application": "WebReader",
        "bundleId": "com.example.MangaReader12",
        "applicationIdentifier":
            "AR5SFJC432.com.example.MangaReader12.AR5SFJC432",
        "channel": "production",
        "build": 71,
        "minimumIOS": "12.0",
        "ipaUrl": ("https://github.com/AugustoArbulu/MangaReader12/"
                   "releases/download/build71/WebReader-Build71-iOS12-adhoc.ipa"),
        "ipaSize": 123456,
        "sha256": hashlib.sha256(b"DISPOSABLE ONLY - NOT A REAL IPA").hexdigest(),
        "releaseNotes": ["Signed update binding test only"],
        "publishedAt": "2026-11-09T23:00:00Z"
    }
    body = folder / "payload.json"
    body.write_bytes(json_bytes(payload))
    sigfile = folder / "payload.der"
    command(["openssl", "dgst", "-sha256", "-sign", str(private),
             "-out", str(sigfile), str(body)])
    envelope = {
        "schemaVersion": 2,
        "algorithm": "ecdsa-p256-sha256",
        "payload": base64.b64encode(body.read_bytes()).decode("ascii"),
        "signature": base64.b64encode(sigfile.read_bytes()).decode("ascii")
    }
    good = folder / "manifest.json"
    good.write_bytes(json_bytes(envelope))
    bad_sig = bytearray(sigfile.read_bytes())
    bad_sig[len(bad_sig)//2] ^= 1
    envelope["signature"] = base64.b64encode(bad_sig).decode("ascii")
    changed = folder / "tampered.json"
    changed.write_bytes(json_bytes(envelope))
    app = folder / "main.swift"
    app.write_text(SWIFT, encoding="utf-8")
    exe = folder / "native-binding-test"
    command(["swiftc", "-swift-version", "5", *map(str, SOURCES),
             str(app), "-framework", "Security", "-o", str(exe)])
    completed = command([str(exe), str(good), str(x963), pin, str(changed)])
    print(completed.stdout.decode("utf-8").strip())

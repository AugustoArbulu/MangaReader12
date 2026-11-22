#!/usr/bin/env python3
"""End-to-end OpenSSL/Python publisher -> native iOS12 Swift verifier test.

Generates ephemeral keys and a synthetic unsigned IPA in a temp folder.
Publishes NOTHING, runs NO networking or privileged installation, and stores
NO signing keys in the repository.
"""
from pathlib import Path
import hashlib
import json
import subprocess
import tempfile

from prepare_signed_webreader_update import prepare
from test_validate_webreader_ipa import make_ipa

ROOT = Path(__file__).resolve().parent.parent
SOURCES = [
    ROOT / "MangaReader12/Core/WebReaderStrictJSON.swift",
    ROOT / "MangaReader12/Core/WebReaderUpdateManifestVerifier.swift",
]

SWIFT = r'''
import Foundation
import Security

func must(_ value: @autoclosure () -> Bool, _ description: String) {
    if !value() { fatalError(description) }
}
let arguments = CommandLine.arguments
must(arguments.count == 5, "requires four fixture filenames")
let manifest = try! Data(contentsOf: URL(fileURLWithPath: arguments[1]))
let publicKey = try! Data(contentsOf: URL(fileURLWithPath: arguments[2]))
let expectedSha = arguments[3]
let expectedSize = Int64(arguments[4])!
let info = try! WebReaderUpdateManifestVerifier.verify(
    envelopeData: manifest,
    publicKeyX963: publicKey,
    installedBuild: 56,
    installedIOS: OperatingSystemVersion(majorVersion: 12, minorVersion: 5, patchVersion: 8)
)
must(info.build == 57, "Python signature accepted by native verifier")
must(info.sha256 == expectedSha, "identical signed file hash")
must(info.ipaSize == expectedSize, "identical signed IPA size")
must(info.ipaURL.absoluteString ==
    "https://github.com/AugustoArbulu/MangaReader12/releases/download/build57/WebReader-iOS12-unsigned.ipa",
    "expected release URL")

// Mutating the signed payload without re-signing must fail closed.
var envelope = try! JSONSerialization.jsonObject(with: manifest) as! [String: Any]
envelope["payload"] = Data(#"{"build":58}"#.utf8).base64EncodedString()
let changed = try! JSONSerialization.data(withJSONObject: envelope)
do {
    _ = try WebReaderUpdateManifestVerifier.verify(
        envelopeData: changed, publicKeyX963: publicKey,
        installedBuild: 56,
        installedIOS: OperatingSystemVersion(majorVersion: 12, minorVersion: 5, patchVersion: 8)
    )
    fatalError("tampered payload accepted")
} catch is WebReaderUpdateValidationError {
    // Expected failure
}
print("PASS: Python/OpenSSL signed release is compatible with native iOS12 Security.framework")
'''

with tempfile.TemporaryDirectory(prefix="webreader-crosslang-signature-") as tmp:
    root = Path(tmp)
    ipa, _ = make_ipa(root, build="57")
    private = root / "private.pem"
    public = root / "public.pem"
    notes = root / "notes.json"
    output = root / "signed-envelope.json"
    notes.write_text('["Cross-language QA fixture only"]', encoding="utf-8")
    subprocess.run(
        ["openssl", "ecparam", "-name", "prime256v1", "-genkey",
         "-noout", "-out", str(private)],
        check=True, capture_output=True
    )
    subprocess.run(
        ["openssl", "pkey", "-in", str(private),
         "-pubout", "-out", str(public)],
        check=True, capture_output=True
    )
    prepared = prepare(
        ipa, private, public, notes, output, "2026-11-05T03:00:00Z"
    )

    # The native SecKey verifier consumes uncompressed ANSI X9.63 P-256.
    # Export the ephemeral PEM public key via OpenSSL DER SubjectPublicKeyInfo
    # (the 65 trailing bytes are the public EC point for this TEST fixture).
    der = subprocess.check_output([
        "openssl", "pkey", "-pubin", "-in", str(public), "-outform", "DER"
    ])
    assert len(der) >= 80 and der[-65] == 0x04, "not an uncompressed P-256 key"
    x963 = root / "public-x963.dat"
    x963.write_bytes(der[-65:])
    swift_main = root / "main.swift"
    binary = root / "native-check"
    swift_main.write_text(SWIFT)
    subprocess.run(
        ["swiftc", "-swift-version", "5", *map(str, SOURCES),
         str(swift_main), "-framework", "Security", "-o", str(binary)],
        check=True
    )
    subprocess.run([
        str(binary), str(output), str(x963), prepared["ipa_sha256"],
        str(prepared["ipa_size"])
    ], check=True)

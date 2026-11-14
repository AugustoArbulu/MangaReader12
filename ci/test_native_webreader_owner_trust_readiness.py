#!/usr/bin/env python3
"""Native macOS/iOS12-compatible pre-network publisher trust readiness test.

Uses an ephemeral signing key generated only inside a temporary directory.
Compiles the real Swift trust code without editing production constants.
Never performs an HTTPS request, IPA creation, or installation.
"""
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

enum WebReaderUpdateChannel {
    static let productionPublicKeyX963: Data? = nil
}
func ensure(_ condition: @autoclosure () -> Bool, _ label: String) {
    if !condition() { fatalError(label) }
}
let args = CommandLine.arguments
ensure(args.count == 3, "must receive ephemeral X9.63 point and SPKI pin")
let bytes = Array(args[1].utf8)
ensure(bytes.count == 130, "X9.63 expected 65 bytes")
var key = Data()
for i in stride(from: 0, to: bytes.count, by: 2) {
    let hex = String(bytes: bytes[i..<(i + 2)], encoding: .utf8)!
    key.append(UInt8(hex, radix: 16)!)
}
let pin = args[2]
let gate = WebReaderProductionPublisherTrust.self
func review(_ p: String?, _ generation: Int, _ point: Data?,
            revoked: Set<String> = []) -> Bool {
    return gate.isCandidateReadyForReview(
        ownerPin: p, generation: generation, publicKeyX963: point,
        revokedPins: revoked
    )
}
ensure(WebReaderSignedReleaseTrustGate.observedP256SPKISHA256(for: key) == pin,
       "canonical DER SPKI must match independently calculated host fingerprint")
ensure(review(pin, 1, key), "real ephemeral public point + true pin passes offline review")
ensure(!review(pin, 0, key), "generation zero rejects")
ensure(!review(pin, -1, key), "negative generation rejects")
let wrongPin = (pin.first == "0" ? "1" : "0") + String(pin.dropFirst())
ensure(!review(wrongPin, 1, key), "different pin cannot match")
ensure(!review(pin.uppercased(), 1, key), "uppercase pin rejected")
ensure(!review(nil, 1, key), "missing pin rejected")
ensure(!review(pin, 1, nil), "missing public key rejected")
ensure(!review(pin, 1, key, revoked: [pin]), "independently revoked pin rejects")
ensure(!review(pin, 1, Data(repeating: 0, count: 65)), "invalid X9.63 prefix rejects")
var offCurve = Data(repeating: 0, count: 65)
offCurve[0] = 0x04
ensure(WebReaderSignedReleaseTrustGate.observedP256SPKISHA256(for: offCurve) == nil,
       "invalid P256 point cannot yield trusted fingerprint")
ensure(!review(pin, 1, offCurve), "invalid EC point rejected")

// No fixture may alter the real compiled production trust policy.
ensure(!gate.isProvisioned, "unprovisioned production root stays disabled")
ensure(gate.productionTrustGeneration == 0, "never auto-enroll trust generation")
ensure(gate.revokedPublisherPins.isEmpty, "fixture never configures revocations")
print("PASS iOS12 Swift owner public trust: exact SPKI pin + on-curve P256 + generation/revocation, production disabled")
'''

with tempfile.TemporaryDirectory(prefix="wr69-owner-trust-readiness-") as tmp:
    root = Path(tmp)
    private = root / "ephemeral-private.pem"
    public = root / "ephemeral-public.pem"
    subprocess.run(
        ["openssl", "ecparam", "-genkey", "-name", "prime256v1",
         "-noout", "-out", str(private)],
        check=True, capture_output=True, timeout=15
    )
    subprocess.run(
        ["openssl", "pkey", "-in", str(private), "-pubout", "-out", str(public)],
        check=True, capture_output=True, timeout=15
    )
    pem = public.read_bytes()
    pin = public_key_spki_sha256(pem)
    key = prepare_public_key_handoff(pem, pin)
    main = root / "main.swift"
    binary = root / "owner-publisher-review"
    main.write_text(SWIFT)
    subprocess.run(
        ["swiftc", "-swift-version", "5",
         *map(str, SOURCES), str(main), "-framework", "Security",
         "-o", str(binary)],
        check=True, timeout=120
    )
    subprocess.run(
        [str(binary), key.x963_public_key_hex, pin],
        check=True, timeout=45
    )

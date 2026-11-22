#!/usr/bin/env python3
"""macOS Security.framework interop for host-only public P-256 handoff.

The EC private key exists only as a temporary test fixture. No production
publisher key, network request, iOS app modification, or installation occurs.
"""
from pathlib import Path
import subprocess
import tempfile

from build66_release_key_pinning_gate import public_key_spki_sha256
from build68_release_public_key_handoff import prepare_public_key_handoff

SWIFT = r'''
import Foundation
import Security

func check(_ condition: @autoclosure () -> Bool, _ label: String) {
    if !condition() { fatalError(label) }
}
let args = CommandLine.arguments
check(args.count == 4, "expected public key hex, payload file, signature file")
let chars = Array(args[1].utf8)
check(chars.count == 130, "Swift Security.framework requires 65 X9.63 bytes")
var octets: [UInt8] = []
for index in stride(from: 0, to: chars.count, by: 2) {
    let token = String(bytes: chars[index..<(index + 2)], encoding: .utf8)!
    guard let byte = UInt8(token, radix: 16) else {
        fatalError("invalid public key hex")
    }
    octets.append(byte)
}
let rawKey = Data(octets)
check(rawKey.count == 65 && rawKey.first == 0x04, "uncompressed EC point")
let attrs: [String: Any] = [
    kSecAttrKeyType as String: kSecAttrKeyTypeECSECPrimeRandom,
    kSecAttrKeyClass as String: kSecAttrKeyClassPublic,
    kSecAttrKeySizeInBits as String: 256,
    kSecAttrIsPermanent as String: false
]
var error: Unmanaged<CFError>?
guard let key = SecKeyCreateWithData(
    rawKey as CFData, attrs as CFDictionary, &error
) else {
    fatalError("Swift Security.framework rejected independently pinned X9.63 key")
}
check(SecKeyIsAlgorithmSupported(
    key, .verify, .ecdsaSignatureMessageX962SHA256
), "P-256 verify support")
let message = try! Data(contentsOf: URL(fileURLWithPath: args[2]))
let signature = try! Data(contentsOf: URL(fileURLWithPath: args[3]))
var signatureError: Unmanaged<CFError>?
check(SecKeyVerifySignature(
    key, .ecdsaSignatureMessageX962SHA256, message as CFData,
    signature as CFData, &signatureError
), "cross-language valid signature accepted")
let altered = Data((message + Data([0x01])))
check(!SecKeyVerifySignature(
    key, .ecdsaSignatureMessageX962SHA256, altered as CFData,
    signature as CFData, nil
), "altered payload signature rejected")
var badKey = Data(repeating: 0, count: 65)
badKey[0] = 0x04
let garbage = SecKeyCreateWithData(
    badKey as CFData, attrs as CFDictionary, nil
)
if let garbage = garbage {
    check(!SecKeyVerifySignature(
        garbage, .ecdsaSignatureMessageX962SHA256, message as CFData,
        signature as CFData, nil
    ), "unrelated key cannot verify release message")
}
print("PASS native Security.framework: pinned P-256 SPKI -> X9.63, positive and negative ECDSA checks; no installer")
'''

with tempfile.TemporaryDirectory(prefix="wr68-native-key-interop-") as tmp:
    root = Path(tmp)
    private = root / "ephemeral.key"
    public = root / "ephemeral.pub"
    message = root / "payload"
    signature = root / "signature.der"
    harness = root / "main.swift"
    exe = root / "public-key-interop"
    subprocess.run([
        "openssl", "ecparam", "-name", "prime256v1", "-genkey",
        "-noout", "-out", str(private)
    ], check=True, capture_output=True, timeout=15)
    subprocess.run([
        "openssl", "pkey", "-in", str(private),
        "-pubout", "-out", str(public)
    ], check=True, capture_output=True, timeout=15)
    public_bytes = public.read_bytes()
    independent_fixture_pin = public_key_spki_sha256(public_bytes)
    receipt = prepare_public_key_handoff(
        public_bytes, independent_fixture_pin
    )
    assert receipt.production_key_configured is False
    assert receipt.installation_authorized is False
    message.write_bytes(b'{"purpose":"WebReader offline test only","build":68}')
    subprocess.run([
        "openssl", "dgst", "-sha256", "-sign", str(private),
        "-out", str(signature), str(message)
    ], check=True, capture_output=True, timeout=15)
    harness.write_text(SWIFT)
    subprocess.run([
        "swiftc", "-swift-version", "5", str(harness),
        "-framework", "Security", "-o", str(exe)
    ], check=True, timeout=120)
    subprocess.run([
        str(exe), receipt.x963_public_key_hex,
        str(message), str(signature)
    ], check=True, timeout=60)

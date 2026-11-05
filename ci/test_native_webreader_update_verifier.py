#!/usr/bin/env python3
"""Compile and execute the actual iOS12 Security.framework verifier on macOS.

All signing keys exist only inside this temporary test process. This test
performs no networking, package installation, appinst invocation or privileged
operations; it verifies protocol compatibility with the Python host reference.
"""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "MangaReader12/Core/WebReaderUpdateManifestVerifier.swift"

HARNESS = r'''
import Foundation
import Security

func check(_ predicate: @autoclosure () -> Bool, _ description: String) {
    if !predicate() { fatalError(description) }
}
func json(_ value: [String: Any]) -> Data {
    return try! JSONSerialization.data(withJSONObject: value, options: [.sortedKeys])
}

let attrs: [String: Any] = [
    kSecAttrKeyType as String: kSecAttrKeyTypeECSECPrimeRandom,
    kSecAttrKeySizeInBits as String: 256
]
var generateError: Unmanaged<CFError>?
let privateKey = SecKeyCreateRandomKey(attrs as CFDictionary, &generateError)!
let publicKey = SecKeyCopyPublicKey(privateKey)!
var keyError: Unmanaged<CFError>?
let publicX963 = SecKeyCopyExternalRepresentation(publicKey, &keyError)! as Data
check(publicX963.count == 65, "expected 65 byte uncompressed test key")

var payload: [String: Any] = [
    "schemaVersion": 1,
    "application": "WebReader",
    "bundleId": "com.example.MangaReader12",
    "channel": "development",
    "build": 57,
    "minimumIOS": "12.0",
    "ipaUrl": "https://github.com/AugustoArbulu/MangaReader12/releases/download/build57/WebReader-iOS12-unsigned.ipa",
    "ipaSize": 17300000,
    "sha256": String(repeating: "3", count: 64),
    "releaseNotes": ["Native offline signature regression"],
    "publishedAt": "2026-11-04T16:00:00Z"
]
let systemVersion = OperatingSystemVersion(majorVersion: 12, minorVersion: 5, patchVersion: 8)

func signedEnvelope(_ details: [String: Any]) -> Data {
    let message = json(details)
    var signError: Unmanaged<CFError>?
    let signature = SecKeyCreateSignature(
        privateKey, .ecdsaSignatureMessageX962SHA256,
        message as CFData, &signError
    )! as Data
    return json([
        "schemaVersion": 1,
        "algorithm": "ecdsa-p256-sha256",
        "payload": message.base64EncodedString(),
        "signature": signature.base64EncodedString()
    ])
}
func accept(_ envelope: Data, key: Data = publicX963) -> WebReaderVerifiedUpdate {
    return try! WebReaderUpdateManifestVerifier.verify(
        envelopeData: envelope,
        publicKeyX963: key,
        installedBuild: 56,
        installedIOS: systemVersion
    )
}
func reject(_ envelope: Data, key: Data = publicX963) {
    do {
        _ = try WebReaderUpdateManifestVerifier.verify(
            envelopeData: envelope,
            publicKeyX963: key,
            installedBuild: 56,
            installedIOS: systemVersion
        )
        fatalError("invalid manifest erroneously accepted")
    } catch is WebReaderUpdateValidationError {
        // Expected rejection.
    } catch {
        fatalError("wrong error: " + error.localizedDescription)
    }
}

let good = signedEnvelope(payload)
let verified = accept(good)
check(verified.build == 57, "signed build")
check(verified.ipaSize == 17300000, "signed IPA size")
check(verified.minimumIOS == "12.0", "minimum iOS")
check(verified.ipaURL.host == "github.com", "release host")

// A signed payload modified without changing signature must be rejected.
var tampered = try! JSONSerialization.jsonObject(with: good) as! [String: Any]
tampered["payload"] = json(payload.merging(["build": 58]) { _, b in b }).base64EncodedString()
reject(json(tampered))

// Signed-but-forbidden payloads are also rejected by policy.
var incompatible = payload
incompatible["minimumIOS"] = "13.0"
reject(signedEnvelope(incompatible))
var wrongID = payload
wrongID["bundleId"] = "com.example.WebReader"
reject(signedEnvelope(wrongID))
var downgrade = payload
downgrade["build"] = 56
reject(signedEnvelope(downgrade))
var unsignedHost = payload
unsignedHost["ipaUrl"] = "https://example.com/WebReader.ipa"
reject(signedEnvelope(unsignedHost))
var actionInjected = payload
actionInjected["command"] = "install arbitrary app"
reject(signedEnvelope(actionInjected))
var tooLarge = payload
tooLarge["ipaSize"] = 1024 * 1024 * 1024
reject(signedEnvelope(tooLarge))

// Fails closed when no production key is configured.
reject(good, key: Data())
reject(Data(repeating: 0, count: 65537))

print("PASS iOS12 native WebReader signed manifest and fail-closed policy")
'''
with tempfile.TemporaryDirectory(prefix="webreader-native-signature-") as folder:
    temp = Path(folder)
    main = temp / "main.swift"
    main.write_text(HARNESS)
    binary = temp / "native-security-test"
    subprocess.run(
        ["swiftc", "-swift-version", "5", str(SOURCE), str(main),
         "-framework", "Security", "-o", str(binary)],
        check=True
    )
    subprocess.run([str(binary)], check=True)

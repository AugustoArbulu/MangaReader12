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
STRICT_SOURCE = ROOT / "MangaReader12/Core/WebReaderStrictJSON.swift"

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
        "schemaVersion": details["schemaVersion"] as? Int ?? 1,
        "algorithm": "ecdsa-p256-sha256",
        "payload": message.base64EncodedString(),
        "signature": signature.base64EncodedString()
    ])
}

func signedRawPayload(_ message: Data) -> Data {
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

// Version 2 binds the exact ad-hoc release asset and existing installation
// application-identifier into the cryptographically signed payload.
var v2 = payload
v2["schemaVersion"] = 2
v2["build"] = 66
v2["applicationIdentifier"] =
    "AR5SFJC432.com.example.MangaReader12.AR5SFJC432"
v2["ipaUrl"] = "https://github.com/AugustoArbulu/MangaReader12/" +
    "releases/download/build66/WebReader-Build66-iOS12-adhoc.ipa"
let verifiedV2 = accept(signedEnvelope(v2))
check(verifiedV2.build == 66, "signed v2 build")
check(verifiedV2.ipaURL.lastPathComponent ==
      "WebReader-Build66-iOS12-adhoc.ipa", "signed v2 asset")
// A signed old Build can only mean "up to date" once the *entire*
 // authenticated URL, content metadata and app identity are valid.
func classifySignedOld(_ details: [String: Any]) -> String {
    do {
        _ = try WebReaderUpdateManifestVerifier.verify(
            envelopeData: signedEnvelope(details),
            publicKeyX963: publicX963, installedBuild: 66,
            installedIOS: systemVersion, expectedChannel: "development"
        )
        return "unexpected-update"
    } catch WebReaderUpdateValidationError.notNewer {
        return "current"
    } catch WebReaderUpdateValidationError.disallowedURL {
        return "invalid-url"
    } catch WebReaderUpdateValidationError.invalidPayload {
        return "invalid-payload"
    } catch WebReaderUpdateValidationError.incompatibleIOS {
        return "incompatible-ios"
    } catch WebReaderUpdateValidationError.wrongApplication {
        return "wrong-identity"
    } catch {
        return "other-rejection"
    }
}
check(classifySignedOld(v2) == "current", "fully verified equal Build is up-to-date")
var oldWrongURL = v2
oldWrongURL["ipaUrl"] = "https://example.com/untrusted.ipa"
check(classifySignedOld(oldWrongURL) == "invalid-url",
      "signed old Build with invalid URL must not become up-to-date")
var oldWrongSHA = v2
oldWrongSHA["sha256"] = "not-a-digest"
check(classifySignedOld(oldWrongSHA) == "invalid-payload",
      "signed old Build with invalid digest must not become up-to-date")
var oldWrongIOS = v2
oldWrongIOS["minimumIOS"] = "13.0"
check(classifySignedOld(oldWrongIOS) == "incompatible-ios",
      "signed old Build with unsupported iOS must not become up-to-date")
var oldWrongChannel = v2
oldWrongChannel["channel"] = "production"
check(classifySignedOld(oldWrongChannel) == "wrong-identity",
      "signed old Build from another channel must not become up-to-date")
var oldExtraClaim = v2
oldExtraClaim["developerOverride"] = true
check(classifySignedOld(oldExtraClaim) == "invalid-payload",
      "signed old Build with unknown field must not become up-to-date")

var wrongV2Identity = v2
wrongV2Identity["applicationIdentifier"] = "ATTACKER"
reject(signedEnvelope(wrongV2Identity))
var missingV2Identity = v2
missingV2Identity.removeValue(forKey: "applicationIdentifier")
reject(signedEnvelope(missingV2Identity))
var extraV1Identity = payload
extraV1Identity["applicationIdentifier"] =
    "AR5SFJC432.com.example.MangaReader12.AR5SFJC432"
reject(signedEnvelope(extraV1Identity))
var wrongV2Filename = v2
wrongV2Filename["ipaUrl"] =
    "https://github.com/AugustoArbulu/MangaReader12/releases/" +
    "download/build66/WebReader-iOS12-unsigned.ipa"
reject(signedEnvelope(wrongV2Filename))
var wrongV1Filename = payload
wrongV1Filename["ipaUrl"] =
    "https://github.com/AugustoArbulu/MangaReader12/releases/" +
    "download/build57/WebReader-Build57-iOS12-adhoc.ipa"
reject(signedEnvelope(wrongV1Filename))
var v2WrapperMismatch = try! JSONSerialization.jsonObject(
    with: signedEnvelope(v2)) as! [String: Any]
v2WrapperMismatch["schemaVersion"] = 1
reject(json(v2WrapperMismatch))
var v2SignedTamper = try! JSONSerialization.jsonObject(
    with: signedEnvelope(v2)) as! [String: Any]
var v2Tampered = v2
v2Tampered["applicationIdentifier"] = "WRONG"
v2SignedTamper["payload"] = json(v2Tampered).base64EncodedString()
reject(json(v2SignedTamper))

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


// Malformed and ambiguous JSON must not be interpreted by Foundation.
check(!WebReaderStrictJSON.accepts(Data(
    #"{"name":"a","name":"b"}"#.utf8
)), "literal duplicate rejected")
check(!WebReaderStrictJSON.accepts(Data(
    #"{"name":"a","\u006eame":"b"}"#.utf8
)), "Unicode-escaped duplicate rejected")
check(!WebReaderStrictJSON.accepts(Data(
    #"{"root":[{"x":1,"\u0078":2}]}"#.utf8
)), "nested duplicate in array rejected")
check(!WebReaderStrictJSON.accepts(Data(
    #"{"outer":{"a":1,"a":2}}"#.utf8
)), "nested duplicate rejected")
check(!WebReaderStrictJSON.accepts(Data(
    #"{"a":1,"b":01}"#.utf8
)), "invalid numeric JSON rejected")
check(WebReaderStrictJSON.accepts(json(payload)), "valid signed payload accepted")

let originalPayloadString = String(data: json(payload), encoding: .utf8)!
let literalDuplicatePayload = "{\"bundleId\":\"com.example.MangaReader12\"," +
    String(originalPayloadString.dropFirst())
reject(signedRawPayload(Data(literalDuplicatePayload.utf8)))
let escapedDuplicatePayload =
    "{\"\\u0062undleId\":\"com.example.MangaReader12\"," +
    String(originalPayloadString.dropFirst())
reject(signedRawPayload(Data(escapedDuplicatePayload.utf8)))

// A duplicate in the outer envelope must fail even if payload is signed.
let originalEnvelopeString = String(data: good, encoding: .utf8)!
let duplicateEnvelopeString = originalEnvelopeString.replacingOccurrences(
    of: "\"algorithm\":",
    with: "\"algorithm\":\"ecdsa-p256-sha256\",\"algorithm\":"
)
check(duplicateEnvelopeString != originalEnvelopeString, "envelope mutated")
reject(Data(duplicateEnvelopeString.utf8))

// Reject excessive nesting and trailing bytes before Foundation accepts it.
let nestedJSON = String(repeating: "[", count: 34) + "0" +
    String(repeating: "]", count: 34)
check(!WebReaderStrictJSON.accepts(Data(nestedJSON.utf8)), "depth bound")
check(!WebReaderStrictJSON.accepts(Data(
    #"{"x":true} trailing"#.utf8
)), "trailing bytes")

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
        ["swiftc", "-swift-version", "5", str(STRICT_SOURCE), str(SOURCE), str(main),
         "-framework", "Security", "-o", str(binary)],
        check=True
    )
    subprocess.run([str(binary)], check=True)

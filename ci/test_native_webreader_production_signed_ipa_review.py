#!/usr/bin/env python3
"""Phase CF: real Swift production IPA gate denies before any file I/O.

The actual app has NO independently provisioned publisher public key or pin.
This host test compiles real iOS12 Swift sources, then exercises the compiled
production-only entry point against deliberately nonexistent file paths.
No network, IPA, private key, publisher bootstrap, or appinst.
"""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "MangaReader12/Core"
SOURCES = [
    CORE / "WebReaderStrictJSON.swift",
    CORE / "WebReaderUpdateManifestVerifier.swift",
    CORE / "WebReaderSignedReleaseTrustGate.swift",
    CORE / "WebReaderNativeIPAAuditor.swift",
    CORE / "WebReaderSignedIPAReview.swift",
    CORE / "WebReaderProductionPublisherTrust.swift",
    CORE / "WebReaderProductionSignedIPAReview.swift",
]

SWIFT = r'''
import Foundation

// A minimal, production-equivalent stub for the currently nil updater root.
enum WebReaderUpdateChannel {
    static let productionPublicKeyX963: Data? = nil
}

func ensure(_ condition: @autoclosure () -> Bool, _ description: String) {
    if !condition() { fatalError(description) }
}

ensure(!WebReaderProductionPublisherTrust.isProvisioned,
       "the real iOS12 app has no owner-pinned editorial root")
ensure(WebReaderProductionPublisherTrust.productionTrustGeneration == 0,
       "no trust root generation is enrolled")
let ios = OperatingSystemVersion(majorVersion: 12, minorVersion: 5, patchVersion: 8)
let file = URL(fileURLWithPath: "/definitely-nonexistent/WebReader-Build71-iOS12-adhoc.ipa")
let fixtures: [Data] = [
    Data(),
    Data("invalid-json".utf8),
    Data("{\"schemaVersion\":2}".utf8)
]
for fixture in fixtures {
    do {
        _ = try WebReaderProductionSignedIPAReview.inspectReadOnly(
            envelopeData: fixture,
            localIPAURL: file,
            installedBuild: 70,
            installedIOS: ios
        )
        fatalError("production IPA gate unexpectedly accepted with nil publisher")
    } catch WebReaderPublisherTrustError.noProvisionedOwnerTrust {
        // MUST reject before looking at malformed metadata or missing IPA.
    } catch {
        fatalError("production IPA gate reached untrusted input before nil-key denial")
    }
}
print("PASS CF: production signed-IPA read-only entry requires immutable owner-pinned root before I/O; NO installer")
'''

with tempfile.TemporaryDirectory(prefix="wr70-prod-local-ipa-gate-") as tmp:
    root = Path(tmp)
    source = root / "main.swift"
    app = root / "owner-ipa-gate"
    source.write_text(SWIFT, encoding="utf-8")
    subprocess.run(
        ["swiftc", "-swift-version", "5",
         *map(str, SOURCES), str(source),
         "-framework", "Security", "-o", str(app)],
        check=True, timeout=150
    )
    subprocess.run([str(app)], check=True, timeout=30)

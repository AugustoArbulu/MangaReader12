#!/usr/bin/env python3
"""Native Swift read-only, privacy-safe updater security report regression."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "MangaReader12/Core/WebReaderUpdaterSecuritySnapshot.swift"

# Minimal stand-ins let the actual report code be executed on macOS.
# Static tests separately verify the *production* properties remain fail-closed.
SWIFT = r'''
import Foundation

enum WebReaderUpdateChannel {
    static let productionPublicKeyX963: Data? = nil
    static var isConfigured: Bool { return productionPublicKeyX963 != nil }
}
enum WebReaderAppinstSocket {
    static let liveInstallationEnabled = false
}
func ensure(_ yes: @autoclosure () -> Bool, _ label: String) {
    if !yes() { fatalError(label) }
}
ensure(!WebReaderUpdaterSecuritySnapshot.installEnabled, "install disabled")
ensure(WebReaderUpdaterSecuritySnapshot.keyDescription.contains("ausente"),
       "production key must not be invented")
ensure(WebReaderUpdaterSecuritySnapshot.peerDescription.contains("não atestada"),
       "peer must not appear authenticated")
let text = WebReaderUpdaterSecuritySnapshot.safeReport(
    installedBuild: 68, iosVersion: "12.5.8"
)
ensure(text.contains("Build: 68 • iOS: 12.5.8"), "version available")
ensure(text.contains("GitHub Releases público"), "metadata explicitly unsigned")
ensure(text.contains("Instalação automática: bloqueada"), "install block clear")
ensure(text.contains("nenhuma instalação".capitalized) == false ||
       text.contains("Nenhuma instalação foi solicitada"),
       "no false success")
ensure(text.contains("Nenhuma instalação foi solicitada"), "not installing")
ensure(!text.contains("/var/mobile/"), "no personal paths")
ensure(!text.contains("I-CONFIRM-INSTALL"), "no privileged commands")
ensure(!text.contains("BEGIN PRIVATE KEY"), "no secret")
let signedBlocked = WebReaderUpdaterSecuritySnapshot.signedChannelReadinessReport(
    installedBuild: 68, iosVersion: "12.5.8",
    publicKeyPresent: false, independentPinPresent: false,
    trustGeneration: 0, verifiedReadiness: false
)
ensure(signedBlocked.contains("Chave pública editorial embutida: NÃO"), "public key absent")
ensure(signedBlocked.contains("Fingerprint SPKI independente embutido: NÃO"), "pin absent")
ensure(signedBlocked.contains("Consulta autenticada pronta: NÃO"), "channel disabled")
ensure(signedBlocked.contains("Instalação direta pelo Chimera: BLOQUEADA"), "helper denied")
ensure(signedBlocked.contains("\nBuild instalada: 68"), "diagnostic is multiline")
ensure(!signedBlocked.contains("/var/mobile/"), "no private paths")
ensure(!signedBlocked.contains("BEGIN PUBLIC KEY"), "no PEM")
ensure(!signedBlocked.contains("BEGIN PRIVATE KEY"), "no private key")
ensure(!signedBlocked.contains("appinst "), "no privileged install commands")
let contradictory = WebReaderUpdaterSecuritySnapshot.signedChannelReadinessReport(
    installedBuild: 68, iosVersion: "12.5.8",
    publicKeyPresent: false, independentPinPresent: true,
    trustGeneration: 1, verifiedReadiness: true
)
ensure(contradictory.contains("Consulta autenticada pronta: NÃO"),
       "an injected readiness claim never overrides absent public key")
let reviewedOnly = WebReaderUpdaterSecuritySnapshot.signedChannelReadinessReport(
    installedBuild: 69, iosVersion: "12.5.8",
    publicKeyPresent: true, independentPinPresent: true,
    trustGeneration: 1, verifiedReadiness: true
)
ensure(reviewedOnly.contains("Consulta autenticada pronta: SIM"),
       "synthetic ready view reflects a fully checked public trust root")
ensure(reviewedOnly.contains("Instalação direta pelo Chimera: BLOQUEADA"),
       "even a ready signed channel does not authorize installation")

let unknown = WebReaderUpdaterSecuritySnapshot.safeReport(
    installedBuild: -2, iosVersion: "../var/mobile/"
)
ensure(unknown.contains("Build: desconhecida • iOS: desconhecido"),
       "untrusted version is not echoed")
ensure(!unknown.contains("../"), "path traversal never echoed")
print("PASS native Swift safe updater diagnostics; no installer, key or personal data")
'''
with tempfile.TemporaryDirectory(prefix="wr68-updater-status-") as temp:
    root = Path(temp)
    runner = root / "main.swift"
    runner.write_text(SWIFT)
    binary = root / "security-snapshot"
    subprocess.run([
        "swiftc", "-swift-version", "5", str(SOURCE),
        str(runner), "-o", str(binary)
    ], check=True, timeout=120)
    subprocess.run([str(binary)], check=True, timeout=60)

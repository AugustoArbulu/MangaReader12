#!/usr/bin/env python3
"""Updater application screen wiring (host-only), no network or installation.

Native UIKit code is also compiled by the normal iOS12 Debug/Release build.
This prevents the Settings UI from accidentally enabling installation
before production release signing/Chimera-helper validation.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
tabs = (ROOT / "MangaReader12/UI/MainTabBarController.swift").read_text()
screen = (ROOT / "MangaReader12/UI/WebReaderAppUpdatesViewController.swift").read_text()
checker = (ROOT / "MangaReader12/Core/WebReaderUpdateChecker.swift").read_text()
project = (ROOT / "MangaReader12.xcodeproj/project.pbxproj").read_text()
helper = (ROOT / "MangaReader12/Core/WebReaderHelperPingProbe.swift").read_text()

assert "final class WebReaderAppUpdatesViewController: UITableViewController" in screen
assert "title = \"Atualizações do WebReader\"" in screen
assert "return 9" in tabs
assert "cell.textLabel?.text = \"Atualizações do WebReader\"" in tabs
assert "WebReaderAppUpdatesViewController()" in tabs
assert "cell.textLabel?.text = \"Atualização da Biblioteca\"" in tabs
assert "BackgroundLibraryUpdateManager.shared.isEnabled" in tabs
assert "WebReaderUpdateChannel.isConfigured" in screen
assert "WebReaderUpdateChecker(" in screen
assert "usePublicGitHubReleases: true" in screen
assert "WebReaderGitHubReleaseParser.swift in Sources" in project
assert "WebReaderReleaseHTTPSProbe()" in screen
assert 'cell.textLabel?.text = testingHTTPS ?' in screen
assert '"Testar HTTPS do GitHub"' in screen
assert 'UIPasteboard.general.string = lines.joined(separator: "\\n")' in screen
assert "return isIPCDiagnostic ? 2 : 6" in screen

assert "current.check { [weak self] result in" in screen
assert "statusDescription" in screen
assert "update.releaseNotes.joined(" in screen
assert "Bundle.main.object(forInfoDictionaryKey: \"CFBundleVersion\")" in screen
assert "Verificar atualizações" in screen
assert "GitHub Releases público • HTTPS" in screen
assert "instalação pelo Chimera ainda está em desenvolvimento" in screen
assert "Somente GitHub Releases públicos" in screen
assert "GitHub Actions não são atualizações disponíveis" in screen
assert "productionPublicKeyX963: Data? = nil" in checker
assert "static var isConfigured: Bool { return productionPublicKeyX963 != nil }" in checker
assert project.count("WebReaderAppUpdatesViewController.swift in Sources") == 2
assert project.count("WebReaderAppUpdatesViewController.swift */ = {isa = PBXFileReference") == 1
assert "A2000000000000000000002E /* WebReaderAppUpdatesViewController.swift */" in project
assert project.count("WebReaderReleaseHTTPSProbe.swift in Sources") == 2
assert "A2000000000000000000002F /* WebReaderReleaseHTTPSProbe.swift */" in project
assert "CURRENT_PROJECT_VERSION = 56;" in project
assert "WebReaderHelperPingProbe.run" in screen
assert "startHelperProbe()" in screen
assert "copyHelperDirectory()" in screen
assert "copyHelperReport()" in screen
assert '"Copiar relatório do helper"' in screen
assert '"Sem appinst, root, download ou instalação"' in screen
assert '"HELPER LOCAL (DIAGNÓSTICO)"' in screen
assert "NÃO autenticado" in helper
assert "static func inspect(directory override: URL? = nil)" in helper
assert 'private static let socketName = "wrp.sock"' in helper
assert project.count("WebReaderHelperPingProbe.swift in Sources") == 2
assert project.count("WebReaderHelperPingProbe.swift */ = {isa = PBXFileReference") == 1
assert "A20000000000000000000031 /* WebReaderHelperPingProbe.swift */" in project
assert "posix_spawn" not in helper
assert "appinst" not in helper or "install an IPA" in helper

# Explicit staging is allowed after a verified update and user confirmation.
assert 'if source == 2 { return availableUpdate != nil ? 5 : 1 }' in screen
assert '"Instalar atualização (Chimera)"' in screen
assert 'confirmAppinstInstallation()' in screen
assert 'WebReaderAppinstSocket.install(' in screen
assert 'title: "Confirmar instalação", style: .destructive' in screen
assert 'stagedSHA256 == update.sha256' in screen
assert 'self.stagedSHA256 = update.sha256' in screen
assert "WebReaderAppinstSocket.swift in Sources" in project
assert '"Copiar comando appinst (manual)"' in screen
assert 'copyManualAppinstCommand(file)' in screen
assert 'UIPasteboard.general.string = "appinst " + quotedPath' in screen
assert 'message: "A IPA já foi baixada e verificada.' in screen
assert '"Baixar IPA verificada"' in screen
assert "update.provenance == .publicGitHubRelease" in screen
assert '"Compartilhar IPA verificada"' in screen
assert 'UIAlertController(title: "Baixar IPA?"' in screen
assert 'WebReaderIPAStager(verifiedUpdate: update)' in screen
assert 'downloader.stage { [weak self, weak downloader] result in' in screen
assert 'let current = availableUpdate' in screen
assert 'WebReaderUpdateChannel.isConfigured' in screen
assert 'stager?.cancel()' in screen
assert 'UIActivityViewController(activityItems: [url]' in screen
assert '"https://github.com/AugustoArbulu/MangaReader12/releases"' in screen
assert 'guard !isIPCDiagnostic' in screen
# No automatic installation, root helper or shell execution in UIKit.
for forbidden in ("appinst(", "Process(", "posix_spawn(", "dlopen(", "system("):
    assert forbidden not in screen, forbidden

print("PASS WebReader iOS12 update UI: signed manual staging/share; no install")

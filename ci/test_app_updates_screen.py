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
assert "WebReaderReleaseHTTPSProbe()" in screen
assert 'cell.textLabel?.text = testingHTTPS ?' in screen
assert '"Testar HTTPS do GitHub"' in screen
assert 'UIPasteboard.general.string = lines.joined(separator: "\\n")' in screen
assert "return isIPCDiagnostic ? 2 : 6" in screen

assert "current.check { [weak self] result in" in screen
assert "statusDescription" in screen
assert "update.releaseNotes.joined(" in screen
assert "Bundle.main.object(forInfoDictionaryKey: \"CFBundleVersion\")" in screen
assert "Verificação indisponível" in screen
assert "ainda não está configurado" in screen
assert "instalação pelo Chimera ainda está em desenvolvimento" in screen
assert "Apenas releases publicados e autenticados" in screen
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
assert '"HELPER LOCAL (DIAGNÓSTICO)"' in screen
assert "NÃO autenticado" in helper
assert "static func inspect(directory override: URL? = nil)" in helper
assert 'private static let socketName = "wrp.sock"' in helper
assert project.count("WebReaderHelperPingProbe.swift in Sources") == 2
assert project.count("WebReaderHelperPingProbe.swift */ = {isa = PBXFileReference") == 1
assert "A20000000000000000000031 /* WebReaderHelperPingProbe.swift */" in project
assert "posix_spawn" not in helper
assert "appinst" not in helper or "install an IPA" in helper

# No installer, automatic download, root helper or shell execution in UI.
for forbidden in ("appinst(", "Process(", "posix_spawn", ".stage(", "dlopen(", "system("):
    assert forbidden not in screen, forbidden

print("PASS WebReader iOS12 updater screen wiring, fail-closed status, no install")

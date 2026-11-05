#!/usr/bin/env python3
"""Host-only isolation assertions for the WebReader IPC diagnostic IPA.

CI also builds iOS 12 Debug/Release after these assertions.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
delegate = (ROOT / "MangaReader12/AppDelegate.swift").read_text()
ui = (ROOT / "MangaReader12/UI/WebReaderAppUpdatesViewController.swift").read_text()
package = (ROOT / "ci/package_ipc_probe_ipa.sh").read_text()
manifest = (ROOT / "MangaReader12/Core/WebReaderUpdateChecker.swift").read_text()
probe = (ROOT / "MangaReader12/Core/WebReaderHelperPingProbe.swift").read_text()

assert 'Bundle.main.bundleIdentifier == "com.example.MangaReader12.ipcprobe"' in delegate
assert 'return UINavigationController(' in delegate
assert 'rootViewController: WebReaderAppUpdatesViewController()' in delegate
assert 'window.rootViewController = makeRootController()' in delegate
assert 'if !isIPCProbe {' in delegate
assert 'BackgroundLibraryUpdateManager.shared.applyScheduling()' in delegate
assert 'guard !isIPCProbe else {' in delegate
assert 'completionHandler(.noData)' in delegate
assert 'let root = makeRootController()' in delegate
assert 'info["CFBundleIdentifier"] = "com.example.MangaReader12.ipcprobe"' in package
assert 'info["CFBundleDisplayName"] = "WebReader IPC Test"' in package
assert 'return isIPCDiagnostic ? 2 : 6' in ui
assert 'return isIPCDiagnostic && displayedSection == 1 ? 5 : displayedSection' in ui
assert 'switch (sectionType(indexPath.section), indexPath.row)' in ui
assert 'let selectedSection = sectionType(indexPath.section)' in ui
assert 'WebReaderHelperPingProbe.run' in ui
assert '"Testar ponte appinst (PING)"' in ui
assert 'WebReaderAppinstSocket.checkConnection' in ui
assert '"Copiar relatório do helper"' in ui
assert '"Bundle: " + (Bundle.main.bundleIdentifier ?? "desconhecido")' in ui
assert '"HELPER LOCAL (DIAGNÓSTICO)"' in ui
assert 'productionPublicKeyX963: Data? = nil' in manifest
assert '"WRPING1\\n"' in probe and '"WRPONG1\\n"' in probe

for forbidden in ('appinst(', 'posix_spawn(', 'system(', 'dlopen('):
    assert forbidden not in probe
print("PASS: standalone IPC diagnostic launches safely; stable app path preserved")

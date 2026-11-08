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
assert "return isIPCDiagnostic ? 2 : 7" in screen
assert 'if source == 6 { return 8 }' in screen
assert '"IPA LOCAL (ARQUIVOS OU FILZA)"' in screen
assert "if source == 5 { return build60DisposableAvailable ? 6 : (pairingDiagnosticAvailable ? 5 : 4) }" in screen

assert "current.check { [weak self] result in" in screen
assert "statusDescription" in screen
assert "update.releaseNotes.joined(" in screen
assert "Bundle.main.object(forInfoDictionaryKey: \"CFBundleVersion\")" in screen
assert "Verificar atualizações" in screen
assert "GitHub Releases • HTTPS • sem autenticação editorial independente" in screen
assert "instalação pelo Chimera ainda está em desenvolvimento" in screen
assert "A consulta pública usa apenas GitHub Releases" in screen
assert "Builds privadas do Actions" in screen
assert "Verificar canal assinado" in screen
assert "Abrir Builds privadas no GitHub Actions" in screen
assert "WebReaderProductionSignedReleaseChecker(" in screen
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
assert '"Nenhum comando appinst executado neste diagnóstico"' in screen
assert '"Testar ponte appinst (PING)"' in screen
assert "WebReaderAppinstSocket.checkConnection" in screen
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
assert 'if source == 2 { return availableUpdate != nil ? 6 : 1 }' in screen
assert 'case (2, 5):' in screen
assert 'copyStagedIPAReceipt()' in screen
assert 'if source == 5 { return build60DisposableAvailable ? 6 : (pairingDiagnosticAvailable ? 5 : 4) }' in screen
assert '"Instalar atualização (Chimera)"' not in screen
assert 'build60DisposableAvailable' in screen
assert '"Teste completo Build 60"' in screen
assert 'copyBuild60DisposableProcedure()' in screen
# The consent literal appears inside the complete terminal command, not
# as a separate quoted Swift expression.
assert 'run-disposable-qa I-CONFIRM-DISPOSABLE-ONLY' in screen
assert 'WebReader-Chimera-Disposable-Gate-iOS12' in screen
# Build62: public GitHub SHA256 + localhost must never reach appinst.
assert 'confirmAppinstInstallation()' not in screen
assert 'requestAppinstInstallation(' not in screen
assert 'WebReaderAppinstSocket.install(' not in screen
assert 'Instalação pelo Chimera bloqueada' in screen
assert 'Aguardando política independente de autorização e chave editorial' in screen
assert 'if selectedSection == 2, indexPath.row == 3 {' in screen
assert "showFilzaInstructions()" in screen
assert 'if selectedSection == 2, indexPath.row == 4 { return }' in screen
assert 'self.stagedSHA256 = update.sha256' in screen
assert "WebReaderAppinstSocket.swift in Sources" in project
assert '"Copiar comando appinst (manual)"' not in screen
assert 'copyManualAppinstCommand(' not in screen
assert 'UIPasteboard.general.string = "appinst "' not in screen
assert '"Como instalar pelo Filza"' in screen
assert '"Instalação manual no Filza"' in screen
assert '"Baixar e conferir IPA"' in screen
assert "update.provenance == .publicGitHubRelease" in screen
assert '"Compartilhar IPA conferida"' in screen
assert 'UIAlertController(title: "Baixar IPA?"' in screen
assert 'let downloader = WebReaderIPAStager(' in screen
assert 'verifiedUpdate: update,' in screen
assert 'onProgress:' in screen
assert 'downloader.stage { [weak self, weak downloader] result in' in screen
assert 'let current = availableUpdate' in screen
assert 'WebReaderUpdateChannel.isConfigured' in screen
assert 'stager?.cancel()' in screen
assert 'UIActivityViewController(activityItems: [url]' in screen
# Public Release discovery is not independent publisher authentication.
assert '"GitHub Releases • HTTPS • sem autenticação editorial independente"' in screen
assert '"GitHub Releases indisponível: sem release ou repositório privado"' in screen
assert '"Metadados do GitHub não têm assinatura editorial independente. "' in screen
assert '"SHA-256 e estrutura IPA conferidos • instalação manual"' in screen
assert "verifyingExport" in screen
assert "WebReaderNativeIPAAuditor.inspect(" in screen
assert 'self.ipaStatus = "IPA alterada ou inválida; baixe novamente"' in screen
assert 'guard self.view.window != nil else { return }' in screen
assert '"https://github.com/AugustoArbulu/MangaReader12/releases"' in screen
assert 'guard !isIPCDiagnostic' in screen
# No automatic installation, root helper or shell execution in UIKit.
for forbidden in ("appinst(", "Process(", "posix_spawn(", "dlopen(", "system("):
    assert forbidden not in screen, forbidden

print("PASS WebReader iOS12 update UI: verified export only; no install IPC or copied appinst command")

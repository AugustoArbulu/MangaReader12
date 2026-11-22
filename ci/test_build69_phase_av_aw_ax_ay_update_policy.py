#!/usr/bin/env python3
"""Build69 AV-AY fail-closed update discovery and offline diagnostic contract."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "MangaReader12/Core"


class FullValidationBeforeUpToDate(unittest.TestCase):
    def test_signed_old_build_must_pass_every_policy_gate(self):
        code = (CORE / "WebReaderUpdateManifestVerifier.swift").read_text()
        self.assertIn("guard let build = exactInteger(manifest[\"build\"])", code)
        self.assertIn("throw WebReaderUpdateValidationError.disallowedURL", code)
        self.assertIn("throw WebReaderUpdateValidationError.invalidPayload", code)
        self.assertIn("guard build > installedBuild else", code)
        self.assertLess(
            code.index("throw WebReaderUpdateValidationError.disallowedURL"),
            code.index("guard build > installedBuild else")
        )
        self.assertLess(
            code.index("components.percentEncodedPath =="),
            code.index("guard build > installedBuild else")
        )
        self.assertIn("throw WebReaderUpdateValidationError.notNewer", code)

    def test_public_old_build_must_have_full_valid_release_asset(self):
        code = (CORE / "WebReaderGitHubReleaseParser.swift").read_text()
        self.assertIn("guard selected.count == 1 else", code)
        self.assertIn('digestField.hasPrefix("sha256:")', code)
        self.assertIn("components.percentEncodedPath ==", code)
        self.assertIn("guard build > installedBuild else { return .upToDate }", code)
        self.assertLess(
            code.index("guard selected.count == 1 else"),
            code.index("guard build > installedBuild else { return .upToDate }")
        )
        self.assertLess(
            code.index("let digest = String(digestField.dropFirst(7))"),
            code.index("guard build > installedBuild else { return .upToDate }")
        )

    def test_provenance_enforced_by_live_release_downloader(self):
        code = (CORE / "WebReaderIPAStager.swift").read_text()
        self.assertIn("switch update.provenance", code)
        self.assertIn("case .signedManifest:", code)
        self.assertIn("case .publicGitHubRelease:", code)
        self.assertIn("case .manualLocalFile:", code)
        self.assertIn("allowedPaths = []", code)
        self.assertIn("allowedPaths = testProtocolClasses == nil ?", code)
        self.assertIn("[signedV2Path] : [legacyPath, signedV2Path]", code)
        self.assertIn("allowedPaths.contains(components.percentEncodedPath)", code)
        self.assertIn("callback(.failed(.invalidRelease))", code)

    def test_ui_has_only_offline_copyable_readiness_report(self):
        code = (ROOT / "MangaReader12/UI/WebReaderAppUpdatesViewController.swift").read_text()
        diag = (CORE / "WebReaderUpdaterSecuritySnapshot.swift").read_text()
        self.assertIn("if source == 1 { return 5 }", code)
        self.assertIn('cell.textLabel?.text = "Copiar diagnóstico do canal assinado"', code)
        self.assertIn("private func copySignedChannelReadinessReport()", code)
        self.assertIn("guard !isIPCDiagnostic else { return }", code)
        self.assertIn("WebReaderUpdaterSecuritySnapshot.signedChannelReadinessReport(", code)
        self.assertIn("UIPasteboard.general.string = report", code)
        self.assertIn("trustGeneration: WebReaderProductionPublisherTrust.productionTrustGeneration", code)
        self.assertIn("verifiedReadiness: WebReaderProductionPublisherTrust.isProvisioned", code)
        self.assertIn("Nenhuma IPA foi baixada ou instalada por este relatório.", diag)
        self.assertIn("Instalação direta pelo Chimera: BLOQUEADA", diag)
        self.assertIn("Este relatório não consulta a rede", diag)
        self.assertNotIn("privateKey", diag)
        self.assertNotIn("SecItemAdd", diag)
        self.assertNotIn("appinst(", diag)
        self.assertNotIn("URLSession(", diag)


if __name__ == "__main__":
    unittest.main()

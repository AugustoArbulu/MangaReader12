#!/usr/bin/env python3
"""Manual updater MVP contract: GitHub -> verified staging -> Filza.
No GitHub calls, IPA publication, appinst, signing, installation, or device I/O.
"""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parent.parent
CORE=ROOT/"MangaReader12/Core"
UI=(ROOT/"MangaReader12/UI/WebReaderAppUpdatesViewController.swift").read_text()
CHECKER=(CORE/"WebReaderUpdateChecker.swift").read_text()
PARSER=(CORE/"WebReaderGitHubReleaseParser.swift").read_text()
STAGER=(CORE/"WebReaderIPAStager.swift").read_text()
HELPER=(CORE/"WebReaderAppinstSocket.swift").read_text()

class PersonalUpdaterMVPContract(unittest.TestCase):
    def test_release_is_fixed_public_endpoint_and_never_actions_artifact(self):
        self.assertIn("https://api.github.com/repos/AugustoArbulu/MangaReader12/releases/latest",PARSER)
        self.assertIn('components.scheme == "https"',PARSER)
        self.assertIn('components.host == "github.com"',PARSER)
        self.assertIn('"digest"',PARSER)
        self.assertIn('"uploaded"',PARSER)
        self.assertIn("selected.count == 1",PARSER)
        self.assertIn("usePublicGitHubReleases: true",UI)
        self.assertNotIn('usePublicGitHubReleases: false',UI)

    def test_no_release_is_not_misreported_as_up_to_date(self):
        self.assertIn("finish(.failed(.unexpectedHTTPStatus(http.statusCode)))",CHECKER)
        self.assertIn("if status == 404",UI)
        self.assertIn("HTTP 404: nenhuma Release pública acessível; não há IPA para baixar",UI)
        self.assertNotIn("case .unexpectedHTTPStatus(404): return .upToDate",CHECKER)

    def test_download_requires_consent_then_integrity_and_manual_share(self):
        for needle in ("confirmIPADownload()", "startIPADownload(update)",
                       "WebReaderIPAStager(", "WebReaderNativeIPAAuditor.inspect(",
                       "UIActivityViewController(activityItems: [url]",
                       "showFilzaInstructions()"):
            self.assertIn(needle,UI)
        self.assertIn("update.build > currentBuild",STAGER)
        self.assertIn("WebReaderIPADownloadBudget.enoughSpace(",STAGER)
        self.assertIn('case .publicGitHubRelease:',STAGER)
        self.assertIn('sha256.range(',STAGER)

    def test_appinst_only_diagnostic_while_peer_is_unproven(self):
        self.assertIn("static let liveInstallationEnabled = false",HELPER)
        self.assertIn("DispatchQueue.main.async { completion(.rejected) }",HELPER)
        self.assertNotIn("WebReaderAppinstSocket.install(",UI)
        self.assertIn("Instalação pelo Chimera bloqueada",UI)
        self.assertIn("Como instalar pelo Filza",UI)

    def test_no_prod_publisher_trust_bootstrapped_from_release(self):
        prod=(CORE/"WebReaderProductionPublisherTrust.swift").read_text()
        self.assertIn("independentlyProvisionedSPKISHA256: String? = nil",prod)
        self.assertIn("productionPublicKeyX963: Data? = nil",CHECKER)
        self.assertNotIn('releaseManifestDestination = "main"',UI)
        self.assertIn("WebReaderSignedProductionEnvelopeBinding",STAGER)

if __name__=="__main__":
    unittest.main()

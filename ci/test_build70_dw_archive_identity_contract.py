#!/usr/bin/env python3
"""DW: archive audit workflow is pinned, read-only, and never installs."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github/workflows/chimera-build70-phase-dw-archive-identity.yml"


class DWArchivedQAContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = WORKFLOW.read_text(encoding="utf-8")

    def test_two_host_jobs_require_macos_native_codesign(self):
        self.assertIn("linux-archived-qa-contract:", self.source)
        self.assertIn("macos-original-build70-native-audit:", self.source)
        self.assertIn("macos-15", self.source)
        self.assertIn("ci/build70_private_qa_ipa_preflight.py", self.source)
        self.assertIn("Xcode_16.4.app", self.source)

    def test_archived_artifact_is_immutable_reference_not_latest(self):
        self.assertIn("run-id: 42705903886", self.source)
        self.assertIn("WebReader-Build70-OwnerApproved-iOS12-QA-Filza", self.source)
        # ubuntu-latest is a runner label, not a mutable artifact selector.
        self.assertNotIn("run-id: latest", self.source.lower())
        self.assertNotIn("run-id: $", self.source.lower())

    def test_actual_historical_ipa_hash_and_cdhash_pinned(self):
        for fact in (
            "526291cc77203c3881e5f3f1c75904e8863dbde3b3bd9df7e1185c3229fb4fc1",
            "e0de7f55a2684da7507c3a862247480bd05c39bd",
            "17845463",
            "ae931abb725977a417a1fcb20b79c82af825dd55",
        ):
            self.assertIn(fact, self.source)

    def test_identity_is_historical_and_not_peer_attestation(self):
        self.assertIn("AR5SFJC432.com.example.MangaReader12.AR5SFJC432", self.source)
        self.assertIn("current iPad bundle identity", self.source)
        self.assertIn("installationAuthorized", self.source)
        self.assertIn("installationPerformed", self.source)

    def test_permissions_are_readonly_and_not_a_release(self):
        self.assertIn("permissions:\n  contents: read\n  actions: read\n", self.source)
        for forbidden in (
            "actions/upload-artifact", "gh release", "git push",
            "appinst ", "scp ", "curl -X POST",
        ):
            self.assertNotIn(forbidden, self.source)

    def test_no_pr_untrusted_artifact_download_trigger(self):
        self.assertIn("  workflow_dispatch:\n", self.source)
        self.assertIn("  push:\n", self.source)
        self.assertNotIn("  pull_request:\n", self.source)
        self.assertIn("cancel-in-progress: true", self.source)
        self.assertIn("github.repository == 'AugustoArbulu/MangaReader12'", self.source)

    def test_production_trust_and_installer_remain_disabled(self):
        sources = (
            ("MangaReader12/Core/WebReaderUpdateChecker.swift",
             "static let productionPublicKeyX963: Data? = nil"),
            ("MangaReader12/Core/WebReaderProductionPublisherTrust.swift",
             "static let independentlyProvisionedSPKISHA256: String? = nil"),
            ("MangaReader12/Core/WebReaderAppinstSocket.swift",
             "static let liveInstallationEnabled = false"),
        )
        for path, token in sources:
            with self.subTest(path=path):
                self.assertIn(token, (ROOT/path).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

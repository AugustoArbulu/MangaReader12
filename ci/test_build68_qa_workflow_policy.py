#!/usr/bin/env python3
"""Build68 private/manual Actions artifact must never turn into auto-updater."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = (ROOT / ".github/workflows/chimera-build68-private-manual-qa.yml").read_text()
PACKAGE = (ROOT / "ci/package_webreader_build68_rehearsal.sh").read_text()
AUDIT = (ROOT / "ci/audit_webreader_build68_rehearsal.py").read_text()
DELIVERY = (ROOT / "ci/build68_private_manual_qa_delivery.py").read_text()
CHECKLIST = (ROOT / "docs/WEBREADER_BUILD68_PRIVATE_MANUAL_QA_CHECKLIST_2026-11-08.md").read_text()
PROJECT = (ROOT / "MangaReader12.xcodeproj/project.pbxproj").read_text()
CHECKER = (ROOT / "MangaReader12/Core/WebReaderUpdateChecker.swift").read_text()
APPINST = (ROOT / "MangaReader12/Core/WebReaderAppinstSocket.swift").read_text()


class ManualBuild68PublishPolicy(unittest.TestCase):
    def test_candidate_can_only_be_triggered_by_unique_explicit_stamp(self):
        self.assertIn("  push:", WORKFLOW)
        self.assertIn("      - feat/chimera-updater-phase1-protocol-audit", WORKFLOW)
        self.assertIn("      - 'ci/build68_candidate_trigger.txt'", WORKFLOW)
        self.assertNotIn("  workflow_dispatch:", WORKFLOW)
        self.assertIn('test "$GITHUB_EVENT_NAME" = "push"', WORKFLOW)
        self.assertIn('test "$GITHUB_REF_NAME" = "feat/chimera-updater-phase1-protocol-audit"', WORKFLOW)
        self.assertIn("WEBREADER_BUILD68_PRIVATE_MANUAL_QA_ONLY_NO_RELEASE_NO_INSTALL", WORKFLOW)
        self.assertIn("contents: read", WORKFLOW)

    def test_only_private_owner_artifact_and_no_external_release(self):
        self.assertIn("actions/upload-artifact@v4", WORKFLOW)
        self.assertIn("retention-days: 14", WORKFLOW)
        self.assertIn("WebReader-Build68-PRIVATE-ManualQA-Filza-iOS12", WORKFLOW)
        self.assertIn("WebReader-Build68-source-provenance.json", WORKFLOW)
        self.assertNotIn("actions/create-release", WORKFLOW)
        self.assertNotIn("gh release", WORKFLOW)
        self.assertNotIn("curl --upload-file", WORKFLOW)
        self.assertNotIn("actions/upload-release-asset", WORKFLOW)
        self.assertNotIn("apple-actions/upload-testflight-build", WORKFLOW)
        self.assertNotIn("appinst ", WORKFLOW)

    def test_package_preserves_legacy_ownership_and_ad_hoc_entitlement(self):
        for phrase in (
            'basename "$OUTPUT"',
            'WebReader-Build68-iOS12-adhoc.ipa',
            'assert info.get("CFBundleIdentifier") == "com.example.MangaReader12"',
            'assert info.get("MinimumOSVersion") == "12.0"',
            'assert info.get("CFBundleVersion") == "56"',
            'info["CFBundleVersion"] = "68"',
            'assert info["CFBundleVersion"] == "68"',
            'codesign --force --sign -',
            'codesign --verify',
            'AR5SFJC432.com.example.MangaReader12.AR5SFJC432',
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, PACKAGE)
        for blocked in ("gh release", "appinst(", "posix_spawn(", "launchctl", "sudo appinst"):
            self.assertNotIn(blocked, PACKAGE)

    def test_native_audit_and_exact_byte_sha_gate_both_required(self):
        self.assertIn("audit_webreader_build68_rehearsal.py", WORKFLOW)
        self.assertIn("build68_private_manual_qa_delivery.py", WORKFLOW)
        for phrase in (
            'result["build"] != 68',
            '"build": 68',
            '"upgradesFromObservedBuild": 66',
            '"nativeAdHocCodeIntegrityVerified": True',
            '"thinArm64Verified": True',
            '"sameInstalledEntitlementIdentifier": True',
            '"installationAuthorized": False',
            '"approvedForAutomaticRelease": False',
        ):
            self.assertIn(phrase, AUDIT)
        for phrase in (
            'receipt["build"] != 68',
            'receipt["upgradesFromObservedBuild"] != 66',
            "current_hash = _hash_ipa(",
            '"WebReader-Build68-private-rehearsal-audit.json"',
            "installationPerformed: bool = False",
            "privateManualQAArtifactEligible: bool = True",
        ):
            self.assertIn(phrase, DELIVERY)

    def test_no_prod_key_helper_main_or_protected_data_changes(self):
        self.assertEqual(PROJECT.count("CURRENT_PROJECT_VERSION = 56;"), 2)
        self.assertIn("static let liveInstallationEnabled = false", APPINST)
        self.assertIn("static let productionPublicKeyX963: Data? = nil", CHECKER)
        self.assertIn("Não apague ou desinstale o WebReader", CHECKLIST)
        self.assertIn("Build 66", CHECKLIST)
        self.assertIn("Capítulos offline", CHECKLIST)
        self.assertIn("Nunca", CHECKLIST + "Nunca")  # Portuguese safe manual QA
        self.assertNotIn("git checkout main", WORKFLOW)
        self.assertNotIn("git push", WORKFLOW)


if __name__ == "__main__":
    unittest.main()

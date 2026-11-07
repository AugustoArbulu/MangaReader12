#!/usr/bin/env python3
"""Offline private/manual Build66 delivery gate tests (NO real IPA or install).

Positive fixture is synthetic bytes plus a synthetic audit JSON; its success
only means the transfer-sidecar consistency gate works. The real workflow
MUST run native macOS codesign + structural audit BEFORE calling this gate.
"""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from build66_private_manual_qa_delivery import (
    IPA_NAME, EXPECTED_ID, ManualQADeliveryRejected,
    verify_private_manual_qa,
)

class ManualQADeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="wr66-qa-handoff-")
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.ipa = root / IPA_NAME
        self.ipa.write_bytes(b"ONLY A SYNTHETIC TEST FIXTURE; NOT AN INSTALLABLE IPA")
        self.sha = root / (IPA_NAME + ".sha256")
        self.report = root / "WebReader-Build66-private-rehearsal-audit.json"
        self.receipt = {
            "status": "PASS", "qaArtifact": IPA_NAME,
            "build": 66, "upgradesFromObservedBuild": 65,
            "minimumIOS": "12.0", "ipaBytes": self.ipa.stat().st_size,
            "ipaSHA256": hashlib.sha256(self.ipa.read_bytes()).hexdigest(),
            "bundleID": "com.example.MangaReader12",
            "applicationIdentifier": EXPECTED_ID,
            "nativeAdHocCodeIntegrityVerified": True,
            "thinArm64Verified": True,
            "sameInstalledEntitlementIdentifier": True,
            "productionPublisherAuthenticated": False,
            "releaseManifestIndependentlySigned": False,
            "ios12DeviceInstallTested": False,
            "userConsentVerified": False,
            "helperPeerAuthenticated": False,
            "installationAuthorized": False,
            "installationPerformed": False,
            "approvedForAutomaticRelease": False,
        }
        self.write_receipt()
        self.write_sha()

    def write_receipt(self):
        self.report.write_text(json.dumps(self.receipt) + "\n")

    def write_sha(self):
        self.sha.write_text(self.receipt["ipaSHA256"] + "  " + IPA_NAME + "\n")

    def call(self):
        return verify_private_manual_qa(self.ipa, self.sha, self.report)

    def refuse(self):
        with self.assertRaises(ManualQADeliveryRejected):
            self.call()

    def test_synthetic_sidecars_consistent_only_for_private_transfer(self):
        item = self.call()
        self.assertEqual(item.build, 66)
        self.assertEqual(item.installedBuildReference, 65)
        self.assertEqual(item.artifact, IPA_NAME)
        self.assertEqual(item.sha256, self.receipt["ipaSHA256"])
        self.assertTrue(item.privateManualQAArtifactEligible)
        self.assertTrue(item.userBackupAndRollbackRequiredBeforeInstall)
        self.assertTrue(item.checksumReverificationRequiredAfterTransfer)
        for key in ("releasePublisherAuthenticated", "automaticUpdateEnabled",
                    "deviceInstallValidated", "userApprovedInstallation",
                    "privilegedHelperAuthenticated", "installationAuthorized",
                    "installationPerformed"):
            self.assertFalse(asdict(item)[key])

    def test_change_candidate_bytes(self):
        self.ipa.write_bytes(self.ipa.read_bytes() + b"forged")
        self.refuse()

    def test_replace_candidate_with_symlink(self):
        other = self.ipa.with_name("fake.ipa")
        self.ipa.rename(other)
        self.ipa.symlink_to(other)
        self.refuse()

    def test_replace_checksum_with_symlink(self):
        other = self.sha.with_name("other.sha256")
        self.sha.rename(other)
        self.sha.symlink_to(other)
        self.refuse()

    def test_replace_report_with_symlink(self):
        other = self.report.with_name("other.json")
        self.report.rename(other)
        self.report.symlink_to(other)
        self.refuse()

    def test_missing_candidate(self):
        self.ipa.unlink()
        self.refuse()

    def test_missing_report(self):
        self.report.unlink()
        self.refuse()

    def test_missing_checksum(self):
        self.sha.unlink()
        self.refuse()

    def test_checksum_wrong_hash(self):
        self.sha.write_text("0"*64 + "  " + IPA_NAME + "\n")
        self.refuse()

    def test_checksum_wrong_target(self):
        self.sha.write_text(self.receipt["ipaSHA256"] + "  different.ipa\n")
        self.refuse()

    def test_checksum_second_line(self):
        self.sha.write_text(self.sha.read_text() + "extra\n")
        self.refuse()

    def test_checksum_missing_trailing_newline(self):
        self.sha.write_text(self.sha.read_text().strip())
        self.refuse()

    def test_checksum_not_ascii(self):
        self.sha.write_bytes(self.sha.read_bytes() + b"\xff")
        self.refuse()

    def test_checksum_extra_tab(self):
        self.sha.write_text(self.receipt["ipaSHA256"] + "\t" + IPA_NAME + "\n")
        self.refuse()

    def test_receipt_wrong_filename(self):
        self.receipt["qaArtifact"] = "WebReader-Build65-iOS12-adhoc.ipa"
        self.write_receipt()
        self.refuse()

    def test_receipt_wrong_build(self):
        self.receipt["build"] = 67
        self.write_receipt()
        self.refuse()

    def test_receipt_wrong_older_build(self):
        self.receipt["upgradesFromObservedBuild"] = 56
        self.write_receipt()
        self.refuse()

    def test_receipt_wrong_ios(self):
        self.receipt["minimumIOS"] = "13.0"
        self.write_receipt()
        self.refuse()

    def test_receipt_wrong_bundle(self):
        self.receipt["bundleID"] = "com.example.MangaReader12.ipcprobe"
        self.write_receipt()
        self.refuse()

    def test_receipt_wrong_entitlement(self):
        self.receipt["applicationIdentifier"] = "ADVERSARY.com.example.MangaReader12"
        self.write_receipt()
        self.refuse()

    def test_receipt_forged_sha(self):
        self.receipt["ipaSHA256"] = "0"*64
        self.write_receipt()
        self.refuse()

    def test_receipt_wrong_size(self):
        self.receipt["ipaBytes"] += 1
        self.write_receipt()
        self.refuse()

    def test_receipt_unsigned_claim(self):
        self.receipt["nativeAdHocCodeIntegrityVerified"] = False
        self.write_receipt()
        self.refuse()

    def test_receipt_not_arm64(self):
        self.receipt["thinArm64Verified"] = False
        self.write_receipt()
        self.refuse()

    def test_receipt_entitlement_mismatch(self):
        self.receipt["sameInstalledEntitlementIdentifier"] = False
        self.write_receipt()
        self.refuse()

    def test_claim_automatic_install_authorized(self):
        for key in ("installationAuthorized", "installationPerformed",
                    "approvedForAutomaticRelease", "helperPeerAuthenticated",
                    "userConsentVerified", "ios12DeviceInstallTested",
                    "productionPublisherAuthenticated",
                    "releaseManifestIndependentlySigned"):
            with self.subTest(key=key):
                self.receipt[key] = True
                self.write_receipt()
                self.refuse()
                self.receipt[key] = False

    def test_boolean_build_rejected(self):
        self.receipt["build"] = True
        self.write_receipt()
        self.refuse()

    def test_boolean_size_rejected(self):
        self.receipt["ipaBytes"] = True
        self.write_receipt()
        self.refuse()

    def test_missing_audit_field(self):
        self.receipt.pop("sameInstalledEntitlementIdentifier")
        self.write_receipt()
        self.refuse()

    def test_duplicate_json_field(self):
        self.report.write_text('{"status":"PASS","status":"FAIL"}')
        self.refuse()

    def test_nonobject_json(self):
        self.report.write_text('[]')
        self.refuse()

    def test_oversized_json(self):
        self.report.write_bytes(b"z"*8193)
        self.refuse()

    def test_wrong_input_path(self):
        other = self.ipa.with_name("WebReader-Build66-iOS12-unsigned.ipa")
        other.write_bytes(self.ipa.read_bytes())
        with self.assertRaises(ManualQADeliveryRejected):
            verify_private_manual_qa(other, self.sha, self.report)

    def test_manual_gate_does_not_prove_signature_of_synthetic_fixture(self):
        # The purpose here is deliberately limited: this Python transfer gate
        # does not inspect Mach-O/codesign. The independent native audit step
        # is a REQUIRED, preceding part of the real macOS workflow.
        self.assertTrue(self.call().privateManualQAArtifactEligible)
        self.assertFalse(self.call().releasePublisherAuthenticated)

if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""DS macOS: actual Apple ad-hoc QA fixture, never a real WebReader IPA.

Reuses the existing DI disposable native compiler/signing harness, but passes
its REAL ZIP bytes through DS with synthetic DQ/DO text. No iPad, no install.
"""
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

import test_build70_di_build71_private_qa_native as di_native
from build70_ds_candidate_evidence_gate import DSRejected, inspect_ds_preupgrade_candidate
from build70_di_build71_private_qa_preflight import QA_FILENAME
from test_build70_dq_installed_bundle_report import synthetic
from test_build70_do_preupgrade_baseline_audit import continuity, offline


@unittest.skipUnless(sys.platform == "darwin", "requires macOS codesign and iphoneos SDK")
class DSNativeSignedIPASnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="wr-ds-synthetic-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.ipa = self.root / QA_FILENAME

    def build(self, **kwargs):
        di_native.DINativeBuild71QATests.build_disposable_ipa(self, **kwargs)

    def audit(self, **kwargs):
        return inspect_ds_preupgrade_candidate(
            dq_report=kwargs.get("dq_report", synthetic()+b"\n"),
            sqlite_count_report=continuity(),
            offline_reports=[offline()],
            ipa_path=self.ipa,
            checksum_data=kwargs.get("checksum_data", self.checksum),
        )

    def test_real_native_adhoc_synthetic_build71_plus_dq_do_no_install(self):
        self.build()
        report = self.audit()
        self.assertEqual(
            report["status"], "DS_HOST_TEXT_AND_SIGNED_CANDIDATE_COHERENT_NOT_INSTALLABLE"
        )
        self.assertEqual(report["candidateIPAStaticSHA256"], self.digest)
        self.assertEqual(report["candidateBuildHostVerified"], 71)
        self.assertTrue(report["ipaAdHocSealCheckedOnHost"])
        self.assertFalse(report["physicalInstalledBuild70IdentityCryptographicallyVerified"])
        self.assertFalse(report["publisherAuthenticated"])
        self.assertFalse(report["readyToDistributeIPA"])
        self.assertFalse(report["installationAuthorized"])
        self.assertFalse(report["installationPerformed"])

    def test_native_adhoc_wrong_signed_entitlement_blocks_ds(self):
        self.build(entitlement="OTHER.com.example.MangaReader12")
        with self.assertRaises(DSRejected):
            self.audit()

    def test_native_adhoc_tampered_after_codesign_blocks_ds(self):
        self.build(alter_signed_exe=True)
        with self.assertRaises(DSRejected):
            self.audit()

    def test_native_signed_candidate_cannot_override_dq_identity_mismatch(self):
        self.build()
        with self.assertRaises(DSRejected):
            self.audit(dq_report=synthetic(build="71")+b"\n")

    def test_native_checksum_does_not_survive_changed_bytes(self):
        self.build()
        original_checksum = self.checksum
        self.ipa.write_bytes(self.ipa.read_bytes()+b"POST-DIGEST-TAMPER")
        with self.assertRaises(DSRejected):
            self.audit(checksum_data=original_checksum)


if __name__ == "__main__":
    unittest.main()

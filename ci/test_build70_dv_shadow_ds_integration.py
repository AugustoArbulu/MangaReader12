#!/usr/bin/env python3
"""DV: synthetic DQ/DO claims + complete app DS code path host regressions.

No real device identity, no installed data, no IPA and no Apple code signing
are created by this file. macOS DL workflow separately tests a real complete
WebReader Build71 app in a disposable signed-shadow temporary directory.
"""
from pathlib import Path
import unittest

from build70_dl_full_app_signed_shadow import (
    _synthetic_dq_installed_claim,
    _synthetic_library_with_three_downloads,
    _synthetic_offline_three_downloads,
)
from build70_dr_preupgrade_crosscheck import DRRejected, audit_dr_preupgrade
from build70_ds_candidate_evidence_gate import (
    DSRejected, inspect_ds_preupgrade_candidate,
)
from build70_di_build71_private_qa_preflight import QA_FILENAME
from build70_dj_continuity_report_compare import parse_continuity_report
from build70_dq_installed_bundle_report import inspect_dq_text
from build70_do_preupgrade_baseline_audit import audit_build70_baseline

ROOT = Path(__file__).resolve().parent


class DVFullAppSignedShadowHostTests(unittest.TestCase):
    def test_dq_fixture_is_unattested_and_canonical_shell_output(self):
        raw = _synthetic_dq_installed_claim()
        self.assertTrue(raw.endswith(b"\n"))
        report = inspect_dq_text(raw)
        self.assertEqual(
            report["status"], "DQ_REPORTED_MATCH_HISTORICAL_METADATA_NOT_ATTESTED"
        )
        self.assertFalse(report["inputProvenToComeFromCurrentPhysicalIPad"])
        self.assertFalse(report["installationAuthorized"])

    def test_synthetic_offline_and_sqlite_counts_are_coherent_only(self):
        counts = _synthetic_library_with_three_downloads()
        offline = _synthetic_offline_three_downloads()
        snapshot = parse_continuity_report(counts, expected_build=70)
        self.assertEqual(snapshot.counts, (2, 5, 2, 1, 1, 3, 2, 1, 1))
        audit = audit_build70_baseline(counts, [offline])
        self.assertEqual(audit["totalCompletedRecordsAsText"], 3)
        self.assertEqual(audit["inspectedChapterRecordsAsText"], 3)
        self.assertEqual(audit["offlinePageEntriesAsText"], 6)
        self.assertFalse(audit["inputTextsIndependentlyAuthenticated"])
        self.assertFalse(audit["installationAuthorized"])

    def test_full_dq_do_dr_text_chain_never_claims_physical_origin(self):
        receipt = audit_dr_preupgrade(
            _synthetic_dq_installed_claim(),
            _synthetic_library_with_three_downloads(),
            [_synthetic_offline_three_downloads()],
        )
        self.assertEqual(
            receipt["status"],
            "DR_PREUPGRADE_TEXT_COHERENT_NOT_ATTESTED_NOT_INSTALLABLE",
        )
        self.assertFalse(receipt["sameDeviceAndSameMomentProven"])
        self.assertFalse(receipt["readyToInstallIPA"])
        self.assertFalse(receipt["installationAuthorized"])

    def test_wrong_synthetic_entitlement_never_reaches_di_ipa_preflight(self):
        raw = _synthetic_dq_installed_claim()
        bad = raw.replace(
            b"APPLICATION_IDENTIFIER_ENTITLEMENT_TEXT=",
            b"APPLICATION_IDENTIFIER_ENTITLEMENT_TEXT=ROGUE.",
        )
        from unittest.mock import patch
        with patch(
            "build70_ds_candidate_evidence_gate.preflight_di_build71_private_qa"
        ) as di:
            with self.assertRaises(DSRejected):
                inspect_ds_preupgrade_candidate(
                    dq_report=bad,
                    sqlite_count_report=_synthetic_library_with_three_downloads(),
                    offline_reports=[_synthetic_offline_three_downloads()],
                    ipa_path=Path("/FAKE-NOT-FOR-INSTALL") / QA_FILENAME,
                    checksum_data=(b"0"*64+b"  "+QA_FILENAME.encode()+b"\n"),
                )
            di.assert_not_called()

    def test_mutated_offline_inventory_is_never_treated_as_coherent(self):
        bad = _synthetic_offline_three_downloads().replace(
            "Arquivos de páginas presentes na amostra: 6".encode(),
            "Arquivos de páginas presentes na amostra: 0".encode(),
        )
        receipt = audit_dr_preupgrade(
            _synthetic_dq_installed_claim(),
            _synthetic_library_with_three_downloads(),
            [bad],
        )
        self.assertEqual(
            receipt["status"], "DR_REPORTED_OFFLINE_METADATA_FAILURE_STOP_QA",
        )
        self.assertFalse(receipt["installationAuthorized"])

    def test_full_app_shadow_uses_integrated_ds_and_both_host_hashes(self):
        source = (ROOT/"build70_dl_full_app_signed_shadow.py").read_text()
        self.assertIn("inspect_ds_preupgrade_candidate(", source)
        self.assertIn("integrated.get(\"candidateIPAStaticSHA256\") != digest", source)
        self.assertIn("integrated.get(\"candidateIPABytes\") != size", source)
        self.assertIn("hashlib.sha256(ipa.read_bytes()).hexdigest() != digest", source)
        self.assertIn('"phaseDVPhysicalDataPreservationAttested": False', source)
        self.assertIn('"phaseDVSameBytesConsumedByInstallerProven": False', source)
        self.assertIn('"artifactUploaded": False', source)
        self.assertIn('"installationAuthorized": False', source)

    def test_native_workflow_runs_shadow_without_upload_or_release(self):
        wf = (ROOT.parent/
            ".github/workflows/chimera-build70-phase-dl-full-app-shadow.yml"
        ).read_text()
        self.assertIn("CURRENT_PROJECT_VERSION=71", wf)
        self.assertIn("CODE_SIGNING_ALLOWED=NO", wf)
        self.assertIn("macos-15", wf)
        self.assertIn("ci/build70_dl_full_app_signed_shadow.py", wf)
        self.assertIn("test_build70_dv_shadow_ds_integration.py", wf)
        self.assertNotIn("actions/upload-artifact", wf)
        self.assertNotIn("gh release", wf)
        self.assertIn("cancel-in-progress: true", wf)


if __name__ == "__main__":
    unittest.main()

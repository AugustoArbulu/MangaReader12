#!/usr/bin/env python3
"""Build69 BE strict offline report comparator, no genuine iPad data."""
import unittest

from build69_be_compare_upgrade_counts import (
    HEADER, PRIVACY, DATABASE, METRICS, FOOTER,
    ContinuityReportRejected, compare_continuity_reports,
    parse_continuity_report
)


def fixture(build, *, edited=None, ios="12.5.8"):
    edits = edited or {}
    counts = {name: 1 + i for i, name in enumerate(METRICS)}
    counts.update(edits)
    content = [
        HEADER, f"Build observada: {build} • iOS: {ios}", PRIVACY, DATABASE,
        *(f"{name}: {counts[name]}" for name in METRICS), *FOOTER
    ]
    return "\n".join(content).encode("utf-8")


class SafeComparison(unittest.TestCase):
    def test_unchanged_records_does_not_claim_physical_qa(self):
        report = compare_continuity_reports(before=fixture(68), after=fixture(69))
        self.assertEqual(report["status"], "DATABASE_RECORD_COUNTS_UNCHANGED_NOT_PHYSICAL_QA")
        self.assertEqual(report["baselineBuild"], 68)
        self.assertEqual(report["observedNewBuild"], 69)
        self.assertTrue(report["sqliteCountsMatchExactly"])
        self.assertEqual(len(report["metrics"]), 9)
        for key in (
            "allDownloadedPageBytesVerified",
            "physicalOfflineReaderTestCompleted", "appReinstallAvoidedVerifiedByTool",
            "backupRestoreAvoidedVerifiedByTool", "reportOriginAuthenticatedByTool",
            "physicalUpgradeSuccessful", "installationAuthorized",
            "installationPerformed", "networkUsed", "mainModified"
        ):
            self.assertIs(report[key], False, key)

    def test_loss_in_offline_index_or_library_is_marked_stop(self):
        for metric in ("Downloads marcados completos no banco", "Obras na biblioteca",
                       "Categorias", "Capítulos registrados", "Registros de histórico"):
            with self.subTest(metric=metric):
                report = compare_continuity_reports(
                    before=fixture(68), after=fixture(69, edited={metric: 0})
                )
                self.assertEqual(report["status"], "POTENTIAL_DATA_LOSS_STOP_REVIEW")
                self.assertGreater(report["decreasedMetricCount"], 0)
                self.assertFalse(report["physicalUpgradeSuccessful"])

    def test_growth_is_not_silent_success(self):
        report = compare_continuity_reports(
            before=fixture(68), after=fixture(69, edited={"Capítulos lidos": 900})
        )
        self.assertEqual(report["status"], "CHANGED_COUNTS_REVIEW_MANUALLY")
        self.assertEqual(report["increasedMetricCount"], 1)
        self.assertFalse(report["physicalOfflineReaderTestCompleted"])

    def test_different_ios_wrong_builds_and_invalid_reports_rejected(self):
        invalid = (
            (fixture(69), fixture(69)),
            (fixture(68), fixture(68)),
            (fixture(68), fixture(70)),
            (fixture(68), fixture(69, ios="13.0")),
            (fixture(68, ios="12.4.9"), fixture(69)),
            (fixture(68), fixture(69).replace(b"leitura", b"ALTERADO")),
            (fixture(68), fixture(69) + b"\nTITULO: SECRET"),
            (fixture(68), fixture(69).replace(b"Obras na biblioteca: 1", b"Obras na biblioteca: -1")),
            (fixture(68), fixture(69).replace(b"Obras na biblioteca: 1", b"Obras na biblioteca: 01")),
            (fixture(68), fixture(69).replace(b"Obras na biblioteca: 1", b"Obras na biblioteca: 10000000000000000000")),
            (fixture(68), fixture(69).replace(b"Downloads completos", b"Downloads incompletos")),
            (fixture(68), fixture(69).replace(b"\n", b"\r\n")),
            (fixture(68), b""),
        )
        for before, after in invalid:
            with self.subTest(sample=after[:40]):
                with self.assertRaises(ContinuityReportRejected):
                    compare_continuity_reports(before=before, after=after)

    def test_no_private_title_or_path_may_be_added(self):
        corrupted = fixture(68).replace(
            b"Obras na biblioteca: 1",
            b"Obras na biblioteca: 1; private file=/var/mobile/hidden"
        )
        with self.assertRaises(ContinuityReportRejected):
            parse_continuity_report(corrupted)

    def test_oversized_or_nonbytes_rejected(self):
        for payload in ("bad", None, b"x" * 4097, b"\xff", b"[]"):
            with self.subTest(value=repr(payload)[:30]):
                with self.assertRaises(ContinuityReportRejected):
                    parse_continuity_report(payload)


if __name__ == "__main__":
    unittest.main()

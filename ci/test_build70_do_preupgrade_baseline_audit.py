#!/usr/bin/env python3
"""Phase DO: hostile Build70 offline batch text vs SQLite count cross-check.

All reports are synthetic and unauthenticated. Success is NEVER a
permission to distribute, install, update, restore or delete user files.
"""
from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

from build70_do_preupgrade_baseline_audit import (
    MAX_BATCH, MAX_REPORTS, OFFLINE_FOOTER, OFFLINE_HEADER, OFFLINE_INTRO,
    FIELDS, OfflineBatch, DORejected, audit_build70_baseline,
    parse_offline_batch,
)
from build70_dj_continuity_report_compare import (
    COUNT_LABELS, DB_HEALTH, FOOTER, HEADER, IOS_VERSION, NOTE,
)

ROOT = Path(__file__).resolve().parent


def continuity(total=3, build=70, ios=IOS_VERSION):
    numbers = (12, 75, 15, 9, 7, total, 6, 2, 4)
    return "\n".join([
        HEADER, f"Build observada: {build} • iOS: {ios}",
        NOTE, DB_HEALTH,
        *(name + ": " + str(value) for name, value in zip(COUNT_LABELS, numbers)),
        *FOOTER,
    ]).encode("utf-8")


def offline(*, total=3, offset=0, valid=None, sealed=None,
            bad=None, pages=None, build=70, ios=IOS_VERSION):
    scanned = min(64, total-offset) if total else 0
    valid = scanned if valid is None else valid
    sealed = valid if sealed is None else sealed
    bad = scanned-valid if bad is None else bad
    pages = valid*2 if pages is None else pages
    nex = offset+64 if offset+64 < total else 0
    values = (
        total, offset, nex, scanned, valid, sealed,
        valid-sealed, bad, total-scanned, pages,
    )
    lines = [
        OFFLINE_HEADER,
        f"Build observada: {build} • iOS: {ios}",
        OFFLINE_INTRO[2], OFFLINE_INTRO[3],
        *(name + ": " + str(n) for name, n in zip(FIELDS, values)),
        *OFFLINE_FOOTER,
    ]
    return "\n".join(lines).encode("utf-8")


class DOOfflineBeforeUpgradeTests(unittest.TestCase):
    def assert_no_authority(self, r):
        for key in (
            "inputTextsIndependentlyAuthenticated",
            "sqliteRowContentsVerified", "offlinePagePayloadBytesRead",
            "offlineImageDecodingVerified",
            "physicalReadingWithoutWiFiVerified",
            "physicalBuild70AppIdentifierAttested", "physicalBuild71Installed",
            "dataContainerSurvivesUpgradeProven",
            "backupRetainedOutsideDeviceVerified",
            "publisherAuthenticated", "ownerQADistributionApprovalRecorded",
            "readyToDistributeIPA", "readyToInstallIPA",
            "installationAuthorized", "installationPerformed",
        ):
            self.assertIs(r[key], False, key)

    def test_three_existing_download_records_textually_covered(self):
        report = audit_build70_baseline(continuity(), [offline()])
        self.assertEqual(report["status"], "DO_TEXT_FULL_COVERAGE_NO_IMAGE_BYTE_PROOF")
        self.assertEqual(report["offlineBatchTextsChecked"], 1)
        self.assertEqual(report["totalCompletedRecordsAsText"], 3)
        self.assertEqual(report["validSequentialChaptersAsText"], 3)
        self.assertEqual(report["offlinePageEntriesAsText"], 6)
        self.assertTrue(report["allCompletedRowsCoveredByTextSequence"])
        self.assert_no_authority(report)

    def test_empty_downloads_does_not_mean_physical_library_is_empty(self):
        report = audit_build70_baseline(continuity(0), [offline(total=0)])
        self.assertEqual(report["status"],
                         "DO_NO_COMPLETE_OFFLINE_CHAPTERS_IN_TEXT_NOT_DEVICE_PROOF")
        self.assertEqual(report["totalCompletedRecordsAsText"], 0)
        self.assert_no_authority(report)

    def test_exact_64_is_single_batch(self):
        report = audit_build70_baseline(continuity(64), [offline(total=64)])
        self.assertTrue(report["allCompletedRowsCoveredByTextSequence"])
        self.assertEqual(report["inspectedChapterRecordsAsText"], 64)
        self.assertEqual(report["expectedNextAuditOffset"], 0)
        self.assert_no_authority(report)

    def test_two_batches_cover_65_without_duplicates(self):
        r = audit_build70_baseline(
            continuity(65),
            [offline(total=65, offset=0), offline(total=65, offset=64)]
        )
        self.assertEqual(r["status"], "DO_TEXT_FULL_COVERAGE_NO_IMAGE_BYTE_PROOF")
        self.assertEqual(r["inspectedChapterRecordsAsText"], 65)
        self.assertEqual(r["offlineBatchTextsChecked"], 2)
        self.assertEqual(r["remainingRecordsNotInspectedAsText"], 0)
        self.assert_no_authority(r)

    def test_130_complete_three_batches(self):
        r = audit_build70_baseline(
            continuity(130),
            [offline(total=130, offset=n) for n in (0, 64, 128)]
        )
        self.assertTrue(r["allCompletedRowsCoveredByTextSequence"])
        self.assertEqual(r["inspectedChapterRecordsAsText"], 130)
        self.assertEqual(r["offlinePageEntriesAsText"], 260)
        self.assert_no_authority(r)

    def test_first_batch_of_many_never_claims_full_coverage(self):
        r = audit_build70_baseline(continuity(130), [offline(total=130)])
        self.assertEqual(r["status"], "DO_PARTIAL_SAMPLE_NEEDS_MORE_BATCHES")
        self.assertEqual(r["remainingRecordsNotInspectedAsText"], 66)
        self.assertEqual(r["expectedNextAuditOffset"], 64)
        self.assertFalse(r["allCompletedRowsCoveredByTextSequence"])
        self.assert_no_authority(r)

    def test_legacy_chapters_without_page_count_receipt_are_flagged(self):
        r = audit_build70_baseline(
            continuity(3), [offline(valid=3, sealed=1)]
        )
        self.assertEqual(r["status"], "DO_LEGACY_WITHOUT_RECEIPT_NEEDS_PHYSICAL_READING")
        self.assertEqual(r["legacyWithoutReceiptAsText"], 2)
        self.assertFalse(r["offlinePagePayloadBytesRead"])
        self.assert_no_authority(r)

    def test_missing_or_unsafe_page_metadata_flags_manual_review(self):
        r = audit_build70_baseline(
            continuity(3), [offline(total=3, valid=2, sealed=2, pages=4)]
        )
        self.assertEqual(r["status"], "DO_OFFLINE_METADATA_FAILURE_OWNER_REVIEW_REQUIRED")
        self.assertEqual(r["missingOrUnsafeChaptersAsText"], 1)
        self.assertFalse(r["readyToInstallIPA"])
        self.assert_no_authority(r)

    def test_negative_findings_take_precedence_over_legacy(self):
        r = audit_build70_baseline(
            continuity(3), [offline(total=3, valid=2, sealed=1, pages=4)]
        )
        self.assertEqual(r["status"], "DO_OFFLINE_METADATA_FAILURE_OWNER_REVIEW_REQUIRED")
        self.assert_no_authority(r)

    def test_64_with_next_64_is_invalid_even_if_total_64(self):
        text = offline(total=64)
        mutated = text.replace(b"Pr\xc3\xb3ximo \xc3\xadndice da auditoria: 0",
                               b"Pr\xc3\xb3ximo \xc3\xadndice da auditoria: 64")
        self.assertNotEqual(text, mutated)
        with self.assertRaises(DORejected):
            parse_offline_batch(mutated)

    def test_last_batch_must_use_next_zero(self):
        text = offline(total=65, offset=64)
        mutated = text.replace(
            "Próximo índice da auditoria: 0".encode(),
            "Próximo índice da auditoria: 128".encode(),
        )
        with self.assertRaises(DORejected):
            parse_offline_batch(mutated)

    def test_skipped_or_repeated_batch_is_rejected(self):
        values = [
            [offline(total=130, offset=64)],
            [offline(total=130), offline(total=130, offset=128)],
            [offline(total=130), offline(total=130)],
            [offline(total=130), offline(total=130, offset=64),
             offline(total=130, offset=64)],
        ]
        for batches in values:
            with self.subTest(n=len(batches)), self.assertRaises(DORejected):
                audit_build70_baseline(continuity(130), batches)

    def test_no_additional_batch_after_full_cycle(self):
        with self.assertRaises(DORejected):
            audit_build70_baseline(
                continuity(3), [offline(), offline()]
            )

    def test_partial_second_batch_valid_but_not_full(self):
        r = audit_build70_baseline(continuity(190), [
            offline(total=190, offset=0), offline(total=190, offset=64)
        ])
        self.assertEqual(r["inspectedChapterRecordsAsText"], 128)
        self.assertEqual(r["remainingRecordsNotInspectedAsText"], 62)
        self.assertEqual(r["expectedNextAuditOffset"], 128)
        self.assertFalse(r["allCompletedRowsCoveredByTextSequence"])

    def test_counts_and_offline_totals_must_match(self):
        with self.assertRaises(DORejected):
            audit_build70_baseline(continuity(3), [offline(total=4)])

    def test_wrong_report_build_in_either_input_fails(self):
        cases = [
            (continuity(build=71), offline()),
            (continuity(), offline(build=71)),
            (continuity(build=69), offline()),
            (continuity(), offline(build=69)),
        ]
        for a, b in cases:
            with self.subTest(a=a[42:80]), self.assertRaises(DORejected):
                audit_build70_baseline(a, [b])

    def test_wrong_ios12_patch_level_fails(self):
        for version in ("12.5.7", "13.0", "18.0"):
            with self.subTest(ios=version):
                with self.assertRaises(DORejected):
                    audit_build70_baseline(continuity(), [offline(ios=version)])

    def test_malformed_schema_or_missing_continuity_is_rejected(self):
        for source in (
            b"",
            continuity().replace(DB_HEALTH.encode(), b"Banco: INDISPONIVEL"),
            continuity().replace(b"Cap\xc3\xadtulos registrados: 75",
                                 b"Cap\xc3\xadtulos registrados: -1"),
        ):
            with self.subTest(value=source[:35]), self.assertRaises(DORejected):
                audit_build70_baseline(source, [offline()])

    def test_malformed_numeric_fields_rejected(self):
        raw = offline()
        for value in ("-1", "01", "+1", "1.2", "1e2", " 1", "1 ",
                      "9223372036854775808", "12abc", "", "1\\nEXTRA"):
            changed = raw.replace(b"Cap\xc3\xadtulos completos no banco: 3",
                                  ("Capítulos completos no banco: "+value).encode())
            with self.subTest(value=value), self.assertRaises(DORejected):
                parse_offline_batch(changed)

    def test_broken_algebra_scanned_valid_sealed_legacy_bad(self):
        baseline = offline()
        replacements = [
            ("Capítulos da amostra inspecionados: 3",
             "Capítulos da amostra inspecionados: 2"),
            ("Capítulos com arquivos sequenciais e não vazios: 3",
             "Capítulos com arquivos sequenciais e não vazios: 4"),
            ("Com recibo de quantidade de páginas: 3",
             "Com recibo de quantidade de páginas: 4"),
            ("Legados sem recibo entre os válidos: 0",
             "Legados sem recibo entre os válidos: 1"),
            ("Capítulos faltantes, incompletos ou inseguros: 0",
             "Capítulos faltantes, incompletos ou inseguros: 1"),
            ("Capítulos fora da amostra: 0",
             "Capítulos fora da amostra: 1"),
            ("Arquivos de páginas presentes na amostra: 6",
             "Arquivos de páginas presentes na amostra: 0"),
        ]
        for old, new in replacements:
            mutated = baseline.replace(old.encode(), new.encode())
            with self.subTest(field=old), self.assertRaises(DORejected):
                parse_offline_batch(mutated)

    def test_bad_footer_and_unapproved_information_rejected(self):
        original = offline()
        for b in (
            original + b"\n",
            original + b"IPA_AUTHORIZED=YES",
            original.replace("sem Wi-Fi".encode(), b"online"),
            original.replace("Nenhuma página foi modificada".encode(),
                             "Arquivos apagados".encode()),
        ):
            with self.subTest(length=len(b)), self.assertRaises(DORejected):
                parse_offline_batch(b)

    def test_cr_nul_invalid_utf8_oversize_rejected(self):
        original = offline()
        for b in (
            original.replace(b"\n", b"\r\n"),
            original + b"\x00",
            original + b"\xff",
            original + b"x" * 4096,
        ):
            with self.subTest(size=len(b)), self.assertRaises(DORejected):
                parse_offline_batch(b)

    def test_zero_total_rejects_impossible_nonzero_pages(self):
        b = offline(total=0).replace(
            b"Arquivos de p\xc3\xa1ginas presentes na amostra: 0",
            b"Arquivos de p\xc3\xa1ginas presentes na amostra: 1",
        )
        with self.assertRaises(DORejected):
            parse_offline_batch(b)

    def test_limit_up_to_256_reports_and_no_empty_or_tuple(self):
        with self.assertRaises(DORejected):
            audit_build70_baseline(continuity(), [])
        with self.assertRaises(DORejected):
            audit_build70_baseline(continuity(), tuple([offline()]))
        with self.assertRaises(DORejected):
            audit_build70_baseline(continuity(), [offline()] * (MAX_REPORTS+1))

    def test_report_max_total_is_limited_to_one_billion(self):
        huge = offline(total=1_000_000_001, offset=0)
        with self.assertRaises(DORejected):
            parse_offline_batch(huge)

    def test_readonly_cli_accepts_generated_fixture_files(self):
        with tempfile.TemporaryDirectory(prefix="wr-do-synthetic-") as temp:
            root = Path(temp)
            counts = root / "count.txt"
            batch = root / "batch.txt"
            counts.write_bytes(continuity())
            batch.write_bytes(offline())
            cli = subprocess.run(
                [sys.executable, str(ROOT / "build70_do_preupgrade_baseline_audit.py"),
                 "--counts", str(counts), "--offline", str(batch)],
                check=False, text=True, capture_output=True, timeout=12,
            )
            self.assertEqual(cli.returncode, 0, cli.stderr)
            receipt = json.loads(cli.stdout)
            self.assertEqual(receipt["status"], "DO_TEXT_FULL_COVERAGE_NO_IMAGE_BYTE_PROOF")
            self.assert_no_authority(receipt)
            self.assertEqual(counts.read_bytes(), continuity())
            self.assertEqual(batch.read_bytes(), offline())

    def test_source_has_no_ipa_install_backup_or_file_mutation_calls(self):
        import ast
        src = (ROOT / "build70_do_preupgrade_baseline_audit.py").read_text()
        calls = set()
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    calls.add(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    calls.add(node.func.attr)
        forbidden = (
            "appinst", "installApplication", "posix_spawn",
            "unlink", "rename", "write_text", "write_bytes", "removeItem",
            "restoreBackup", "clearAllDownloads", "publish_release",
            "upload_artifact", "Popen", "run", "system", "chmod", "chown",
        )
        for name in forbidden:
            with self.subTest(name=name):
                self.assertNotIn(name, calls)
        for exact in (
            '"inputTextsIndependentlyAuthenticated": False',
            '"offlinePagePayloadBytesRead": False',
            '"physicalReadingWithoutWiFiVerified": False',
            '"ownerQADistributionApprovalRecorded": False',
            '"installationAuthorized": False',
            '"installationPerformed": False',
        ):
            self.assertIn(exact, src)

    def test_deterministic_250_mutations_never_grant_authority(self):
        rng = random.Random(20261111)
        for _ in range(250):
            data = bytearray(offline())
            data[rng.randrange(len(data))] ^= rng.randrange(1, 256)
            try:
                result = audit_build70_baseline(continuity(), [bytes(data)])
            except DORejected:
                continue
            self.assert_no_authority(result)


if __name__ == "__main__":
    unittest.main()

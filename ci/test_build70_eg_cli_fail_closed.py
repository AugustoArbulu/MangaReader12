#!/usr/bin/env python3
"""EG: real subprocess exit status contracts for read-only host auditors.

Never call any iOS app, network, backup restoration, or installer.
All test directories, databases and pages are synthetic.
"""
import json
from pathlib import Path
import plistlib
import subprocess
import sys
import unittest

import test_build70_eb_copy_vs_device_text as eb
import test_build70_ec_full_container_dual_copy as ec
import test_build70_ed_portable_vs_external_library as ed
import test_build70_ee_portable_preferences_plist as ee
import test_build70_ef_offline_payload_triage as ef

HERE = Path(__file__).resolve().parent
DENIALS = (
    "installationAuthorized", "restorationAuthorized",
    "readyToInstallIPA", "readyToDistributeIPA", "automaticUpdaterEnabled",
)


def call(auditor, *args):
    proc = subprocess.run(
        [sys.executable, str(HERE / auditor), *map(str, args)],
        capture_output=True, text=True, check=False, timeout=15,
    )
    result = json.loads(proc.stdout)
    for field in DENIALS:
        if field in result and result[field] is not False:
            raise AssertionError("CLI unexpectedly granted authority: " + field)
    return proc, result


class CLIExitCodeContractTests(unittest.TestCase):
    def fixture(self, cls, method):
        instance = cls(method)
        instance.setUp()
        self.addCleanup(instance.doCleanups)
        return instance

    def check_pair(self, auditor, args, expected_success, expected_stop, mutate, secret):
        before, before_report = call(auditor, *args)
        self.assertEqual(before.returncode, 0, before.stdout + before.stderr)
        self.assertEqual(before_report["status"], expected_success)
        self.assertNotIn(secret, before.stdout + before.stderr)
        mutate()
        after, after_report = call(auditor, *args)
        self.assertEqual(after.returncode, 2, after.stdout + after.stderr)
        self.assertEqual(after_report["status"], expected_stop)
        self.assertNotIn(secret, after.stdout + after.stderr)

    def test_eb_mismatch_exits_nonzero(self):
        f = self.fixture(eb.EBTests, "test_positive_counts_only_never_authenticates")
        f.add()
        counts = f.root.parent / "counts.txt"
        offline = f.root.parent / "offline.txt"
        counts.write_bytes(eb.counts(1))
        offline.write_bytes(eb.offline(1))
        args = ("--snapshot", f.root, "--counts", counts, "--offline", offline)
        self.check_pair(
            "build70_eb_copy_vs_device_text.py", args,
            "EB_COPIED_BYTES_AND_DEVICE_TEXT_TOTALS_AGREE_NOT_ATTESTED",
            "EB_STOP_COMPLETED_CHAPTER_COUNTS_DIFFER",
            lambda: (counts.write_bytes(eb.counts(2)),
                     offline.write_bytes(eb.offline(2))),
            str(f.root),
        )

    def test_ec_changed_full_copy_exits_nonzero(self):
        f = self.fixture(ec.ECDualCopyTests, "test_identical_full_copies_never_prove_device")
        args = ("--first", f.first, "--second", f.second)
        pref = f.second / "Library" / "Preferences" / "app.plist"
        self.check_pair(
            "build70_ec_full_container_dual_copy.py", args,
            "EC_TWO_EXTERNAL_COPIES_IDENTICAL_NOT_DEVICE_PROOF",
            "EC_STOP_EXTERNAL_COPIES_DIFFER",
            lambda: pref.write_bytes(b"not-the-same"),
            str(f.first),
        )

    def test_ed_changed_read_progress_exits_nonzero(self):
        f = self.fixture(ed.EDPortableLibraryTests, "test_exact_library_rows_equal_but_not_attested")
        portable = f.root.parent / "library.mr12backup"
        portable.write_bytes(f.backup)
        args = ("--snapshot", f.root, "--backup", portable)
        self.check_pair(
            "build70_ed_portable_vs_external_library.py", args,
            "ED_LIBRARY_ROWS_EQUAL_NOT_ATTESTED",
            "ED_STOP_LIBRARY_ROWS_DIFFER",
            lambda: f.mutate("UPDATE chapters SET last_page_read=99 WHERE internal_id=1"),
            str(f.root),
        )

    def test_ee_changed_preference_exits_nonzero(self):
        f = self.fixture(ee.EEPreferencesTests, "test_match_binary_plist_and_json_export")
        portable = f.root.parent / "library.mr12backup"
        portable.write_bytes(f.backup())
        args = ("--snapshot", f.root, "--backup", portable)
        def change():
            f.prefs["app.theme"] = "light"
            f.file.write_bytes(plistlib.dumps(f.prefs))
        self.check_pair(
            "build70_ee_portable_preferences_plist.py", args,
            "EE_EXPORTED_PREFERENCES_EQUAL_NOT_ATTESTED",
            "EE_STOP_EXPORTED_PREFERENCES_DIFFER",
            change, str(f.root),
        )

    def test_ef_html_exits_nonzero(self):
        f = self.fixture(ef.EFPayloadTriageTests, "test_plausible_signatures_do_not_claim_decoding")
        args = ("--snapshot", f.root)
        self.check_pair(
            "build70_ef_offline_payload_triage.py", args,
            "EF_KNOWN_IMAGE_SIGNATURES_PLAUSIBLE_NOT_DECODED",
            "EF_STOP_HTML_OR_TRUNCATED_OFFLINE_FILES",
            lambda: f.first.write_bytes(b"<!DOCTYPE html><html>blocked</html>"),
            str(f.root),
        )

    def test_cross_phase_cli_code_contracts_without_install(self):
        for prefix in ("eb", "ec", "ed", "ee", "ef"):
            src = (HERE / ("build70_" + prefix + "_" + {
                "eb": "copy_vs_device_text.py",
                "ec": "full_container_dual_copy.py",
                "ed": "portable_vs_external_library.py",
                "ee": "portable_preferences_plist.py",
                "ef": "offline_payload_triage.py",
            }[prefix])).read_text(encoding="utf-8")
            self.assertIn(
                'return 2 if result["status"].startswith("' + prefix.upper() + '_STOP_") else 0',
                src,
            )
            self.assertNotIn("appinst", src)
            self.assertNotIn("restoreBackup(", src)
            self.assertIn('"installationAuthorized": False', src)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""DQ integration: execute a TEMPORARILY REBASED read-only probe against fake files.

The real script is never edited. Its four fixed iPad paths stay pinned in the
repository; only a throwaway host copy maps ONE allowed bundle root and TWO
tool executables to a temporary fixture. No iPad, root, network or installer.
"""
from pathlib import Path
import subprocess
import tempfile
import unittest

from build70_dq_installed_bundle_report import (
    DQReportRejected, inspect_dq_text,
)
from build70_dr_preupgrade_crosscheck import audit_dr_preupgrade
from test_build70_do_preupgrade_baseline_audit import continuity, offline

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "build70_dq_installed_bundle_readonly.sh"
UUID = "12345678-abcd-4000-8000-123456789abc"
BUNDLE = "com.example.MangaReader12"
ENTITLEMENT = "AR5SFJC432.com.example.MangaReader12.AR5SFJC432"


def only_replace(source: str, before: str, after: str) -> str:
    if source.count(before) != 1:
        raise AssertionError("unexpected DQ shell contract; fixture rewrite refused")
    return source.replace(before, after, 1)


class DQShellParserIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="webreader-dq-e2e-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.allowed = self.root / "Bundle" / "Application"
        self.app = self.allowed / UUID / "MangaReader12.app"
        self.app.mkdir(parents=True)
        (self.app / "Info.plist").write_bytes(b"synthetic fixture; not a real plist")
        (self.app / "MangaReader12").write_bytes(b"synthetic executable, not Mach-O")
        self.tools = self.root / "tools"
        self.tools.mkdir()
        self.shell = self.root / "dq-host-rebased.sh"

        source = SOURCE.read_text(encoding="utf-8")
        source = only_replace(
            source,
            "    /var/containers/Bundle/Application|\\\n",
            f"    {self.allowed}|\\\n",
        )
        source = only_replace(
            source,
            "for tool in /usr/bin/plutil /bin/plutil /usr/local/bin/plutil; do",
            f"for tool in {self.tools / 'plutil'}; do",
        )
        source = only_replace(
            source,
            "for tool in /usr/bin/ldid /bin/ldid /usr/local/bin/ldid; do",
            f"for tool in {self.tools / 'ldid'}; do",
        )
        # Ubuntu's /usr/bin/awk is normally a symlink; the production
        # script deliberately rejects such tools. Resolve the HOST binary
        # in this temporary fixture ONLY; leave iOS allowlists unchanged.
        self.awk_host_path = Path("/usr/bin/awk").resolve(strict=True)
        source = only_replace(
            source,
            "for tool in /usr/bin/awk /bin/awk; do",
            f"for tool in {self.awk_host_path}; do",
        )
        self.shell.write_text(source, encoding="utf-8")
        self.write_stub("plutil", self.plutil_lines())
        self.write_stub("ldid", self.ldid_lines())

    def write_stub(self, name, lines):
        target = self.tools / name
        script = "#!/bin/sh\nprintf '%s\\n' " + " ".join(
            "'" + line.replace("'", "'\\''") + "'" for line in lines
        ) + "\n"
        target.write_text(script, encoding="utf-8")
        target.chmod(0o755)

    def plutil_lines(self, bundle=BUNDLE, build="70"):
        return (
            f'  "CFBundleIdentifier" => "{bundle}"',
            f'  "CFBundleVersion" => "{build}"',
        )

    def ldid_lines(self, entitlement=ENTITLEMENT):
        return (
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<plist><dict>',
            '<key>application-identifier</key>',
            f'<string>{entitlement}</string>',
            '</dict></plist>',
        )

    def execute(self, path=None):
        chosen = self.app if path is None else path
        return subprocess.run(
            ["/bin/sh", str(self.shell), str(chosen)],
            text=False, capture_output=True, timeout=10,
        )

    def assert_no_install(self, receipt):
        for key in (
            "installationAuthorized", "installationPerformed",
            "readyToDistributeIPA", "readyToInstallIPA",
            "inputProvenToComeFromCurrentPhysicalIPad",
            "nativeCodeSignatureCryptographicallyValidated",
            "publisherIdentityAuthenticated",
            "installedBuild70IndependentEntitlementAttested",
            "userLibraryAndOfflinePreservationVerified",
        ):
            self.assertIs(receipt[key], False, key)

    def test_actual_shell_output_matches_parser_with_final_lf(self):
        original_info = (self.app / "Info.plist").read_bytes()
        original_exe = (self.app / "MangaReader12").read_bytes()
        proc = self.execute()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(proc.stdout.endswith(b"\n"))
        self.assertFalse(proc.stdout.endswith(b"\n\n"))
        self.assertEqual(proc.stderr, b"")
        receipt = inspect_dq_text(proc.stdout)
        self.assertEqual(
            receipt["status"], "DQ_REPORTED_MATCH_HISTORICAL_METADATA_NOT_ATTESTED",
            proc.stdout.decode("utf-8", errors="replace"),
        )
        self.assert_no_install(receipt)
        self.assertEqual((self.app / "Info.plist").read_bytes(), original_info)
        self.assertEqual((self.app / "MangaReader12").read_bytes(), original_exe)

    def test_real_shell_output_dr_dq_do_full_chain_is_non_authorizing(self):
        proc = self.execute()
        self.assertEqual(proc.returncode, 0)
        result = audit_dr_preupgrade(proc.stdout, continuity(), [offline()])
        self.assertEqual(
            result["status"],
            "DR_PREUPGRADE_TEXT_COHERENT_NOT_ATTESTED_NOT_INSTALLABLE",
        )
        self.assertTrue(result["bothReportFormatsTextuallyCoherent"])
        self.assertIs(result["sameDeviceAndSameMomentProven"], False)
        self.assertIs(result["readyToDistributeIPA"], False)
        self.assertIs(result["readyToInstallIPA"], False)
        self.assertIs(result["installationAuthorized"], False)

    def test_real_shell_wrong_build_makes_dr_stop_qa(self):
        self.write_stub("plutil", self.plutil_lines(build="71"))
        proc = self.execute()
        self.assertEqual(proc.returncode, 0)
        result = audit_dr_preupgrade(proc.stdout, continuity(), [offline()])
        self.assertEqual(result["status"], "DR_REPORTED_IDENTITY_MISMATCH_STOP_QA")
        self.assertIs(result["bothReportFormatsTextuallyCoherent"], False)
        self.assertIs(result["installationAuthorized"], False)

    def test_missing_ldid_is_explicit_unavailable(self):
        (self.tools / "ldid").unlink()
        receipt = inspect_dq_text(self.execute().stdout)
        self.assertEqual(receipt["reportedApplicationIdentifierEntitlement"], "UNAVAILABLE")
        self.assertEqual(receipt["status"], "DQ_REPORTED_INSTALLED_IDENTITY_FIELDS_UNAVAILABLE")
        self.assert_no_install(receipt)

    def test_missing_awk_is_explicit_unavailable(self):
        # The production script refuses symlinked awk executables; it
        # must report unknown metadata rather than silently trusting them.
        source = self.shell.read_text(encoding="utf-8")
        source = only_replace(
            source,
            f"for tool in {self.awk_host_path}; do",
            f"for tool in {self.tools / 'missing-awk'}; do",
        )
        self.shell.write_text(source, encoding="utf-8")
        receipt = inspect_dq_text(self.execute().stdout)
        self.assertEqual(receipt["reportedBundleID"], "UNAVAILABLE")
        self.assertEqual(receipt["reportedInstalledBuild"], "UNAVAILABLE")
        self.assertEqual(receipt["reportedApplicationIdentifierEntitlement"], "UNAVAILABLE")
        self.assert_no_install(receipt)

    def test_missing_plutil_is_explicit_unavailable(self):
        (self.tools / "plutil").unlink()
        receipt = inspect_dq_text(self.execute().stdout)
        self.assertEqual(receipt["reportedBundleID"], "UNAVAILABLE")
        self.assertEqual(receipt["reportedInstalledBuild"], "UNAVAILABLE")
        self.assert_no_install(receipt)

    def test_different_version_is_stop_qa(self):
        self.write_stub("plutil", self.plutil_lines(build="71"))
        receipt = inspect_dq_text(self.execute().stdout)
        self.assertEqual(
            receipt["status"], "DQ_REPORTED_BUNDLE_VERSION_OR_ENTITLEMENT_MISMATCH_STOP_QA",
        )
        self.assert_no_install(receipt)

    def test_different_entitlement_is_stop_qa(self):
        self.write_stub("ldid", self.ldid_lines(entitlement="DIFFERENT.bundle"))
        receipt = inspect_dq_text(self.execute().stdout)
        self.assertEqual(
            receipt["status"], "DQ_REPORTED_BUNDLE_VERSION_OR_ENTITLEMENT_MISMATCH_STOP_QA",
        )
        self.assert_no_install(receipt)

    def test_unexpected_shell_metacharacters_become_unavailable(self):
        self.write_stub("plutil", self.plutil_lines(bundle="bad;sh"))
        receipt = inspect_dq_text(self.execute().stdout)
        self.assertEqual(receipt["reportedBundleID"], "UNAVAILABLE")
        self.assert_no_install(receipt)

    def test_missing_or_symlinked_info_plist_is_denied(self):
        target = self.app / "Info.plist"
        target.unlink()
        result = self.execute()
        self.assertEqual(result.returncode, 2)
        self.assertIn(b"DQ_STATUS=DENIED", result.stdout)
        target.symlink_to(self.app / "MangaReader12")
        result = self.execute()
        self.assertEqual(result.returncode, 2)

    def test_symlinked_app_is_denied(self):
        real_app = self.allowed / UUID / "real.app"
        self.app.rename(real_app)
        self.app.symlink_to(real_app, target_is_directory=True)
        result = self.execute()
        self.assertEqual(result.returncode, 2)
        self.assertIn(b"INSTALLATION_AUTHORIZED=NO", result.stdout)

    def test_unapproved_parent_rejected_even_with_fake_matching_files(self):
        another = self.root / "not-allowed" / UUID / "MangaReader12.app"
        another.mkdir(parents=True)
        (another / "Info.plist").write_bytes(b"x")
        (another / "MangaReader12").write_bytes(b"x")
        result = self.execute(another)
        self.assertEqual(result.returncode, 2)
        self.assertIn(b"DQ_STATUS=DENIED", result.stdout)

    def test_extra_newline_or_injected_authority_from_pipe_is_rejected(self):
        original = self.execute().stdout
        for edited in (original+b"\n", original+b"INSTALLATION_AUTHORIZED=YES\n"):
            with self.subTest(edited=edited[-36:]), self.assertRaises(DQReportRejected):
                inspect_dq_text(edited)


if __name__ == "__main__":
    unittest.main()

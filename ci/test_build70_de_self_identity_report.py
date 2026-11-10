#!/usr/bin/env python3
"""DE: host compilation of iOS12-oriented self-only CLI + report parser.

The reports are untrusted text. Distinct EUID observations are never
proof of a code-signed iOS helper or peer authorization. No device is used.
"""
from dataclasses import replace
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
import tempfile
import unittest

from build70_de_self_identity_report import (
    DEReportRejected, assess_self_report_pair, parse_self_report,
)

ROOT = Path(__file__).resolve().parent


class DEHostReadOnlyReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="wr-de-self-host-")
        compiler = shutil.which("clang") or shutil.which("cc")
        if not compiler:
            raise RuntimeError("no native compiler; test cannot silently skip")
        cls.executables = {}
        for role, define in (
            ("mobile", "WR_DE_MOBILE_ROLE"),
            ("helper", "WR_DE_HELPER_ROLE"),
        ):
            path = Path(cls.tmp.name) / ("wr-de-" + role)
            subprocess.run([
                compiler, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
                "-D" + define, str(ROOT / "build70_de_ios12_self_identity_probe.c"),
                "-o", str(path),
            ], check=True, capture_output=True, text=True, timeout=30)
            cls.executables[role] = path
        cls.reports = {
            role: subprocess.run([str(path)], check=True, capture_output=True,
                                 timeout=10).stdout
            for role, path in cls.executables.items()
        }

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def mobile(self):
        return parse_self_report(self.reports["mobile"])

    def helper(self):
        return parse_self_report(self.reports["helper"])

    @staticmethod
    def edit(data: bytes, key: str, replacement: str) -> bytes:
        lines = data.decode("ascii").splitlines()
        hits = [i for i, line in enumerate(lines) if line.startswith(key + "=")]
        if len(hits) != 1:
            raise AssertionError("missing or duplicated test target")
        lines[hits[0]] = key + "=" + replacement
        return ("\n".join(lines) + "\n").encode("ascii")

    def assert_denied(self, observation):
        for field in (
            "real_ios12_process_identity_attested",
            "peer_identity_authenticated",
            "ios12_helper_uid_isolation_proven",
            "ipad_app_write_denial_proven",
            "binary_code_signature_verified",
            "installation_authorized", "installation_performed",
        ):
            self.assertFalse(getattr(observation, field), field)

    def test_two_role_binaries_are_self_only_and_not_authentication(self):
        mobile, helper = self.mobile(), self.helper()
        self.assertEqual(mobile.role_label, "MOBILE_CANDIDATE")
        self.assertEqual(helper.role_label, "HELPER_CANDIDATE")
        for obj in (mobile, helper):
            self.assertEqual(obj.uid, os.getuid())
            self.assertEqual(obj.euid, os.geteuid())
            self.assertEqual(obj.gid, os.getgid())
            self.assertEqual(obj.egid, os.getegid())
            self.assertTrue(obj.pid > 0)
            self.assert_denied(obj)

    def test_compiled_executable_metadata_is_read_only(self):
        obj = self.mobile()
        self.assertIsNotNone(obj.binary_owner_uid)
        self.assertEqual(obj.binary_owner_uid, os.geteuid())
        self.assertIsNotNone(obj.binary_mode)
        self.assertIn(obj.kernel_family, ("Linux", "Darwin"))
        self.assert_denied(obj)

    def test_comparing_same_uid_reports_cannot_prove_isolation(self):
        result = assess_self_report_pair(self.mobile(), self.helper())
        self.assertEqual(result.verdict, "SAME_EUID_SELF_REPORTED_NOT_ISOLATED")
        self.assertFalse(result.self_reported_euids_differ)
        self.assertFalse(result.actual_process_separation_proven_on_ios12)
        self.assertFalse(result.installation_authorized)

    def test_spoofed_distinct_uid_never_becomes_credential_evidence(self):
        fake = self.edit(self.reports["helper"], "DE_SELF_EUID",
                         str(self.helper().euid + 1))
        result = assess_self_report_pair(self.mobile(), parse_self_report(fake))
        self.assertEqual(result.verdict, "DISTINCT_EUID_SELF_REPORTED_UNATTESTED")
        self.assertTrue(result.self_reported_euids_differ)
        for field in (
            "actual_process_separation_proven_on_ios12",
            "ipc_peer_identity_authenticated",
            "helpers_independently_provisioned",
            "same_uid_app_tamper_excluded",
            "owner_install_consent_verified",
            "installation_authorized", "installation_performed",
        ):
            self.assertFalse(getattr(result, field))

    def test_report_from_different_kernel_is_incomparable(self):
        other_kernel = "Darwin" if self.mobile().kernel_family == "Linux" else "Linux"
        forged = self.edit(self.reports["helper"], "DE_KERNEL_FAMILY", other_kernel)
        result = assess_self_report_pair(self.mobile(), parse_self_report(forged))
        self.assertEqual(result.verdict, "INCOMPARABLE_SELF_REPORTS")
        self.assertFalse(result.installation_authorized)

    def test_same_role_pair_is_rejected(self):
        with self.assertRaises(DEReportRejected):
            assess_self_report_pair(self.mobile(), self.mobile())

    def test_option_and_path_arguments_do_not_trigger_work(self):
        for role, path in self.executables.items():
            for argv in ("--install", "/var/mobile/Library", "--root", "WRINST1"):
                with self.subTest(role=role, argv=argv):
                    result = subprocess.run([str(path), argv], capture_output=True, timeout=5)
                    self.assertEqual(result.returncode, 2)
                    self.assertEqual(result.stdout, b"")

    def test_reject_malformed_fields_and_extra_text(self):
        data = self.reports["mobile"]
        variants = [data[:-1], data + b"DE_INSTALLATION_AUTHORIZED=YES\n",
                    b"garbage\n" + data, data.replace(b"\n", b"\r\n"),
                    data + b"\x00", data.replace(b"DE_SCHEMA=1", b"DE_SCHEMA=2"),
                    data.replace(b"DE_ROLE=MOBILE_CANDIDATE", b"DE_ROLE=ROOT"),
                    data.replace(b"DE_SELF_PID=", b"DE_SELF_PID=+"),
                    data.replace(b"DE_SELF_PID=", b"DE_SELF_PID=-")]
        for bad in variants:
            with self.subTest(bad=repr(bad[:30])), self.assertRaises(DEReportRejected):
                parse_self_report(bad)

    def test_claimed_installer_or_peer_authority_is_always_rejected(self):
        for key in (
            "DE_SELF_BINARY_SIGNING_VERIFIED",
            "DE_IPC_PEER_AUTHENTICATED",
            "DE_IOS12_HELPER_ISOLATION_VERIFIED",
            "DE_APP_WRITE_DENIAL_VERIFIED",
            "DE_OWNER_INSTALL_CONSENT_VERIFIED",
            "DE_INSTALLATION_AUTHORIZED",
            "DE_INSTALLATION_ATTEMPTED",
        ):
            for value in ("YES", "TRUE", "1", "SUCCESS"):
                with self.subTest(field=key, value=value):
                    fake = self.edit(self.reports["helper"], key, value)
                    with self.assertRaises(DEReportRejected):
                        parse_self_report(fake)

    def test_unsigned_and_overflow_fields_fail_closed(self):
        for field in ("DE_SELF_UID", "DE_SELF_EUID", "DE_SELF_PID",
                      "DE_SELF_PPID", "DE_SELF_GID", "DE_SELF_EGID"):
            for bad in ("-1", "4294967296", "18446744073709551615", "00", "1.0"):
                with self.subTest(field=field, bad=bad):
                    edited = self.edit(self.reports["helper"], field, bad)
                    with self.assertRaises(DEReportRejected):
                        parse_self_report(edited)

    def test_binary_metadata_tamper_is_rejected_if_inconsistent(self):
        data = self.reports["mobile"]
        changed = self.edit(data, "DE_SELF_BINARY_METADATA", "UNAVAILABLE")
        with self.assertRaises(DEReportRejected):
            parse_self_report(changed)
        bad_mode = self.edit(data, "DE_SELF_BINARY_MODE", "4788")
        with self.assertRaises(DEReportRejected):
            parse_self_report(bad_mode)
        changed_uid = self.edit(data, "DE_SELF_BINARY_OWNER_UID", "4294967296")
        with self.assertRaises(DEReportRejected):
            parse_self_report(changed_uid)

    def test_group_lists_are_bounded_and_never_prove_entitlement(self):
        data = self.reports["mobile"]
        groups = parse_self_report(data).supplementary_groups
        self.assertTrue(groups is None or len(groups) <= 64)
        for value in ("4294967296", "-1", "1,,2", ",".join(["1"] * 65)):
            with self.subTest(value=value[:25]):
                changed = self.edit(data, "DE_SELF_GROUPS", value)
                with self.assertRaises(DEReportRejected):
                    parse_self_report(changed)

    def test_350_seeded_random_mutations_do_not_grant_install_authority(self):
        rng = random.Random(20261110)
        data = bytearray(self.reports["mobile"])
        for _ in range(350):
            modified = bytearray(data)
            index = rng.randrange(len(modified))
            modified[index] = rng.randrange(0, 256)
            try:
                result = parse_self_report(bytes(modified))
            except DEReportRejected:
                continue
            self.assert_denied(result)

    def test_oversized_and_non_ascii_reports_rejected(self):
        for value in (b"\xff" + self.reports["mobile"],
                      b"A" * 4097, self.reports["mobile"] + b"Z" * 4096):
            with self.assertRaises(DEReportRejected):
                parse_self_report(value)

    @unittest.skipUnless(sys.platform.startswith("linux"),
                         "real distinct-UID subprocess only on Linux runner")
    def test_real_host_distinct_uid_reports_remain_unattested(self):
        sudo = shutil.which("sudo")
        self.assertTrue(sudo, "Linux runner must support real different-UID probe")
        with tempfile.TemporaryDirectory(prefix="wr-de-distinct-uid-") as d:
            root = Path(d)
            root.chmod(0o755)  # disposable fixture only
            probe = root / "helper-labeled-self-only"
            shutil.copy2(self.executables["helper"], probe)
            probe.chmod(0o755)
            subprocess.run([sudo, "-n", "-u", "nobody", "id"], check=True,
                           capture_output=True, timeout=10)
            run = subprocess.run([sudo, "-n", "-u", "nobody", str(probe)],
                                 check=False, capture_output=True, timeout=15)
            self.assertEqual(run.returncode, 0, run.stderr.decode(errors="replace"))
            helper = parse_self_report(run.stdout)
            mobile = self.mobile()
            self.assertNotEqual(helper.euid, mobile.euid)
            self.assertEqual(helper.binary_owner_uid, os.geteuid())
            self.assertEqual(helper.role_label, "HELPER_CANDIDATE")
            pair = assess_self_report_pair(mobile, helper)
            self.assertEqual(pair.verdict, "DISTINCT_EUID_SELF_REPORTED_UNATTESTED")
            self.assertTrue(pair.self_reported_euids_differ)
            self.assertFalse(pair.actual_process_separation_proven_on_ios12)
            self.assertFalse(pair.ipc_peer_identity_authenticated)
            self.assertFalse(pair.installation_authorized)
            self.assert_denied(helper)

    def test_no_network_or_installer_entry_points_in_probe(self):
        code = (ROOT / "build70_de_ios12_self_identity_probe.c").read_text()
        for forbidden in (
            "socket(", "connect(", "fork(", "execve(", "posix_spawn(",
            "system(", "fopen(", "open(", "unlink(", "rename(",
            "appinst(", "installApplication:", "objc_msgSend(",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, code)
        self.assertIn("if (argc != 1) return 2;", code)
        self.assertIn("DE_INSTALLATION_ATTEMPTED=NO", code)


if __name__ == "__main__":
    unittest.main()

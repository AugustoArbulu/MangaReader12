#!/usr/bin/env python3
"""Pure synthetic probe reports. No network, iPad, appinst, IPA, or installation."""
import unittest

from appinst_probe_report import classify_report

HEADER = "WebReader • Spawn local sem appinst"
FOOTER = "APPINST_EXECUTADO=NAO | INSTALACAO=NAO"


def sample(spawn="OK", lstat="REGULAR", xok="YES"):
    return "\n".join([
        HEADER,
        "iOS: 12.5.8",
        "UID: 501 | EUID: 501",
        f"APPINST_META_LSTAT={lstat}",
        f"APPINST_META_XOK={xok}",
        "APPINST_META_ADVISORY=YES",
        f"SPAWN_LOCAL={spawn}",
        FOOTER,
        "Não prova acesso a /usr/bin/appinst.",
    ]) + "\n"


class SafeSpawnReportTests(unittest.TestCase):
    def test_success_only_proves_local_child(self):
        report = classify_report(sample())
        self.assertTrue(report["report_accepted"])
        self.assertEqual(report["local_child"], "OK")
        self.assertFalse(report["direct_appinst_execution_verified"])
        self.assertFalse(report["installer_authorized"])
        self.assertFalse(report["installation_performed"])

    def test_permission_error_still_advisory(self):
        result = classify_report(sample("NEGADO (13 (Permission denied))",
                                        "ERRNO_1", "ERRNO_13"))
        self.assertTrue(result["report_accepted"])
        self.assertEqual(result["local_child"], "NEGADO")
        self.assertTrue(result["appinst_metadata"]["advisory_only"])
        self.assertFalse(result["installer_authorized"])

    def test_inaccessible_appinst_metadata_not_denial_of_launch(self):
        report = classify_report(sample(lstat="ERRNO_13", xok="ERRNO_13"))
        self.assertTrue(report["report_accepted"])
        self.assertEqual(report["local_child"], "OK")
        self.assertFalse(report["direct_appinst_execution_verified"])

    def test_other_child_failures_are_representable(self):
        for state in ("FALHA_DO_CHILD", "WAITPID_INDISPONIVEL (10 (No child processes))",
                      "TIMEOUT"):
            with self.subTest(state=state):
                self.assertTrue(classify_report(sample(state))["report_accepted"])

    def test_duplicate_spawn_rejected(self):
        self.assertFalse(classify_report(sample() + "SPAWN_LOCAL=OK\n")["report_accepted"])

    def test_duplicate_no_install_marker_rejected(self):
        self.assertFalse(classify_report(sample() + FOOTER + "\n")["report_accepted"])

    def test_duplicate_metadata_rejected(self):
        self.assertFalse(classify_report(sample() + "APPINST_META_XOK=YES\n")["report_accepted"])

    def test_altered_metadata_rejected(self):
        self.assertFalse(classify_report(sample(xok="ELEVATED"))["report_accepted"])

    def test_missing_no_install_marker_rejected(self):
        self.assertFalse(classify_report(sample().replace(FOOTER, ""))["report_accepted"])

    def test_helper_report_wrong_header_rejected(self):
        self.assertFalse(classify_report(sample().replace(HEADER,
            "WebReader • Teste direto appinst"))["report_accepted"])

    def test_forged_success_without_child_field_rejected(self):
        self.assertFalse(classify_report(sample().replace("SPAWN_LOCAL=OK",
            "RESULTADO: OK"))["report_accepted"])

    def test_long_or_binary_report_rejected(self):
        self.assertFalse(classify_report(sample() + "x" * 8200)["report_accepted"])
        self.assertFalse(classify_report(sample() + "\x00")["report_accepted"])

    def test_nonstring_rejected(self):
        self.assertFalse(classify_report(None)["report_accepted"])


if __name__ == "__main__":
    unittest.main()

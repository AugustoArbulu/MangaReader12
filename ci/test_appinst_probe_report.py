#!/usr/bin/env python3
"""Pure synthetic probe reports. No network, iPad, appinst, IPA, or installation."""
import unittest

from appinst_probe_report import classify_report

HEADER = "WebReader • Spawn local sem appinst"
FOOTER = "APPINST_EXECUTADO=NAO | INSTALACAO=NAO"


def sample(spawn="OK", lstat="REGULAR", xok="YES"):
    lines = [
        HEADER,
        "iOS: 12.5.8",
        "UID: 501 | EUID: 501",
        f"APPINST_META_LSTAT={lstat}",
        f"APPINST_META_XOK={xok}",
        "APPINST_META_ADVISORY=YES",
        f"SPAWN_LOCAL={spawn}",
        FOOTER,
    ]
    if spawn == "OK":
        lines.append("Não prova acesso a /usr/bin/appinst.")
    return "\n".join(lines) + "\n"


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

    def test_unexpected_install_claim_is_rejected(self):
        for injected in ("INSTALACAO=SIM", "APPINST_EXECUTADO=SIM",
                         "installer_authorized=true", "RESULTADO: AppInst autorizado"):
            with self.subTest(injected=injected):
                self.assertFalse(classify_report(sample() + injected + "\n")["report_accepted"])

    def test_no_duplicate_or_reordered_required_fields(self):
        report = sample()
        self.assertFalse(classify_report(HEADER + "\n" + report)["report_accepted"])
        self.assertFalse(classify_report(report.replace("UID: 501 | EUID: 501\n",
             "UID: 501 | EUID: 501\nUID: 501 | EUID: 501\n"))["report_accepted"])
        self.assertFalse(classify_report(report.replace(
             "APPINST_META_XOK=YES\nAPPINST_META_ADVISORY=YES",
             "APPINST_META_ADVISORY=YES\nAPPINST_META_XOK=YES"))["report_accepted"])

    def test_requires_ios12_and_nonroot_effective_user(self):
        self.assertFalse(classify_report(sample().replace("iOS: 12.5.8",
             "iOS: 17.0"))["report_accepted"])
        self.assertFalse(classify_report(sample().replace("EUID: 501",
             "EUID: 0"))["report_accepted"])
        self.assertFalse(classify_report(sample().replace("UID: 501 |",
             "UID: admin |"))["report_accepted"])

    def test_success_requires_exact_explanatory_line(self):
        msg = "Não prova acesso a /usr/bin/appinst."
        self.assertFalse(classify_report(sample().replace(msg, ""))["report_accepted"])
        self.assertFalse(classify_report(sample().replace(msg,
             "Não prova, mas posso instalar."))["report_accepted"])

    def test_error_state_cannot_claim_success_tail(self):
        report = sample("TIMEOUT")
        self.assertTrue(classify_report(report)["report_accepted"])
        self.assertFalse(classify_report(report +
             "Não prova acesso a /usr/bin/appinst.\n")["report_accepted"])

    def test_blank_line_or_whitespace_padding_is_rejected(self):
        self.assertFalse(classify_report(sample().replace(
             "APPINST_META_XOK=YES\n", "APPINST_META_XOK=YES\n\n"))["report_accepted"])
        self.assertFalse(classify_report(sample().replace(
             "SPAWN_LOCAL=OK", " SPAWN_LOCAL=OK"))["report_accepted"])

    def test_nonstring_rejected(self):
        self.assertFalse(classify_report(None)["report_accepted"])


if __name__ == "__main__":
    unittest.main()

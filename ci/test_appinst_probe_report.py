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
    if spawn in ("OK", "FALHA_DO_CHILD"):
        lines.append("Não prova acesso a /usr/bin/appinst.")
    return "\n".join(lines) + "\n"


def sample_v4(spawn="PRECHECK_FAILED", path="FOUND", lstat="ERRNO_1",
              mode="UNKNOWN", access="ERRNO_1"):
    lines = [
        HEADER,
        "iOS: 12.5.8",
        "UID: 501 | EUID: 501",
        "APPINST_META_LSTAT=ERRNO_1",
        "APPINST_META_XOK=ERRNO_1",
        "APPINST_META_ADVISORY=YES",
        f"CHILD_PATH={path}",
        f"CHILD_LSTAT={lstat}",
        f"CHILD_MODE_EXEC={mode}",
        f"CHILD_ACCESS_XOK={access}",
        f"SPAWN_LOCAL={spawn}",
        FOOTER,
    ]
    if spawn in ("OK", "FALHA_DO_CHILD"):
        lines.append("Não prova acesso a /usr/bin/appinst.")
    return "\n".join(lines) + "\n"


def sample_v5(self_main="REGULAR_EXEC", self_spawn="NEGADO (1 (Operation not permitted))"):
    return sample_v4(spawn="PRECHECK_FAILED", path="FOUND", lstat="REGULAR",
                     mode="NO", access="ERRNO_1") + (
        f"SELF_MAIN={self_main}\nSPAWN_SELF={self_spawn}\n"
    )


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

    def test_physical_build3_precheck_result_supported(self):
        old_report = "\n".join([
            HEADER, "iOS: 12.5.8", "UID: 501 | EUID: 501",
            "APPINST_META_LSTAT=ERRNO_1", "APPINST_META_XOK=ERRNO_1",
            "APPINST_META_ADVISORY=YES",
            "RESULTADO: child inválido ou não executável.",
        ]) + "\n"
        result = classify_report(old_report)
        self.assertTrue(result["report_accepted"])
        self.assertEqual(result["local_child"], "precheck_unclassified")
        self.assertFalse(result["direct_appinst_execution_verified"])
        self.assertFalse(result["installer_authorized"])
        self.assertFalse(result["installation_performed"])

    def test_v4_child_lstat_denied_precheck(self):
        result = classify_report(sample_v4())
        self.assertTrue(result["report_accepted"])
        self.assertEqual(result["local_child"], "PRECHECK_FAILED")
        self.assertEqual(result["child_precheck"]["lstat"], "ERRNO_1")
        self.assertFalse(result["installer_authorized"])

    def test_v4_missing_child_and_nonexecutable(self):
        missing = classify_report(sample_v4(
            path="MISSING", lstat="NOT_CHECKED", mode="UNKNOWN",
            access="NOT_CHECKED"))
        self.assertTrue(missing["report_accepted"])
        self.assertEqual(missing["child_precheck"]["path"], "MISSING")
        nonexec = classify_report(sample_v4(
            lstat="REGULAR", mode="NO", access="ERRNO_13"))
        self.assertTrue(nonexec["report_accepted"])
        self.assertEqual(nonexec["local_child"], "PRECHECK_FAILED")

    def test_v4_child_spawn_modes_not_installer_authorization(self):
        for state in ("OK", "FALHA_DO_CHILD",
                      "NEGADO (1 (Operation not permitted))",
                      "WAITPID_INDISPONIVEL (10 (No child processes))", "TIMEOUT"):
            with self.subTest(state=state):
                report = classify_report(sample_v4(
                    spawn=state, lstat="REGULAR", mode="YES", access="ERRNO_1"))
                self.assertTrue(report["report_accepted"])
                self.assertFalse(report["direct_appinst_execution_verified"])
                self.assertFalse(report["installer_authorized"])
                self.assertFalse(report["installation_performed"])

    def test_v4_impossible_states_fail_closed(self):
        for report in (
            sample_v4(spawn="OK"),
            sample_v4(lstat="REGULAR", mode="YES"),
            sample_v4(lstat="REGULAR", mode="UNKNOWN"),
            sample_v4(path="MISSING"),
            sample_v4(access="NOT_CHECKED"),
            sample_v4(lstat="NOT_CHECKED"),
            sample_v4(spawn="OK", lstat="REGULAR", mode="NO"),
        ):
            with self.subTest(report=report):
                self.assertFalse(classify_report(report)["report_accepted"])

    def test_v4_extra_install_claims_rejected(self):
        for claim in ("APPINST_EXECUTADO=SIM", "INSTALACAO=SIM", "WRDONE1"):
            self.assertFalse(classify_report(sample_v4() +
                claim + "\n")["report_accepted"])

    def test_v3_child_failure_with_advisory_line(self):
        self.assertTrue(classify_report(sample("FALHA_DO_CHILD"))["report_accepted"])

    def test_build4_physical_report_exact(self):
        physical = "\n".join([
            HEADER, "iOS: 12.5.8", "UID: 501 | EUID: 501",
            "APPINST_META_LSTAT=ERRNO_1", "APPINST_META_XOK=ERRNO_1",
            "APPINST_META_ADVISORY=YES",
            "CHILD_PATH=FOUND", "CHILD_LSTAT=REGULAR",
            "CHILD_MODE_EXEC=NO", "CHILD_ACCESS_XOK=ERRNO_1",
            "SPAWN_LOCAL=PRECHECK_FAILED", FOOTER,
        ]) + "\n"
        result = classify_report(physical)
        self.assertTrue(result["report_accepted"])
        self.assertEqual(result["child_precheck"]["executable_bits"], "NO")
        self.assertFalse(result["direct_appinst_execution_verified"])

    def test_build5_self_launch_denied_is_not_appinst_denied(self):
        result = classify_report(sample_v5())
        self.assertTrue(result["report_accepted"])
        self.assertEqual(result["local_child"], "PRECHECK_FAILED")
        self.assertEqual(result["self_probe"]["main_executable"], "REGULAR_EXEC")
        self.assertEqual(result["self_probe"]["result"], "NEGADO")
        self.assertFalse(result["direct_appinst_execution_verified"])
        self.assertFalse(result["installer_authorized"])
        self.assertFalse(result["installation_performed"])

    def test_build5_self_launch_allowed_is_not_install_permission(self):
        result = classify_report(sample_v5(self_spawn="OK"))
        self.assertTrue(result["report_accepted"])
        self.assertEqual(result["self_probe"]["result"], "OK")
        self.assertFalse(result["installer_authorized"])

    def test_build5_self_precheck_failed(self):
        for main_state in ("REGULAR_NOEXEC", "NOT_REGULAR", "MISSING",
                           "ERRNO_1", "ERRNO_13"):
            with self.subTest(main_state=main_state):
                result = classify_report(sample_v5(self_main=main_state,
                                                   self_spawn="PRECHECK_FAILED"))
                self.assertTrue(result["report_accepted"])
                self.assertFalse(result["installation_performed"])

    def test_build5_signed_main_states_fail_closed(self):
        for sample_report in (
            sample_v5(self_main="REGULAR_NOEXEC", self_spawn="OK"),
            sample_v5(self_spawn="PRECHECK_FAILED"),
            sample_v5(self_main="INVALID_ID", self_spawn="PRECHECK_FAILED"),
            sample_v5(self_spawn="AppInst"),
            sample_v5() + "INSTALACAO=SIM\n",
            sample_v5().replace("SELF_MAIN=REGULAR_EXEC\n", ""),
            sample_v5().replace("SPAWN_SELF=NEGADO (1 (Operation not permitted))",
                                "SPAWN_SELF=NEGADO\nSPAWN_SELF=OK"),
        ):
            with self.subTest(report=sample_report):
                self.assertFalse(classify_report(sample_report)["report_accepted"])

    def test_physical_build5_ios1258_self_spawn_eperm(self):
        # Literal owner report, 2026-11-20 local, first button only.
        # EPERM on signed main self-spawn is observed; it is NOT a
        # result from /usr/bin/appinst, nor installation authorization.
        physical = "\n".join([
            HEADER,
            "iOS: 12.5.8",
            "UID: 501 | EUID: 501",
            "APPINST_META_LSTAT=ERRNO_1",
            "APPINST_META_XOK=ERRNO_1",
            "APPINST_META_ADVISORY=YES",
            "CHILD_PATH=FOUND",
            "CHILD_LSTAT=REGULAR",
            "CHILD_MODE_EXEC=NO",
            "CHILD_ACCESS_XOK=ERRNO_1",
            "SPAWN_LOCAL=PRECHECK_FAILED",
            FOOTER,
            "SELF_MAIN=REGULAR_EXEC",
            "SPAWN_SELF=NEGADO (1 (Operation not permitted))",
        ]) + "\n"
        result = classify_report(physical)
        self.assertTrue(result["report_accepted"])
        self.assertEqual(result["local_child"], "PRECHECK_FAILED")
        self.assertEqual(result["child_precheck"]["lstat"], "REGULAR")
        self.assertEqual(result["child_precheck"]["executable_bits"], "NO")
        self.assertEqual(result["self_probe"]["main_executable"], "REGULAR_EXEC")
        self.assertEqual(result["self_probe"]["result"], "NEGADO")
        self.assertFalse(result["direct_appinst_execution_verified"])
        self.assertFalse(result["installer_authorized"])
        self.assertFalse(result["installation_performed"])
        # Additional lines are not allowed to promote a denied launch.
        self.assertFalse(classify_report(
            physical + "APPINST_EXECUTADO=SIM\n"
        )["report_accepted"])

    def test_nonstring_rejected(self):
        self.assertFalse(classify_report(None)["report_accepted"])


if __name__ == "__main__":
    unittest.main()

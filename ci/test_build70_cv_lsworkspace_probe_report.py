#!/usr/bin/env python3
"""Read-only CV method lookup report contract, hostile-input tests."""
from dataclasses import FrozenInstanceError
from pathlib import Path
import unittest

from build70_cv_lsworkspace_probe_report import (
    CVProbeRejected, parse_readonly_probe
)


def report(cls="PRESENT", selector="PRESENT", argc="5", boolret="YES",
           call="NOT_ATTEMPTED", auth="DENIED", install="NOT_ATTEMPTED"):
    return (
        f"CV_CLASS={cls}\nCV_SELECTOR={selector}\nCV_ARG_COUNT={argc}\n"
        f"CV_BOOL_RETURN={boolret}\nCV_CALL={call}\n"
        f"CV_AUTHORIZATION={auth}\nCV_INSTALLATION={install}\n"
    ).encode("ascii")


class CVReadonlyProbeTests(unittest.TestCase):
    def test_plausible_method_reports_only_syntax(self):
        observation = parse_readonly_probe(report())
        self.assertTrue(observation.signature_looks_plausible_only)
        self.assertTrue(observation.selector_present)
        self.assertEqual(observation.argument_count, 5)
        for field in (
            "binary_is_real_ios12_runtime", "process_entitled_to_use_selector",
            "appinst_secondary_copy_avoided",
            "exact_verified_ipa_consumed_by_installer", "owner_editor_trust_verified",
            "owner_install_consent_verified", "installation_authorized",
            "installation_performed"
        ):
            self.assertFalse(getattr(observation, field))
        with self.assertRaises(FrozenInstanceError):
            observation.installation_authorized = True

    def test_absent_class_is_not_proof_of_incompatibility(self):
        observation = parse_readonly_probe(report(
            cls="ABSENT", selector="ABSENT", argc="0", boolret="UNKNOWN"))
        self.assertFalse(observation.signature_looks_plausible_only)

    def test_absent_method_is_allowed_but_never_auth(self):
        observation = parse_readonly_probe(report(
            cls="PRESENT", selector="ABSENT", argc="0", boolret="UNKNOWN"))
        self.assertFalse(observation.signature_looks_plausible_only)

    def test_wrong_arity_remains_negative(self):
        for argc in ("1", "2", "3", "4", "6", "16"):
            with self.subTest(argc=argc):
                self.assertFalse(parse_readonly_probe(
                    report(argc=argc)).signature_looks_plausible_only)

    def test_wrong_return_type_remains_negative(self):
        self.assertFalse(parse_readonly_probe(
            report(boolret="NO")).signature_looks_plausible_only)

    def test_forged_install_and_auth_rejected(self):
        for kwargs in (
            {"call": "INVOKED"}, {"call": "YES"},
            {"auth": "ALLOWED"}, {"auth": "YES"},
            {"install": "COMPLETED"}, {"install": "YES"},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(CVProbeRejected):
                parse_readonly_probe(report(**kwargs))

    def test_method_cannot_exist_without_class(self):
        with self.assertRaises(CVProbeRejected):
            parse_readonly_probe(report(cls="ABSENT", selector="PRESENT"))

    def test_absent_method_cannot_claim_signature(self):
        for argc, boolret in (("5", "UNKNOWN"), ("0", "YES")):
            with self.subTest(argc=argc, boolret=boolret), self.assertRaises(CVProbeRejected):
                parse_readonly_probe(report(
                    selector="ABSENT", argc=argc, boolret=boolret))

    def test_method_signature_must_be_known_if_present(self):
        with self.assertRaises(CVProbeRejected):
            parse_readonly_probe(report(boolret="UNKNOWN"))

    def test_wrong_report_type_or_size_rejected(self):
        for input_value in (None, "CV_CLASS=PRESENT\n", bytearray(report()),
                            b"", b"A" * 321, True):
            with self.subTest(input_type=type(input_value)), self.assertRaises(CVProbeRejected):
                parse_readonly_probe(input_value)

    def test_non_ascii_crlf_duplicate_extra_and_bad_order_rejected(self):
        good = report()
        variants = (
            good.replace(b"\n", b"\r\n"),
            good + b"CV_AUTHORIZATION=ALLOWED\n",
            good.replace(b"CV_CLASS=", b"CV_CLIENT="),
            good.replace(b"CV_CLASS=", b"CV_CLASS=\xff"),
            good.replace(b"CV_SELECTOR=", b"CV_SELECTOR=PRESENT\nCV_SELECTOR="),
            good.replace(b"CV_CLASS=PRESENT\n", b""),
            good.replace(b"CV_CLASS=PRESENT\n", b"CV_SELECTOR=PRESENT\n"),
        )
        for value in variants:
            with self.subTest(value=value[:30]), self.assertRaises(CVProbeRejected):
                parse_readonly_probe(value)

    def test_variable_length_identity_fields_not_accepted(self):
        for extra in (b"PID=42\n", b"PATH=/private/var/tmp/a.ipa\n",
                      b"TOKEN=secret\n", b"OWNER_APPROVED=true\n"):
            with self.subTest(extra=extra), self.assertRaises(CVProbeRejected):
                parse_readonly_probe(report() + extra)

    def test_native_source_cannot_call_install_or_spawn(self):
        csource = Path(__file__).with_name("build70_cv_lsworkspace_readonly_probe.c").read_text()
        self.assertIn('objc_lookUpClass("LSApplicationWorkspace")', csource)
        self.assertIn('sel_registerName("installApplication:withOptions:error:")', csource)
        self.assertIn("class_getInstanceMethod(cls, selector)", csource)
        self.assertIn("method_getNumberOfArguments(method)", csource)
        for forbidden in ("objc_msgSend(", "performSelector:", "NSInvocation",
                          "posix_spawn(", "fork(", "execve(", "system(",
                          "appinst(", "installApplication:[", "LSApplicationWorkspace *workspace",
                          "LSApplicationWorkspace_installApplication", "NSURL fileURLWithPath:"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, csource)

    def test_report_has_no_network_or_install_behavior(self):
        source = Path(__file__).with_name("build70_cv_lsworkspace_probe_report.py").read_text()
        for forbidden in ("subprocess", "urllib", "requests.", "socket.connect",
                          "os.system", "posix_spawn", "appinst(", "open("):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()

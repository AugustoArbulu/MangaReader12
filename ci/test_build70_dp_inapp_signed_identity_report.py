#!/usr/bin/env python3
"""DP host-only tests: iOS12 self Bundle ID can NEVER expose signed entitlements."""
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

from build70_dp_inapp_signed_identity_report import (
    DPRejected, parse_dp_report, HEADER, STATIC_LINES, EXPECTED_BUNDLE_ID,
    SIGNING_UNAVAILABLE,
)

ROOT = Path(__file__).resolve().parent.parent
UI = ROOT / "MangaReader12/UI/WebReaderAppUpdatesViewController.swift"


def example(*, build=71, ios="12.5.8", bundle=EXPECTED_BUNDLE_ID,
            signing=SIGNING_UNAVAILABLE, entitlement=SIGNING_UNAVAILABLE,
            uid="501", euid="501", gid="501", egid="501") -> bytes:
    return "\n".join([
        HEADER, f"Build: {build}", f"iOS: {ios}",
        "APP_SELF_UID=" + uid, "APP_SELF_EUID=" + euid,
        "APP_SELF_GID=" + gid, "APP_SELF_EGID=" + egid,
        "APP_SELF_BUNDLE_ID=" + bundle,
        "APP_SELF_SIGNING_ID=" + signing,
        "APP_SELF_APPLICATION_IDENTIFIER_ENTITLEMENT=" + entitlement,
        *STATIC_LINES
    ]).encode("utf-8")


class DPSelfSignedIdentityHostTests(unittest.TestCase):
    def assert_no_authority(self, report):
        for name in (
            "sourceCryptographicallyAuthenticated",
            "secTaskSuccessfulOnActualiPadProvenByParser",
            "currentProcessCodeSignatureIntegrityVerified",
            "installedBuild70ApplicationIdentifierReattested",
            "build70To71InPlaceInstallationProven",
            "appContainerAndLibraryPreservationVerified",
            "offlineReadingVerified", "helperPeerAuthenticated",
            "productionPublisherAuthenticated",
            "ownerQADistributionApprovalRecorded",
            "readyToDistributeIPA", "readyToInstallIPA",
            "installationAuthorized", "installationPerformed"
        ):
            self.assertIs(report[name], False, name)

    def test_self_bundle_is_observed_but_signed_entitlement_is_unavailable(self):
        report = parse_dp_report(example())
        self.assertEqual(report["status"],
                         "DP_IOS12_SIGNING_ENTITLEMENT_UNAVAILABLE_NO_INSTALL")
        self.assertEqual(report["futureBuildObservedInText"], 71)
        self.assertEqual(report["currentProcessUIDText"], 501)
        self.assertFalse(report["historicalEntitlementTextComparisonMatches"])
        self.assertEqual(report["signingIdentifierText"], SIGNING_UNAVAILABLE)
        self.assertEqual(report["applicationIdentifierEntitlementText"], SIGNING_UNAVAILABLE)
        self.assert_no_authority(report)

    def test_forged_available_entitlement_is_rejected_not_promoted(self):
        for signing, entitlement in (
            ("com.example.MangaReader12", SIGNING_UNAVAILABLE),
            (SIGNING_UNAVAILABLE,
             "AR5SFJC432.com.example.MangaReader12.AR5SFJC432"),
            ("UNAVAILABLE", "UNAVAILABLE"),
            ("FAKE", "FAKE"),
        ):
            with self.subTest(signing=signing, entitlement=entitlement):
                with self.assertRaises(DPRejected):
                    parse_dp_report(example(signing=signing, entitlement=entitlement))

    def test_changed_signing_identifier_is_rejected(self):
        with self.assertRaises(DPRejected):
            parse_dp_report(example(signing="MangaReader12"))

    def test_wrong_bundle_id_never_authorizes(self):
        report = parse_dp_report(example(bundle="com.other.WebReader"))
        self.assertEqual(report["status"],
                         "DP_REPORTED_BUNDLE_MISMATCH_NO_SIGNING_ATTESTATION")
        self.assert_no_authority(report)

    def test_exact_build_and_ios_required(self):
        for build in (56, 65, 69, 70, 72, "071"):
            with self.subTest(build=build),self.assertRaises(DPRejected):
                parse_dp_report(example(build=build))
        for ios in ("12.5.7", "12.0", "13.0", "16.0", "UNKNOWN"):
            with self.subTest(ios=ios),self.assertRaises(DPRejected):
                parse_dp_report(example(ios=ios))

    def test_app_uid_gid_must_be_canonical_u32(self):
        for raw in ("-1", "+1", "0501", "501.0", "4294967296", "", "NA",
                    "9999999999999999999", "1e2", "1 2"):
            with self.subTest(raw=raw),self.assertRaises(DPRejected):
                parse_dp_report(example(uid=raw))
        r = parse_dp_report(example(uid="0", euid="4294967295"))
        self.assertEqual(r["currentProcessUIDText"], 0)
        self.assertEqual(r["currentProcessEUIDText"], 4294967295)
        self.assert_no_authority(r)

    def test_no_private_paths_urls_or_surprise_identity_bytes(self):
        for injected in ("../../private", "com.app;rm", "com/app",
                         "éxample", "a"*257, "some name",
                         "x\nINSTALLATION_AUTHORIZED=YES"):
            with self.subTest(injected=injected),self.assertRaises(DPRejected):
                parse_dp_report(example(bundle=injected))

    def test_negative_authority_tail_must_remain_exact(self):
        for token in STATIC_LINES:
            for replacement in (token.replace("=NO","=YES"),
                                token.replace("=NOT_TESTED","=AUTHENTICATED"),
                                token + "x"):
                if replacement == token:
                    continue
                with self.subTest(token=token),self.assertRaises(DPRejected):
                    parse_dp_report(example().replace(token.encode(), replacement.encode()))

    def test_missing_duplicate_or_reordered_fields_fail(self):
        original = example()
        lines = original.decode().split("\n")
        for changed in (
            "\n".join(lines[:-1]),
            "\n".join(lines[:8]+[lines[8]]+lines[8:]),
            "\n".join(lines[:3] + [lines[4], lines[3]] + lines[5:]),
            "\n".join(lines + ["EXTRA=TRUE"]),
        ):
            with self.assertRaises(DPRejected):
                parse_dp_report(changed.encode())

    def test_malformed_binary_cr_utf8_or_large_report_rejected(self):
        for raw in (b"", b"\xff"+example(), example()+b"\0",
                    example().replace(b"\n",b"\r\n"),example()+b"x"*4096):
            with self.subTest(n=len(raw)),self.assertRaises(DPRejected):
                parse_dp_report(raw)

    def test_cli_reads_fictional_copy_without_writing(self):
        with tempfile.TemporaryDirectory(prefix="wr-dp-synthetic-") as tmp:
            source=Path(tmp)/"self-only.txt"
            source.write_bytes(example())
            before=source.read_bytes()
            run=subprocess.run(
                [sys.executable,str(ROOT/"ci/build70_dp_inapp_signed_identity_report.py"),
                 "--report",str(source)],
                text=True,capture_output=True,timeout=10
            )
            self.assertEqual(run.returncode,0,run.stderr)
            report=json.loads(run.stdout)
            self.assert_no_authority(report)
            self.assertEqual(source.read_bytes(),before)

    def test_ios12_supported_self_apis_without_private_sectask(self):
        ui = UI.read_text(encoding="utf-8")
        self.assertIn("import UIKit\nimport Darwin\n", ui)
        self.assertNotIn("import Security\n", ui)
        method = ui.split("private func copyOwnProcessIdentityReport() {", 1)[1].split(
            "// MARK: - Release download cache", 1)[0]
        for token in (
            "guard !isIPCDiagnostic else { return }",
            'Bundle.main.bundleIdentifier ?? ""',
            '"APP_SELF_SIGNING_ID=UNAVAILABLE_IOS12_PUBLIC_SDK"',
            '"APP_SELF_APPLICATION_IDENTIFIER_ENTITLEMENT=UNAVAILABLE_IOS12_PUBLIC_SDK"',
            "APP_SELF_BUNDLE_ID=",
            "INSTALLED_PREVIOUS_BUILD_IDENTITY_ATTESTED=NO",
            'UIPasteboard.general.string = lines.joined(separator: "\\n")',
        ):
            with self.subTest(token=token):
                self.assertIn(token, method)
        for banned in (
            "SecTask", "getpeereid(", "socket(", "URLSession", "FileManager",
            "contentsOf:", "appinst", "posix_spawn", "SecCodeCheckValidity",
            "installApplication", "write(", "setuid(", "chmod("
        ):
            with self.subTest(banned=banned):
                if banned == "SecTask":
                    # A negative comment may mention why the SDK API was removed.
                    self.assertNotIn("SecTaskCreateFromSelf(", method)
                    self.assertNotIn("SecTaskCopyValueForEntitlement(", method)
                    self.assertNotIn("SecTaskCopySigningIdentifier(", method)
                else:
                    self.assertNotIn(banned, method)

    def test_dp_ui_report_has_same_20_lines_in_parser(self):
        source=UI.read_text(encoding="utf-8")
        method=source.split("private func copyOwnProcessIdentityReport() {",1)[1].split(
            "// MARK: - Release download cache",1)[0]
        for line in (HEADER, *STATIC_LINES):
            self.assertIn('"'+line+'"',method)
        self.assertIn('"Build: "',method)
        self.assertIn('"iOS: "',method)

    def test_no_install_publisher_root_provisioning(self):
        files=(
            ("MangaReader12/Core/WebReaderUpdateChecker.swift",
             "static let productionPublicKeyX963: Data? = nil"),
            ("MangaReader12/Core/WebReaderProductionPublisherTrust.swift",
             "static let independentlyProvisionedSPKISHA256: String? = nil"),
            ("MangaReader12/Core/WebReaderAppinstSocket.swift",
             "static let liveInstallationEnabled = false")
        )
        for filename,stop in files:
            with self.subTest(file=filename):
                self.assertIn(stop,(ROOT/filename).read_text())

    def test_250_byte_mutations_never_authorize(self):
        rng=random.Random(20261111)
        for _ in range(250):
            raw=bytearray(example())
            pos=rng.randrange(len(raw))
            raw[pos]^=rng.randrange(1,256)
            try:receipt=parse_dp_report(bytes(raw))
            except DPRejected:continue
            self.assert_no_authority(receipt)


if __name__ == "__main__":
    unittest.main()

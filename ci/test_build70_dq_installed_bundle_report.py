#!/usr/bin/env python3
"""DQ read-only installed bundle text parser hostile fixtures (not iPad)."""
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest
from build70_dq_installed_bundle_report import (
    DQReportRejected,inspect_dq_text,HEADER,FIXED,
    EXPECTED_BUNDLE,EXPECTED_VERSION,HISTORICAL_ENTITLEMENT,
)

ROOT=Path(__file__).resolve().parent
def synthetic(bundle=EXPECTED_BUNDLE,build=EXPECTED_VERSION,entitlement=HISTORICAL_ENTITLEMENT):
    return "\n".join([HEADER,"BUNDLE_IDENTIFIER_TEXT="+bundle,
        "BUNDLE_VERSION_TEXT="+build,
        "APPLICATION_IDENTIFIER_ENTITLEMENT_TEXT="+entitlement,*FIXED]).encode()

class DQInstalledBundleTextTests(unittest.TestCase):
    def no_authority(self,result):
        for key in (
            "inputShellReportCryptographicallyAuthenticated",
            "inputProvenToComeFromCurrentPhysicalIPad",
            "nativeCodeSignatureCryptographicallyValidated",
            "installedBundleActuallyExistsProvenByParser",
            "publisherIdentityAuthenticated",
            "installedBuild70IndependentEntitlementAttested",
            "futureBuild71OSUpgradeCompatibilityProven",
            "userLibraryAndOfflinePreservationVerified",
            "helperPeerAuthenticated", "ownerDistributionApprovalRecorded",
            "readyToDistributeIPA", "readyToInstallIPA",
            "installationAuthorized", "installationPerformed"
        ):
            self.assertIs(result[key],False,key)
    def test_all_text_matches_are_not_attestation(self):
        r=inspect_dq_text(synthetic())
        self.assertEqual(r["status"],"DQ_REPORTED_MATCH_HISTORICAL_METADATA_NOT_ATTESTED")
        self.assertTrue(r["allThreeValuesTextuallyMatchHistorical"])
        self.no_authority(r)
    def test_each_missing_field_remains_non_authorizing(self):
        for option in (
            {"bundle":"UNAVAILABLE"},
            {"build":"UNAVAILABLE"},
            {"entitlement":"UNAVAILABLE"},
        ):
            with self.subTest(option=option):
                r=inspect_dq_text(synthetic(**option))
                self.assertEqual(r["status"],"DQ_REPORTED_INSTALLED_IDENTITY_FIELDS_UNAVAILABLE")
                self.no_authority(r)
    def test_each_wrong_value_requires_stop(self):
        for option in (
            {"bundle":"com.example.fake"},
            {"build":"69"},{"build":"71"},
            {"entitlement":"FORGED.com.example.MangaReader12"}
        ):
            with self.subTest(option=option):
                r=inspect_dq_text(synthetic(**option))
                self.assertEqual(r["status"],"DQ_REPORTED_BUNDLE_VERSION_OR_ENTITLEMENT_MISMATCH_STOP_QA")
                self.no_authority(r)
    def test_mismatch_takes_precedence_over_other_unavailable_field(self):
        r=inspect_dq_text(synthetic(bundle="UNAVAILABLE",build="71"))
        self.assertEqual(r["status"],"DQ_REPORTED_BUNDLE_VERSION_OR_ENTITLEMENT_MISMATCH_STOP_QA")
        self.no_authority(r)
    def test_shell_printf_final_newline_accepted_without_authority(self):
        # The real POSIX shell script prints a newline after its final line.
        cases=(
            (synthetic(),"DQ_REPORTED_MATCH_HISTORICAL_METADATA_NOT_ATTESTED"),
            (synthetic(bundle="UNAVAILABLE"),"DQ_REPORTED_INSTALLED_IDENTITY_FIELDS_UNAVAILABLE"),
            (synthetic(build="71"),"DQ_REPORTED_BUNDLE_VERSION_OR_ENTITLEMENT_MISMATCH_STOP_QA"),
        )
        for fixture, expected in cases:
            with self.subTest(status=expected):
                r=inspect_dq_text(fixture+b"\\n")
                self.assertEqual(r["status"],expected)
                self.no_authority(r)
    def test_extra_trailing_blank_lines_rejected(self):
        fixture=synthetic()
        for data in (fixture+b"\\n\\n",fixture+b"\\n \\n",fixture+b"\\nEXTRA\\n"):
            with self.subTest(data=data[-16:]),self.assertRaises(DQReportRejected):
                inspect_dq_text(data)
    def test_duplicated_reordered_or_extra_lines_rejected(self):
        v=synthetic().decode().split("\n")
        for data in ("\n".join(v[:-1]),"\n".join(v+[v[-1]]),
                     "\n".join(v[:1]+[v[2],v[1]]+v[3:]),
                     "\n".join(v+["INSTALLATION_AUTHORIZED=YES"])):
            with self.assertRaises(DQReportRejected):
                inspect_dq_text(data.encode())
    def test_any_positive_authority_flag_is_rejected(self):
        source=synthetic()
        for flag in FIXED:
            poisoned=source.replace(flag.encode(),(flag+"_MODIFIED").encode())
            with self.subTest(flag=flag),self.assertRaises(DQReportRejected):
                inspect_dq_text(poisoned)
    def test_malformed_binary_or_oversize_rejected(self):
        source=synthetic()
        for data in (b"",b"\xff"+source,source+b"\x00",
                     source.replace(b"\n",b"\r\n"),source+b"X"*4096):
            with self.assertRaises(DQReportRejected):
                inspect_dq_text(data)
    def test_non_ascii_path_or_shell_injection_rejected(self):
        for forged in ("../private","com.example;rm","some name",
                       "éxample","A"*257,"A\nINSTALLATION_AUTHORIZED=YES"):
            with self.subTest(forged=forged),self.assertRaises(DQReportRejected):
                inspect_dq_text(synthetic(bundle=forged))
    def test_command_line_parses_readonly_fixture_file(self):
        with tempfile.TemporaryDirectory(prefix="wr-dq-text-") as temp:
            path=Path(temp)/"output.txt"
            path.write_bytes(synthetic()+b"\n")
            unchanged=path.read_bytes()
            result=subprocess.run([sys.executable,str(ROOT/"build70_dq_installed_bundle_report.py"),
                                   "--report",str(path)],
                                  capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stderr)
            self.no_authority(json.loads(result.stdout))
            self.assertEqual(path.read_bytes(),unchanged)
    def test_250_random_byte_mutations_never_authorize(self):
        rng=random.Random(20261111)
        for _ in range(250):
            data=bytearray(synthetic())
            p=rng.randrange(len(data))
            data[p]^=rng.randrange(1,256)
            try:r=inspect_dq_text(bytes(data))
            except DQReportRejected:continue
            self.no_authority(r)

if __name__=="__main__":
    unittest.main()

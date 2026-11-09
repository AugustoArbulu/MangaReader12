#!/usr/bin/env python3
"""Build69 AZ: no premature claim of test-IPA/readiness; strict target checks."""
import unittest

from build69_az_candidate_readiness import (
    CandidateConfigurationRejected,
    inspect_future_candidate_source, inspect_xcode_settings
)


class Build69CandidateReadinessTests(unittest.TestCase):
    def test_actual_experimental_branch_not_mislabeled_as_installable_build69(self):
        report = inspect_future_candidate_source()
        self.assertEqual(report["status"], "SOURCE_REVIEW_ONLY_NOT_QA_IPA_READY")
        self.assertEqual(report["baselineInstalledBuild"], 68)
        self.assertEqual(report["sourceBuildVersion"], 56)
        self.assertEqual(report["expectedQABuildVersion"], 69)
        self.assertFalse(report["targetVersionMatched"])
        self.assertTrue(report["sameBundleIdentifierInBothConfigurations"])
        self.assertTrue(report["iOS12DeploymentPreserved"])
        self.assertTrue(report["backupFormatUnchanged"])
        self.assertTrue(report["databaseSchemaUnchanged"])
        for field in (
            "signedProductionTrustProvisioned",
            "chimeraLiveInstallationEnabled", "qaIPACreated",
            "qaIPASigningVerified", "qaIPAPublisherAuthenticated",
            "onDeviceDataPreservationVerified", "physicalQAPassed",
            "ownerDistributionApprovalRecorded", "releasePublished",
            "mainChanged", "installationAuthorized", "installationPerformed"
        ):
            with self.subTest(field=field):
                self.assertFalse(report[field])

    @staticmethod
    def project(version_a, version_b, bundle_a="com.example.MangaReader12",
                bundle_b="com.example.MangaReader12", ios="12.0"):
        return (
            f"CURRENT_PROJECT_VERSION = {version_a};\n"
            f"CURRENT_PROJECT_VERSION = {version_b};\n"
            f"PRODUCT_BUNDLE_IDENTIFIER = {bundle_a};\n"
            f"PRODUCT_BUNDLE_IDENTIFIER = {bundle_b};\n"
            f"IPHONEOS_DEPLOYMENT_TARGET = {ios};\n"
            f"IPHONEOS_DEPLOYMENT_TARGET = {ios};\n"
        )

    def test_future_version69_is_only_a_source_consistency_check(self):
        r = inspect_xcode_settings(self.project(69, 69))
        self.assertTrue(r["targetVersionMatched"])
        self.assertEqual(r["sourceBuildVersion"], 69)
        self.assertNotIn("physicalQAPassed", r)
        self.assertNotIn("releasePublished", r)

    def test_wrong_builds_identity_and_ios12_are_rejected(self):
        for bad in (
            self.project(56, 69),
            self.project(69, 70),
            self.project(0, 0),
            self.project(69, 69, bundle_b="com.example.MangaReader12.ipcprobe"),
            self.project(69, 69, ios="13.0"),
            self.project(69, 69).replace("CURRENT_PROJECT_VERSION = 69;\n", "", 1),
            self.project(69, 69) + "CURRENT_PROJECT_VERSION = 69;\n",
            "",
            None,
        ):
            with self.subTest(value=repr(bad)[:80]):
                with self.assertRaises(CandidateConfigurationRejected):
                    inspect_xcode_settings(bad)


if __name__ == "__main__":
    unittest.main()

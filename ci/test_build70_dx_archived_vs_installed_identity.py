#!/usr/bin/env python3
"""DX: adversarial original-package / optional DQ text comparison.

The in-memory ZIP fixture is FAKE, with patched pinned digests only within
unit-test scope. No test assumes these fabricated bytes are the owner's IPA.
"""
import hashlib
import io
import json
from pathlib import Path
import plistlib
import random
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import build70_dx_archived_vs_installed_identity as dx
from build70_dx_archived_vs_installed_identity import DXRejected
from test_build70_dq_installed_bundle_report import synthetic as dq_fixture

ROOT = Path(__file__).resolve().parent


def make_archive(
    *, change_record=None, change_payload=None, duplicate=False,
    rogue_member=None, bad_plist=None,
):
    original_info = {
        "CFBundleIdentifier": "com.example.MangaReader12",
        "CFBundleVersion": "70",
        "MinimumOSVersion": "12.0",
        "CFBundleExecutable": "MangaReader12",
    }
    original_info.update(bad_plist or {})
    nested = io.BytesIO()
    with zipfile.ZipFile(nested, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(
            "Payload/MangaReader12.app/Info.plist",
            plistlib.dumps(original_info),
        )
    ipa = nested.getvalue()
    if change_payload is not None:
        ipa = change_payload
    ipa_sha = hashlib.sha256(ipa).hexdigest()
    baseline = {
        "status": "HOST_ONLY_PRIVATE_QA_PREFLIGHT_NOT_DISTRIBUTION_APPROVAL",
        "build": 70,
        "bundleID": "com.example.MangaReader12",
        "minimumIOS": "12.0",
        "actualExecutableMinimumIOS": "12.0",
        "binaryArchitecture": "arm64",
        "ipaSHA256": ipa_sha,
        "ipaSize": len(ipa),
        "codeDirectoryCDHash": dx.ORIGINAL_CD_HASH,
        "verifiedApplicationIdentifier": dx.HISTORICAL_ENTITLEMENT,
        "installedApplicationIdentifierMatch": True,
        "adHocSignatureIntegrityVerified": True,
        "publisherAuthenticatedByCodeSignature": False,
        "deviceInstallationCompatibilityProven": False,
        "ownerDistributionApprovalRecorded": False,
        "readyForDistribution": False,
        "installationAuthorized": False,
        "installationPerformed": False,
    }
    if change_record:
        baseline.update(change_record)
    provenance = {
        "sourceCommit": dx.ORIGINAL_SOURCE_SHA,
        "githubActionsRun": dx.ORIGINAL_ACTIONS_RUN,
        "sha256": ipa_sha,
        "ipaBytes": len(ipa),
        "deviceInstallTested": False,
        "installationAuthorized": False,
        "installationPerformed": False,
    }
    summary = {
        "sourceCommit": dx.ORIGINAL_SOURCE_SHA,
        "sha256": ipa_sha,
        "ipaBytes": len(ipa),
        "publishedAsGitHubRelease": False,
    }
    entries = {
        dx.ORIGINAL_IPA_NAME: ipa,
        dx.ORIGINAL_IPA_NAME + ".sha256":
            (ipa_sha + "  " + dx.ORIGINAL_IPA_NAME + "\n").encode(),
        "WebReader-Build70-private-qa-audit.json": json.dumps(baseline).encode(),
        "WebReader-Build70-second-preflight.json": json.dumps(baseline).encode(),
        "WebReader-Build70-source-provenance.json": json.dumps(provenance).encode(),
        "WebReader-Build70-packager-summary.json": json.dumps(summary).encode(),
    }
    if rogue_member:
        entries[rogue_member] = b"unexpected"
    outer = io.BytesIO()
    with zipfile.ZipFile(outer, "w", zipfile.ZIP_DEFLATED) as z:
        for filename, value in entries.items():
            z.writestr(filename, value)
        if duplicate:
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                z.writestr(dx.ORIGINAL_IPA_NAME, ipa)
    archive = outer.getvalue()
    return archive, ipa_sha, len(ipa)


class DXArchivedVsInstalledContractTests(unittest.TestCase):
    def review(self, text=None, *, archive=None, build_kwargs=None):
        if archive is None:
            archive, ipa_sha, size = make_archive(**(build_kwargs or {}))
        else:
            ipa_sha, size = None, None
        if text is None:
            text = dq_fixture() + b"\n"
        with patch.object(dx, "ORIGINAL_ARCHIVE_SHA256", hashlib.sha256(archive).hexdigest()):
            if ipa_sha is None:
                # Used for adversarial hand-built source with different
                # bytes; the full pin is restored after this call.
                with patch.object(dx, "ORIGINAL_IPA_SHA256", "f"*64):
                    return dx.inspect_dx_archive_and_device_text(archive, text)
            with patch.object(dx, "ORIGINAL_IPA_SHA256", ipa_sha), patch.object(
                dx, "ORIGINAL_IPA_SIZE", size,
            ):
                return dx.inspect_dx_archive_and_device_text(archive, text)

    def assert_no_authority(self, report):
        for key in (
            "archivedNativeCodeSealReverifiedInThisComparison",
            "dqTextOriginCryptographicallyAuthenticated",
            "currentlyInstalledBuild70CryptographicallyAttested",
            "deviceAndArchiveSameCodeDirectoryProven",
            "physicalBundleDataContainerPreservationProven",
            "physicalOfflineChapterPagesVerified",
            "externalBackupValidated", "publisherAuthenticated",
            "ownerPrivateQADistributionConsentRecorded",
            "readyToDistributeIPA", "readyToInstallIPA",
            "automaticUpdaterEnabled",
            "installationAuthorized", "installationPerformed",
        ):
            self.assertIs(report[key], False, key)

    def test_coherent_original_and_dq_text_still_not_attestation(self):
        result = self.review()
        self.assertEqual(
            result["status"],
            "DX_ARCHIVED_PACKAGE_MATCHES_DQ_TEXT_ONLY_NOT_DEVICE_ATTESTED",
        )
        self.assertTrue(result["dqTextMatchesReference"])
        self.assertTrue(result["archivedArtifactMatchesPinnedOriginalBytes"])
        self.assert_no_authority(result)

    def test_iphone_unknown_entitlement_does_not_authorize(self):
        result = self.review(dq_fixture(entitlement="UNAVAILABLE")+b"\n")
        self.assertEqual(result["status"], "DX_WAIT_REPORTED_INSTALLED_IDENTITY_INCOMPLETE")
        self.assert_no_authority(result)

    def test_wrong_build_does_not_authorize(self):
        result = self.review(dq_fixture(build="69")+b"\n")
        self.assertEqual(result["status"], "DX_STOP_REPORTED_INSTALLED_IDENTITY_DIFFERS_FROM_ARCHIVE")
        self.assert_no_authority(result)

    def test_wrong_bundle_does_not_authorize(self):
        result = self.review(dq_fixture(bundle="other.bundle"))
        self.assertEqual(result["status"], "DX_STOP_REPORTED_INSTALLED_IDENTITY_DIFFERS_FROM_ARCHIVE")
        self.assert_no_authority(result)

    def test_different_entitlement_does_not_authorize(self):
        result = self.review(dq_fixture(entitlement="OTHER.bundle"))
        self.assertEqual(result["status"], "DX_STOP_REPORTED_INSTALLED_IDENTITY_DIFFERS_FROM_ARCHIVE")
        self.assert_no_authority(result)

    def test_missing_or_forged_dq_negative_fields_refused(self):
        for bad in (
            dq_fixture()+b"\nINSTALLATION_AUTHORIZED=YES",
            dq_fixture()+b"\n\n",
            dq_fixture().replace(b"READY_TO_DISTRIBUTE_IPA=NO",
                                 b"READY_TO_DISTRIBUTE_IPA=YES"),
            b"",
        ):
            with self.subTest(bad=bad[-25:]), self.assertRaises(DXRejected):
                self.review(bad)

    def test_wrong_ipa_receipt_sha_refused(self):
        with self.assertRaises(DXRejected):
            self.review(build_kwargs={"change_record": {"ipaSHA256": "1"*64}})

    def test_receipt_unauthorized_grant_is_refused(self):
        for mutation in (
            {"installationAuthorized": True},
            {"readyForDistribution": True},
            {"publisherAuthenticatedByCodeSignature": True},
            {"ownerDistributionApprovalRecorded": True},
            {"installedApplicationIdentifierMatch": False},
            {"codeDirectoryCDHash": "0"*40},
            {"build": 71},
        ):
            with self.subTest(mutation=mutation), self.assertRaises(DXRejected):
                self.review(build_kwargs={"change_record": mutation})

    def test_wrong_embedded_info_plist_refused(self):
        for mutation in (
            {"CFBundleVersion": "71"},
            {"MinimumOSVersion": "13.0"},
            {"CFBundleIdentifier": "other.bundle"},
        ):
            with self.subTest(mutation=mutation), self.assertRaises(DXRejected):
                self.review(build_kwargs={"bad_plist": mutation})

    def test_duplicate_or_extra_archive_files_refused(self):
        with self.assertRaises(DXRejected):
            self.review(build_kwargs={"duplicate": True})
        with self.assertRaises(DXRejected):
            self.review(build_kwargs={"rogue_member": "device-library.sqlite"})

    def test_non_original_archive_sha_refused_before_dq(self):
        fixture, _, _ = make_archive()
        with self.assertRaises(DXRejected):
            dx.inspect_dx_archive_and_device_text(fixture, dq_fixture())

    def test_binary_or_oversize_dq_refused(self):
        for text in (b"\x00", b"\xff"+dq_fixture(), dq_fixture()+b"X"*16384):
            with self.subTest(data=text[:10]), self.assertRaises(DXRejected):
                self.review(text)

    def test_random_mutations_never_authorize(self):
        rng = random.Random(20261111)
        dq = dq_fixture()+b"\n"
        for _ in range(160):
            mutated = bytearray(dq)
            pos = rng.randrange(len(mutated))
            mutated[pos] ^= rng.randrange(1, 256)
            try:
                out = self.review(bytes(mutated))
            except DXRejected:
                continue
            self.assert_no_authority(out)

    def test_repository_source_is_readonly_and_no_installer(self):
        source = (ROOT/"build70_dx_archived_vs_installed_identity.py").read_text()
        for forbidden in (
            "appinst(", "posix_spawn(", "subprocess.run(",
            "installApplication(", "write_bytes(", "write_text(",
            "unlink(", "extractall(", "publish_release(",
        ):
            self.assertNotIn(forbidden, source)
        self.assertIn('"installationAuthorized": False', source)
        self.assertIn('"readyToDistributeIPA": False', source)

    def test_physical_readiness_is_not_the_same_as_text_match(self):
        out = self.review()
        self.assertNotIn("READY_TO_INSTALL", out["status"])
        self.assertIs(out["dqTextOriginCryptographicallyAuthenticated"], False)
        self.assertIs(out["deviceAndArchiveSameCodeDirectoryProven"], False)


if __name__ == "__main__":
    unittest.main()

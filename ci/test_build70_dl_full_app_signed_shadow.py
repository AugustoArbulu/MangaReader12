#!/usr/bin/env python3
"""DL host adversarial tests for full-app shadow CI gate.

Only the macOS GitHub runner actually builds, ad-hoc signs and ZIPs
the complete WebReader application; the Linux cases here must NEVER
create an IPA. Mocked readings provide no signing or device evidence.
"""
import ast
import os
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

from build70_dj_continuity_report_compare import (
    parse_continuity_report,
)
from build70_dl_full_app_signed_shadow import (
    BRANCH, WORKFLOW, EXPECTED_REPOSITORY, DLShadowRejected,
    _audit_shadow_unsigned_candidate, _synthetic_baseline,
    require_dl_ephemeral_runner, run_shadow_validation,
)

ROOT = Path(__file__).resolve().parent


def stub_env(tmp: Path) -> dict:
    return {
        "GITHUB_ACTIONS": "true",
        "GITHUB_REPOSITORY": EXPECTED_REPOSITORY,
        "GITHUB_REF": "refs/heads/" + BRANCH,
        "GITHUB_EVENT_NAME": "push",
        "GITHUB_WORKFLOW_REF": EXPECTED_REPOSITORY + "/" + WORKFLOW
            + "@refs/heads/" + BRANCH,
        "GITHUB_SHA": "a" * 40,
        "RUNNER_TEMP": str(tmp),
    }


class DLShadowCIHostContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="wr-dl-deny-ci-")
        self.addCleanup(self.tmp.cleanup)
        self.temp = Path(self.tmp.name)

    def test_unrelated_local_execution_is_denied_before_any_sign(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(DLShadowRejected):
                run_shadow_validation(self.temp / "MangaReader12.app")

    def test_exact_mocked_runner_context_is_accepted_only_as_environment(self):
        with patch.dict(os.environ, stub_env(self.temp), clear=True), patch(
                "build70_dl_full_app_signed_shadow.sys.platform", "darwin"):
            self.assertEqual(require_dl_ephemeral_runner(), self.temp.resolve())

    def test_wrong_repository_branch_workflow_event_or_missing_sha_denied(self):
        base = stub_env(self.temp)
        broken = (
            {"GITHUB_REPOSITORY": "attacker/MangaReader12"},
            {"GITHUB_REF": "refs/heads/main"},
            {"GITHUB_REF": "refs/tags/Build71"},
            {"GITHUB_EVENT_NAME": "pull_request"},
            {"GITHUB_WORKFLOW_REF": "attacker/other-workflow.yml"},
            {"GITHUB_SHA": "z" * 40},
            {"GITHUB_SHA": ""},
            {"GITHUB_ACTIONS": "false"},
            {"RUNNER_TEMP": ""},
        )
        with patch("build70_dl_full_app_signed_shadow.sys.platform", "darwin"):
            for difference in broken:
                with self.subTest(difference=difference):
                    with patch.dict(os.environ, {**base, **difference}, clear=True):
                        with self.assertRaises(DLShadowRejected):
                            require_dl_ephemeral_runner()

    def test_non_macos_is_rejected_even_if_environment_is_forged(self):
        with patch.dict(os.environ, stub_env(self.temp), clear=True), patch(
                "build70_dl_full_app_signed_shadow.sys.platform", "linux"):
            with self.assertRaises(DLShadowRejected):
                require_dl_ephemeral_runner()

    def test_symlinked_temp_root_is_rejected(self):
        link = self.temp / "run-link"
        physical = self.temp / "real"
        physical.mkdir()
        link.symlink_to(physical, target_is_directory=True)
        e = stub_env(self.temp)
        e["RUNNER_TEMP"] = str(link)
        with patch.dict(os.environ, e, clear=True), patch(
                "build70_dl_full_app_signed_shadow.sys.platform", "darwin"):
            with self.assertRaises(DLShadowRejected):
                require_dl_ephemeral_runner()

    def test_synthetic_library_fixture_is_not_empty_library_attestation(self):
        data = _synthetic_baseline()
        parsed = parse_continuity_report(data, expected_build=70)
        self.assertEqual(parsed.counts, (0,) * 9)
        self.assertFalse(parsed.report_authenticity_verified)
        self.assertFalse(parsed.physical_readout_verified)
        self.assertFalse(parsed.offline_image_files_verified)

    def test_unsigned_candidate_metadata_is_only_an_observation(self):
        app = self.temp / "MangaReader12.app"
        app.mkdir()
        fake_receipt = {
            "status": "DH_UNSIGNED_APP_METADATA_ONLY_NOT_INSTALLABLE",
            "observedCompiledBuild": 71,
            "compiledBinaryArchitecture": "arm64",
            "actualExecutableMinimumIOS": "12.0",
            "ownerDistributionApprovalRecorded": False,
            "installationAuthorized": False,
            "installableIPAProduced": False,
        }
        with patch(
            "build70_dl_full_app_signed_shadow.require_dl_ephemeral_runner",
            return_value=self.temp,
        ), patch(
            "build70_dl_full_app_signed_shadow.inspect_dh_unsigned_app",
            return_value=fake_receipt,
        ) as inspect:
            _audit_shadow_unsigned_candidate(app)
        inspect.assert_called_once()
        self.assertEqual(inspect.call_args.kwargs["source_root"].name,
                         "MangaReader12")

    def test_unsigned_candidate_receipt_fails_closed_on_any_elevated_claim(self):
        app = self.temp / "MangaReader12.app"
        app.mkdir()
        base = {
            "status": "DH_UNSIGNED_APP_METADATA_ONLY_NOT_INSTALLABLE",
            "observedCompiledBuild": 71,
            "compiledBinaryArchitecture": "arm64",
            "actualExecutableMinimumIOS": "12.0",
            "ownerDistributionApprovalRecorded": False,
            "installationAuthorized": False,
            "installableIPAProduced": False,
        }
        bad_cases = (
            {"observedCompiledBuild": 70},
            {"observedCompiledBuild": True},
            {"compiledBinaryArchitecture": "x86_64"},
            {"actualExecutableMinimumIOS": "13.0"},
            {"status": "READY_TO_INSTALL"},
            {"ownerDistributionApprovalRecorded": True},
            {"installationAuthorized": True},
            {"installableIPAProduced": True},
        )
        with patch(
            "build70_dl_full_app_signed_shadow.require_dl_ephemeral_runner",
            return_value=self.temp,
        ):
            for mutation in bad_cases:
                with self.subTest(mutation=mutation), patch(
                    "build70_dl_full_app_signed_shadow.inspect_dh_unsigned_app",
                    return_value={**base, **mutation},
                ):
                    with self.assertRaises(DLShadowRejected):
                        _audit_shadow_unsigned_candidate(app)

    def test_unsigned_candidate_must_be_inside_temporary_runner(self):
        outside = Path(tempfile.mkdtemp(prefix="wr-dl-outside-"))
        self.addCleanup(lambda: outside.rmdir())
        app = outside / "MangaReader12.app"
        app.mkdir()
        self.addCleanup(lambda: app.rmdir())
        good = {
            "status": "DH_UNSIGNED_APP_METADATA_ONLY_NOT_INSTALLABLE",
            "observedCompiledBuild": 71, "compiledBinaryArchitecture": "arm64",
            "actualExecutableMinimumIOS": "12.0",
            "ownerDistributionApprovalRecorded": False,
            "installationAuthorized": False,
            "installableIPAProduced": False,
        }
        with patch(
            "build70_dl_full_app_signed_shadow.require_dl_ephemeral_runner",
            return_value=self.temp,
        ), patch(
            "build70_dl_full_app_signed_shadow.inspect_dh_unsigned_app",
            return_value=good,
        ):
            with self.assertRaises(DLShadowRejected):
                _audit_shadow_unsigned_candidate(app)

    def test_no_package_or_code_sign_api_is_called_without_host_gate(self):
        with patch.dict(os.environ, {}, clear=True), patch(
            "build70_dl_full_app_signed_shadow._command",
        ) as run:
            with self.assertRaises(DLShadowRejected):
                run_shadow_validation(self.temp / "MangaReader12.app")
            run.assert_not_called()

    def test_only_reviewed_native_commands_present(self):
        src = (ROOT / "build70_dl_full_app_signed_shadow.py").read_text()
        tree = ast.parse(src)
        forbidden = {
            "appinst", "installApplication", "posix_spawn", "fork",
            "execve", "system", "upload_artifact", "publish_release",
            "make_archive", "requests", "urlopen",
        }
        calls = set()
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    calls.add(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    calls.add(node.func.attr)
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            if isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])
        self.assertFalse(calls & forbidden, calls & forbidden)
        self.assertFalse(imports & {"socket", "requests", "urllib", "http"})
        self.assertIn('"/usr/bin/ditto"', src)
        self.assertIn('"/usr/bin/codesign"', src)
        self.assertIn('"/usr/bin/zip"', src)
        self.assertIn("with tempfile.TemporaryDirectory(", src)
        self.assertNotIn("actions/upload-artifact", src)
        self.assertIn('"ownerDistributionApprovalRecorded": False', src)
        self.assertIn('"persistentIPAProduced": False', src)
        self.assertIn('"releasePublished": False', src)
        self.assertIn('"installationAuthorized": False', src)

    def test_no_physical_identity_offline_or_publisher_evidence_asserted(self):
        src = (ROOT / "build70_dl_full_app_signed_shadow.py").read_text()
        for negative in (
            '"physicalLibraryCountsCaptured": False',
            '"physicalOfflineReadingVerified": False',
            '"physicalBuild70AppIdentifierReattested": False',
            '"realDeviceIOS12ExecutionVerified": False',
            '"realDeviceInstallationCompatibilityProven": False',
            '"publisherCryptographicallyAuthenticated": False',
            '"helperIdentityAuthenticated": False',
            '"readyToDistributeIPA": False',
            '"readyToInstallIPA": False',
            '"installationPerformed": False',
            '"artifactUploaded": False',
        ):
            with self.subTest(claim=negative):
                self.assertIn(negative, src)


if __name__ == "__main__":
    unittest.main()

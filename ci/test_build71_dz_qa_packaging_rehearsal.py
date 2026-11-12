#!/usr/bin/env python3
"""DZ negative-only host tests; no signing, no packager execution, no IPA."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import build71_dz_qa_packaging_rehearsal as dz
import build71_owner_approved_actions_qa_package as dy

ROOT = Path(__file__).resolve().parent.parent


class DZRehearsalContractTests(unittest.TestCase):
    def test_no_real_owner_marker(self):
        path = ROOT / dy.TRIGGER
        self.assertFalse(path.exists(), "owner trigger must not exist in branch")
        self.assertFalse(path.is_symlink())

    def test_live_installer_and_editorial_trust_remain_disabled(self):
        for path, literal in (
            ("MangaReader12/Core/WebReaderAppinstSocket.swift",
             "static let liveInstallationEnabled = false"),
            ("MangaReader12/Core/WebReaderUpdateChecker.swift",
             "static let productionPublicKeyX963: Data? = nil"),
            ("MangaReader12/Core/WebReaderProductionPublisherTrust.swift",
             "static let independentlyProvisionedSPKISHA256: String? = nil"),
        ):
            self.assertIn(literal, (ROOT/path).read_text())

    def test_not_a_local_execution_even_with_fake_app(self):
        with tempfile.TemporaryDirectory() as td:
            app = Path(td) / "MangaReader12.app"
            app.mkdir()
            with patch.dict(dz.os.environ, {}, clear=True):
                with self.assertRaises(dz.DZRejected):
                    dz.require_ephemeral_dz_runner(app)

    def test_no_rehearsal_without_dedicated_workflow(self):
        self.assertIn("phase-dz-build71-package-rehearsal.yml", dz.WORKFLOW)
        source = (ROOT/"ci/build71_dz_qa_packaging_rehearsal.py").read_text()
        self.assertIn('or env.get("GITHUB_WORKFLOW_REF") !=', source)
        self.assertIn('or env.get("GITHUB_RUN_ATTEMPT") != "1"', source)
        self.assertIn("test-only", source.lower() if "test-only" in source.lower() else source.lower().replace("test double", "test-only"))
        self.assertIn("(ROOT/dy.TRIGGER).exists()", source)

    def test_only_dy_trigger_guard_is_mocked_not_the_signing_or_di_ds(self):
        source = (ROOT/"ci/build71_dz_qa_packaging_rehearsal.py").read_text()
        self.assertIn('"require_explicit_single_commit_trigger"', source)
        self.assertIn("dy.package_one_shot_build71_qa(unsigned_app, output)", source)
        self.assertNotIn('patch.object(dy, "_run"', source)
        self.assertNotIn("patch.object(dy, '_run'", source)
        self.assertNotIn("patch.object(dy, '_inspect_signed_qa'", source)
        self.assertNotIn('patch.object(dy, "_inspect_signed_qa"', source)

    def test_rehearsal_does_not_persist_a_qa_ipa(self):
        source = (ROOT/"ci/build71_dz_qa_packaging_rehearsal.py").read_text()
        self.assertIn("TemporaryDirectory(prefix=", source)
        self.assertIn("temporary_path.exists()", source)
        self.assertIn('"deliverableRetained": False', source)
        self.assertIn('"artifactUploaded": False', source)
        self.assertIn('"installationAuthorized": False', source)
        self.assertIn('"actualOwnerTriggerUsed": False', source)

    def test_workflow_macos_real_full_app_only_without_artifact(self):
        source = (
            ROOT/".github/workflows/chimera-build70-phase-dz-build71-package-rehearsal.yml"
        ).read_text()
        for needle in (
            "runs-on: macos-15",
            "CURRENT_PROJECT_VERSION=71",
            "CODE_SIGNING_ALLOWED=NO",
            "ci/build71_dz_qa_packaging_rehearsal.py",
            "ci/test_build71_dz_qa_packaging_rehearsal.py",
        ):
            self.assertIn(needle, source)
        for forbidden in ("upload-artifact", "gh release", "appinst ", "curl -X POST"):
            self.assertNotIn(forbidden, source)

    def test_python_imports_do_not_dirty_macos_checkout(self):
        workflow = (
            ROOT/".github/workflows/chimera-build70-phase-dz-build71-package-rehearsal.yml"
        ).read_text()
        self.assertIn('PYTHONDONTWRITEBYTECODE: "1"', workflow)
        source = (ROOT/"ci/build71_dz_qa_packaging_rehearsal.py").read_text()
        self.assertIn('git", "-C", str(ROOT)', source)
        self.assertIn('"status", "--porcelain=v1", "--untracked-files=all"', source)
        self.assertNotIn("git clean -fd", workflow)
        self.assertNotIn("git clean -fd", source)

    def test_mocked_owner_cannot_be_confused_with_real_trigger(self):
        source = (ROOT/"ci/build71_dz_qa_packaging_rehearsal.py").read_text()
        self.assertIn('"temporaryMockOwnerContextUsed": True', source)
        self.assertIn('"realInstalledDeviceIdentityAttested": False', source)
        self.assertIn('"physicalLibraryAndOfflinePreservationProven": False', source)


if __name__ == "__main__":
    unittest.main()

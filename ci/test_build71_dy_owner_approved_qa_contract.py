#!/usr/bin/env python3
"""DY: no Build71 IPA without separate owner trigger; host QA negatives only.

Tests never sign, package, install, publish, or read private user data.
"""
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import build71_owner_approved_actions_qa_package as dy

ROOT = Path(__file__).resolve().parent.parent
WF = ROOT / ".github/workflows/chimera-build71-owner-approved-one-shot-qa.yml"


def context(root: Path, temp: Path, **change):
    env = {
        "GITHUB_ACTIONS": "true",
        "GITHUB_REPOSITORY": dy.REPOSITORY,
        "GITHUB_EVENT_NAME": "push",
        "GITHUB_REF": "refs/heads/" + dy.BRANCH,
        "GITHUB_WORKFLOW_REF": dy.REPOSITORY + "/" + dy.WORKFLOW +
                               "@refs/heads/" + dy.BRANCH,
        "GITHUB_SHA": "a" * 40,
        "GITHUB_RUN_ID": "123456",
        "GITHUB_RUN_ATTEMPT": "1",
        "RUNNER_TEMP": str(temp),
    }
    env.update(change)
    return env


class DYOwnerOnlyQATests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="wr-dy-qa-deny-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "repo"
        self.runner = Path(self.temp.name) / "runner"
        self.root.mkdir()
        self.runner.mkdir()
        self.trigger = self.root / dy.TRIGGER
        self.trigger.parent.mkdir()
        self.good_env = context(self.root, self.runner)

    def write_trigger(self, marker=None, parent=None):
        self.trigger.write_text(
            (marker if marker is not None else dy.MARKER) + "\n" +
            (parent if parent is not None else "b" * 40) + "\n",
            encoding="ascii",
        )

    @staticmethod
    def git_stub(*args):
        if args == ("rev-parse", "HEAD"):
            return "a" * 40
        if args == ("rev-parse", "HEAD^"):
            return "b" * 40
        if args == ("diff", "--name-only", "HEAD^", "HEAD"):
            return dy.TRIGGER
        if args == ("status", "--porcelain=v1", "--untracked-files=all"):
            return ""
        raise AssertionError("unexpected command " + repr(args))

    def admitted(self, env=None):
        with patch.object(dy, "ROOT", self.root), patch.dict(
            dy.os.environ, self.good_env if env is None else env, clear=True,
        ), patch.object(dy.sys, "platform", "darwin"), patch.object(
            dy, "_git", side_effect=self.git_stub,
        ):
            return dy.require_explicit_single_commit_trigger()

    def test_real_local_or_non_macos_context_denied(self):
        with patch.dict(dy.os.environ, {}, clear=True):
            with self.assertRaises(dy.DYRejected):
                dy.require_explicit_single_commit_trigger()
        self.write_trigger()
        with patch.object(dy, "ROOT", self.root), patch.dict(
            dy.os.environ, self.good_env, clear=True,
        ), patch.object(dy.sys, "platform", "linux"), patch.object(
            dy, "_git", side_effect=self.git_stub,
        ):
            with self.assertRaises(dy.DYRejected):
                dy.require_explicit_single_commit_trigger()

    def test_exact_one_shot_marker_and_parent_are_required(self):
        with self.assertRaises(dy.DYRejected):
            self.admitted()
        self.write_trigger()
        sha, parent, root = self.admitted()
        self.assertEqual(sha, "a"*40)
        self.assertEqual(parent, "b"*40)
        self.assertEqual(root, self.runner.resolve())

    def test_mutated_context_never_grants_qa(self):
        self.write_trigger()
        for different in (
            {"GITHUB_REPOSITORY": "attacker/MangaReader12"},
            {"GITHUB_EVENT_NAME": "pull_request"},
            {"GITHUB_EVENT_NAME": "workflow_dispatch"},
            {"GITHUB_REF": "refs/heads/main"},
            {"GITHUB_WORKFLOW_REF": dy.REPOSITORY + "/other.yml"},
            {"GITHUB_SHA": "z"*40},
            {"GITHUB_SHA": ""},
            {"GITHUB_RUN_ID": "bad"},
            {"GITHUB_RUN_ATTEMPT": "2"},
            {"GITHUB_RUN_ATTEMPT": "0"},
            {"GITHUB_RUN_ATTEMPT": ""},
            {"RUNNER_TEMP": ""},
        ):
            with self.subTest(different=different), self.assertRaises(dy.DYRejected):
                self.admitted({**self.good_env, **different})

    def test_wrong_parent_or_fake_marker_denied(self):
        for marker, parent in (
            ("INSTALLATION_AUTHORIZED=YES", "b"*40),
            (dy.MARKER, "c"*40),
            (dy.MARKER + "\nEXTRA", "b"*40),
        ):
            with self.subTest(marker=marker[-16:], parent=parent[:5]):
                self.write_trigger(marker, parent)
                with self.assertRaises(dy.DYRejected):
                    self.admitted()

    def test_marker_format_must_have_exact_two_lf_terminated_lines(self):
        samples = (
            (dy.MARKER + "\n" + "b"*40).encode("ascii"),
            (dy.MARKER + "\r\n" + "b"*40 + "\r\n").encode("ascii"),
            (dy.MARKER + "\n" + "b"*40 + "\n\n").encode("ascii"),
        )
        for value in samples:
            with self.subTest(size=len(value)):
                self.trigger.write_bytes(value)
                with self.assertRaises(dy.DYRejected):
                    self.admitted()

    def test_symlinked_marker_is_denied(self):
        actual = self.root / "actual-marker.txt"
        actual.write_text(dy.MARKER + "\n" + "b"*40 + "\n")
        self.trigger.symlink_to(actual)
        with self.assertRaises(dy.DYRejected):
            self.admitted()

    def test_trigger_commit_must_change_only_marker(self):
        self.write_trigger()
        def bad_git(*args):
            if args == ("diff", "--name-only", "HEAD^", "HEAD"):
                return dy.TRIGGER + "\nMangaReader12/Core/WebReaderAppinstSocket.swift"
            return self.git_stub(*args)
        with patch.object(dy, "ROOT", self.root), patch.dict(
            dy.os.environ, self.good_env, clear=True,
        ), patch.object(dy.sys, "platform", "darwin"), patch.object(
            dy, "_git", side_effect=bad_git,
        ):
            with self.assertRaises(dy.DYRejected):
                dy.require_explicit_single_commit_trigger()

    def test_different_checked_out_commit_is_denied(self):
        self.write_trigger()
        def bad_git(*args):
            if args == ("rev-parse", "HEAD"):
                return "c"*40
            return self.git_stub(*args)
        with patch.object(dy, "ROOT", self.root), patch.dict(
            dy.os.environ, self.good_env, clear=True,
        ), patch.object(dy.sys, "platform", "darwin"), patch.object(
            dy, "_git", side_effect=bad_git,
        ):
            with self.assertRaises(dy.DYRejected):
                dy.require_explicit_single_commit_trigger()

    def test_source_tree_or_symlinked_runner_root_is_denied(self):
        self.write_trigger()
        link = Path(self.temp.name) / "runner-alias"
        link.symlink_to(self.runner, target_is_directory=True)
        for path in (str(self.root), str(link)):
            with self.subTest(path=path), self.assertRaises(dy.DYRejected):
                self.admitted({**self.good_env, "RUNNER_TEMP": path})

    def test_hash_regular_stable_and_refuses_symlink(self):
        path = self.runner / "example.ipa"
        path.write_bytes(b"WR_FAKE_IPA_DO_NOT_INSTALL"*24)
        a = dy._hash_regular(path)
        self.assertEqual(a[2], path.stat().st_size)
        self.assertEqual(a[3], hashlib.sha256(path.read_bytes()).hexdigest())
        alias = self.runner / "link.ipa"
        alias.symlink_to(path)
        with self.assertRaises(dy.DYRejected):
            dy._hash_regular(alias)

    def test_package_refuses_without_owner_context_before_ever_signing(self):
        with patch.dict(dy.os.environ, {}, clear=True), patch.object(
            dy, "_run",
        ) as command:
            with self.assertRaises(dy.DYRejected):
                dy.package_one_shot_build71_qa(
                    self.runner / "MangaReader12.app", self.runner / "delivery",
                )
            command.assert_not_called()

    def test_package_refuses_missing_real_unsigned_app_before_sign(self):
        self.write_trigger()
        with patch.object(dy, "require_explicit_single_commit_trigger",
                          return_value=("a"*40, "b"*40, self.runner)), patch.object(
            dy, "_run",
        ) as command:
            with self.assertRaises(dy.DYRejected):
                dy.package_one_shot_build71_qa(
                    self.runner / "MangaReader12.app", self.runner,
                )
            command.assert_not_called()

    @staticmethod
    def di_receipt():
        return dict(
            status="DI_SIGNED_QA_SNAPSHOT_HOST_ONLY_NOT_DISTRIBUTABLE",
            expectedInstalledPhysicalBuild=70, candidateBuild=71,
            bundleID="com.example.MangaReader12",
            iosMinimumDeclared="12.0", iosMinimumFromExecutable="12.0",
            architecture="arm64", ipaSHA256="a"*64, ipaBytes=1024,
            adHocCodeSealIntegrityVerifiedOnHost=True,
            historicalApplicationIdentifierMatches=True,
            historicalApplicationIdentifier=dy.INSTALLED_APPLICATION_IDENTIFIER,
            staticCodeDirectoryCDHash="b"*40,
            readyForPrivateQADistribution=False,
            installationAuthorized=False, installationPerformed=False,
            publisherCryptographicallyAuthenticated=False,
            physicalBuild70AppIdentityNewlyAttested=False,
            actualDeviceInstallabilityProven=False,
        )

    def test_DI_has_no_false_positive_authority(self):
        good = self.di_receipt()
        dy._check_di(good, "a"*64, 1024)
        for patch_value in (
            {"status": "READY_TO_INSTALL"},
            {"installationAuthorized": True},
            {"publisherCryptographicallyAuthenticated": True},
            {"readyForPrivateQADistribution": True},
            {"physicalBuild70AppIdentityNewlyAttested": True},
            {"staticCodeDirectoryCDHash": "x"*40},
            {"candidateBuild": 70},
            {"candidateBuild": True},
        ):
            with self.subTest(change=patch_value), self.assertRaises(dy.DYRejected):
                dy._check_di({**good, **patch_value}, "a"*64, 1024)

    def test_DS_synthetic_device_text_cannot_promote_physical_claim(self):
        ds = dict(
            status="DS_HOST_TEXT_AND_SIGNED_CANDIDATE_COHERENT_NOT_INSTALLABLE",
            candidateIPAStaticSHA256="a"*64, candidateIPABytes=1024,
            candidateStaticCDHash="b"*40,
            ipaAdHocSealCheckedOnHost=True,
            physicalDeviceAndReportOriginAuthenticated=False,
            physicalInstalledBuild70IdentityCryptographicallyVerified=False,
            localAppDataContainerRetentionProven=False,
            readyToDistributeIPA=False, readyToInstallIPA=False,
            installationAuthorized=False,
        )
        dy._check_ds(ds, "a"*64, 1024, "b"*40)
        for change in (
            {"physicalDeviceAndReportOriginAuthenticated": True},
            {"physicalInstalledBuild70IdentityCryptographicallyVerified": True},
            {"localAppDataContainerRetentionProven": True},
            {"installationAuthorized": True},
            {"candidateIPAStaticSHA256": "0"*64},
            {"candidateIPABytes": 1025},
        ):
            with self.subTest(change=change), self.assertRaises(dy.DYRejected):
                dy._check_ds({**ds, **change}, "a"*64, 1024, "b"*40)

    def test_workflow_is_inert_until_only_trigger_changes(self):
        source = WF.read_text(encoding="utf-8")
        self.assertIn("ci/build71_owner_approved_qa_trigger.txt", source)
        self.assertIn("WEBREADER_BUILD71_OWNER_APPROVED_ONE_SHOT_ACTIONS_QA_IPA_NO_INSTALL", source)
        self.assertIn('git diff --name-only HEAD^ HEAD', source)
        self.assertIn("run: python3 ci/build71_owner_approved_actions_qa_package.py", source.replace(
            "          python3 ci/build71_owner_approved_actions_qa_package.py",
            "        run: python3 ci/build71_owner_approved_actions_qa_package.py"
        ))
        self.assertNotIn("  workflow_dispatch:\n", source)
        self.assertNotIn("  pull_request:\n", source)
        self.assertIn("    paths:\n      - 'ci/build71_owner_approved_qa_trigger.txt'", source)

    def test_actions_artifact_is_private_qa_not_release_or_installer(self):
        source = WF.read_text(encoding="utf-8")
        self.assertIn("actions/upload-artifact@v4", source)
        self.assertIn("retention-days: 14", source)
        self.assertIn("macos-15", source)
        self.assertIn("CURRENT_PROJECT_VERSION=71", source)
        self.assertIn("CODE_SIGNING_ALLOWED=NO", source)
        self.assertIn("ci/build70_di_build71_private_qa_preflight.py", source)
        for forbidden in (
            "gh release", "git push", "appinst ",
            "  workflow_dispatch:\n", "  pull_request:\n",
            "liveInstallationEnabled = true",
        ):
            self.assertNotIn(forbidden, source)

    def test_script_has_no_automatic_installer_or_backup_cleanup(self):
        source = (ROOT/"ci/build71_owner_approved_actions_qa_package.py").read_text()
        for forbidden in (
            "appinst(", "installApplication(", "restoreBackup(",
            "shutil.rmtree(", "webreader_data_dir.unlink(",
            "requests.post(", "create_release(",
        ):
            self.assertNotIn(forbidden, source)
        self.assertIn('"installationAuthorized": False', source)
        self.assertIn('"automaticUpdaterEnabled": False', source)
        self.assertIn('"ownerIdentityCryptographicallyAuthenticatedByTrigger": False', source)

    def test_production_trust_still_denied(self):
        targets = (
            ("MangaReader12/Core/WebReaderUpdateChecker.swift",
             "static let productionPublicKeyX963: Data? = nil"),
            ("MangaReader12/Core/WebReaderProductionPublisherTrust.swift",
             "static let independentlyProvisionedSPKISHA256: String? = nil"),
            ("MangaReader12/Core/WebReaderAppinstSocket.swift",
             "static let liveInstallationEnabled = false"),
        )
        for path, needle in targets:
            self.assertIn(needle, (ROOT/path).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Host-only QA for scoped GitHub Actions on the oversized Draft PR #90.

This is a static contract test, not proof of GitHub runner availability.
No App Store / appinst / IPA packaging, device access, or network requests.
"""
import fnmatch
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"


def text_of(name):
    return (WORKFLOWS / name).read_text(encoding="utf-8")


def yaml_event_body(text, event, next_event):
    first = "\n  " + event + ":\n"
    last = "\n  " + next_event + ":"
    if first not in text or last not in text:
        raise AssertionError("missing workflow event: " + event)
    return text.split(first, 1)[1].split(last, 1)[0]


class TriggerScopeTests(unittest.TestCase):
    def test_direct_appinst_diagnostic_has_narrow_push_paths(self):
        workflow = text_of("appinst-direct-test.yml")
        push = yaml_event_body(workflow, "push", "workflow_dispatch")
        self.assertIn("paths:", push)
        self.assertIn("'ci/appinst_direct_probe/**'", push)
        self.assertIn("'ci/build_appinst_direct_probe.sh'", push)
        self.assertIn("'ci/test_appinst_direct_probe.py'", push)
        self.assertIn("'.github/workflows/appinst-direct-test.yml'", push)
        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotIn("pull_request:", workflow)
        self.assertNotIn("ci/build70_e", push)
        self.assertIn("com.example.WebReaderAppinstDirectProbe", (
            ROOT / "ci" / "test_appinst_direct_probe.py"
        ).read_text())

    def test_legacy_ios_build_ignores_readonly_audit_only_changes(self):
        workflow = text_of("build.yml")
        push = yaml_event_body(workflow, "push", "pull_request")
        pr = yaml_event_body(workflow, "pull_request", "workflow_dispatch")
        for section in (push, pr):
            self.assertIn("paths-ignore:", section)
            for pattern in (
                "docs/**", "ci/build70_e*.py",
                "ci/test_build70_e*.py",
                ".github/workflows/chimera-build70-phase-e*.yml",
            ):
                self.assertIn("'" + pattern + "'", section)
        self.assertIn("if: github.event_name != 'pull_request' || "
                      "github.event.pull_request.draft == false", workflow)
        self.assertIn("runs-on: macos-14", workflow)
        self.assertIn("workflow_dispatch:", workflow)

    def test_ignore_patterns_cover_only_audit_changes_not_native_code(self):
        ignored = (
            "docs/HANDOFF_WEBREADER_FASES_EA_EK_2026-11-13.md",
            "ci/build70_ei_all_downloads_inventory.py",
            "ci/test_build70_ek_partial_prefix_metadata.py",
            ".github/workflows/chimera-build70-phase-ei-all-downloads.yml",
        )
        patterns = (
            "docs/**", "ci/build70_e*.py",
            "ci/test_build70_e*.py",
            ".github/workflows/chimera-build70-phase-e*.yml",
        )
        self.assertTrue(all(
            any(fnmatch.fnmatchcase(name, pattern) for pattern in patterns)
            for name in ignored
        ))
        native = (
            "MangaReader12/Downloads/ChapterDownloadManager.swift",
            "MangaReader12/Core/WebReaderAppinstSocket.swift",
            "ci/audit_ios12.sh",
            "ci/test_build51_general.py",
            ".github/workflows/build.yml",
        )
        self.assertTrue(all(
            not any(fnmatch.fnmatchcase(name, pattern) for pattern in patterns)
            for name in native
        ))

    def test_integrated_audit_still_includes_linux_and_macos(self):
        workflow = text_of("chimera-build70-phase-eg-cli-failclosed.yml")
        self.assertIn("os: [ubuntu-latest, macos-15]", workflow)
        self.assertIn("cancel-in-progress: true", workflow)
        self.assertIn("wr-build70-ea-ek-integrated-", workflow)
        self.assertIn("permissions:\n  contents: read", workflow)
        self.assertIn("test_build70_ek_partial_prefix_metadata.py", workflow)
        self.assertIn("test_build70_ei_all_downloads_inventory.py", workflow)
        self.assertNotIn("actions/upload-artifact", workflow)
        self.assertNotIn("package_webreader_build71", workflow)

    def test_ei_and_ek_keep_distinct_concurrency_groups(self):
        ei = text_of("chimera-build70-phase-ei-all-downloads.yml")
        ek = text_of("chimera-build70-phase-ek-partial-prefix.yml")
        self.assertIn("wr-build70-ei-copied-data-", ei)
        self.assertIn("wr-build70-ek-partial-prefix-", ek)
        for workflow in (ei, ek):
            self.assertIn("cancel-in-progress: true", workflow)
            self.assertIn("os: [ubuntu-latest, macos-15]", workflow)
            self.assertIn("permissions:\n  contents: read", workflow)

    def test_legacy_ios_build_cancels_only_its_own_superseded_run(self):
        workflow = text_of("build.yml")
        self.assertIn("concurrency:\n", workflow)
        self.assertIn("cancel-in-progress: true", workflow)
        self.assertIn("github.workflow", workflow)
        self.assertIn("github.event.pull_request.number || github.ref", workflow)
        self.assertIn(
            "github.event_name == 'workflow_dispatch' && github.run_id", workflow
        )
        self.assertNotIn("github.workflow", text_of("chimera-build70-phase-eg-cli-failclosed.yml"))

    def test_no_owner_build71_trigger_or_automatic_install_activation(self):
        self.assertFalse((ROOT / "ci/build71_owner_approved_qa_trigger.txt").exists())
        source = (ROOT / "MangaReader12/Core/WebReaderAppinstSocket.swift").read_text()
        self.assertIn("static let liveInstallationEnabled = false", source)
        source = (ROOT / "MangaReader12/Core/WebReaderUpdateChecker.swift").read_text()
        self.assertIn("static let productionPublicKeyX963: Data? = nil", source)
        source = (
            ROOT / "MangaReader12/Core/WebReaderProductionPublisherTrust.swift"
        ).read_text()
        self.assertIn("static let independentlyProvisionedSPKISHA256: String? = nil", source)


if __name__ == "__main__":
    unittest.main()

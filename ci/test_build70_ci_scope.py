#!/usr/bin/env python3
"""Host-only QA for scoped GitHub Actions on the oversized Draft PR #90.

This is a static contract test, not proof of GitHub runner availability.
No App Store / appinst / IPA packaging, device access, or network requests.
"""
import fnmatch
import re
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

    def test_ready_for_review_transition_can_request_native_validation(self):
        workflow = text_of("build.yml")
        pr = yaml_event_body(workflow, "pull_request", "workflow_dispatch")
        self.assertIn(
            "types: [opened, synchronize, reopened, ready_for_review]", pr
        )
        self.assertIn(
            "if: github.event_name != 'pull_request' || "
            "github.event.pull_request.draft == false", workflow
        )
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

    def test_oneapp_expensive_ipa_has_narrow_push_inputs_and_safe_manual_run(self):
        workflow = text_of("chimera-oneapp.yml")
        push = yaml_event_body(workflow, "push", "workflow_dispatch")
        self.assertIn("paths:", push)
        for required in (
            "MangaReader12/**",
            "MangaReader12.xcodeproj/**",
            "ci/webreader_helper_probe.c",
            "ci/package_chimera_oneapp_ipa.sh",
            "ci/test_chimera_oneapp_ipa.py",
            ".github/workflows/chimera-oneapp.yml",
        ):
            self.assertIn("'" + required + "'", push)
        self.assertNotIn("ci/build70_e*.py", push)
        self.assertNotIn("pull_request:", workflow)
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("github.event_name == 'workflow_dispatch' && github.run_id",
                      workflow)
        self.assertIn("cancel-in-progress: true", workflow)
        self.assertIn("runs-on: macos-15", workflow)
        self.assertIn("WebReader-Chimera-OneApp-iOS12-TEST", workflow)

    def test_build60_ping_ipa_has_narrow_push_inputs_and_safe_manual_run(self):
        workflow = text_of("chimera-mobile-ping.yml")
        push = yaml_event_body(workflow, "push", "workflow_dispatch")
        self.assertIn("paths:", push)
        for required in (
            "MangaReader12/**",
            "MangaReader12.xcodeproj/**",
            "ci/webreader_appinst_bridge.c",
            "ci/webreader_chimera_disposable_gate.c",
            "ci/chimera_mobile_ping.entitlements",
            "ci/chimera_disposable_app.entitlements",
            "ci/appinst_disposable/**",
            "ci/build_appinst_disposable.sh",
            "ci/package_ipc_probe_ipa.sh",
            "ci/test_chimera_mobile_ping_kit.py",
            ".github/workflows/chimera-mobile-ping.yml",
        ):
            self.assertIn("'" + required + "'", push)
        self.assertNotIn("ci/build70_e*.py", push)
        self.assertNotIn("pull_request:", workflow)
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("github.event_name == 'workflow_dispatch' && github.run_id",
                      workflow)
        self.assertIn("cancel-in-progress: true", workflow)
        self.assertIn("runs-on: macos-15", workflow)
        self.assertIn("WebReader-Chimera-Build60-SignedQA-iOS12", workflow)

    def test_draft_pr_gates_38_historical_workflows_without_losing_manual_review(self):
        # These historical workflows would otherwise re-run against the
        # accumulated diff of PR #90 on every unrelated commit.
        legacy = (
            "chimera-build66-audittoken-probe.yml",
            "chimera-build66-csops-probe.yml",
            "chimera-build66-fd-handoff.yml",
            "chimera-build66-queued-stream.yml",
            "chimera-build66-separate-peers.yml",
            "chimera-build66-preflight.yml",
            "chimera-build70-phase-cr-fd-alias.yml",
            "chimera-build70-phase-cs-appinst-source-audit.yml",
            "chimera-build70-phase-ct-two-hop-review.yml",
            "chimera-build70-phase-cu-helper-custody.yml",
            "chimera-build70-phase-cv-readonly-abi.yml",
            "chimera-build70-phase-cw-native-checkonly.yml",
            "chimera-build70-phase-cx-bounded-check-queue.yml",
            "chimera-build70-phase-cy-cooperative-watchdog.yml",
            "chimera-build70-phase-cz-synthetic-worker.yml",
            "chimera-build70-phase-da-crash-evidence.yml",
            "chimera-build70-phase-db-host-uid-custody.yml",
            "chimera-build70-phase-dc-anchored-custody.yml",
            "chimera-build70-phase-dd-full-ancestry.yml",
            "chimera-build70-phase-de-self-identity.yml",
            "chimera-build70-phase-df-macho-preflight.yml",
            "chimera-build70-phase-dg-inapp-self-identity.yml",
            "chimera-build70-phase-dh-unsigned-71-preview.yml",
            "chimera-build70-phase-di-build71-private-qa-preflight.yml",
            "chimera-build70-phase-dj-library-continuity.yml",
            "chimera-build70-phase-dk-evidence-bridge.yml",
            "chimera-build70-phase-dn-startup-data-guard.yml",
            "chimera-build70-phase-do-offline-baseline.yml",
            "chimera-build70-phase-dp-sectask-self-identity.yml",
            "chimera-build70-phase-dq-installed-bundle-readonly.yml",
            "chimera-build70-phase-dr-preupgrade-evidence.yml",
            "chimera-build70-phase-ds-candidate-evidence.yml",
            "chimera-build70-phase-dt-postupgrade-readonly.yml",
            "chimera-build70-phase-dx-original-archive-dq-compare.yml",
            "chimera-build70-phase-dy-build71-delivery-readiness.yml",
            "chimera-build70-phase-cn-untrusted-trigger.yml",
            "chimera-build70-phase-co-owner-ceremony.yml",
            "chimera-build70-phase-cp-owner-v2-signer.yml",
        )
        self.assertEqual(len(legacy), 38)
        guard = (
            "    if: github.event_name != 'pull_request' || "
            "github.event.pull_request.draft == false"
        )
        for name in legacy:
            with self.subTest(workflow=name):
                workflow = text_of(name)
                self.assertIn(
                    "  pull_request:\n"
                    "    types: [opened, synchronize, reopened, ready_for_review]\n",
                    workflow
                )
                self.assertIn("  workflow_dispatch:", workflow)
                self.assertIn("\njobs:\n", workflow)
                jobs = workflow.split("\njobs:\n", 1)[1]
                blocks = re.findall(
                    r"(?ms)^  [A-Za-z0-9_-]+:\n.*?"
                    r"(?=^  [A-Za-z0-9_-]+:\n|\Z)", jobs
                )
                self.assertTrue(blocks)
                for block in blocks:
                    self.assertIn(guard, block)
                if "\n  push:\n" in workflow:
                    push = workflow.split("\n  push:\n", 1)[1].split(
                        "\n  pull_request:\n", 1
                    )[0]
                    self.assertIn("    paths:", push)
                    # An edit only to the YAML should be covered by static
                    # scope QA, not rebuild every historical macOS artifact.
                    self.assertNotIn(
                        "'.github/workflows/" + name + "'", push
                    )

    def test_general_ios_build_ignores_ci_scope_only_changes(self):
        workflow = text_of("build.yml")
        push = yaml_event_body(workflow, "push", "pull_request")
        pr = yaml_event_body(workflow, "pull_request", "workflow_dispatch")
        for section in (push, pr):
            for path in (
                "ci/test_build70_ci_scope.py",
                ".github/workflows/chimera-build66-*.yml",
                ".github/workflows/chimera-build70-phase-*.yml",
            ):
                self.assertIn("'" + path + "'", section)
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("runs-on: macos-14", workflow)

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

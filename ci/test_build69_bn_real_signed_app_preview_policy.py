#!/usr/bin/env python3
"""Build69 BN: real app ad-hoc rehearsal is ephemeral and never emits an IPA."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
PREVIEW = (ROOT / "ci/build69_bn_real_signed_app_preview.py").read_text()
WORKFLOW = (
    ROOT / ".github/workflows/chimera-build69-phase-ac-af-integrated-qa.yml"
).read_text()


class EphemeralRealAppReview(unittest.TestCase):
    def test_codesign_only_disposable_real_app_and_reinspect_source(self):
        for marker in (
            "inspect_unsigned_candidate(app)",
            '("Info.plist", "MangaReader12", "Assets.car")',
            'TemporaryDirectory(prefix="wr69-bn-signed-app-only-")',
            '"/usr/bin/ditto", str(app), str(disposable_app)',
            '"/usr/bin/codesign", "--force", "--sign", "-"',
            '"--timestamp=none", "--entitlements", str(ENTITLEMENTS)',
            '"/usr/bin/codesign", "--verify", "--verbose=2"',
            '"/usr/bin/codesign", "-d", "--entitlements", ":-"',
            'Signature=adhoc',
            "CDHash=",
            'list(Path(td).rglob("*.ipa"))',
            '"temporarySignedAppDeleted": True',
            '"installableIPAProduced": False',
            '"installationAuthorized": False',
            '"installationPerformed": False',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, PREVIEW)
        self.assertIn("source app changed during signing rehearsal", PREVIEW)
        self.assertLess(PREVIEW.index("inspect_unsigned_candidate(app)"),
                        PREVIEW.index("TemporaryDirectory("))
        self.assertLess(PREVIEW.index("TemporaryDirectory("),
                        PREVIEW.index('"/usr/bin/codesign", "--force"'))
        self.assertIn("str(disposable_app)", PREVIEW)
        self.assertNotIn('codesign", "--force", "--sign", "-", str(app)', PREVIEW)

    def test_no_packaging_or_github_distribution_in_preview(self):
        for forbidden in (
            "zipfile", "/usr/bin/zip", "ditto -c", "shutil.make_archive",
            "shutil.copytree(", "appinst(", "posix_spawn(",
            "gh release", "actions/upload-artifact",
            "GenUI.openUrl", "git push", "git merge",
            "WebReader-Build69-iOS12-adhoc.ipa",
            "I-APPROVE-BUILD69-PRIVATE-QA-PACKAGING",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, PREVIEW)

    def test_workflow_keeps_source_unmodified_and_no_ipa_upload(self):
        self.assertIn("CODE_SIGNING_ALLOWED=NO CODE_SIGNING_REQUIRED=NO clean build",
                      WORKFLOW)
        self.assertIn("CURRENT_PROJECT_VERSION=69", WORKFLOW)
        self.assertNotIn("upload-artifact@", WORKFLOW)
        self.assertNotIn("WR69_PRIVATE_QA_PACKAGE_APPROVAL:", WORKFLOW)
        self.assertNotIn("package_webreader_build69_private_qa_ipa.sh --", WORKFLOW)


if __name__ == "__main__":
    unittest.main()

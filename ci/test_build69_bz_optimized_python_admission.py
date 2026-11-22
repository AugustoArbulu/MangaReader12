#!/usr/bin/env python3
"""BZ: private IPA checks must NOT disappear under Python -O / PYTHONOPTIMIZE.

Tests run extracted inline Python against synthetic input and mocked admission
modules only. No real IPA, codesign, network, publishing, or installation.
"""
import ast
import os
from pathlib import Path
import plistlib
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
PACKAGER = ROOT / "ci/package_webreader_build69_private_qa_ipa.sh"
EXPECTED_APPLICATION_ID = "AR5SFJC432.com.example.MangaReader12.AR5SFJC432"


def inline_scripts():
    source = PACKAGER.read_text(encoding="utf-8")
    scripts = re.findall(r"<<'PY'\n(.*?)\nPY(?:\n|$)", source, re.S)
    if len(scripts) != 3:
        raise ValueError("expected entitlements, IPA and atomic publisher scripts")
    return scripts


def run_inline(source, *args, env=None, cwd=None):
    environment = dict(os.environ)
    if env:
        environment.update(env)
    environment["PYTHONOPTIMIZE"] = "2"
    return subprocess.run(
        [sys.executable, "-O", "-c", source, *(str(a) for a in args)],
        env=environment, cwd=cwd, capture_output=True, text=True, timeout=10
    )


class OptimizedPythonAdmissions(unittest.TestCase):
    def test_all_packager_inline_scripts_have_no_python_assert(self):
        for index, script in enumerate(inline_scripts()):
            with self.subTest(block=index):
                parsed = ast.parse(script)
                self.assertFalse(
                    any(isinstance(node, ast.Assert) for node in ast.walk(parsed)),
                    "security or publication code must not rely on optimized-away assert"
                )

    def test_identity_and_metadata_guards_reject_under_optimized_python(self):
        identity, _, _ = inline_scripts()
        valid_entitlements = {"application-identifier": EXPECTED_APPLICATION_ID}
        valid_metadata = {
            "CFBundleIdentifier": "com.example.MangaReader12",
            "CFBundleDisplayName": "WebReader",
            "CFBundleExecutable": "MangaReader12",
            "CFBundleVersion": "69",
            "MinimumOSVersion": "12.0",
        }
        with tempfile.TemporaryDirectory(prefix="wr69-bz-invalid-identity-") as tmp:
            root = Path(tmp)
            ent = root / "entitlements.plist"
            info = root / "Info.plist"
            cases = (
                ({"application-identifier": "WRONG"}, valid_metadata),
                (valid_entitlements, dict(valid_metadata, CFBundleVersion="68")),
                (valid_entitlements, dict(valid_metadata, MinimumOSVersion="13.0")),
                (valid_entitlements, dict(valid_metadata, CFBundleIdentifier="wrong")),
                (valid_entitlements, dict(valid_metadata, CFBundleExecutable="wrong")),
            )
            for ent_data, info_data in cases:
                with self.subTest(entitlements=ent_data, metadata=info_data):
                    ent.write_bytes(plistlib.dumps(ent_data))
                    info.write_bytes(plistlib.dumps(info_data))
                    result = run_inline(identity, ent, info, cwd=tmp)
                    self.assertNotEqual(result.returncode, 0, result.stdout)
                    self.assertIn("BLOCKED:", result.stderr)

    def test_staged_ipa_rejections_survive_optimized_python(self):
        _, admission, _ = inline_scripts()
        with tempfile.TemporaryDirectory(prefix="wr69-bz-synthetic-") as tmp:
            root = Path(tmp)
            fake_ipa = root / "NOT_AN_IPA.synthetic"
            fake_ipa.write_bytes(b"synthetic bytes, no IPA")
            (root / "build66_ipa_preflight.py").write_text(
                "import os\n"
                "MAX_IPA_BYTES = 1 if os.getenv('BZ_CASE') == 'size' else 1024\n"
                "def inspect_ipa(*args, **kwargs):\n"
                "    return {'ipa_snapshot': b'fake', "
                "'build': 68 if os.getenv('BZ_CASE') == 'build' else 69, "
                "'minimum_ios': '13.0' if os.getenv('BZ_CASE') == 'ios' else '12.0'}\n",
                encoding="utf-8"
            )
            (root / "build66_code_signature_gate.py").write_text(
                "import os\n"
                "INSTALLED_APPLICATION_IDENTIFIER = "
                "'AR5SFJC432.com.example.MangaReader12.AR5SFJC432'\n"
                "def audit_code_signature_snapshot(*args):\n"
                "    case = os.getenv('BZ_CASE')\n"
                "    return {\n"
                "        'adHocSignatureIntegrityVerified': case != 'seal',\n"
                "        'installedApplicationIdentifierMatch': case != 'identifier',\n"
                "        'applicationIdentifier': 'WRONG' if case == 'actual-id' "
                "else INSTALLED_APPLICATION_IDENTIFIER,\n"
                "        'thinArm64ExecutableVerified': case != 'arch',\n"
                "    }\n",
                encoding="utf-8"
            )
            for case in ("size", "build", "ios", "seal", "identifier",
                         "actual-id", "arch"):
                with self.subTest(case=case):
                    result = run_inline(
                        admission, fake_ipa, cwd=root,
                        env={"PYTHONPATH": str(root), "BZ_CASE": case}
                    )
                    self.assertNotEqual(result.returncode, 0, result.stdout)
                    self.assertIn("BLOCKED:", result.stderr)
                    self.assertNotIn("PASS:", result.stdout)

    def test_packager_and_ci_still_block_real_ipa_creation(self):
        package = PACKAGER.read_text(encoding="utf-8")
        workflow = (ROOT / ".github/workflows/chimera-build69-phase-ac-af-integrated-qa.yml"
                    ).read_text(encoding="utf-8")
        self.assertIn('if [[ "${WR69_PRIVATE_QA_PACKAGE_APPROVAL:-}" != "$CONSENT" ]]',
                      package)
        self.assertIn('if [[ -n "${GITHUB_ACTIONS:-}" || -n "${CI:-}" ]]', package)
        self.assertIn('WR69_PRIVATE_QA_REVIEWED_COMMIT', package)
        self.assertNotIn('package_webreader_build69_private_qa_ipa.sh',
                         workflow.split("\njobs:\n", 1)[1])
        self.assertNotIn('upload-artifact@', workflow)


if __name__ == "__main__":
    unittest.main()

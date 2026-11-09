#!/usr/bin/env python3
"""Build69 BL: execute only atomic local publication code with dummy bytes.

Extracts the two-link publication step from owner-gated Bash script, never
runs the actual packager, codesign, xcodebuild, or any installer.
"""
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = (ROOT / "ci/package_webreader_build69_private_qa_ipa.sh").read_text()
MARKER = 'python3 - "$STAGED_IPA" "$OUTPUT" <<\'PY\'\n'
assert PACKAGE.count(MARKER) == 1
PUBLISH = PACKAGE.split(MARKER, 1)[1].split("\nPY\n", 1)[0]


class AtomicPrivateDelivery(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="wr69-bl-exclusivelink-")
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.stage = root / ".wr69-private-qa.abcdefgh"
        self.stage.mkdir()
        self.filename = "WebReader-Build69-iOS12-adhoc.ipa"
        self.source = self.stage / self.filename
        self.final = root / self.filename
        self.source.write_bytes(b"NOT-AN-IPA: synthetic staging bytes")
        digest = hashlib.sha256(self.source.read_bytes()).hexdigest()
        Path(str(self.source) + ".sha256").write_bytes(
            digest.encode("ascii") + b"  " + self.filename.encode() + b"\n"
        )
        self.checksum = Path(str(self.final) + ".sha256")

    def run_publisher(self, *, injected=""):
        return subprocess.run(
            [sys.executable, "-c", injected + "\n" + PUBLISH,
             str(self.source), str(self.final)],
            capture_output=True, text=True, timeout=10
        )

    def test_staged_files_are_published_only_after_exclusive_link(self):
        self.assertFalse(self.final.exists())
        result = self.run_publisher()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.final.read_bytes(), self.source.read_bytes())
        self.assertEqual(self.checksum.read_bytes(), Path(
            str(self.source) + ".sha256"
        ).read_bytes())
        # A second attempt must never overwrite the already-published bytes.
        again = self.run_publisher()
        self.assertNotEqual(again.returncode, 0)
        self.assertEqual(self.final.read_bytes(), self.source.read_bytes())

    def test_preexisting_archive_is_preserved_and_no_checksum_created(self):
        self.final.write_bytes(b"prior owner archive; do not overwrite")
        result = self.run_publisher()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.final.read_bytes(), b"prior owner archive; do not overwrite")
        self.assertFalse(self.checksum.exists())

    def test_preexisting_checksum_stops_publication(self):
        self.checksum.write_bytes(b"owner checksum; do not overwrite")
        result = self.run_publisher()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.final.exists())
        self.assertEqual(self.checksum.read_bytes(), b"owner checksum; do not overwrite")

    def test_symlink_target_is_not_overwritten(self):
        private = self.final.parent / "preserve"
        private.write_bytes(b"important")
        self.final.symlink_to(private)
        result = self.run_publisher()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(private.read_bytes(), b"important")
        self.assertTrue(self.final.is_symlink())
        self.assertFalse(self.checksum.exists())

    def test_failed_second_link_rolls_back_only_its_created_checksum(self):
        inject = """
import os
original_link = os.link
calls = [0]
def fail_second_link(*args, **kwargs):
    calls[0] += 1
    if calls[0] == 2:
        raise OSError("test-only simulated publication interruption")
    return original_link(*args, **kwargs)
os.link = fail_second_link
"""
        result = self.run_publisher(injected=inject)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.final.exists())
        self.assertFalse(self.checksum.exists())
        self.assertTrue(self.source.exists())
        self.assertTrue(Path(str(self.source) + ".sha256").exists())

    def test_wrong_staged_checksum_blocks_publication(self):
        Path(str(self.source) + ".sha256").write_bytes(
            b"0" * 64 + b"  " + self.filename.encode() + b"\\n"
        )
        result = self.run_publisher()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("differs from checksum", result.stderr)
        self.assertFalse(self.final.exists())
        self.assertFalse(self.checksum.exists())

    def test_final_link_mutation_triggers_rollback(self):
        inject = """
import os
original_link = os.link
calls = [0]
def mutate_after_second_link(*args, **kwargs):
    original_link(*args, **kwargs)
    calls[0] += 1
    if calls[0] == 2:
        with open(args[1], "r+b") as stream:
            stream.seek(0)
            stream.write(b"INVALID")
os.link = mutate_after_second_link
"""
        result = self.run_publisher(injected=inject)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("changed after linking", result.stderr)
        self.assertFalse(self.final.exists())
        self.assertFalse(self.checksum.exists())

    def test_source_script_guards_actual_archive_before_final_name(self):
        self.assertIn('STAGED_IPA="$TMP/$EXPECTED_NAME"', PACKAGE)
        self.assertIn('mktemp -d "$OUTPUT_DIR/.wr69-private-qa.XXXXXXXX"', PACKAGE)
        self.assertIn('size = ipa.stat().st_size', PACKAGE)
        self.assertIn('0 < size <= MAX_IPA_BYTES', PACKAGE)
        self.assertIn('audit_code_signature_snapshot(snapshot, digest, size)', PACKAGE)
        self.assertLess(PACKAGE.index('PYTHONPATH="$ROOT/ci" python3 - "$STAGED_IPA"'),
                        PACKAGE.index(MARKER))
        self.assertIn('os.link(checksum_staged, checksum_final)', PUBLISH)
        self.assertIn('os.link(staged, final)', PUBLISH)
        self.assertLess(PUBLISH.index('os.link(checksum_staged, checksum_final)'),
                        PUBLISH.index('os.link(staged, final)'))
        self.assertNotIn('os.replace(', PUBLISH)
        self.assertNotIn('shutil.copyfile(', PUBLISH)


if __name__ == "__main__":
    unittest.main()

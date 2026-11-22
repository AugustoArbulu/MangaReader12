"""Smoke-test the read-only NewTerm collector with synthetic command output."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("observe_appinst_identity.sh")
DIGEST = "fa" * 32


class ObserveAppinstIdentityTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.bin = Path(temporary.name)

    def command(self, name, body):
        path = self.bin / name
        path.write_text("#!/bin/sh\n" + body + "\n")
        path.chmod(0o700)

    def collect(self):
        return subprocess.run(
            ["/bin/sh", str(SCRIPT.resolve())],
            env={**os.environ, "PATH": str(self.bin)},
            capture_output=True, text=True, timeout=5,
        )

    def test_hash_and_package_metadata(self):
        self.command("sha256sum", f'[ "$*" = /usr/bin/appinst ] && printf "%s  %s\\n" {DIGEST} "$1"')
        self.command("dpkg-query", """case "$1" in
-S) [ "$2" = /usr/bin/appinst ] && printf '%s\\n' 'ai.akemi.appinst: /usr/bin/appinst';;
-W) [ "$3" = ai.akemi.appinst ] && printf '%s\\n' 'install ok installed|2.1.1|iphoneos-arm';;
esac""")
        result = self.collect()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [
            "APPINST_PATH=/usr/bin/appinst",
            f"APPINST_SHA256={DIGEST}",
            "APPINST_DPKG_OWNER=ai.akemi.appinst: /usr/bin/appinst",
            "APPINST_DPKG_STATUS_VERSION_ARCH=install ok installed|2.1.1|iphoneos-arm",
        ])

    def test_shasum_fallback_preserves_hash_without_package_metadata(self):
        self.command("shasum", f'[ "$*" = "-a 256 /usr/bin/appinst" ] && printf "%s  %s\\n" {DIGEST} "$3"')
        result = self.collect()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"APPINST_SHA256={DIGEST}\n", result.stdout)
        self.assertIn("APPINST_DPKG_OWNER=UNAVAILABLE\n", result.stdout)
        self.assertIn("APPINST_DPKG_STATUS_VERSION_ARCH=UNAVAILABLE\n", result.stdout)

    def test_bad_or_failed_hash_does_not_print_a_receipt(self):
        for body in ("printf '%s\\n' invalid", f"printf '%s\\n' {DIGEST}; exit 1"):
            with self.subTest(body=body):
                self.command("sha256sum", body)
                result = self.collect()
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")

"""Test the NewTerm capability preflight without querying host processes."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().with_name("observe_installd_visibility.sh")


class InstalldVisibilityTests(unittest.TestCase):
    def observe(self, lsof_body):
        with tempfile.TemporaryDirectory() as tools:
            tools = Path(tools)
            (tools / "grep").symlink_to("/usr/bin/grep")
            if lsof_body is not None:
                lsof = tools / "lsof"
                lsof.write_text(
                    '#!/bin/sh\n[ "$*" = "-a -c installd -Fpc" ] || exit 99\n'
                    + lsof_body + "\n"
                )
                lsof.chmod(0o700)
            return subprocess.run(
                ["/bin/sh", str(SCRIPT)],
                env={**os.environ, "PATH": str(tools)},
                check=True, capture_output=True, text=True, timeout=5,
            ).stdout

    def test_only_exact_installd_name_is_accepted(self):
        for body, expected in (
            ("printf 'p12\\ncinstalld\\n'", "PROCESS_LISTED"),
            ("printf 'p12\\ncinstalld-other\\n'", "NOT_OBSERVED"),
            ("printf 'p12\\ncinstalld\\n'; exit 1", "NOT_OBSERVED"),
            (None, "LSOF_UNAVAILABLE"),
        ):
            with self.subTest(expected=expected):
                self.assertEqual(self.observe(body), f"WR_INSTALLD_VISIBILITY={expected}\n")

#!/usr/bin/env python3
"""Offline negative checks for Build66 rehearsal packaging and audit."""
from pathlib import Path
import hashlib
import tempfile
import unittest

from audit_webreader_build66_rehearsal import (
    EXPECTED_FILENAME, RehearsalRejected, audit
)
from test_build66_signed_release_preflight import synthetic_ipa


class Build66RehearsalReadOnlyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="wr66-qa-denial-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.ipa = self.root / EXPECTED_FILENAME
        self.ipa.write_bytes(synthetic_ipa(build="66"))
        self.checksum = self.root / (EXPECTED_FILENAME + ".sha256")
        self.make_checksum()

    def make_checksum(self):
        self.checksum.write_text(
            hashlib.sha256(self.ipa.read_bytes()).hexdigest() +
            "  " + EXPECTED_FILENAME + "\n", encoding="ascii"
        )

    def rejected(self, ipa=None, sha=None):
        with self.assertRaises(RehearsalRejected):
            audit(ipa or self.ipa, sha or self.checksum)

    def test_synthetic_unsigned_fixture_cannot_pass_native_codesign(self):
        self.rejected()

    def test_missing_ipa(self):
        self.ipa.unlink()
        self.rejected()

    def test_wrong_filename(self):
        replacement = self.root / "WebReader-iOS12-unsigned.ipa"
        self.ipa.rename(replacement)
        self.rejected(ipa=replacement)

    def test_wrong_manifest_file(self):
        self.rejected(sha=self.root / "sha.txt")

    def test_changed_ipa_bytes(self):
        self.ipa.write_bytes(self.ipa.read_bytes() + b"forged")
        self.rejected()

    def test_wrong_digest(self):
        self.checksum.write_text("0" * 64 + "  " + EXPECTED_FILENAME + "\n")
        self.rejected()

    def test_extra_checksum_lines(self):
        self.checksum.write_text(self.checksum.read_text() + "extra\n")
        self.rejected()

    def test_wrong_digest_target(self):
        self.checksum.write_text(
            hashlib.sha256(self.ipa.read_bytes()).hexdigest() +
            "  attacker.ipa\n"
        )
        self.rejected()

    def test_symlink_ipa(self):
        elsewhere = self.root / "source.ipa"
        self.ipa.rename(elsewhere)
        self.ipa.symlink_to(elsewhere)
        self.rejected()

    def test_symlink_checksum(self):
        elsewhere = self.root / "source.sha256"
        self.checksum.rename(elsewhere)
        self.checksum.symlink_to(elsewhere)
        self.rejected()

    def test_old_build_rejected(self):
        self.ipa.write_bytes(synthetic_ipa(build="65"))
        self.make_checksum()
        self.rejected()

    def test_zip_header_not_macho_signature(self):
        self.ipa.write_bytes(b"PK\x03\x04" + bytes(45))
        self.make_checksum()
        self.rejected()

    def test_empty_candidate(self):
        self.ipa.write_bytes(b"")
        self.make_checksum()
        self.rejected()

    def test_package_script_explicitly_nonprivileged(self):
        source = (Path(__file__).resolve().parent /
                  "package_webreader_build66_rehearsal.sh").read_text()
        for requirement in (
            'if [[ "$EUID" -eq 0 ]]', 'APP_PATH="$1"', 'OUTPUT="$2"', 'CFBundleVersion"] = "66"',
            'codesign --force --sign -', 'codesign --verify',
            '"application-identifier"', "installed Build65", '"56"',
        ):
            self.assertIn(requirement, source)
        for forbidden in (
            "appinst(", "/usr/bin/appinst", "launchctl", "sudo appinst",
            "posix_spawn", "curl ", "wget ", "git push", "gh release",
        ):
            self.assertNotIn(forbidden, source)

    def test_auditor_refuses_to_grant_authority(self):
        source = (Path(__file__).resolve().parent /
                  "audit_webreader_build66_rehearsal.py").read_text()
        for flag in (
            '"installationAuthorized": False',
            '"installationPerformed": False',
            '"productionPublisherAuthenticated": False',
            '"approvedForAutomaticRelease": False',
            '"ios12DeviceInstallTested": False',
        ):
            self.assertIn(flag, source)
        self.assertNotIn("appinst(", source)


if __name__ == "__main__":
    unittest.main()

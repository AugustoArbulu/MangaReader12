#!/usr/bin/env python3
"""CJ: a real iOS bridge must NEVER carry an untrusted path into appinst.

The legacy pathname-based CLI is retained only behind an explicit fake-appinst
test build. A user phrase, SHA check, UID, or a PING response never grants
installation authority. This is a source/compile contract, not iPad QA.
"""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parent.parent
C=(ROOT/"ci/webreader_appinst_bridge.c").read_text()
SWIFT=(ROOT/"MangaReader12/Core/WebReaderAppinstSocket.swift").read_text()


class ChimeraUnsafeLegacyCLILock(unittest.TestCase):
    def test_default_contains_no_real_appinst_path_or_launcher(self):
        self.assertNotIn('#define APPINST_BINARY "/usr/bin/appinst"', C)
        self.assertIn("#ifdef WEBREADER_FAKE_APPINST_QA\n#define APPINST_BINARY WEBREADER_TEST_APPINST\n#endif", C)
        self.assertIn("#ifdef WEBREADER_FAKE_APPINST_QA\n/* Host-only legacy", C)
        self.assertIn("#endif /* WEBREADER_FAKE_APPINST_QA */", C)
        self.assertIn("#include <spawn.h>\n#endif", C)
        self.assertIn("INSTALL_DISABLED: unsafe legacy CLI removed", C)
        self.assertIn("APPINST_CLI_DISABLED", C)
        self.assertIn('/* Both NORMAL and PING-only builds must be strictly non-installing.', C)
        self.assertIn("#ifndef WEBREADER_FAKE_APPINST_QA", C)
        self.assertIn('    (void)send_all(connection, SOCKET_FAILURE, 8);', C)
        self.assertIn('if (memcmp(header, SOCKET_PING, 8) == 0)', C)

    def test_bad_macro_combinations_fail_at_compile_time(self):
        self.assertIn("#if !defined(WEBREADER_TEST_ROOT) || !defined(WEBREADER_TEST_APPINST)", C)
        self.assertIn("#error \"Fake appinst QA requires BOTH", C)
        self.assertIn("#if defined(WEBREADER_PING_ONLY)\n#error \"PING mode must never", C)

    def test_app_install_still_denied_until_real_peer_auth(self):
        self.assertIn("static let liveInstallationEnabled = false", SWIFT)
        self.assertIn("DispatchQueue.main.async { completion(.rejected) }", SWIFT)
        self.assertNotIn("WEBREADER_FAKE_APPINST_QA", SWIFT)

    def test_only_host_diagnostic_can_use_fake_installer(self):
        source=(ROOT/"ci/test_webreader_appinst_bridge.py").read_text()
        self.assertIn('"-DWEBREADER_FAKE_APPINST_QA=1"', source)
        self.assertIn('self.assertNotIn("posix_spawn", symbols)', source)
        self.assertIn('self.assertIn("INSTALL_DISABLED", result.stderr)', source)
        self.assertIn('self.assertNotIn(b"/usr/bin/appinst", binary)', source)

if __name__=="__main__":
    unittest.main()

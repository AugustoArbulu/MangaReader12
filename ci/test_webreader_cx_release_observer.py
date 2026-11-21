#!/usr/bin/env python3
"""DB2: actual iOS12 Swift public-Release checker in an OFFLINE host CLI.

One fixed endpoint; no releases are produced, no IPA is downloaded, no
installer functions are invoked. Optional real HTTPS is a separate,
explicit workflow_dispatch and MUST NOT be called from this unittest.
"""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "MangaReader12" / "Core"
SOURCE = ROOT / "ci" / "webreader_cx_release_observer.swift"
SOURCES = [
    CORE / "WebReaderStrictJSON.swift",
    CORE / "WebReaderUpdateManifestVerifier.swift",
    CORE / "WebReaderUpdateChecker.swift",
    CORE / "WebReaderGitHubReleaseParser.swift",
    SOURCE,
]
FIXED_ENDPOINT = (
    "https://api.github.com/repos/AugustoArbulu/"
    "MangaReader12/releases/latest"
)


class DB2ReadOnlyReleaseDiscovery(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if sys.platform != "darwin":
            raise unittest.SkipTest("Real Swift Foundation/Security requires macOS")
        if os.geteuid() == 0:
            raise unittest.SkipTest("Never run this client with root privileges")
        cls.temp = tempfile.TemporaryDirectory(prefix="wr-db2-release-")
        cls.bin = Path(cls.temp.name) / "release-observer"
        result = subprocess.run(
            ["xcrun", "swiftc", "-parse-as-library"] +
            [str(x) for x in SOURCES] + ["-o", str(cls.bin)],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_synthetic_release_parsing_and_no_install_authority(self):
        test = subprocess.run([str(self.bin), "--selftest"],
                              capture_output=True, text=True, timeout=12)
        self.assertEqual(test.returncode, 0, test.stdout + test.stderr)
        self.assertIn("WR_DB2_SYNTHETIC_PARSER_SELFTEST=PASS", test.stdout)
        self.assertIn("WR_DB2_OBSERVATION=UNTRUSTED_NEWER_METADATA_BUILD_71",
                      test.stdout)
        for claim in (
            "WR_DB2_PUBLIC_RELEASE_IS_SIGNED_PUBLISHER=NO",
            "WR_DB2_OWNER_TRUST_PROVISIONED=NO",
            "WR_DB2_PEER_AUTHENTICATED=NO",
            "WR_DB2_IPA_DOWNLOADED=NO",
            "WR_DB2_INSTALL_AUTHORIZED=NO",
            "WR_DB2_INSTALL_PERFORMED=NO",
        ):
            self.assertIn(claim, test.stdout)
        self.assertNotIn("AVAILABLE_AUTHENTICATED", test.stdout)

    def test_invalid_arguments_do_not_trigger_network(self):
        for args in ([], ["--install"], ["--live", FIXED_ENDPOINT],
                     ["--selftest", "--live"],
                     ["/tmp/ipa"], ["https://example.com"],
                     ["--release", "build71"], ["--install", "--live"]):
            with self.subTest(args=args):
                call = subprocess.run(
                    [str(self.bin)] + args, capture_output=True,
                    text=True, timeout=5
                )
                self.assertEqual(call.returncode, 2, call.stdout + call.stderr)

    def test_unchanged_production_key_gates_and_static_endpoint(self):
        observer = SOURCE.read_text()
        channel = (CORE / "WebReaderUpdateChecker.swift").read_text()
        parser = (CORE / "WebReaderGitHubReleaseParser.swift").read_text()
        trust = (CORE / "WebReaderProductionPublisherTrust.swift").read_text()
        bridge = (CORE / "WebReaderAppinstSocket.swift").read_text()
        assert "WRDB2HostProbe" in observer
        assert "usePublicGitHubReleases: true" in observer
        assert "WebReaderGitHubReleaseParser.parse" in observer
        assert "WebReaderUpdateChecker(" in observer
        assert FIXED_ENDPOINT in observer
        assert FIXED_ENDPOINT in parser.replace('"\n    )!', '"\n    )!') or (
            '"https://api.github.com/repos/AugustoArbulu/MangaReader12/releases/latest"' in parser
        )
        assert "static let productionPublicKeyX963: Data? = nil" in channel
        assert "static let independentlyProvisionedSPKISHA256: String? = nil" in trust
        assert "static let liveInstallationEnabled = false" in bridge
        assert "DispatchQueue.main.async { completion(.rejected) }" in bridge
        assert '"--live"' in observer and '"--selftest"' in observer
        assert 'installApplication:' not in observer
        assert 'WRINST1' not in observer
        assert "/usr/bin/appinst" not in observer
        for forbidden in (
            "posix_spawn(", "fork(", "execve(", "system(",
            "dlopen(", "FileManager.default", "fopen(",
            "URLSession.shared", "URLSessionDownloadTask",
            "downloadTask", "data.write(", "ipaURL:"
        ):
            self.assertNotIn(forbidden, observer)
        # The previous CX service is strictly network-free and unchanged.
        cx = (ROOT / "ci/webreader_chimera_checkonly_service.c").read_text()
        for forbidden in ("https://", "NSURLSession", "curl ", "appinst("):
            self.assertNotIn(forbidden, cx)


if __name__ == "__main__":
    unittest.main()

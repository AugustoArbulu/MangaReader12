#!/usr/bin/env python3
"""DB4 read-only standalone iOS12 HTTPS status / headers QA IPA audit.

No network in this audit. Never install, download releases, create files on
device or publish a WebReader app. Checks the iOS12 ad-hoc signature in macOS.
"""
import hashlib
from pathlib import Path
import plistlib
import struct
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "ci/chimera_db4_https_app_probe/main.m"
SCRIPT = ROOT / "ci/build_chimera_db4_https_qa_ipa.sh"
ENT = ROOT / "ci/chimera_db4_https_app_probe/qa.entitlements"
IPA = ROOT / "WebReader-DB4-HTTPS-Only-iOS12-adhoc.ipa"
SHA = ROOT / (IPA.name + ".sha256")
APP = "Payload/WRDB4HTTPS.app/"
BIN = APP + "WRDB4HTTPS"
INFO = APP + "Info.plist"
BUNDLE = "com.example.WebReaderDB4HTTPSProbe"
APP_ID = "WRTEST0001." + BUNDLE
FIXED = "https://api.github.com/repos/AugustoArbulu/MangaReader12/releases/latest"


def run():
    src = SOURCE.read_text()
    pkg = SCRIPT.read_text()
    assert FIXED in src, "fixed GitHub endpoint absent"
    assert 'request.HTTPMethod = @"GET"' in src
    assert "NSURLSessionResponseCancel" in src
    assert "completionHandler(nil)" in src
    assert "ephemeralSessionConfiguration" in src
    assert "URLCredentialStorage = nil" in src
    assert "HTTPCookieStorage = nil" in src
    assert "config.URLCache = nil" in src
    assert "WR_DB4_IPA_DOWNLOADED=NO" in src
    assert "WR_DB4_INSTALL=NEVER" in src
    assert "WR_DB4_PUBLISHER_AUTHENTICATED=NO" in src
    assert "@selector(runProbe)" in src
    assert "WRDB4SafeHeader" in src
    for forbidden in ("posix_spawn(", "execve(", "fork(", "system(", "dlopen(",
                      "installApplication:", "WRINST1", "appinst(",
                      "downloadTask", "writeToFile:", "WebReaderUpdateChecker",
                      "NSData dataWithContentsOfURL", "sqlite3_open"):
        assert forbidden not in src, forbidden

    assert "ci/chimera_db4_https_app_probe/main.m" in pkg
    assert "ci/chimera_db4_https_app_probe/qa.entitlements" in pkg
    assert "com.example.WebReaderDB4HTTPSProbe" in pkg
    assert "WebReader.app" not in pkg
    assert IPA.exists() and SHA.exists(), "QA IPA not generated"
    binary = IPA.read_bytes()
    assert 1024 < len(binary) < 5_000_000
    digest = hashlib.sha256(binary).hexdigest()
    assert SHA.read_text().strip() == digest + "  " + IPA.name

    with zipfile.ZipFile(IPA) as archive:
        names = archive.namelist()
        assert len(names) == len(set(names)), "duplicate ZIP entries"
        assert INFO in names and BIN in names
        assert len(names) <= 12, names
        assert all(name.startswith(APP) or name == "Payload/" for name in names)
        assert not any(part == ".." for n in names for part in n.split("/"))
        assert not any(n.lower().endswith((".ipa", ".deb")) or
                       "appinst" in n.lower() or "webreader-pinglab" in n.lower()
                       for n in names)
        info = plistlib.loads(archive.read(INFO))
        assert info["CFBundleIdentifier"] == BUNDLE
        assert info["CFBundleExecutable"] == "WRDB4HTTPS"
        assert info["CFBundleDisplayName"] == "WebReader HTTPS Teste"
        assert info["CFBundleVersion"] == "1"
        assert info["MinimumOSVersion"] == "12.0"
        assert info["UIDeviceFamily"] == [1, 2]
        for forbidden in ("UIBackgroundModes", "UIFileSharingEnabled",
                          "NSAppTransportSecurity", "NSAllowsArbitraryLoads",
                          "CFBundleDocumentTypes"):
            assert forbidden not in info
        executable = archive.read(BIN)
        assert executable[:4] == b"\xcf\xfa\xed\xfe"
        assert struct.unpack_from("<I", executable, 4)[0] == 0x0100000C
        for forbidden in (b"/usr/bin/appinst", b"WRINST1\n",
                          b"LSApplicationWorkspace", b"installApplication:",
                          b"sqlite3_open"):
            assert forbidden not in executable, forbidden
        with tempfile.TemporaryDirectory(prefix="wr-db4-ipa-") as td:
            archive.extractall(td)
            app = Path(td) / APP
            signed = subprocess.run(
                ["codesign", "-d", "--entitlements", ":-", str(app)],
                capture_output=True
            )
            assert signed.returncode == 0, signed.stderr
            identity = {"application-identifier": APP_ID}
            assert plistlib.loads(signed.stdout) == identity
            assert plistlib.loads(ENT.read_bytes()) == identity
            result = subprocess.run(
                ["codesign", "--verify", "--verbose", str(app)],
                capture_output=True, text=True
            )
            assert result.returncode == 0, result.stderr
            nm = subprocess.run(
                ["xcrun", "nm", "-u", str(app / "WRDB4HTTPS")],
                capture_output=True, text=True, check=True
            ).stdout
            for forbidden in ("_posix_spawn", "_fork", "_execve", "_system",
                              "_dlopen", "_sqlite3_open", "_chmod",
                              "_LSApplicationWorkspace"):
                assert forbidden not in nm, forbidden

    print("PASS DB4: standalone ad-hoc signed ARM64 iOS12 sandbox HTTP headers QA")
    print("PASS DB4: one exact HTTPS URL, no redirects, no body, no install")
    print("PASS DB4: no WebReader data, IPA, helper, custom root entitlement")


if __name__ == "__main__":
    run()

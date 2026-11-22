#!/usr/bin/env python3
"""DA: offline audit of isolated, signed iOS 12 CX-only sandbox IPA.

No GitHub Releases, AppInst, device, network or WebReader user data involved.
"""
import hashlib
from pathlib import Path
import plistlib
import struct
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parent.parent
IPA = ROOT / "WebReader-CX-Sandbox-DA-iOS12-adhoc.ipa"
SHA = ROOT / (IPA.name + ".sha256")
APP = "Payload/WRCXSandbox.app/"
BIN = APP + "WRCXSandbox"
INFO = APP + "Info.plist"
ENT = ROOT / "ci/chimera_cx_app_probe/qa.entitlements"


def main():
    assert IPA.is_file() and SHA.is_file()
    data = IPA.read_bytes()
    assert 2000 < len(data) < 5_000_000
    checksum = hashlib.sha256(data).hexdigest()
    assert SHA.read_text().strip() == checksum + "  " + IPA.name

    with zipfile.ZipFile(IPA) as z:
        names = z.namelist()
        assert len(names) == len(set(names)), "duplicate ZIP entries"
        assert all(name.startswith(APP) or name == "Payload/" for name in names)
        assert INFO in names and BIN in names
        assert not any(part in ("..", ".") for n in names for part in n.split("/") if part)
        assert not any(n.endswith(".ipa") or n.endswith(".deb") or
                       "appinst" in n.lower() or "webreader-pinglab" in n.lower()
                       for n in names)
        assert len(names) <= 12, names
        plist = plistlib.loads(z.read(INFO))
        assert plist["CFBundleIdentifier"] == "com.example.WebReaderCXSandboxProbe"
        assert plist["CFBundleExecutable"] == "WRCXSandbox"
        assert plist["MinimumOSVersion"] == "12.0"
        assert plist["CFBundleVersion"] == "1"
        assert plist["CFBundleDisplayName"] == "WebReader CX Teste"
        assert plist["UIDeviceFamily"] == [1, 2]
        assert "UIBackgroundModes" not in plist
        assert "UIFileSharingEnabled" not in plist
        assert "NSAppTransportSecurity" not in plist
        executable = z.read(BIN)
        assert executable[:4] == b"\xcf\xfa\xed\xfe", "thin ARM64 Mach-O"
        assert struct.unpack_from("<I", executable, 4)[0] == 0x0100000C
        assert len(executable) > 3000
        assert ((z.getinfo(BIN).external_attr >> 16) & 0o111) != 0
        for forbidden in (b"/usr/bin/appinst", b"WRINST1\n",
                          b"installApplication:", b"LSApplicationWorkspace",
                          b"/var/mobile/Containers", b"sqlite3_open"):
            assert forbidden not in executable, forbidden
        with tempfile.TemporaryDirectory(prefix="wr-da-audit-") as td:
            z.extractall(td)
            installed = Path(td) / APP
            signed = subprocess.run(
                ["codesign", "-d", "--entitlements", ":-", str(installed)],
                capture_output=True
            )
            assert signed.returncode == 0, signed.stderr
            expected = {
                "application-identifier":
                    "WRTEST0001.com.example.WebReaderCXSandboxProbe"
            }
            assert plistlib.loads(signed.stdout) == expected
            assert plistlib.loads(ENT.read_bytes()) == expected
            checked = subprocess.run(
                ["codesign", "--verify", "--verbose", str(installed)],
                capture_output=True, text=True
            )
            assert checked.returncode == 0, checked.stderr

    script = (ROOT / "ci/build_chimera_cx_sandbox_qa_ipa.sh").read_text()
    assert "codesign --force --sign -" in script
    assert "--entitlements ci/chimera_cx_app_probe/qa.entitlements" in script
    assert "ci/chimera_cx_app_probe/cx_client.c" in script
    assert "ci/chimera_cx_app_probe/main.m" in script
    assert "com.example.WebReaderCXSandboxProbe" in script
    assert "WebReader.app" not in script
    print("PASS DA: standalone signed iOS12 ARM64 sandbox diagnostic IPA")
    print("PASS DA: separate Bundle ID, minimal app identifier entitlement")
    print("PASS DA: no executable helper, installer, WebReader data or release")


if __name__ == "__main__":
    main()

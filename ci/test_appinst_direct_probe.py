#!/usr/bin/env python3
"""Audit one small iOS12 appinst direct launch IPA, without running it.

Never check in a production installer or actual IPA to this build.
"""
import hashlib
from pathlib import Path
import plistlib
import struct
import zipfile

IPA = Path("WebReader-Appinst-Direto-iOS12-unsigned.ipa")
SHA = Path(IPA.name + ".sha256")
SOURCE = Path("ci/appinst_direct_probe/main.m")
INFO = "Payload/WRAppinstDirect.app/Info.plist"
EXEC = "Payload/WRAppinstDirect.app/WRAppinstDirect"


def main():
    assert IPA.is_file()
    assert SHA.is_file()
    assert len(IPA.read_bytes()) < 5 * 1024 * 1024
    digest = hashlib.sha256(IPA.read_bytes()).hexdigest()
    assert SHA.read_text().strip() == f"{digest}  {IPA.name}"
    with zipfile.ZipFile(IPA) as archive:
        contents = archive.namelist()
        assert len(contents) == len(set(contents)), "duplicate ZIP entries"
        assert len(contents) <= 8
        assert not any(".." in p.split("/") for p in contents)
        assert INFO in contents and EXEC in contents
        info = plistlib.loads(archive.read(INFO))
        exe = archive.read(EXEC)
        assert info["CFBundleIdentifier"] == "com.example.WebReaderAppinstDirectProbe"
        assert info["CFBundleIdentifier"] != "com.example.MangaReader12"
        assert info["CFBundleDisplayName"] == "WebReader appinst Test"
        assert info["MinimumOSVersion"] == "12.0"
        assert info["CFBundleVersion"] == "2"
        assert info["CFBundleExecutable"] == "WRAppinstDirect"
        assert "UIBackgroundModes" not in info
        assert "UIFileSharingEnabled" not in info
        assert exe[:4] == b"\xcf\xfa\xed\xfe"
        assert struct.unpack_from("<I", exe, 4)[0] == 0x0100000C
        assert len(exe) > 2048
    source = SOURCE.read_text()
    assert '"/usr/bin/appinst"' in source
    assert '(char *)"--help"' in source
    assert 'posix_spawn(&child, binary, NULL, NULL, arguments, environ)' in source
    assert 'Diagnóstico lstat:' in source
    assert 'Diagnóstico access(X_OK):' in source
    assert 'Tentando posix_spawn diretamente' in source
    diagnostic = source.split("    // Read-only metadata probes are advisory:", 1)[1]
    before_spawn = diagnostic.split("    char * const arguments[]", 1)[0]
    assert "return report;" not in before_spawn.split('if (lstat(binary, &st) != 0)', 1)[1].split('else if (!S_ISREG(st.st_mode))', 1)[0]
    assert "return report;" not in before_spawn.split('if (access(binary, X_OK) != 0)', 1)[1]
    assert "UIAlertController" in source
    assert "Arquivos temporários" not in source or "temporári" in source
    assert "pode limpar arquivos temporários" in source
    assert "I-CONFIRM-INSTALL" not in source
    assert "system(" not in source
    assert "execve(" not in source
    assert "installApplication:" not in source
    assert "appinst_bridge" not in source
    assert "WebReaderAppinstDirectProbe" in source
    print("PASS one direct-appinst iOS12 diagnostic IPA: isolated bundle and help-only process")


if __name__ == "__main__":
    main()

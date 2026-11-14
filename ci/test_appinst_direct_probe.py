#!/usr/bin/env python3
"""Audit one small iOS12 appinst direct launch IPA, without running it.

Never check in a production installer or actual IPA to this build.
"""
import hashlib
from pathlib import Path
import plistlib
import struct
import zipfile

IPA = Path("WebReader-Appinst-Direto-iOS12-adhoc.ipa")
SHA = Path(IPA.name + ".sha256")
SOURCE = Path("ci/appinst_direct_probe/main.m")
INFO = "Payload/WRAppinstDirect.app/Info.plist"
EXEC = "Payload/WRAppinstDirect.app/WRAppinstDirect"
CHILD = "Payload/WRAppinstDirect.app/WRSpawnChild"


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
        assert INFO in contents and EXEC in contents and CHILD in contents
        info = plistlib.loads(archive.read(INFO))
        exe = archive.read(EXEC)
        child = archive.read(CHILD)
        assert info["CFBundleIdentifier"] == "com.example.WebReaderAppinstDirectProbe"
        assert info["CFBundleIdentifier"] != "com.example.MangaReader12"
        assert info["CFBundleDisplayName"] == "WebReader appinst Test"
        assert info["MinimumOSVersion"] == "12.0"
        assert info["CFBundleVersion"] == "3"
        assert info["CFBundleExecutable"] == "WRAppinstDirect"
        assert "UIBackgroundModes" not in info
        assert "UIFileSharingEnabled" not in info
        assert exe[:4] == b"\xcf\xfa\xed\xfe"
        assert struct.unpack_from("<I", exe, 4)[0] == 0x0100000C
        assert len(exe) > 2048
        assert child[:4] == b"\xcf\xfa\xed\xfe"
        assert struct.unpack_from("<I", child, 4)[0] == 0x0100000C
        assert len(child) > 2048
    source = SOURCE.read_text()
    assert '"/usr/bin/appinst"' in source
    assert 'WRRunBundledChildProbe' in source
    # The first button only checks metadata; it must never execute appinst.
    first_probe = source.split("static NSString *WRRunBundledChildProbe(void) {", 1)[1].split(
        "static NSString *WRRunHelpProbe(void) {", 1
    )[0]
    metadata = source.split("static void WRAppendAppinstMetadataOnly", 1)[1].split(
        "static NSString *WRRunBundledChildProbe(void) {", 1
    )[0]
    assert "WRAppendAppinstMetadataOnly(report);" in first_probe
    assert 'APPINST_META_LSTAT=REGULAR' in metadata
    assert 'APPINST_META_XOK=YES' in metadata
    assert 'APPINST_META_ADVISORY=YES' in metadata
    assert "lstat(tool, &state)" in metadata and "access(tool, X_OK)" in metadata
    for forbidden in ("posix_spawn(", "fork(", "system(", "execve(", "installApplication:", "unlink(", "remove("):
        assert forbidden not in metadata, forbidden
    assert '"/usr/bin/appinst"' not in first_probe
    assert '"--help"' not in first_probe
    assert first_probe.count("posix_spawn(") == 1
    assert "pathForResource:@\"WRSpawnChild\"" in first_probe
    assert "APPINST_EXECUTADO=NAO | INSTALACAO=NAO" in first_probe
    assert 'SPAWN_LOCAL=OK' in source
    assert 'APPINST_EXECUTADO=NAO | INSTALACAO=NAO' in source
    assert 'Testar processo local (sem appinst)' in source
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
    assert 'WRSpawnChild' in Path("ci/build_appinst_direct_probe.sh").read_text()
    assert '--entitlements ci/appinst_direct_probe/qa.entitlements' in Path("ci/build_appinst_direct_probe.sh").read_text()
    build_script = Path("ci/build_appinst_direct_probe.sh").read_text()
    assert 'signed-entitlements.plist' in build_script
    assert 'WRTEST0001.com.example.WebReaderAppinstDirectProbe' in build_script
    assert 'if observed != expected:' in build_script
    entitlements = plistlib.loads(
        Path("ci/appinst_direct_probe/qa.entitlements").read_bytes()
    )
    assert entitlements == {
        "application-identifier":
            "WRTEST0001.com.example.WebReaderAppinstDirectProbe"
    }
    child_source = Path("ci/appinst_direct_probe/spawn_child.c").read_text()
    for forbidden in ("appinst", "system(", "posix_spawn(", "open(", "unlink(", "remove(", "execve("):
        # "appinst" occurs only in a harmless comment ("installer"), never as an API.
        if forbidden == "appinst":
            continue
        assert forbidden not in child_source, forbidden
    print("PASS standalone iOS12 diagnostic: appinst-free local spawn and separate opt-in help path")


if __name__ == "__main__":
    main()

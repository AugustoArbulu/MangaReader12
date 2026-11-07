#!/usr/bin/env python3
"""Offline identity and isolation checks for the iOS12 IPC diagnostic IPA.

Runs on the CI-built IPA only. Never signs, installs, publishes, or executes it.
"""
import argparse
import hashlib
import plistlib
from pathlib import Path
import zipfile

PLIST = "Payload/MangaReader12.app/Info.plist"
EXEC = "Payload/MangaReader12.app/MangaReader12"


class DiagnosticIPARejected(ValueError):
    pass


def identity(path):
    if not path.is_file():
        raise DiagnosticIPARejected("missing IPA")
    with zipfile.ZipFile(path) as z:
        plist = plistlib.loads(z.read(PLIST))
        names = set(z.namelist())
        if EXEC not in names:
            raise DiagnosticIPARejected("app executable missing")
        executable_digest = hashlib.sha256(z.read(EXEC)).hexdigest()
        return plist, executable_digest, names


def check(base_path, tls_path, ipc_path):
    stable, stable_bin, stable_names = identity(base_path)
    tls, tls_bin, tls_names = identity(tls_path)
    ipc, ipc_bin, ipc_names = identity(ipc_path)
    ids = {
        stable.get("CFBundleIdentifier"),
        tls.get("CFBundleIdentifier"),
        ipc.get("CFBundleIdentifier"),
    }
    if ids != {
        "com.example.MangaReader12",
        "com.example.MangaReader12.httpsprobe",
        "com.example.MangaReader12.ipcprobe",
    }:
        raise DiagnosticIPARejected("diagnostic Bundle ID collision/identity mismatch")
    if len(ids) != 3:
        raise DiagnosticIPARejected("diagnostic apps are not isolated")
    for plist in [tls, ipc]:
        if (plist.get("CFBundleExecutable") != stable.get("CFBundleExecutable") or
            plist.get("CFBundleVersion") != stable.get("CFBundleVersion") or
            plist.get("CFBundleVersion") != "56" or
            plist.get("MinimumOSVersion") != "12.0"):
            raise DiagnosticIPARejected("unexpected app executable, version or minimum iOS")
    if (stable.get("CFBundleDisplayName") != "WebReader" or
        tls.get("CFBundleDisplayName") != "WebReader TLS Test" or
        ipc.get("CFBundleDisplayName") != "WebReader IPC Test"):
        raise DiagnosticIPARejected("incorrect diagnostic display names")
    if ipc.get("UIBackgroundModes") is not None:
        raise DiagnosticIPARejected("IPC diagnostic must not request background execution")
    if stable_bin != ipc_bin or stable_bin != tls_bin:
        raise DiagnosticIPARejected("diagnostic apps changed the WebReader executable")
    if stable_names != ipc_names or stable_names != tls_names:
        raise DiagnosticIPARejected("diagnostic app contains injected/missing files")
    if any("WebReader-Helper-Ping-iOS12" in x for x in ipc_names):
        raise DiagnosticIPARejected("helper binary unexpectedly bundled with IPA")
    print("PASS: isolated IPC/TLS diagnostics; stable WebReader app unchanged")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stable", type=Path)
    parser.add_argument("tls", type=Path)
    parser.add_argument("ipc", type=Path)
    args = parser.parse_args()
    check(args.stable, args.tls, args.ipc)


if __name__ == "__main__":
    main()

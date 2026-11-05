#!/usr/bin/env python3
"""Verify the separately installable, unsigned WebReader iOS12 TLS test IPA.

Ensures the CI app cannot be interpreted as an update to the real user app.
This does not sign, install, execute or publish an IPA.
"""
import argparse
from pathlib import Path
import plistlib
import zipfile

def verify(production_ipa: Path, probe_ipa: Path) -> None:
    def get(ipa):
        with zipfile.ZipFile(ipa, "r") as z:
            path = "Payload/MangaReader12.app/Info.plist"
            return plistlib.loads(z.read(path))
    stable = get(production_ipa)
    probe = get(probe_ipa)
    assert stable["CFBundleIdentifier"] == "com.example.MangaReader12"
    assert probe["CFBundleIdentifier"] == "com.example.MangaReader12.httpsprobe"
    assert probe["CFBundleIdentifier"] != stable["CFBundleIdentifier"]
    assert probe["CFBundleExecutable"] == stable["CFBundleExecutable"]
    assert probe["CFBundleVersion"] == stable["CFBundleVersion"] == "56"
    assert probe["MinimumOSVersion"] == stable["MinimumOSVersion"] == "12.0"
    assert probe["CFBundleDisplayName"] == "WebReader TLS Test"
    assert stable["CFBundleDisplayName"] == "WebReader"
    print("PASS separate TLS diagnostic identity; original production IPA unchanged")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("production_ipa", type=Path)
    ap.add_argument("probe_ipa", type=Path)
    args = ap.parse_args()
    verify(args.production_ipa, args.probe_ipa)

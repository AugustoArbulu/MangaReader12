#!/usr/bin/env python3
"""Build 54: verify public WebReader branding and preservation of app identity.

CI runs this before Xcode and ci/verify_binary.sh checks compiled Info.plist.
"""
from pathlib import Path
import plistlib
import re

ROOT = Path(__file__).resolve().parent.parent
info = plistlib.loads((ROOT / "MangaReader12/Info.plist").read_bytes())
project = (ROOT / "MangaReader12.xcodeproj/project.pbxproj").read_text()
ui = (ROOT / "MangaReader12/UI/MainTabBarController.swift").read_text()
packager = (ROOT / "ci/package_ipa.sh").read_text()
workflow = (ROOT / ".github/workflows/build.yml").read_text()
verifier = (ROOT / "ci/verify_binary.sh").read_text()

assert info["CFBundleDisplayName"] == "WebReader"
assert info["CFBundleName"] == "WebReader"
assert info["CFBundleExecutable"] == "$(EXECUTABLE_NAME)"
assert info["CFBundleIdentifier"] == "$(PRODUCT_BUNDLE_IDENTIFIER)"
assert info["CFBundleVersion"] == "$(CURRENT_PROJECT_VERSION)"
assert project.count("PRODUCT_BUNDLE_IDENTIFIER = com.example.MangaReader12;") == 2
assert project.count('PRODUCT_NAME = "$(TARGET_NAME)";') == 2
assert project.count("CURRENT_PROJECT_VERSION = 54;") == 2
assert 'cell.textLabel?.text = "WebReader"' in ui
assert '"Build 54 • compatível com iOS 12.0"' in ui
assert 'title: "Repositório demo do WebReader"' in ui
assert "WebReader-iOS12-unsigned.ipa" in workflow
assert "WebReader-unsigned.ipa" in packager
assert "Print :CFBundleDisplayName" in verifier
assert "Print :CFBundleIdentifier" in verifier
assert "Print :CFBundleExecutable" in verifier
assert 'BIN="$APP_PATH/MangaReader12"' in verifier
assert len(re.findall(r"IPHONEOS_DEPLOYMENT_TARGET = 12\.0;", project)) >= 2
print("PASS Build54: WebReader display brand and legacy bundle identity.")

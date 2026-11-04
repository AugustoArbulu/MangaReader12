#!/usr/bin/env python3
"""Offline checks for the approved WebReader app icon on iOS12."""
from pathlib import Path
import json
import struct

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "MangaReader12/Assets.xcassets"
APPICON = ASSETS / "AppIcon.appiconset"
manifest = json.loads((APPICON / "Contents.json").read_text())
project = (ROOT / "MangaReader12.xcodeproj/project.pbxproj").read_text()
workflow = (ROOT / ".github/workflows/build.yml").read_text()
assert len(manifest["images"]) >= 18
assert project.count("ASSETCATALOG_COMPILER_APPICON_NAME = AppIcon;") == 2
assert "Assets.xcassets in Resources" in project
assert "python3 ci/prepare_webreader_icons.py" in workflow
assert "python3 ci/test_build54_icon.py" in workflow
required = {20,29,40,58,60,76,80,87,120,152,167,180,1024}
found = set()
for icon in manifest["images"]:
    size = float(icon["size"].split("x")[0])
    multiplier = int(icon["scale"].removesuffix("x"))
    pixels = round(size * multiplier)
    assert (pixels, pixels) == (size * multiplier, size * multiplier)
    asset = APPICON / icon["filename"]
    assert asset.name == f"icon-{pixels}.png"
    img = asset.read_bytes()
    assert img[:8] == b"\x89PNG\r\n\x1a\n"
    assert tuple(struct.unpack(">II", img[16:24])) == (pixels, pixels)
    found.add(pixels)
assert found == required, (found, required)
assert any(x["idiom"] == "ios-marketing" and x["size"] == "1024x1024"
           for x in manifest["images"])
assert any(x["idiom"] == "iphone" for x in manifest["images"])
assert any(x["idiom"] == "ipad" for x in manifest["images"])
assert "CFBundleIcons" in (ROOT / "ci/verify_binary.sh").read_text()
print("PASS Build54: approved AppIcon PNGs for iPhone, iPad and marketing.")

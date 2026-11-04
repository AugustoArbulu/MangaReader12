#!/usr/bin/env python3
"""Build55: verify original Keiyoushi icon bytes and UI mappings (offline)."""
from pathlib import Path
import hashlib
import json
import struct
import re

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "MangaReader12/Assets.xcassets"
UI = (ROOT / "MangaReader12/UI/MangaArtwork.swift").read_text()
TABS = (ROOT / "MangaReader12/UI/MainTabBarController.swift").read_text()
PROJECT = (ROOT / "MangaReader12.xcodeproj/project.pbxproj").read_text()
EXPECTED = [{"id":"kei.asurascans.en","asset":"KeiAsuraScans","sha":"a38ffbc68c48079c97ffca069d9e3ff18290af5e"},{"id":"kei.weebcentral.en","asset":"KeiWeebCentral","sha":"8cc011d9a951a4c7199a3f17eff8880ff9a1f5e2"},{"id":"kei.webtoons.en","asset":"KeiWebtoons","sha":"957cbe99b67ac7318ccaa0485d67e3c0655528f7"},{"id":"kei.hotcomics","asset":"KeiHotComics","sha":"0549a3a8f580ef32e8cb7831b3fc6eecbfd2ea7a"},{"id":"kei.comix","asset":"KeiComix","sha":"c25865fac427afbea1e2bcd39e3c064d15470a20"},{"id":"kei.vortexscans","asset":"KeiVortexScans","sha":"8f646462eb87992378ae423a7a5d755f7bdca5c7"},{"id":"kei.toongod","asset":"KeiToonGod","sha":"7c788a87596d26cf61677dc9d2bee8b89f06d608"},{"id":"kei.madaradex","asset":"KeiMadaraDex","sha":"d77ac49d0d51b430f20f8416315b676615204545"},{"id":"org.mangareader12.mangadex","asset":"KeiMangaDex","sha":"ab5b8b0e8f455580375711d7a01024fa59e254ff"}]

versions = re.findall(r"CURRENT_PROJECT_VERSION = (\d+);", PROJECT)
assert len(versions) == 2 and versions[0] == versions[1] and int(versions[0]) >= 55
assert "Assets.xcassets in Resources" in PROJECT
assert "ASSETCATALOG_COMPILER_APPICON_NAME = AppIcon" in PROJECT
assert f'"Build {versions[0]} • compatível com iOS 12.0"' in TABS
assert "sourceID: source.manifest.id" in TABS
assert "sourceID: manifest.id" in TABS
assert 'KeiyoushiSourceIconAssets.image(for: sourceID)' in UI
assert "UIImage(named: asset)" in UI
assert "self.representedSourceID == sourceID" in UI
assert "CoverImageLoader.shared.load(" in UI
assert '"kei.manhwa18net":' not in UI

for item in EXPECTED:
    directory = ASSETS / (item["asset"] + ".imageset")
    manifest = json.loads((directory / "Contents.json").read_text())
    images = manifest["images"]
    assert len(images) == 1
    assert images[0]["idiom"] == "universal"
    assert images[0]["filename"] == "icon.png"
    data = (directory / "icon.png").read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    width, height = struct.unpack(">II", data[16:24])
    assert 48 <= width <= 2048 and 48 <= height <= 2048
    sha = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
    assert sha == item["sha"], (item["id"], sha, item["sha"])
    assert f'"{item["id"]}": "{item["asset"]}"' in UI
print("PASS Build55: official local Keiyoushi icons and ID-based UIKit routing.")

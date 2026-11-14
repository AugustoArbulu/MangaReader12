#!/usr/bin/env python3
"""Webtoon landscape width: Swift preference math + reader layout guardrails.

No reading-library access, no live requests, and no device installation.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
PREF = ROOT / "MangaReader12/UI/ReaderPreferences.swift"
READER = ROOT / "MangaReader12/UI/ReaderViewController.swift"
SETTINGS = ROOT / "MangaReader12/UI/ReaderSettingsViewController.swift"


class WebtoonLandscapeWidthTests(unittest.TestCase):
    def test_preferences_are_separate_from_paged_scale(self):
        src = PREF.read_text(encoding="utf-8")
        self.assertIn('private let webtoonWidthKey = "reader.webtoon.widthMode"', src)
        self.assertIn('private let scaleModeKey = "reader.scaleMode"', src)
        self.assertIn('var webtoonWidth: ReaderWebtoonWidth', src)
        self.assertIn('ReaderWebtoonWidth(rawValue: defaults.integer(forKey: webtoonWidthKey))', src)
        self.assertIn('?? .adaptive', src)

    def test_webtoon_images_and_cells_share_width_fraction(self):
        source = READER.read_text(encoding="utf-8")
        checks = (
            'zoomScrollView.isScrollEnabled = !webtoonMode',
            'webtoonWidthFraction: effectiveWebtoonWidthFraction()',
            'factor = horizontal * (isWebtoon ? webtoonWidthFraction : 1)',
            '(viewport.width - scaledSize.width) / 2',
            'zoomScrollView.contentInset = .zero',
            'let artWidth = width * effectiveWebtoonWidthFraction()',
            'CGSize(width: width, height: max(1, artWidth * ratio))',
            'let anchor = captureWebtoonPosition()',
            'restoreWebtoonPosition(anchor)',
            'override func viewWillTransition(',
            'self?.restoreWebtoonPosition(readingAnchor)',
            'preferences.webtoonWidth = mode',
            'imageLoaded(image)',
        )
        for text in checks:
            with self.subTest(expression=text):
                self.assertIn(text, source)
        # No special Webtoon reread or progress write on width adjustment.
        change = source.split('private func changeWebtoonWidth(', 1)[1].split(
            '\n    private func showScaleComparison()', 1
        )[0]
        for text in ("imageLoader.load", "collectionView.reloadData()",
                     "persistProgress(", "readerImageCache", "delete", "removeItem"):
            self.assertNotIn(text, change)
        self.assertIn('trimMargins: displayMode == .pages && preferences.trimMargins',
                      source)

    def test_settings_and_in_reader_controls(self):
        src = SETTINGS.read_text(encoding="utf-8")
        reader = READER.read_text(encoding="utf-8")
        self.assertIn('case (3, 0):\n            cell.textLabel?.text = "Largura do Webtoon"', src)
        self.assertIn('case (3, 0):\n            showWebtoonWidthPicker()', src)
        self.assertIn('case .adaptive', PREF.read_text(encoding="utf-8"))
        self.assertIn('title: "Largura Webtoon:', reader)
        self.assertIn('title: "Largura do Webtoon"', reader)
        self.assertIn('title: "Largura do Webtoon"', src)

    def test_swift_fraction_modes_and_persistence_runtime(self):
        compiler = shutil.which("swiftc")
        if not compiler:
            self.skipTest("swiftc absent: macOS native iOS12 build still mandatory")
        with tempfile.TemporaryDirectory(prefix="wr-webtoon-landscape-test-") as temp:
            root = Path(temp)
            (root / "ModeStub.swift").write_text(
                'import Foundation\n'
                'enum ReaderDisplayMode: Int { case pages = 0; case webtoon = 1 }\n',
                encoding="utf-8"
            )
            (root / "main.swift").write_text(
                'import Foundation\n'
                'let suite = "wr-webtoon-" + UUID().uuidString\n'
                'guard let storage = UserDefaults(suiteName: suite) else { fatalError("defaults") }\n'
                'defer { storage.removePersistentDomain(forName: suite) }\n'
                'let prefs = ReaderPreferences(defaults: storage)\n'
                'func approx(_ observed: CGFloat, _ expected: CGFloat) {\n'
                '  precondition(abs(observed - expected) < 0.0001, "width fraction mismatch")\n'
                '}\n'
                'let portrait = CGSize(width: 768, height: 1024)\n'
                'let landscape = CGSize(width: 1024, height: 768)\n'
                'precondition(prefs.webtoonWidth == .adaptive)\n'
                'approx(prefs.webtoonWidth.fraction(for: portrait), 1.0)\n'
                'approx(prefs.webtoonWidth.fraction(for: landscape), 0.75)\n'
                'for (mode, frac) in [\n'
                '  (ReaderWebtoonWidth.full, CGFloat(1.0)),\n'
                '  (.wide, CGFloat(0.85)),\n'
                '  (.comfortable, CGFloat(0.75)),\n'
                '  (.narrow, CGFloat(0.60))] {\n'
                '  approx(mode.fraction(for: portrait), frac)\n'
                '  approx(mode.fraction(for: landscape), frac)\n'
                '  prefs.webtoonWidth = mode\n'
                '  precondition(prefs.webtoonWidth == mode)\n'
                '}\n'
                'storage.set(999, forKey: "reader.webtoon.widthMode")\n'
                'precondition(prefs.webtoonWidth == .adaptive)\n'
                'prefs.scaleMode = .fitHeight\n'
                'prefs.webtoonWidth = .wide\n'
                'precondition(prefs.scaleMode == .fitHeight)\n'
                'precondition(prefs.webtoonWidth == .wide)\n'
                'print("PASS adaptive Webtoon 100% portrait / 75% landscape and manual widths")\n',
                encoding="utf-8"
            )
            binary = root / "run"
            subprocess.run(
                [compiler, str(PREF), str(root / "ModeStub.swift"),
                 str(root / "main.swift"), "-o", str(binary)],
                check=True, capture_output=True, timeout=70
            )
            result = subprocess.run(
                [str(binary)], check=True, capture_output=True,
                text=True, timeout=15
            )
            self.assertIn("PASS adaptive Webtoon", result.stdout)


if __name__ == "__main__":
    unittest.main()

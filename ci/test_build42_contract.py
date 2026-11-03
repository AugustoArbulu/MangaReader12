#!/usr/bin/env python3
"""Build42 native source contracts. ZIP parsing is independently executed by
test_safe_cbz.py, not merely string-matched here.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
def src(path): return (ROOT / path).read_text(encoding="utf8")


class Contracts(unittest.TestCase):
    def test_ios12_file_picker_and_atomic_storage(self):
        s = src("MangaReader12/UI/LocalComicsViewController.swift")
        self.assertIn("UIDocumentPickerViewController(", s)
        self.assertIn('in: .import', s)
        self.assertIn('["cbz", "zip"].contains(url.pathExtension.lowercased())', s)
        self.assertIn("DispatchQueue.global(qos: .utility).async", s)
        self.assertIn('".import-" + id', s)
        self.assertIn("try manager.moveItem(at: staging, to: final)", s)
        self.assertIn("defer { try? manager.removeItem(at: staging) }", s)
        self.assertIn("try SafeCBZArchive.extract(", s)
        self.assertIn("func documentPicker(", s)
        self.assertIn("didPickDocumentsAt urls: [URL]", s)
        self.assertIn("func remove(_ comic: LocalComic) throws", s)
        self.assertIn('sourceID: "local.cbz"', s)
        self.assertIn("ReaderViewController(", s)
        self.assertIn("LocalComicsViewController: ThemeApplicable", s)

    def test_no_remote_source_data_mutation(self):
        s = src("MangaReader12/UI/LibraryViewController.swift")
        h = src("MangaReader12/UI/HistoryViewController.swift")
        self.assertIn("LocalComicsViewController()", s)
        self.assertIn("private func localComicsTapped()", s)
        self.assertIn('if record.sourceID == "local.cbz"', h)
        self.assertIn("LocalComicStore.open(comic, from: navigationController)", h)
        self.assertIn("showMessage(", h)
        local = src("MangaReader12/UI/LocalComicsViewController.swift")
        self.assertNotIn("runtime.callDecoded(", local)
        self.assertNotIn("manager.install", local)
        self.assertNotIn("URLSession", local)
        self.assertIn('domains: ["localhost.invalid"]', local)
        self.assertIn("allSatisfy({ Self.isSafePageName($0) })", local)

    def test_reader_crop_is_opt_in_and_image_files_unchanged(self):
        p = src("MangaReader12/UI/ReaderPreferences.swift")
        r = src("MangaReader12/UI/ReaderViewController.swift")
        settings = src("MangaReader12/UI/ReaderSettingsViewController.swift")
        self.assertIn('private let trimMarginsKey = "reader.trimMargins"', p)
        self.assertIn("defaultValue: false", p)
        self.assertIn('title: "Recortar bordas (3%)"', settings)
        self.assertIn("private func transformedImage() -> UIImage?", r)
        self.assertIn("cg.cropping(to: rect)", r)
        self.assertIn("trimMargins: displayMode == .pages && preferences.trimMargins", r)
        self.assertIn("imageLoaded(image)", r)
        self.assertNotIn("image.write", r)
        self.assertIn("private let maxConcurrentTransfers = 3", r)

    def test_zip_hardening_has_concrete_checks(self):
        z = src("MangaReader12/Core/SafeCBZArchive.swift")
        for term in [
            "maxArchiveBytes", "maxIndexBytes", "maxEntries",
            "maxImageBytes", "maxTotalBytes", "maxImagePixels",
            "crc32(output) == entry.crc32",
            "path.hasPrefix(\"/\")",
            "localName == entry.nameBytes",
            "unixType != 0xA000",
            "UInt64(entry.compressedSize) <= indexOffset - dataOffset",
            "COMPRESSION_ZLIB",
            "volumeAvailableCapacityKey",
            "seen.insert(unique).inserted",
        ]:
            self.assertIn(term, z, term)
        xcode = src("MangaReader12.xcodeproj/project.pbxproj")
        self.assertIn("SafeCBZArchive.swift in Sources", xcode)
        self.assertIn("LocalComicsViewController.swift in Sources", xcode)

if __name__ == "__main__":
    unittest.main(verbosity=2)

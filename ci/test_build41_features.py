#!/usr/bin/env python3
"""Offline regression checks for the Build41 reader/library changes.

This is a structural contract test, not an iPhone UI test.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent

def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


class Build41ReaderLibraryTests(unittest.TestCase):
    def test_pager_remains_local_and_accessible(self):
        source = read("MangaReader12/UI/ReaderViewController.swift")
        self.assertIn("private let pageNavigationSlider = UISlider()", source)
        self.assertIn("private func configurePageNavigation()", source)
        self.assertIn('pageNavigationSlider.accessibilityLabel = "Ir para página"', source)
        self.assertIn("private func updatePageNavigation()", source)
        self.assertIn("pageNavigationView.isHidden = controlsHidden", source)
        self.assertIn("pageNavigationView.frame.contains(location)", source)
        self.assertIn("private func changeChapter(to newChapter: Chapter)", source)
        self.assertIn("adjacentChapter(forward: false)", source)
        self.assertIn("adjacentChapter(forward: true)", source)
        self.assertIn("persistProgress(index: index)", source)
        self.assertIn("zoomScrollView.zoom(to: rect, animated: true)", source)
        self.assertIn("memoryCache.totalCostLimit = 48 * 1024 * 1024", source)
        self.assertIn("private let maxConcurrentTransfers = 3", source)

    def test_history_uses_exact_saved_chapter(self):
        details = read("MangaReader12/UI/SourceBrowserViewController.swift")
        history = read("MangaReader12/UI/HistoryViewController.swift")
        self.assertIn("private let resumeChapterID: String?", details)
        self.assertIn("resumeChapterID: String? = nil", details)
        self.assertIn("chapters.first(where: { $0.id == chapterID })", details)
        self.assertIn("attemptedResume = true", details)
        self.assertIn("loadPages(for: chapter)", details)
        self.assertIn("HistoryViewController: UITableViewController", history)
        self.assertIn("init(resumeLatest: Bool = false)", history)
        self.assertIn("records.first(where: { $0.sourceChapterID != nil })", history)
        self.assertIn("resumeChapterID: resumeLatestOnOpen", history)

    def test_grid_is_opt_in_with_list_fallback(self):
        library = read("MangaReader12/UI/LibraryViewController.swift")
        artwork = read("MangaReader12/UI/MangaArtwork.swift")
        self.assertIn('title: "Grade"', library)
        self.assertIn("private func showGrid()", library)
        self.assertIn('forKey: "library.layout"', library)
        self.assertIn("class LibraryGridViewController:", library)
        self.assertIn("class LibraryGridCoverCell: UICollectionViewCell", library)
        self.assertIn("CoverImageLoader.shared.load(", library)
        self.assertIn("self?.open(record: record)", library)
        self.assertIn("return (self.records, self.metrics)", library)
        self.assertIn('title: "Lista"', library)
        self.assertIn("if isMovingFromParent", library)
        self.assertIn("func applyLocalFilters()", library)
        self.assertIn("func reloadLibrary()", library)
        self.assertIn("countLimit = 120", artwork)
        self.assertIn("totalCostLimit = 24 * 1024 * 1024", artwork)

    def test_continue_reading_uses_saved_history(self):
        source = read("MangaReader12/UI/LibraryViewController.swift")
        self.assertIn("ReadingProgressRepository.defaultRepository()", source)
        self.assertIn("history.first(where: { $0.sourceChapterID != nil })", source)
        self.assertIn('action.setTitle("▶ Continuar lendo', source)
        self.assertIn("HistoryViewController(resumeLatest: true)", source)
        self.assertIn("tableView.tableHeaderView = header", source)


if __name__ == "__main__":
    unittest.main()

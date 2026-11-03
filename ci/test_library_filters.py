#!/usr/bin/env python3
"""Build40 SQLite contract and UIKit wiring tests; no remote source requests.

The SQL is extracted from LibraryRepository.readingMetrics() rather than
retyped, then executed against a small representative in-memory database.
"""
import pathlib
import re
import sqlite3
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
DB_SWIFT = (ROOT / "MangaReader12/Database/SQLiteDatabase.swift").read_text()
UI_SWIFT = (ROOT / "MangaReader12/UI/LibraryViewController.swift").read_text()


class LibraryFilterTests(unittest.TestCase):
    def test_metrics_are_derived_from_local_database(self):
        match = re.search(
            r'func readingMetrics\(\) throws -> \[Int64: LibraryMangaMetrics\]'
            r'.*?let statement = try prepareStatement\(\s*"""(.*?)"""',
            DB_SWIFT, re.S
        )
        self.assertIsNotNone(match, "Manga metrics SQL query not found")
        query = match.group(1)
        self.assertIn("FROM library l", query)
        self.assertIn("GROUP BY m.internal_id", query)
        self.assertIn("d.state = 'completed'", query)
        self.assertIn("LEFT JOIN history", query)
        with sqlite3.connect(":memory:") as db:
            db.executescript("""
                CREATE TABLE manga(internal_id INTEGER PRIMARY KEY, title TEXT);
                CREATE TABLE library(manga_id INTEGER PRIMARY KEY);
                CREATE TABLE chapters(internal_id INTEGER PRIMARY KEY,
                    manga_id INTEGER NOT NULL, is_read INTEGER NOT NULL);
                CREATE TABLE history(manga_id INTEGER PRIMARY KEY,
                    last_read_at REAL NOT NULL);
                CREATE TABLE downloads(chapter_id INTEGER, state TEXT);
                INSERT INTO manga VALUES (1,'A'),(2,'B'),(3,'C');
                INSERT INTO library VALUES (1),(2),(3);
                INSERT INTO chapters VALUES
                    (10,1,0),(11,1,1),(12,1,0),(30,3,1);
                INSERT INTO history VALUES (1,123.5),(3,33);
                INSERT INTO downloads VALUES
                    (10,'completed'),(11,'completed'),(30,'queued');
            """)
            rows = {row[0]: row[1:] for row in db.execute(query).fetchall()}
        self.assertEqual(rows[1], (3,2,123.5,1))
        self.assertEqual(rows[2], (0,0,None,0))
        self.assertEqual(rows[3], (1,0,33.0,0))

    def test_filter_and_sort_are_offline_and_keep_category_support(self):
        self.assertIn("private func applyLocalFilters()", UI_SWIFT)
        self.assertIn("func updateSearchResults(for searchController: UISearchController)", UI_SWIFT)
        self.assertIn("record.title.range(", UI_SWIFT)
        self.assertIn('case "title-az":', UI_SWIFT)
        self.assertIn('case "title-za":', UI_SWIFT)
        self.assertIn('case "last-read":', UI_SWIFT)
        self.assertIn('case "unread":', UI_SWIFT)
        self.assertIn('statusKey != "all"', UI_SWIFT)
        self.assertIn('if onlyUnread && (entry?.unreadChapters ?? 0) == 0', UI_SWIFT)
        self.assertIn('if onlyDownloaded && !(entry?.hasCompletedDownload ?? false)', UI_SWIFT)
        self.assertIn('records = allRecords.filter', UI_SWIFT)
        self.assertIn("repository.list(categoryID: category)", UI_SWIFT)
        self.assertIn("categoryRepository?.list()", UI_SWIFT)
        self.assertIn("CategoryAssignmentViewController(", UI_SWIFT)
        self.assertIn("repository.remove(", UI_SWIFT)
        self.assertIn("private func open(record: LibraryMangaRecord)", UI_SWIFT)

    def test_ui_uses_ios12_sheet_and_persistent_settings(self):
        self.assertIn("class LibraryFilterSheetViewController: UIViewController", UI_SWIFT)
        self.assertIn("controller.modalPresentationStyle = .overFullScreen", UI_SWIFT)
        self.assertNotIn("Filtrar Biblioteca", UI_SWIFT,
                         "Old actionSheet replaced by modern library filter sheet")
        self.assertIn("panel.heightAnchor.constraint(equalTo: view.heightAnchor", UI_SWIFT)
        self.assertIn("scroll.alwaysBounceVertical = true", UI_SWIFT)
        self.assertIn('forKey: "library.categoryID"', UI_SWIFT)
        self.assertIn('forKey: "library.sort"', UI_SWIFT)
        self.assertIn('forKey: "library.status"', UI_SWIFT)
        self.assertIn('forKey: "library.onlyUnread"', UI_SWIFT)
        self.assertIn('forKey: "library.onlyDownloaded"', UI_SWIFT)
        self.assertIn("ThemeManager.shared.palette", UI_SWIFT)
        self.assertIn("não lidos considera", UI_SWIFT.lower())
        self.assertIn("if left.dateAdded != right.dateAdded", UI_SWIFT)
        # No reliance on network or source functions to calculate filters.
        block = UI_SWIFT.split("private func applyLocalFilters()")[1].split(
            "private func updateFilterPresentation()")[0]
        self.assertNotIn("runtime.callDecoded", block)
        self.assertNotIn("HTTPClient", block)


if __name__ == "__main__":
    unittest.main()

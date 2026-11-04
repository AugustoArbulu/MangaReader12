#!/usr/bin/env python3
"""Build56: execute real Swift UpdateFeedStore and LibrarySourceLabels offline.

Checks old feed compatibility, acknowledgement persistence, collision-safe
source identities, non-destructive 'viewed' semantics, and UIKit wiring.
No requests to third-party sites or modification of a device's database.
"""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
updates = (ROOT / "MangaReader12/Library/LibraryUpdateManager.swift").read_text()
library = (ROOT / "MangaReader12/UI/LibraryViewController.swift").read_text()
reader = (ROOT / "MangaReader12/UI/SourceBrowserViewController.swift").read_text()
feed_ui = (ROOT / "MangaReader12/UI/UpdatesViewController.swift").read_text()
art = (ROOT / "MangaReader12/UI/MangaArtwork.swift").read_text()
project = (ROOT / "MangaReader12.xcodeproj/project.pbxproj").read_text()

assert project.count("CURRENT_PROJECT_VERSION = 56;") == 2
assert updates.count("struct LibraryUpdateEvent: Codable, Equatable {") == 1
assert updates.count("final class UpdateFeedStore {") == 1
assert updates.count("final class LibraryUpdateManager {") == 1
assert library.count("// BEGIN BUILD56_SOURCE_ATTRIBUTION") == 1
assert library.count("// END BUILD56_SOURCE_ATTRIBUTION") == 1
store = updates.split("struct LibraryUpdateEvent: Codable, Equatable {", 1)[1].split(
    "final class LibraryUpdateManager {", 1
)[0]
store = "struct LibraryUpdateEvent: Codable, Equatable {" + store
labels = library.split("// BEGIN BUILD56_SOURCE_ATTRIBUTION", 1)[1].split(
    "// END BUILD56_SOURCE_ATTRIBUTION", 1
)[0]
assert "sourceID: record.sourceID" in library
assert '"Fonte: " + sourceName' in library
assert "sourceIcon.image = KeiyoushiSourceIconAssets.image(for: record.sourceID)" in library
assert "sourceName: sourceRecord.manifest.name" in reader
assert "sourceID: sourceRecord.manifest.id" in reader
assert "KeiyoushiSourceIconAssets.image(for: sourceID)" in art
assert "sourceIconView.isHidden" in art
assert 'UISegmentedControl(items: ["Novas", "Todas"])' in feed_ui
assert "feedStore.pendingEvents()" in feed_ui
assert "feedStore.acknowledgeAll()" in feed_ui
assert "feedStore.acknowledge(event)" in feed_ui
assert "sourceID: event.sourceID" in feed_ui
assert "LibrarySourceLabels.displayName(" in feed_ui

runner = r'''
import Foundation
func expect(_ value: Bool, _ label: String) {
    if !value { fatalError(label) }
}
let suite = "webreader-build56-feed-offline"
let defaults = UserDefaults(suiteName: suite)!
defaults.removePersistentDomain(forName: suite)
func event(_ source: String, _ manga: String, _ chapter: String) -> LibraryUpdateEvent {
    return LibraryUpdateEvent(
        sourceID: source, sourceMangaID: manga,
        mangaTitle: "Same Manga", mangaCover: nil, mangaURL: nil,
        sourceChapterID: chapter, chapterName: "Chapter " + chapter,
        discoveredAt: 1800000000
    )
}
let a = event("kei.asurascans.en", "manga-001", "chapter-1")
let b = event("kei.weebcentral.en", "manga-001", "chapter-1")
let c = event("kei.asurascans.en", "manga-001", "chapter-2")
let store = UpdateFeedStore(defaults: defaults)
expect(store.events().isEmpty, "fresh feed")
store.append([a, b, a])
expect(store.events().count == 2, "dedup and two sources")
expect(store.pendingEvents().count == 2, "both discoveries new")
store.acknowledge(a)
expect(store.events().count == 2, "acknowledge never deletes history")
expect(store.pendingEvents() == [b], "only unrelated source remains new")
let reopened = UpdateFeedStore(defaults: defaults)
expect(reopened.isAcknowledged(a), "acknowledgement persisted across store instances")
expect(!reopened.isAcknowledged(b), "other-source identical titles not linked")
reopened.append([c])
expect(reopened.pendingEvents().count == 2, "newly discovered chapter remains new")
reopened.acknowledgeAll()
expect(reopened.pendingEvents().isEmpty, "mark all")
expect(reopened.events().count == 3, "mark all is not destructive")
let first = event("a|b", "c", "d")
let second = event("a", "b|c", "d")
expect(UpdateFeedStore.identity(first) != UpdateFeedStore.identity(second),
       "length delimited IDs prevent old pipe collisions")
expect(LibrarySourceLabels.displayName(
    sourceID: "kei.asurascans.en",
    knownNames: ["kei.asurascans.en": "Asura Scans EN"]) == "Asura Scans EN",
    "exact source ID lookup")
expect(LibrarySourceLabels.displayName(
    sourceID: "kei.weebcentral.en",
    knownNames: ["kei.asurascans.en": "Asura Scans EN"]
).contains("kei.weebcentral.en"), "missing source retains identity")
reopened.clear()
expect(reopened.events().isEmpty && reopened.pendingEvents().isEmpty,
       "explicit clear clears feed and acknowledgements")

// An existing format-v1 feed stays decodable; no new event field is required.
defaults.set(try! JSONEncoder().encode([a]), forKey: "updates.feed.v1")
let legacy = UpdateFeedStore(defaults: defaults)
expect(legacy.events() == [a] && legacy.pendingEvents() == [a],
       "legacy event feed compatibility")
defaults.removePersistentDomain(forName: suite)
print("PASS: Build56 persisted feed and per-title source ID tests")
'''
with tempfile.TemporaryDirectory(prefix="webreader-build56-") as temp:
    src = Path(temp) / "main.swift"
    binary = Path(temp) / "check"
    src.write_text("import Foundation\n" + store + "\n" + labels + "\n" + runner)
    subprocess.run(["swiftc", str(src), "-o", str(binary)], check=True)
    subprocess.run([str(binary)], check=True)

#!/usr/bin/env python3
"""EL: non-destructive default retry policy; synthetic-only Swift host tests."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MANAGER = (ROOT / "MangaReader12/Downloads/ChapterDownloadManager.swift").read_text()
DOWNLOADS = (ROOT / "MangaReader12/UI/DownloadsViewController.swift").read_text()
BROWSER = (ROOT / "MangaReader12/UI/SourceBrowserViewController.swift").read_text()

class SafePartialRetryContract(unittest.TestCase):
    def test_download_defaults_to_preservation(self):
        body = MANAGER.split("    func download(\n", 1)[1].split(
            "    // Returns false for a job left over", 1)[0]
        for required in (
            "existingDataPolicy: ChapterDownloadExistingDataPolicy = .preserve",
            "existingDataPolicy == .replaceAfterExplicitUserConfirmation",
            "throw ChapterDownloadError.existingLocalDataRequiresReview",
            'previous.state == "failed" || previous.state == "paused"',
            "WebReaderPartialRetryFolderAudit.canReplace(",
            "throw ChapterDownloadError.unsafeExistingLocalData",
        ):
            self.assertIn(required, body)
            self.assertLess(body.index(required), body.index("self.savePlan(for: job)"))
        self.assertIn('existing.state == "completed"', body)
        self.assertNotIn("removeItem(at: directory)", body)
        self.assertIn("let existingDirectory = self.fileManager.fileExists(", body)
        self.assertIn("if existingDirectory {", body)
        self.assertIn("} else {\n                    try self.fileManager.createDirectory(", body)
        self.assertLess(body.index("WebReaderPartialRetryFolderAudit.canReplace("),
                        body.index("self.savePlan(for: job)"))
        self.assertIn("manager.download(", BROWSER)
        self.assertNotIn("existingDataPolicy:", BROWSER)

    def test_in_place_retry_does_not_destroy_previous_pages_before_network(self):
        body = MANAGER.split("    func download(\n", 1)[1].split(
            "    // Returns false for a job left over", 1)[0]
        req = MANAGER.split("private func performPageRequest(", 1)[1].split(
            "private func fail(", 1)[0]
        self.assertNotIn("removeItem(at: directory)", body)
        self.assertNotIn("removeItem(at: directory)", req)
        self.assertIn("try response.data.write(to: destination, options: .atomic)", req)
        self.assertIn("ChapterDownloadImageValidator.canStore(", req)
        self.assertLess(req.index("ChapterDownloadImageValidator.canStore("),
                        req.index("try response.data.write(to: destination"))
        self.assertIn("let existingDirectory =", body)
        self.assertIn("if existingDirectory {", body)
        self.assertLess(body.index("if existingDirectory {"),
                        body.index("self.savePlan(for: job)"))

    def test_in_place_retry_never_trusts_legacy_prefix_after_restart(self):
        plan = MANAGER.split("private struct DownloadRecoveryPlan: Codable {", 1)[1].split(
            "// A job keeps", 1)[0]
        restore = MANAGER.split("private func restorePreviousSession()", 1)[1].split(
            "private func jobKey(", 1)[0]
        admission = MANAGER.split("    func download(\n", 1)[1].split(
            "    // Returns false for a job left over", 1)[0]
        save = MANAGER.split("private func savePlan(for job:", 1)[1].split(
            "private func completedPagePrefix(", 1)[0]
        self.assertIn("let requiresFullReplay: Bool?", plan)
        self.assertIn("requiresFullReplay: job.requiresFullReplay ? true : nil", save)
        self.assertIn("requiresFullReplay: existingDirectory,", admission)
        self.assertIn("requiresFullReplay: plan.requiresFullReplay == true,", restore)
        self.assertIn(
            "job.nextIndex = job.requiresFullReplay ? 0 : completedPagePrefix(", restore
        )
        self.assertIn("let requiresFullReplay: Bool", MANAGER)
        self.assertIn("self.requiresFullReplay = requiresFullReplay", MANAGER)

    def test_only_confirmed_downloads_ui_supplies_replacement_policy(self):
        prompt = DOWNLOADS.split("private func retryDownload(", 1)[1].split(
            "private func beginRetryDownload(", 1)[0]
        for required in (
            'title: "Reiniciar este download?"',
            "As imagens não estão incluídas no .mr12backup.",
            "style: .cancel", "style: .destructive",
            "self?.beginRetryDownload(record)",
        ):
            self.assertIn(required, prompt)
        retry = DOWNLOADS.split("private func resolveRetryPages(", 1)[1].split(
            "private func finishRetry(", 1)[0]
        self.assertIn(
            "existingDataPolicy: .replaceAfterExplicitUserConfirmation,", retry
        )
        self.assertEqual(DOWNLOADS.count(
            "existingDataPolicy: .replaceAfterExplicitUserConfirmation"
        ), 1)
        self.assertNotIn("manager.remove(", prompt)

    def test_auditor_rejects_unknown_files_and_symlinks(self):
        source = MANAGER.split("// BEGIN BUILD70_EL_SAFE_PARTIAL_RETRY", 1)[1].split(
            "// END BUILD70_EL_SAFE_PARTIAL_RETRY", 1)[0]
        for required in (
            "Darwin.lstat(directory.path, &before)", "O_DIRECTORY | O_NOFOLLOW",
            "Darwin.fstatat(", "AT_SYMLINK_NOFOLLOW", "item.st_nlink == 1",
            'name == "_download-plan.json"', 'of: "^page-[0-9]{5}\\\\.bin$"',
            "index < plannedPages", "names.count <= plannedPages + 1",
            "sameIdentity(before, afterPath)",
        ):
            self.assertIn(required, source)
        for forbidden in ("removeItem(", "createDirectory(", "URLSession(",
                          "appinst(", "setState(", "write(to:", "contentsOf:"):
            self.assertNotIn(forbidden, source)
        self.assertIn("case .unsafeExistingLocalData:", MANAGER)

    def test_explicit_remove_and_completed_guards_still_exist(self):
        self.assertIn("throw ChapterDownloadError.alreadyCompleted", MANAGER)
        explicit = MANAGER.split("    func remove(\n", 1)[1]
        self.assertIn("fileManager.removeItem(at: current)", explicit)
        self.assertIn("ChapterDownloadError.downloadInProgress", explicit)

    @unittest.skipUnless(sys.platform == "darwin", "native Swift Codable check")
    def test_native_legacy_recovery_plan_decodes_without_full_replay_flag(self):
        # Compile the actual Swift Codable struct, replacing app-only types
        # with tiny synthetic stubs. No filesystem access outside temp data.
        struct = MANAGER.split(
            "private struct DownloadRecoveryPlan: Codable {", 1
        )[1].split("\n}\n\n// A job keeps", 1)[0]
        native = shutil.which("swiftc")
        self.assertIsNotNone(native)
        swift = """
import Foundation
struct Manga: Codable { let id: String }
struct Chapter: Codable { let id: String }
struct Page: Codable { let index: Int }
struct SourceManifest: Codable { let id: String }
private struct DownloadRecoveryPlan: Codable {
""" + struct + """
}

let previous: [String: Any] = [
    "schemaVersion": 1,
    "sourceID": "source",
    "manga": ["id": "manga"],
    "chapter": ["id": "chapter"],
    "pages": [["index": 0]],
    "manifest": ["id": "source"],
    "queueOrder": 1
]
let legacyBytes = try JSONSerialization.data(withJSONObject: previous)
let legacy = try JSONDecoder().decode(DownloadRecoveryPlan.self, from: legacyBytes)
precondition(legacy.requiresFullReplay == nil,
             "legacy plan missing optional field must decode")
let replay = DownloadRecoveryPlan(
    schemaVersion: 1,
    sourceID: "source",
    manga: Manga(id: "manga"),
    chapter: Chapter(id: "chapter"),
    pages: [Page(index: 0)],
    manifest: SourceManifest(id: "source"),
    queueOrder: 1,
    requiresFullReplay: true
)
let replayBytes = try JSONEncoder().encode(replay)
let recovered = try JSONDecoder().decode(DownloadRecoveryPlan.self, from: replayBytes)
precondition(recovered.requiresFullReplay == true, "retry marker lost")
let replayJSON = try JSONSerialization.jsonObject(with: replayBytes) as! [String: Any]
precondition((replayJSON["requiresFullReplay"] as? Bool) == true,
             "retry marker must persist as JSON Boolean")
let normal = DownloadRecoveryPlan(
    schemaVersion: 1,
    sourceID: "source",
    manga: Manga(id: "manga"),
    chapter: Chapter(id: "chapter"),
    pages: [Page(index: 0)],
    manifest: SourceManifest(id: "source"),
    queueOrder: 1,
    requiresFullReplay: nil
)
let normalJSON = try JSONSerialization.jsonObject(
    with: JSONEncoder().encode(normal)) as! [String: Any]
precondition(normalJSON["requiresFullReplay"] == nil,
             "new downloads must omit optional marker")
print("PASS EN native Swift: old plan compatible; forced replay persists")
"""
        with tempfile.TemporaryDirectory(prefix="wr-en-codable-") as directory:
            folder = Path(directory)
            main = folder / "main.swift"
            executable = folder / "codable-check"
            main.write_text(swift, encoding="utf-8")
            compile_result = subprocess.run(
                [native, "-swift-version", "5", str(main), "-o", str(executable)],
                text=True, capture_output=True, timeout=120
            )
            self.assertEqual(
                compile_result.returncode, 0, compile_result.stderr[-5000:]
            )
            run = subprocess.run(
                [str(executable)], text=True, capture_output=True, timeout=30
            )
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr[-5000:])
            self.assertIn("PASS EN native Swift:", run.stdout)

    @unittest.skipUnless(sys.platform == "darwin", "native Darwin Swift only")
    def test_real_swift_auditor_with_disposable_adversarial_files(self):
        code = MANAGER.split("// BEGIN BUILD70_EL_SAFE_PARTIAL_RETRY\n", 1)[1].split(
            "// END BUILD70_EL_SAFE_PARTIAL_RETRY", 1)[0]
        swiftc = shutil.which("swiftc")
        self.assertIsNotNone(swiftc)
        fixture = r'''
import Foundation
import Darwin
let root = URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true)
let fm = FileManager.default
func folder(_ name: String) throws -> URL {
    let u = root.appendingPathComponent(name, isDirectory: true)
    try fm.createDirectory(at: u, withIntermediateDirectories: false)
    return u
}
func put(_ u: URL, _ name: String, _ bytes: [UInt8] = [1, 2, 3]) throws {
    try Data(bytes).write(to: u.appendingPathComponent(name))
}
func check(_ value: Bool, _ note: String) { precondition(value, note) }
func allowed(_ u: URL, _ count: Int = 2) -> Bool {
    return WebReaderPartialRetryFolderAudit.canReplace(directory: u, plannedPages: count)
}
let good = try folder("good")
try put(good, "page-00000.bin")
try put(good, "_download-plan.json")
check(allowed(good), "regular bounded pages and plan")
check(try Data(contentsOf: good.appendingPathComponent("page-00000.bin"))
    == Data([1, 2, 3]), "no mutation")

let empty = try folder("empty")
check(allowed(empty), "empty folder policy is managed by caller")
let orphan = try folder("orphan")
try put(orphan, ".wr69-plan-crash.tmp")
check(!allowed(orphan), "unknown crash evidence")
let completed = try folder("completed")
try put(completed, "page-00000.bin")
try put(completed, ".webreader-completion-v1")
check(!allowed(completed), "completed receipt")
let wrong = try folder("wrong")
try put(wrong, "page-00002.bin")
check(!allowed(wrong), "outside planned page index")
let zero = try folder("zero")
try Data().write(to: zero.appendingPathComponent("page-00000.bin"))
check(!allowed(zero), "zero page retained")
let nested = try folder("nested")
try fm.createDirectory(at: nested.appendingPathComponent("unexpected"),
                       withIntermediateDirectories: false)
check(!allowed(nested), "unexpected directory")
let outside = root.appendingPathComponent("outside-private.bin")
try Data([9, 8, 7]).write(to: outside)
let symlink = try folder("symlink")
try fm.createSymbolicLink(at: symlink.appendingPathComponent("page-00000.bin"),
                          withDestinationURL: outside)
check(!allowed(symlink), "symbolic page")
try fm.createSymbolicLink(at: root.appendingPathComponent("symlink-root"),
                          withDestinationURL: good)
check(!allowed(root.appendingPathComponent("symlink-root")), "symbolic folder")
check(try Data(contentsOf: outside) == Data([9, 8, 7]), "outside data retained")
check(!allowed(good, 0) && !allowed(good, 5001), "invalid plan counts")
print("PASS EL native Swift: scoped replacement only, no files touched")
'''
        with tempfile.TemporaryDirectory(prefix="wr-el-") as temp:
            d = Path(temp)
            main = d / "main.swift"
            source = d / "Audit.swift"
            exe = d / "audit-test"
            main.write_text(fixture)
            source.write_text("import Foundation\nimport Darwin\n" + code)
            compile_result = subprocess.run(
                [swiftc, "-swift-version", "5", str(source), str(main), "-o", str(exe)],
                text=True, capture_output=True, timeout=120
            )
            self.assertEqual(compile_result.returncode, 0, compile_result.stderr[-5000:])
            result = subprocess.run([str(exe), str(d)],
                                    text=True, capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr[-5000:])
            self.assertIn("PASS EL native Swift:", result.stdout)


if __name__ == "__main__":
    unittest.main()

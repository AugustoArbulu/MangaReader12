#!/usr/bin/env python3
"""FG: compiled read-only manager preview, synthetic Swift with no app writes."""
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
SOURCE=(ROOT/'MangaReader12/Downloads/ChapterDownloadManager.swift').read_text()

def extract(a,b):
    return SOURCE.split(a,1)[1].split(b,1)[0]
TYPES=extract("// BEGIN BUILD70_FG_READONLY_BATCH_PREVIEW",
              "// END BUILD70_FG_READONLY_BATCH_PREVIEW")
GATE=extract("// BEGIN BUILD70_FF_INERT_READONLY_DELETION_BRIDGE",
             "// END BUILD70_FF_INERT_READONLY_DELETION_BRIDGE")
API=extract("// BEGIN BUILD70_FG_READONLY_MANAGER_PREVIEW",
            "// END BUILD70_FG_READONLY_MANAGER_PREVIEW")

class FGPreviewTests(unittest.TestCase):
    def test_api_reads_supplied_rows_without_sqlite_or_writes(self):
        self.assertIn("from recorded: [DownloadListRecord]",API)
        self.assertIn("worker.sync",API)
        self.assertIn("recorded.count <= 5_000",API)
        self.assertIn("keyCounts[keys[index]] != 1",API)
        self.assertIn("runningKey != nil || !pending.isEmpty || !jobs.isEmpty",API)
        self.assertIn("WebReaderOfflineDeletionV2ShadowGate.previewForAudit",API)
        for forbidden in ("repository.", "removeItem(", "renameat", "unlinkat", "sqlite3_",
                          "URLSession", "createDirectory(", "jobs.remove", "pending.remove",
                          "startNextIfNeeded(", "try repository.remove"):
            self.assertNotIn(forbidden,API)

    def test_api_has_no_caller_in_destructive_legacy_routes(self):
        for name in ("func remove(\n", "func removeAllConfirmed() throws -> Int"):
            body=SOURCE.split(name,1)[1]
            self.assertNotIn("previewOfflineDeletionCandidates(",body.split("private func chapterDirectory(",1)[0])
        self.assertEqual(SOURCE.count("func previewOfflineDeletionCandidates("),1)

    def test_compiled_swift_preview_decisions(self):
        stub=r"""
import Foundation
enum ChapterDownloadError: Error { case unsafeOfflineDeletionContents }
struct DownloadListRecord {
    let sourceID: String
    let sourceMangaID: String
    let sourceChapterID: String
    let state: String
}
enum WebReaderOfflineCanonicalOwnership {
    static func collides(sourceID: String, mangaID: String, chapterID: String,
                         recorded: [DownloadListRecord]) -> Bool {
        return recorded.contains {
            $0.sourceID != sourceID && $0.sourceMangaID == mangaID &&
            $0.sourceChapterID == chapterID
        }
    }
}
enum WebReaderOfflineDeletionPreflight {
    enum Verdict { case allowed, absent, unsafe }
    static func inspect(directory: URL, sourceID: String, mangaID: String,
                        chapterID: String, fileManager: FileManager) -> Verdict {
        var isDir: ObjCBool = false
        return fileManager.fileExists(atPath: directory.path, isDirectory: &isDir) &&
            isDir.boolValue ? .allowed : .absent
    }
}
"""
        mgr=r"""
final class Manager {
    let worker=DispatchQueue(label:"synthetic-fg")
    let fileManager=FileManager.default
    let root: URL
    var runningKey: String?
    var pending: [String]=[]
    var jobs: [String:Int]=[:]
    init(root: URL){self.root=root}
    func jobKey(sourceID:String,mangaID:String,chapterID:String)->String {
        return sourceID+"-"+mangaID+"-"+chapterID
    }
    func chapterDirectory(sourceID:String,mangaID:String,chapterID:String)throws->URL {
        return root.appendingPathComponent(chapterID)
    }
""" + API + "\n}\n"
        main=r"""
@main struct Run {
    static func main() throws {
        let root=FileManager.default.temporaryDirectory.appendingPathComponent("FG-"+UUID().uuidString)
        try FileManager.default.createDirectory(at:root,withIntermediateDirectories:false)
        defer{try? FileManager.default.removeItem(at:root)}
        try FileManager.default.createDirectory(at:root.appendingPathComponent("c"),withIntermediateDirectories:false)
        let m=Manager(root:root)
        let completed=DownloadListRecord(sourceID:"s",sourceMangaID:"m",sourceChapterID:"c",state:"completed")
        let paused=DownloadListRecord(sourceID:"s",sourceMangaID:"m",sourceChapterID:"c",state:"paused")
        func decision(_ records:[DownloadListRecord])throws->[WebReaderOfflineDeletionV2ShadowGate.Preview] {
            return try m.previewOfflineDeletionCandidates(from:records).map{$0.decision}
        }
        precondition(try! decision([completed]) == [.provisionalCopyOnly])
        precondition(try! decision([paused]) == [.requiresReview])
        precondition(try! decision([completed,completed]) == [.requiresReview,.requiresReview])
        m.pending=["s-m-c"]
        precondition(try! decision([completed]) == [.requiresReview])
        m.pending=[]
        try Data("private URL".utf8).write(to:root.appendingPathComponent("c/_download-plan.json"))
        precondition(try! decision([completed]) == [.requiresReview])
        print("FG_READONLY_PREVIEW_PASS")
    }
}
"""
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'fg.swift'
            executable=Path(tmp)/'fg'
            source.write_text(stub+GATE+TYPES+mgr+main)
            subprocess.run(['swiftc','-parse-as-library',str(source),'-o',str(executable)],
                           check=True,timeout=60,capture_output=True,text=True)
            output=subprocess.run([str(executable)],check=True,timeout=15,
                                  capture_output=True,text=True)
            self.assertIn('FG_READONLY_PREVIEW_PASS',output.stdout)
if __name__=='__main__':
    unittest.main()

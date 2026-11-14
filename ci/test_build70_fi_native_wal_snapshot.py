#!/usr/bin/env python3
"""FI: compile the *app's* SQLite Swift code with deterministic WAL concurrency."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
DB = (ROOT/'MangaReader12/Database/SQLiteDatabase.swift').read_text()

def between(a,b): return DB.split(a,1)[1].split(b,1)[0]

class FINativeWALTests(unittest.TestCase):
    def test_implementation_is_readonly_and_schema_pinned(self):
        code=between('// BEGIN BUILD70_FH_STRICT_READONLY_SQLITE',
                     '// END BUILD70_FH_STRICT_READONLY_SQLITE')
        self.assertIn('SQLITE_OPEN_READONLY | SQLITE_OPEN_FULLMUTEX',code)
        self.assertIn('BEGIN TRANSACTION;',code)
        self.assertIn('auditRequiresSchemaV1',code)
        self.assertNotIn('SQLITE_OPEN_CREATE', '\n'.join(
            line for line in code.splitlines() if not line.strip().startswith('//')))

    def test_wal_real_swift_reader_remains_consistent_under_writer(self):
        if not shutil.which('swiftc'):
            self.skipTest('Swift compiler unavailable')
        dbclass='final class SQLiteDatabase {'+between('final class SQLiteDatabase {','\nenum SQLiteDatabaseError')
        errors='enum SQLiteDatabaseError'+between('enum SQLiteDatabaseError','\n// MARK: - Installed source persistence')
        record='struct DownloadListRecord'+between('struct DownloadListRecord','\nfinal class ReadingProgressRepository')
        method=between('// BEGIN BUILD70_FH_READONLY_DOWNLOAD_ROWS','// END BUILD70_FH_READONLY_DOWNLOAD_ROWS')
        helpers='private func executeSQLite('+DB.split('private func executeSQLite(',1)[1]
        program=r'''
import Foundation
import SQLite3
''' + dbclass+'\n'+errors+'\n'+record+r'''
final class Audit {
    let database: SQLiteDatabase
    init(_ database: SQLiteDatabase) {self.database=database}
'''+method+'\n}\n'+helpers+r'''
@main struct Runner {
    static func run(_ h: OpaquePointer, _ sql: String) {
        let rc=sqlite3_exec(h,sql,nil,nil,nil)
        precondition(rc==SQLITE_OK, "sqlite error \(rc): \(sql)")
    }
    static func state(_ h: OpaquePointer)->String {
        var s: OpaquePointer?
        precondition(sqlite3_prepare_v2(h,"SELECT state FROM downloads WHERE chapter_id=1",-1,&s,nil)==SQLITE_OK)
        defer { sqlite3_finalize(s) }
        precondition(sqlite3_step(s)==SQLITE_ROW)
        return String(cString:sqlite3_column_text(s,0))
    }
    static func main() throws {
        let root=FileManager.default.temporaryDirectory.appendingPathComponent("FI-"+UUID().uuidString)
        try FileManager.default.createDirectory(at:root,withIntermediateDirectories:false)
        defer{try? FileManager.default.removeItem(at:root)}
        let path=root.appendingPathComponent("library.sqlite").path
        let owner=SQLiteDatabase(path:path)
        try owner.openAndMigrate()
        try owner.withConnection { h in
            run(h,"INSERT INTO manga(source_id,source_manga_id,title,date_added) VALUES ('s','m','Fixture',1)")
            run(h,"INSERT INTO chapters(manga_id,source_chapter_id,name,downloaded) VALUES (1,'c','First',1)")
            run(h,"INSERT INTO downloads(chapter_id,state,updated_at) VALUES (1,'completed',1)")
        }
        let audit=Audit(owner)
        precondition(try! audit.listDownloadsForAuditReadOnly()[0].state=="completed")
        var writer: OpaquePointer?
        precondition(sqlite3_open_v2(path,&writer,SQLITE_OPEN_READWRITE|SQLITE_OPEN_FULLMUTEX,nil)==SQLITE_OK)
        guard let w=writer else {fatalError("writer absent")}
        defer { _ = sqlite3_close(w) }
        run(w,"PRAGMA journal_mode=WAL")
        run(w,"BEGIN IMMEDIATE")
        run(w,"UPDATE downloads SET state='paused' WHERE chapter_id=1")
        // Uncommitted metadata must not leak into the read-only preview.
        precondition(try! audit.listDownloadsForAuditReadOnly()[0].state=="completed")
        run(w,"COMMIT")
        precondition(try! audit.listDownloadsForAuditReadOnly()[0].state=="paused")
        try owner.withStrictReadOnlyConnection { h in
            precondition(state(h)=="paused")
            // Writer may commit in WAL while this snapshot is held open.
            run(w,"BEGIN IMMEDIATE")
            run(w,"UPDATE downloads SET state='completed' WHERE chapter_id=1")
            run(w,"COMMIT")
            precondition(state(h)=="paused")
            let rejected=sqlite3_exec(h,"UPDATE downloads SET state='failed'",nil,nil,nil)
            precondition(rejected != SQLITE_OK)
        }
        precondition(try! audit.listDownloadsForAuditReadOnly()[0].state=="completed")
        run(w,"PRAGMA user_version=2")
        do { _ = try audit.listDownloadsForAuditReadOnly(); fatalError("accepted v2") }
        catch SQLiteDatabaseError.auditRequiresSchemaV1(let v) {precondition(v==2)}
        run(w,"PRAGMA user_version=1")
        precondition(try! audit.listDownloadsForAuditReadOnly().count==1)
        print("FI_NATIVE_WAL_SNAPSHOT_PASS")
    }
}
'''
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            source=root/'fi.swift'
            exe=root/'fi'
            source.write_text(program)
            command=['swiftc','-parse-as-library']
            if sys.platform!='darwin':
                mod=root/'SQLite3';mod.mkdir()
                (mod/'module.modulemap').write_text(
                    'module SQLite3 [system] { header "/usr/include/sqlite3.h" link "sqlite3" export * }\n')
                command+=['-I',str(root)]
            command += [str(source),'-lsqlite3','-o',str(exe)]
            cp=subprocess.run(command,capture_output=True,text=True,timeout=90)
            self.assertEqual(cp.returncode,0,cp.stderr)
            e=subprocess.run([str(exe)],capture_output=True,text=True,timeout=30)
            self.assertEqual(e.returncode,0,e.stderr)
            self.assertIn('FI_NATIVE_WAL_SNAPSHOT_PASS',e.stdout)

if __name__=='__main__':unittest.main()

#!/usr/bin/env python3
"""Native Swift Build69 BD: read-only local SQLite before/after snapshot.

Uses disposable SQLite schema-v1 fixtures only. No real app/user database.
The report deliberately contains numeric counts, never titles or paths.
"""
from pathlib import Path
import re
import sqlite3
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "MangaReader12/Core/WebReaderUpgradeContinuitySnapshot.swift"
SQLITE_SOURCE = (ROOT / "MangaReader12/Database/SQLiteDatabase.swift").read_text()
SCHEMA = re.search(
    r'private static let schemaV1 = """(.*?)"""',
    SQLITE_SOURCE, re.DOTALL
).group(1)
SWIFT = r'''
import Foundation

func ensure(_ condition: @autoclosure () -> Bool, _ message: String) {
    if !condition() { fatalError(message) }
}
ensure(CommandLine.arguments.count == 3, "require test app support and mode")
let base = URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true)
let ios = OperatingSystemVersion(majorVersion: 12, minorVersion: 5, patchVersion: 8)
let output = WebReaderUpgradeContinuitySnapshot.report(
    installedBuild: 68, ios: ios, applicationSupportOverride: base
)
ensure(output.utf8.count < 4096, "bounded owner clipboard report")
ensure(output.contains("Build observada: 68 • iOS: 12.5.8"), "actual build identification")
ensure(output.contains("não altera arquivos nem usa rede"), "must stay read only")
ensure(!output.contains("ONE_PIECE_SECRET_TITLE"), "no titles ever")
ensure(!output.contains("private-library-location"), "no filesystem paths ever")
ensure(!output.contains("kei.weebcentral"), "no source IDs ever")
if CommandLine.arguments[2] == "normal" {
    ensure(output.contains("Banco SQLite: legível • schema v1"), "accepted existing schema")
    ensure(output.contains("Obras na biblioteca: 1"), "existing library retained")
    ensure(output.contains("Capítulos registrados: 2"), "chapter count retained")
    ensure(output.contains("Capítulos lidos: 1"), "read state retained")
    ensure(output.contains("Capítulos com página registrada: 1"), "page position retained")
    ensure(output.contains("Capítulos favoritos: 1"), "bookmark retained")
    ensure(output.contains("Downloads marcados completos no banco: 1"), "download index retained")
    ensure(output.contains("Registros de histórico: 1"), "history retained")
    ensure(output.contains("Categorias: 1"), "category retained")
    ensure(output.contains("Vínculos obra/categoria: 1"), "category link retained")
    ensure(output.contains("NÃO páginas verificadas"), "does not claim offline page files verified")
    ensure(!output.contains("INDISPONÍVEL"), "healthy snapshot")
} else if CommandLine.arguments[2] == "after-loss" {
    ensure(output.contains("Downloads marcados completos no banco: 0"),
           "detect changed downloaded index")
    ensure(output.contains("Obras na biblioteca: 1"), "loss did not alter library")
} else {
    ensure(output.contains("Banco: INDISPONÍVEL"), "missing/schema mismatch fails closed")
    ensure(!output.contains("Obras na biblioteca: 0"), "missing DB is not empty library")
}
print(output)
'''
with tempfile.TemporaryDirectory(prefix="wr69-bd-sqlite-privacy-") as tmp:
    root = Path(tmp)
    support = root / "private-library-location" / "Application Support"
    datadir = support / "MangaReader12"
    datadir.mkdir(parents=True)
    dbpath = datadir / "library.sqlite"
    with sqlite3.connect(dbpath) as db:
        db.execute("PRAGMA foreign_keys=ON")
        db.executescript(SCHEMA)
        db.execute("PRAGMA user_version=1")
        db.execute(
            "INSERT INTO manga(source_id,source_manga_id,title,date_added)"
            " VALUES(?,?,?,?)",
            ("kei.weebcentral.en", "private-id", "ONE_PIECE_SECRET_TITLE", 1730000000)
        )
        db.execute("INSERT INTO library(manga_id,date_added) VALUES(1,?)", (1730000000,))
        db.execute(
            "INSERT INTO chapters(manga_id,source_chapter_id,name,is_read,"
            "last_page_read,bookmarked,downloaded) VALUES(?,?,?,?,?,?,?)",
            (1, "one", "chapter1", 1, 24, 1, 1)
        )
        db.execute(
            "INSERT INTO chapters(manga_id,source_chapter_id,name,is_read)"
            " VALUES(?,?,?,?)", (1, "two", "chapter2", 0)
        )
        db.execute(
            "INSERT INTO downloads(chapter_id,state,progress,updated_at)"
            " VALUES(?,?,?,?)", (1, "completed", 1.0, 1730000100)
        )
        db.execute(
            "INSERT INTO history(manga_id,chapter_id,last_read_at) VALUES(?,?,?)",
            (1, 1, 1730000150)
        )
        db.execute("INSERT INTO categories(name) VALUES('Romance')")
        db.execute("INSERT INTO manga_categories(manga_id,category_id) VALUES(1,1)")
        db.commit()

    main = root / "main.swift"
    main.write_text(SWIFT)
    executable = root / "snapshot-qa"
    subprocess.run(
        ["swiftc", "-swift-version", "5", str(SOURCE), str(main),
         "-lsqlite3", "-o", str(executable)],
        check=True, timeout=120
    )
    run = lambda mode: subprocess.run(
        [str(executable), str(support), mode],
        check=True, timeout=30, capture_output=True, text=True
    ).stdout
    before = run("normal")
    after = run("normal")
    assert before == after, "read-only snapshot changed without a DB update"
    with sqlite3.connect(dbpath) as db:
        db.execute("DELETE FROM downloads")
        db.commit()
    changed = run("after-loss")
    assert changed != before, "deleted completion record should change report"
    with sqlite3.connect(dbpath) as db:
        db.execute("PRAGMA user_version=2")
        db.commit()
    unavailable = run("missing")
    assert "Banco: INDISPONÍVEL" in unavailable
    dbpath.unlink()
    assert "Banco: INDISPONÍVEL" in run("missing")
    print("PASS native Swift BD: stable read-only SQLite counts, detects loss, schema mismatch, no personal data or network")

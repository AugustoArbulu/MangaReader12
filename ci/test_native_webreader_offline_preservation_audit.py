#!/usr/bin/env python3
"""Build69 BI: native Swift metadata-only offline inspection on fake iOS data.

Tests contiguous filenames, sparse files, untrusted stored local_path,
bounded sample and schema-mismatch denial. Never reads personal content.
"""
from pathlib import Path
import re
import sqlite3
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
AUDIT = ROOT / "MangaReader12/Core/WebReaderOfflinePreservationAudit.swift"
INVENTORY = ROOT / "MangaReader12/Downloads/WebReaderOfflinePageInventory.swift"
RECEIPT = ROOT / "MangaReader12/Downloads/WebReaderOfflineCompletionReceipt.swift"
MANAGER = (ROOT / "MangaReader12/Downloads/ChapterDownloadManager.swift").read_text()
PATH_SOURCE = MANAGER.split("// BEGIN OFFLINE_PATH_RELOCATION", 1)[1].split(
    "// END OFFLINE_PATH_RELOCATION", 1
)[0]
SCHEMA = re.search(
    r'private static let schemaV1 = """(.*?)"""',
    (ROOT / "MangaReader12/Database/SQLiteDatabase.swift").read_text(), re.DOTALL
).group(1)

SWIFT = r'''
import Foundation
let support = URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true)
let mode = CommandLine.arguments[2]
let os = OperatingSystemVersion(majorVersion: 12, minorVersion: 5, patchVersion: 8)
let audit = WebReaderOfflinePreservationAudit.diagnostic(
    installedBuild: 69, ios: os,
    sampleOffset: mode == "second" ? 64 : (mode == "reset" ? 128 : 0),
    applicationSupportOverride: support
)
let report = audit.report
func check(_ ok: @autoclosure () -> Bool, _ message: String) {
    if !ok() { fatalError(message + " (" + mode + ") " + report) }
}
check(report.utf8.count < 4096, "privacy bounded")
check(!report.contains("SECRET MANGA"), "private title not leaked")
check(!report.contains("secret-source"), "private source ID not leaked")
check(!report.contains("chapter-secret"), "chapter ID not leaked")
check(!report.contains("private-location"), "private path not leaked")
if mode == "three" {
    check(report.contains("Capítulos completos no banco: 3"), "completed count")
    check(report.contains("Capítulos da amostra inspecionados: 3"), "sample count")
    check(report.contains("Capítulos com arquivos sequenciais e não vazios: 1"), "valid files")
    check(report.contains("Com recibo de quantidade de páginas: 1"), "Build69 receipt")
    check(report.contains("Legados sem recibo entre os válidos: 0"), "no legacy valid chapter")
    check(report.contains("Capítulos faltantes, incompletos ou inseguros: 2"), "sparse/empty")
    check(report.contains("Capítulos fora da amostra: 0"), "full first sample")
    check(audit.nextOffset == 0, "single batch loops to first")
    check(report.contains("Arquivos de páginas presentes na amostra: 2"), "two valid pages")
    check(report.contains("NÃO comprova imagem íntegra"), "not a full image audit")
} else if mode == "large" {
    check(report.contains("Capítulos completos no banco: 66"), "all DB records")
    check(report.contains("Capítulos da amostra inspecionados: 64"), "bounded sample")
    check(report.contains("Capítulos fora da amostra: 2"), "honest partial scan")
    check(report.contains("Índice inicial deste lote: 0"), "first batch")
    check(audit.nextOffset == 64, "next batch starts at 64")
} else if mode == "second" {
    check(report.contains("Capítulos completos no banco: 66"), "same total")
    check(report.contains("Índice inicial deste lote: 64"), "second batch")
    check(report.contains("Capítulos da amostra inspecionados: 2"), "two remaining")
    check(audit.nextOffset == 0, "restarts when last batch completes")
} else if mode == "reset" {
    check(report.contains("Índice inicial deste lote: 0"), "invalid offset loops")
    check(report.contains("Capítulos da amostra inspecionados: 64"), "first batch again")
    check(audit.nextOffset == 64, "loop cycles through source")
} else {
    check(report.contains("Banco: INDISPONÍVEL"), "schema/broken DB fails closed")
    check(!report.contains("Capítulos completos no banco: 0"), "missing DB never zero")
}
print("PASS native Swift BI " + mode)
'''
with tempfile.TemporaryDirectory(prefix="wr69-bi-privacy-") as temp:
    root = Path(temp)
    support = root / "private-location" / "Application Support"
    data_dir = support / "MangaReader12"
    data_dir.mkdir(parents=True)
    dbfile = data_dir / "library.sqlite"
    swift_path = root / "path.swift"
    swift_path.write_text("import Foundation\n" + PATH_SOURCE)
    main = root / "main.swift"
    main.write_text(SWIFT)
    exe = root / "qa-offline"
    cmd = [
        "swiftc", "-swift-version", "5",
        str(swift_path), str(INVENTORY), str(RECEIPT), str(AUDIT), str(main),
        "-lsqlite3", "-o", str(exe),
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=120)

    def check_report(label):
        p = subprocess.run(
            [str(exe), str(support), label],
            capture_output=True, text=True, timeout=35,
        )
        if p.returncode:
            raise RuntimeError("BI native " + label + ": " + p.stderr[-3500:])
        print(p.stdout.strip())

    with sqlite3.connect(dbfile) as db:
        db.executescript(SCHEMA)
        db.execute("PRAGMA user_version=1")
        db.execute(
            "INSERT INTO manga(source_id,source_manga_id,title,date_added)"
            " VALUES(?,?,?,?)",
            ("secret-source", "private-work", "SECRET MANGA TITLE", 1730000000)
        )
        for i in range(3):
            db.execute(
                "INSERT INTO chapters(manga_id,source_chapter_id,name)"
                " VALUES(?,?,?)", (1, f"chapter-secret-{i}", f"PRIVATE TITLE {i}")
            )
            db.execute(
                "INSERT INTO downloads(chapter_id,state,progress,local_path,updated_at)"
                " VALUES(?,?,?,?,?)",
                (i+1, "completed", 1.0, "/OLD/UNTRUSTED-CONTAINER/" + str(i), 1730000000)
            )
        db.commit()
    downloads = support / "MangaReader12" / "Downloads" / "secret-source" / "private-work"
    for i in range(3):
        folder = downloads / f"chapter-secret-{i}"
        folder.mkdir(parents=True)
        if i == 0:
            for j in (0, 1):
                (folder / f"page-{j:05d}.bin").write_bytes(b"fake_image")
            (folder / ".webreader-completion-v1").write_bytes(
                b"WR-OFFLINE-COMPLETE-V1:2\n"
            )
        elif i == 1:
            for j in (0, 2):
                (folder / f"page-{j:05d}.bin").write_bytes(b"fake_image")
        else:
            (folder / "page-00000.bin").write_bytes(b"")
    before = dbfile.read_bytes()
    check_report("three")
    assert dbfile.read_bytes() == before, "SQLite contents changed during readonly audit"
    assert (downloads / "chapter-secret-1" / "page-00002.bin").exists()
    with sqlite3.connect(dbfile) as db:
        for i in range(3,66):
            db.execute(
                "INSERT INTO chapters(manga_id,source_chapter_id,name)"
                " VALUES(?,?,?)", (1, f"chapter-secret-{i}", "PRIVATE TITLE")
            )
            db.execute(
                "INSERT INTO downloads(chapter_id,state,progress,updated_at)"
                " VALUES(?,?,?,?)", (i+1, "completed", 1.0, 1730000000)
            )
        db.commit()
    check_report("large")
    check_report("second")
    check_report("reset")
    with sqlite3.connect(dbfile) as db:
        db.execute("PRAGMA user_version=2")
        db.commit()
    check_report("unknown")
    dbfile.unlink()
    check_report("unknown")
    print("PASS native Swift BI: partial offline file presence only, no writes or leaked identifiers")

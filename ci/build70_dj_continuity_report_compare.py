#!/usr/bin/env python3
"""WebReader Build70 / DJ — read-only before/after SQLite COUNT report audit.

Consumes the exact clipboard format of WebReaderUpgradeContinuitySnapshot.swift.
Reports are user-supplied, UNAUTHENTICATED, and can be forged. Exact matching
of nine SQLite counts is never proof of preserved images, favorites content,
database integrity, publisher identity, installation consent or success.
No iOS/Chimera API, DB access, appinst, network, writing, IPA or installation.
"""
from __future__ import annotations

from dataclasses import dataclass
import argparse
import json
import os
from pathlib import Path
import re
import stat

BEFORE_BUILD = 70
AFTER_BUILD = 71
IOS_VERSION = "12.5.8"
MAX_REPORT_BYTES = 4096

COUNT_LABELS = (
    "Obras na biblioteca",
    "Capítulos registrados",
    "Capítulos lidos",
    "Capítulos com página registrada",
    "Capítulos favoritos",
    "Downloads marcados completos no banco",
    "Registros de histórico",
    "Categorias",
    "Vínculos obra/categoria",
)
HEADER = "WebReader • CONTINUIDADE DE DADOS — leitura local apenas"
NOTE = "Números do SQLite, sem títulos, IDs, caminhos ou páginas de obras."
DB_HEALTH = "Banco SQLite: legível • schema v1"
FOOTER = (
    "Downloads completos = registros no banco, NÃO páginas verificadas.",
    "Compare este texto ANTES e DEPOIS do upgrade manual.",
    "Faça o teste real de capítulos offline com Wi-Fi DESLIGADO.",
    "O backup .mr12backup NÃO inclui imagens; restaurar apaga Downloads.",
    "Este diagnóstico não abre imagens, não altera arquivos nem usa rede.",
)


class DJRejected(ValueError):
    pass


@dataclass(frozen=True)
class DJCounts:
    reported_build: int
    ios_version: str
    counts: tuple[int, ...]
    report_authenticity_verified: bool = False
    physical_readout_verified: bool = False
    sqlite_row_contents_verified: bool = False
    offline_image_files_verified: bool = False
    library_backup_verified: bool = False
    installation_authorized: bool = False


def parse_continuity_report(source: bytes, *, expected_build: int) -> DJCounts:
    if type(expected_build) is not int or expected_build not in (BEFORE_BUILD, AFTER_BUILD):
        raise DJRejected("unsupported exact build")
    if type(source) is not bytes or not 0 < len(source) <= MAX_REPORT_BYTES:
        raise DJRejected("invalid or oversized report")
    if b"\x00" in source or b"\r" in source:
        raise DJRejected("NUL/CR not accepted")
    try:
        decoded = source.decode("utf-8")
    except UnicodeError as exc:
        raise DJRejected("invalid UTF-8 report") from exc
    # The app's current clipboard uses joined lines with no trailing newline.
    # Only that exact canonical form is accepted, never unknown extra fields.
    lines = decoded.split("\n")
    if len(lines) != 4 + len(COUNT_LABELS) + len(FOOTER):
        raise DJRejected("unexpected count or reordered report lines")
    if lines[0] != HEADER:
        raise DJRejected("not a WebReader read-only continuity report")
    expected_version_line = (
        f"Build observada: {expected_build} • iOS: {IOS_VERSION}"
    )
    if lines[1] != expected_version_line or lines[2] != NOTE or lines[3] != DB_HEALTH:
        raise DJRejected("wrong build/OS/schema or database unavailable")
    counts = []
    for i, label in enumerate(COUNT_LABELS):
        value = lines[4 + i]
        prefix = label + ": "
        if not value.startswith(prefix):
            raise DJRejected("missing/reordered SQLite count label")
        raw = value[len(prefix):]
        if re.fullmatch(r"(?:0|[1-9][0-9]{0,17})", raw, flags=re.ASCII) is None:
            raise DJRejected("invalid count integer")
        number = int(raw)
        if number > 9_223_372_036_854_775_807:
            raise DJRejected("count exceeds SQLite signed int64")
        counts.append(number)
    if tuple(lines[4 + len(COUNT_LABELS):]) != FOOTER:
        raise DJRejected("footer changed / offline warning missing")
    return DJCounts(
        reported_build=expected_build,
        ios_version=IOS_VERSION,
        counts=tuple(counts),
    )


def _receipt(status: str, *, before: DJCounts, after: DJCounts | None = None,
             changes: tuple[str, ...] = ()) -> dict:
    # All status values are UNAUTHENTICATED observations, NOT safe-to-install.
    return {
        "status": status,
        "expectedInstalledBuild": BEFORE_BUILD,
        "candidateQABuild": AFTER_BUILD,
        "ios": IOS_VERSION,
        "countLabelTotal": len(COUNT_LABELS),
        "differentCountLabels": list(changes),
        "allNineCountsTextuallyEqual":
            after is not None and not changes,
        "originalReportsAuthenticated": False,
        "physicalBeforeAndAfterExecutionAttested": False,
        "sqliteContentsVerified": False,
        "libraryTitlesOrProgressIntegrityVerified": False,
        "offlinePageImageBytesVerified": False,
        "offlineReadingWithoutWifiVerified": False,
        "externalPortableBackupVerified": False,
        "onDeviceBuild71Installed": False,
        "publisherAuthenticated": False,
        "ownerQADistributionApprovalRecorded": False,
        "readyToDistributeIPA": False,
        "readyToInstallIPA": False,
        "installationAuthorized": False,
        "installationPerformed": False,
    }


def check_before_report(source: bytes) -> dict:
    parsed = parse_continuity_report(source, expected_build=BEFORE_BUILD)
    return _receipt("DJ_BASELINE_COUNT_TEXT_ACCEPTED_UNATTESTED", before=parsed)


def compare_reports(before: bytes, after: bytes) -> dict:
    a = parse_continuity_report(before, expected_build=BEFORE_BUILD)
    b = parse_continuity_report(after, expected_build=AFTER_BUILD)
    changed = tuple(
        label for label, left, right in zip(COUNT_LABELS, a.counts, b.counts)
        if left != right
    )
    status = (
        "DJ_NINE_COUNTS_TEXTUALLY_EQUAL_NOT_OFFLINE_PROOF"
        if not changed else "DJ_COUNT_DIFFERENCE_REQUIRES_MANUAL_REVIEW"
    )
    return _receipt(status, before=a, after=b, changes=changed)


def _read_file_once(path: Path) -> bytes:
    if not hasattr(os, "O_NOFOLLOW"):
        raise DJRejected("platform has no atomic symlink rejection")
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    try:
        fd = os.open(path, flags)
        with os.fdopen(fd, "rb") as stream:
            before = os.fstat(stream.fileno())
            if (not stat.S_ISREG(before.st_mode) or
                    not 0 < before.st_size <= MAX_REPORT_BYTES):
                raise DJRejected("report must be bounded regular file")
            data = stream.read(MAX_REPORT_BYTES + 1)
            after = os.fstat(stream.fileno())
            attrs = lambda s: (s.st_dev, s.st_ino, s.st_size,
                                s.st_mtime_ns, s.st_ctime_ns)
            if attrs(before) != attrs(after) or len(data) != before.st_size:
                raise DJRejected("file changed during read")
            return data
    except OSError as exc:
        raise DJRejected("cannot safely read report") from exc


def main() -> None:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--before", type=Path, required=True)
    cli.add_argument("--after", type=Path)
    args = cli.parse_args()
    try:
        before = _read_file_once(args.before)
        report = (
            compare_reports(before, _read_file_once(args.after))
            if args.after is not None else check_before_report(before)
        )
    except DJRejected as exc:
        cli.error("BLOCKED: " + str(exc))
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()

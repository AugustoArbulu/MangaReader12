#!/usr/bin/env python3
"""WebReader Build70 / DO: physical baseline TEXT protocol cross-check.

Compares the EXISTING Build70 read-only SQLite counter report with one or
more existing 64-item offline inventory report texts. There is NO new iOS
code, shell access, file enumeration on the iPad, networking, persistence,
publisher authentication, or installation.

The texts are NOT signed or attested. Even a complete matching set cannot
prove the contents or actual decodability of the downloaded page images.
This tool can at most reject inconsistent / potentially missing metadata,
never authorize an IPA or prove container preservation across an upgrade.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re

from build70_dj_continuity_report_compare import (
    BEFORE_BUILD, IOS_VERSION, DJRejected, COUNT_LABELS,
    MAX_REPORT_BYTES, parse_continuity_report, _read_file_once,
)

MAX_BATCH = 64
MAX_REPORTS = 256
MAX_TOTAL = 1_000_000_000
OFFLINE_HEADER = "WebReader • PRESENÇA OFFLINE — diagnóstico local parcial"
OFFLINE_INTRO = (
    OFFLINE_HEADER,
    f"Build observada: {BEFORE_BUILD} • iOS: {IOS_VERSION}",
    "Amostra máxima: 64 capítulos marcados completos.",
    "Sem títulos, IDs, caminhos, imagens ou consultas à rede.",
)
FIELDS = (
    "Capítulos completos no banco",
    "Índice inicial deste lote",
    "Próximo índice da auditoria",
    "Capítulos da amostra inspecionados",
    "Capítulos com arquivos sequenciais e não vazios",
    "Com recibo de quantidade de páginas",
    "Legados sem recibo entre os válidos",
    "Capítulos faltantes, incompletos ou inseguros",
    "Capítulos fora da amostra",
    "Arquivos de páginas presentes na amostra",
)
OFFLINE_FOOTER = (
    "Presença de arquivo ou recibo NÃO comprova imagem íntegra ou capítulo completo na origem.",
    "Se houver falhas, não desinstale nem restaure backup automaticamente.",
    "Teste a leitura REAL sem Wi-Fi, inclusive após fechar e reabrir o app.",
    "Nenhuma página foi modificada; este diagnóstico não faz download.",
)


class DORejected(ValueError):
    pass


@dataclass(frozen=True)
class OfflineBatch:
    total: int
    offset: int
    next_offset: int
    scanned: int
    valid: int
    sealed: int
    legacy: int
    bad: int
    outside_sample: int
    pages: int


def _count(text: str, label: str) -> int:
    prefix = label + ": "
    if not text.startswith(prefix):
        raise DORejected("missing or reordered offline sample field")
    tail = text[len(prefix):]
    if re.fullmatch(r"(?:0|[1-9][0-9]{0,18})", tail, re.ASCII) is None:
        raise DORejected("noncanonical offline sample number")
    n = int(tail)
    if n > 9_223_372_036_854_775_807:
        raise DORejected("sample number exceeds SQLite int64")
    return n


def parse_offline_batch(source: bytes) -> OfflineBatch:
    if type(source) is not bytes or not 0 < len(source) <= MAX_REPORT_BYTES:
        raise DORejected("missing or oversized offline report")
    if b"\x00" in source or b"\r" in source:
        raise DORejected("binary/CR in offline report")
    try:
        decoded = source.decode("utf-8")
    except UnicodeError as exc:
        raise DORejected("offline report must be UTF-8") from exc
    lines = decoded.split("\n")
    if len(lines) != len(OFFLINE_INTRO) + len(FIELDS) + len(OFFLINE_FOOTER):
        raise DORejected("offline report line count changed")
    if tuple(lines[:4]) != OFFLINE_INTRO or tuple(lines[-4:]) != OFFLINE_FOOTER:
        raise DORejected("wrong Build70/iOS or safety footer changed")
    v = [_count(line, label)
         for line, label in zip(lines[4:4+len(FIELDS)], FIELDS)]
    batch = OfflineBatch(*v)
    if batch.total > MAX_TOTAL:
        raise DORejected("unreasonably large completed chapter total")
    if batch.total == 0:
        if (batch.offset, batch.next_offset, batch.scanned,
                batch.valid, batch.sealed, batch.legacy,
                batch.bad, batch.outside_sample, batch.pages) != (0,)*9:
            raise DORejected("zero-completed report internally inconsistent")
        return batch
    if batch.offset >= batch.total or batch.offset % MAX_BATCH != 0:
        raise DORejected("unexpected offline sample offset")
    # Production LIMIT 64 with OFFSET n, and native next-offset logic.
    expected_scanned = min(MAX_BATCH, batch.total-batch.offset)
    expected_next = (batch.offset + MAX_BATCH
                     if batch.offset + MAX_BATCH < batch.total else 0)
    if batch.scanned != expected_scanned or batch.next_offset != expected_next:
        raise DORejected("sample bounds, page length or next offset incorrect")
    if batch.outside_sample != batch.total-batch.scanned:
        raise DORejected("out-of-sample count mismatch")
    if not (0 <= batch.sealed <= batch.valid <= batch.scanned):
        raise DORejected("impossible count of valid or sealed chapters")
    if batch.legacy != batch.valid-batch.sealed or batch.bad != batch.scanned-batch.valid:
        raise DORejected("offline failure/legacy counters are contradictory")
    if not batch.valid <= batch.pages <= batch.valid*99_999:
        raise DORejected("offline page count contradicts scanned chapter count")
    return batch


def audit_build70_baseline(counts: bytes, offline_batches: list[bytes]) -> dict:
    if type(offline_batches) is not list or not 1 <= len(offline_batches) <= MAX_REPORTS:
        raise DORejected("one to 256 offline sample reports required")
    try:
        snapshot = parse_continuity_report(counts, expected_build=BEFORE_BUILD)
    except DJRejected as exc:
        raise DORejected("canonical Build70 SQLite continuity report missing") from exc
    if len(snapshot.counts) != len(COUNT_LABELS):
        raise DORejected("nine SQLite counters required")
    total = snapshot.counts[5]  # downloads WHERE state='completed'
    if total > MAX_TOTAL:
        raise DORejected("completed chapter total above audit safety bound")

    expected_offset = 0
    scanned_total = 0
    valid_total = 0
    sealed_total = 0
    missing_total = 0
    legacy_total = 0
    page_total = 0
    completed = False
    for raw in offline_batches:
        batch = parse_offline_batch(raw)
        if completed or batch.total != total or batch.offset != expected_offset:
            raise DORejected("overlapping/missing sample or inconsistent SQLite total")
        scanned_total += batch.scanned
        valid_total += batch.valid
        sealed_total += batch.sealed
        legacy_total += batch.legacy
        missing_total += batch.bad
        page_total += batch.pages
        if batch.next_offset == 0:
            completed = True
            expected_offset = 0
        else:
            expected_offset = batch.next_offset
    if scanned_total > total or valid_total > scanned_total:
        raise DORejected("double-counted offline samples")
    if completed and scanned_total != total:
        raise DORejected("apparently complete cycle did not cover all chapters")
    if not completed and (scanned_total >= total or expected_offset != scanned_total):
        raise DORejected("inconsistent partial coverage")
    remaining = total - scanned_total
    if missing_total > 0:
        status = "DO_OFFLINE_METADATA_FAILURE_OWNER_REVIEW_REQUIRED"
    elif legacy_total > 0:
        status = "DO_LEGACY_WITHOUT_RECEIPT_NEEDS_PHYSICAL_READING"
    elif not completed:
        status = "DO_PARTIAL_SAMPLE_NEEDS_MORE_BATCHES"
    else:
        status = "DO_TEXT_FULL_COVERAGE_NO_IMAGE_BYTE_PROOF"
    if total == 0:
        status = "DO_NO_COMPLETE_OFFLINE_CHAPTERS_IN_TEXT_NOT_DEVICE_PROOF"

    return {
        "status": status,
        "expectedInstalledBuild": BEFORE_BUILD,
        "targetIOS": IOS_VERSION,
        "totalCompletedRecordsAsText": total,
        "offlineBatchTextsChecked": len(offline_batches),
        "inspectedChapterRecordsAsText": scanned_total,
        "validSequentialChaptersAsText": valid_total,
        "sealedChapterReceiptsAsText": sealed_total,
        "legacyWithoutReceiptAsText": legacy_total,
        "missingOrUnsafeChaptersAsText": missing_total,
        "offlinePageEntriesAsText": page_total,
        "remainingRecordsNotInspectedAsText": remaining,
        "allCompletedRowsCoveredByTextSequence": completed,
        "expectedNextAuditOffset": expected_offset,
        "inputTextsIndependentlyAuthenticated": False,
        "sqliteRowContentsVerified": False,
        "offlinePagePayloadBytesRead": False,
        "offlineImageDecodingVerified": False,
        "physicalReadingWithoutWiFiVerified": False,
        "physicalBuild70AppIdentifierAttested": False,
        "physicalBuild71Installed": False,
        "dataContainerSurvivesUpgradeProven": False,
        "backupRetainedOutsideDeviceVerified": False,
        "publisherAuthenticated": False,
        "ownerQADistributionApprovalRecorded": False,
        "readyToDistributeIPA": False,
        "readyToInstallIPA": False,
        "installationAuthorized": False,
        "installationPerformed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--counts", type=Path, required=True)
    parser.add_argument("--offline", action="append", type=Path,
                        dest="offline_paths", required=True)
    args = parser.parse_args()
    try:
        if len(args.offline_paths) > MAX_REPORTS:
            raise DORejected("too many offline sample reports")
        result = audit_build70_baseline(
            _read_file_once(args.counts),
            [_read_file_once(path) for path in args.offline_paths]
        )
    except (DORejected, DJRejected, OSError) as exc:
        parser.error("BLOCKED: " + str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

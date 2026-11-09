#!/usr/bin/env python3
"""Build69 BE: fail-closed comparison of TWO local count-only iPad reports.

This does not read a live iPad database, authenticate who copied the reports,
or verify chapter-image bytes. It rejects any missing or inconsistent fields.
It only helps identify obvious database record losses after manual in-place QA.
"""
import argparse
import json
import re
from pathlib import Path

from build69_production_release_preflight import _read_external_regular

METRICS = (
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
PRIVACY = "Números do SQLite, sem títulos, IDs, caminhos ou páginas de obras."
DATABASE = "Banco SQLite: legível • schema v1"
FOOTER = (
    "Downloads completos = registros no banco, NÃO páginas verificadas.",
    "Compare este texto ANTES e DEPOIS do upgrade manual.",
    "Faça o teste real de capítulos offline com Wi-Fi DESLIGADO.",
    "O backup .mr12backup NÃO inclui imagens; restaurar apaga Downloads.",
    "Este diagnóstico não abre imagens, não altera arquivos nem usa rede.",
)
MAX_REPORT = 4096


class ContinuityReportRejected(ValueError):
    pass


def parse_continuity_report(payload: bytes):
    if type(payload) is not bytes or not 0 < len(payload) <= MAX_REPORT:
        raise ContinuityReportRejected("missing or oversized count report")
    try:
        text = payload.decode("utf-8")
    except UnicodeError as exc:
        raise ContinuityReportRejected("count report is not UTF-8") from exc
    if "\r" in text or "\x00" in text:
        raise ContinuityReportRejected("ambiguous line endings or control chars")
    lines = text.rstrip("\n").split("\n")
    if (len(lines) != 4 + len(METRICS) + len(FOOTER)
            or lines[0] != HEADER or lines[2] != PRIVACY
            or lines[3] != DATABASE
            or tuple(lines[-len(FOOTER):]) != FOOTER):
        raise ContinuityReportRejected("unknown or incomplete report structure")
    header = re.fullmatch(
        r"Build observada: (68|69) • iOS: (12\.5\.8)", lines[1]
    )
    if not header:
        raise ContinuityReportRejected("wrong build, device OS or report provenance")
    counts = {}
    for idx, name in enumerate(METRICS, start=4):
        prefix = name + ": "
        line = lines[idx]
        if not line.startswith(prefix):
            raise ContinuityReportRejected("unexpected report metric")
        value = line[len(prefix):]
        if not re.fullmatch(r"(?:0|[1-9][0-9]{0,11})", value):
            raise ContinuityReportRejected("invalid or unbounded row count")
        counts[name] = int(value)
    return {"build": int(header.group(1)), "ios": header.group(2), "counts": counts}


def compare_continuity_reports(*, before: bytes, after: bytes) -> dict:
    baseline = parse_continuity_report(before)
    current = parse_continuity_report(after)
    if baseline["build"] != 68 or current["build"] != 69:
        raise ContinuityReportRejected("requires real Build68 -> Build69 manual upgrade")
    if baseline["ios"] != current["ios"] or current["ios"] != "12.5.8":
        raise ContinuityReportRejected("reports must originate from same iOS version")
    differences = []
    lost = 0
    added = 0
    for name in METRICS:
        old = baseline["counts"][name]
        new = current["counts"][name]
        delta = new - old
        if delta < 0:
            lost += 1
        if delta > 0:
            added += 1
        differences.append({
            "metric": name,
            "before": old,
            "after": new,
            "delta": delta
        })
    status = (
        "POTENTIAL_DATA_LOSS_STOP_REVIEW" if lost else
        "CHANGED_COUNTS_REVIEW_MANUALLY" if added else
        "DATABASE_RECORD_COUNTS_UNCHANGED_NOT_PHYSICAL_QA"
    )
    return {
        "status": status,
        "baselineBuild": 68,
        "observedNewBuild": 69,
        "ios": "12.5.8",
        "metrics": differences,
        "decreasedMetricCount": lost,
        "increasedMetricCount": added,
        "sqliteCountsMatchExactly": not lost and not added,
        "allDownloadedPageBytesVerified": False,
        "physicalOfflineReaderTestCompleted": False,
        "appReinstallAvoidedVerifiedByTool": False,
        "backupRestoreAvoidedVerifiedByTool": False,
        "reportOriginAuthenticatedByTool": False,
        "physicalUpgradeSuccessful": False,
        "installationAuthorized": False,
        "installationPerformed": False,
        "networkUsed": False,
        "mainModified": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    args = parser.parse_args()
    result = compare_continuity_reports(
        before=_read_external_regular(args.before, MAX_REPORT),
        after=_read_external_regular(args.after, MAX_REPORT)
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

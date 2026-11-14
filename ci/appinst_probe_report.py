#!/usr/bin/env python3
"""Classify ONLY the standalone safe-spawn probe's copied text.
Offline and non-privileged: never opens an IPA, calls appinst or changes files.
Positive bundled-child launch cannot authorize installation of any app.
"""
from __future__ import annotations

import argparse
import json
import re
import sys

MAX_REPORT_BYTES = 8192
HEADER = "WebReader • Spawn local sem appinst"
NO_INSTALL = "APPINST_EXECUTADO=NAO | INSTALACAO=NAO"
STATES = {"OK", "NEGADO", "FALHA_DO_CHILD", "WAITPID_INDISPONIVEL", "TIMEOUT"}
META_RE = re.compile(r"^(?:REGULAR|NOT_REGULAR|ERRNO_[0-9]{1,5})$")
XOK_RE = re.compile(r"^(?:YES|ERRNO_[0-9]{1,5})$")
SPAWN_RE = re.compile(
    r"^SPAWN_LOCAL=(OK|NEGADO|FALHA_DO_CHILD|WAITPID_INDISPONIVEL|TIMEOUT)"
    r"(?: \([^\r\n]{1,180}\))?$"
)


def classify_report(raw: str) -> dict:
    """Fail closed on malformed, duplicate, or non-diagnostic reports."""
    outcome = {
        "report_accepted": False,
        "local_child": "not_established",
        "appinst_metadata": "not_established",
        "direct_appinst_execution_verified": False,
        "installer_authorized": False,
        "installation_performed": False,
        "next_step": "Use apenas o primeiro botão do aplicativo de diagnóstico.",
    }
    if not isinstance(raw, str):
        return outcome
    encoded = raw.encode("utf-8", errors="replace")
    if len(encoded) > MAX_REPORT_BYTES or "\x00" in raw or "\r" in raw:
        return outcome
    lines = [line.strip() for line in raw.split("\n") if line.strip()]
    if not lines or lines[0] != HEADER or NO_INSTALL not in lines:
        return outcome
    if lines.count(NO_INSTALL) != 1:
        return outcome

    def one(prefix: str) -> str | None:
        matches = [line for line in lines if line.startswith(prefix)]
        return matches[0] if len(matches) == 1 else None

    spawn = one("SPAWN_LOCAL=")
    meta = one("APPINST_META_LSTAT=")
    xok = one("APPINST_META_XOK=")
    advisory = one("APPINST_META_ADVISORY=")
    if not spawn or not meta or not xok or advisory != "APPINST_META_ADVISORY=YES":
        return outcome
    found = SPAWN_RE.fullmatch(spawn)
    m = meta.split("=", 1)[1]
    a = xok.split("=", 1)[1]
    if not found or not META_RE.fullmatch(m) or not XOK_RE.fullmatch(a):
        return outcome
    state = found.group(1)
    if state not in STATES:
        return outcome
    outcome["report_accepted"] = True
    outcome["local_child"] = state
    outcome["appinst_metadata"] = {
        "lstat": m,
        "access_x_ok": a,
        "advisory_only": True,
    }
    if state == "OK":
        outcome["next_step"] = (
            "O child local iniciou; isso NAO prova execucao de /usr/bin/appinst. "
            "A instalacao in-app continua bloqueada ate QA fisico separado."
        )
    else:
        outcome["next_step"] = (
            "O child local nao comprovou execucao. Investigar sandbox e assinatura "
            "antes de qualquer teste de instalacao."
        )
    return outcome


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", nargs="?", type=argparse.FileType("r", encoding="utf-8"),
                        default=sys.stdin)
    args = parser.parse_args()
    try:
        data = args.report.read(MAX_REPORT_BYTES + 1)
        result = classify_report(data)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
        return 0 if result["report_accepted"] else 2
    finally:
        if args.report is not sys.stdin:
            args.report.close()


if __name__ == "__main__":
    raise SystemExit(main())

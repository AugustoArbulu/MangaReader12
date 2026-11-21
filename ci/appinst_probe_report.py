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
    # The standalone iOS12 app emits exactly eight fields, plus one
    # informational line only when the bundled child exits successfully.
    # Unknown assertions (for example, "INSTALACAO=SIM") must not be
    # silently discarded by the offline report classifier.
    lines = raw.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    if len(lines) not in (8, 9) or lines[0] != HEADER:
        return outcome
    if any(not line or line != line.strip() for line in lines):
        return outcome
    if not re.fullmatch(r"iOS: 12(?:\.[0-9]{1,3}){1,2}", lines[1]):
        return outcome
    identity = re.fullmatch(r"UID: ([0-9]{1,10}) \| EUID: ([0-9]{1,10})", lines[2])
    if identity is None or int(identity.group(2)) == 0:
        return outcome
    if lines[5] != "APPINST_META_ADVISORY=YES" or lines[7] != NO_INSTALL:
        return outcome
    spawn, meta, xok = lines[6], lines[3], lines[4]
    if not meta.startswith("APPINST_META_LSTAT=") or not xok.startswith("APPINST_META_XOK="):
        return outcome
    found = SPAWN_RE.fullmatch(spawn)
    m = meta.split("=", 1)[1]
    a = xok.split("=", 1)[1]
    if not found or not META_RE.fullmatch(m) or not XOK_RE.fullmatch(a):
        return outcome
    state = found.group(1)
    if state not in STATES:
        return outcome
    if state == "OK":
        if len(lines) != 9 or lines[8] != "Não prova acesso a /usr/bin/appinst.":
            return outcome
    elif len(lines) != 8:
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

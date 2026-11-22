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
STATES = {"OK", "NEGADO", "FALHA_DO_CHILD", "WAITPID_INDISPONIVEL", "TIMEOUT", "PRECHECK_FAILED"}
META_RE = re.compile(r"^(?:REGULAR|NOT_REGULAR|ERRNO_[0-9]{1,5})$")
XOK_RE = re.compile(r"^(?:YES|ERRNO_[0-9]{1,5})$")
SPAWN_RE = re.compile(
    r"^SPAWN_LOCAL=(OK|NEGADO|FALHA_DO_CHILD|WAITPID_INDISPONIVEL|TIMEOUT|PRECHECK_FAILED)"
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

    # Build5 appends a separately scoped self-spawn of the ALREADY SIGNED
    # main binary (not a resource, appinst or an installable helper).
    # Validate the exact suffix before handing the historical core report
    # to the Build3/Build4 parser.
    self_probe = None
    if len(lines) >= 2 and lines[-2].startswith("SELF_MAIN="):
        if len(lines) not in (14, 15) or not lines[-1].startswith("SPAWN_SELF="):
            return outcome
        main_state = lines[-2].split("=", 1)[1]
        self_result = lines[-1].split("=", 1)[1]
        if not re.fullmatch(
            r"(?:REGULAR_EXEC|REGULAR_NOEXEC|NOT_REGULAR|MISSING|ERRNO_[0-9]{1,5}|INVALID_ID)",
            main_state,
        ):
            return outcome
        result_match = re.fullmatch(
            r"(OK|NEGADO|FALHA_DO_SELF|WAITPID_INDISPONIVEL|TIMEOUT|PRECHECK_FAILED)"
            r"(?: \([^\r\n]{1,180}\))?",
            self_result,
        )
        if result_match is None:
            return outcome
        self_state = result_match.group(1)
        if (main_state == "REGULAR_EXEC") == (self_state == "PRECHECK_FAILED"):
            return outcome
        if main_state == "INVALID_ID":
            return outcome
        self_probe = {"main_executable": main_state, "result": self_state}
        lines = lines[:-2]
    if len(lines) not in (7, 8, 9, 12, 13) or lines[0] != HEADER:
        return outcome
    if any(not line or line != line.strip() for line in lines):
        return outcome
    if not re.fullmatch(r"iOS: 12(?:\.[0-9]{1,3}){1,2}", lines[1]):
        return outcome
    identity = re.fullmatch(r"UID: ([0-9]{1,10}) \| EUID: ([0-9]{1,10})", lines[2])
    if identity is None or int(identity.group(2)) == 0:
        return outcome
    if lines[5] != "APPINST_META_ADVISORY=YES":
        return outcome
    meta, xok = lines[3], lines[4]
    if not meta.startswith("APPINST_META_LSTAT=") or not xok.startswith("APPINST_META_XOK="):
        return outcome
    m = meta.split("=", 1)[1]
    a = xok.split("=", 1)[1]
    if not META_RE.fullmatch(m) or not XOK_RE.fullmatch(a):
        return outcome

    # The physical Build3 report can stop before spawning the child; it
    # intentionally has no install footer. Accept only exact known text and
    # classify it as a preflight failure, never as process execution.
    if len(lines) == 7:
        if lines[6] not in (
            "RESULTADO: child inválido ou não executável.",
            "RESULTADO: child de teste ausente.",
        ):
            return outcome
        outcome["report_accepted"] = True
        outcome["local_child"] = "precheck_unclassified"
        outcome["appinst_metadata"] = {"lstat": m, "access_x_ok": a, "advisory_only": True}
        outcome["next_step"] = (
            "O Build3 parou antes de posix_spawn. Verificar a IPA Build4 com "
            "diagnostico separado de bundle, lstat, bits e access(X_OK)."
        )
        return outcome

    is_v4 = len(lines) in (12, 13)
    if is_v4:
        if lines[11] != NO_INSTALL:
            return outcome
        child_path, child_lstat, child_mode, child_access = lines[6:10]
        if child_path not in ("CHILD_PATH=FOUND", "CHILD_PATH=MISSING"):
            return outcome
        if not child_lstat.startswith("CHILD_LSTAT=") or not child_mode.startswith(
            "CHILD_MODE_EXEC="
        ) or not child_access.startswith("CHILD_ACCESS_XOK="):
            return outcome
        lstat_value = child_lstat.split("=", 1)[1]
        mode_value = child_mode.split("=", 1)[1]
        access_value = child_access.split("=", 1)[1]
        if not re.fullmatch(r"(?:REGULAR|NOT_REGULAR|NOT_CHECKED|ERRNO_[0-9]{1,5})",
                            lstat_value):
            return outcome
        if mode_value not in ("YES", "NO", "UNKNOWN"):
            return outcome
        if not re.fullmatch(r"(?:YES|NOT_CHECKED|ERRNO_[0-9]{1,5})", access_value):
            return outcome
        spawn = lines[10]
        found = SPAWN_RE.fullmatch(spawn)
        if not found:
            return outcome
        state = found.group(1)
        if child_path == "CHILD_PATH=MISSING":
            if (lstat_value, mode_value, access_value, state) != (
                "NOT_CHECKED", "UNKNOWN", "NOT_CHECKED", "PRECHECK_FAILED"
            ):
                return outcome
        elif lstat_value == "REGULAR":
            if mode_value not in ("YES", "NO"):
                return outcome
            if (mode_value == "NO") != (state == "PRECHECK_FAILED"):
                return outcome
        else:
            if mode_value != "UNKNOWN" or state != "PRECHECK_FAILED" or (
                access_value == "NOT_CHECKED"
            ):
                return outcome
        if child_path == "CHILD_PATH=FOUND" and (
            lstat_value == "NOT_CHECKED" or access_value == "NOT_CHECKED"
        ):
            return outcome
        details = {
            "path": child_path.split("=", 1)[1],
            "lstat": lstat_value,
            "executable_bits": mode_value,
            "access_x_ok": access_value,
            "advisory_only": True,
        }
        extra = lines[12:]
    else:
        if lines[7] != NO_INSTALL:
            return outcome
        found = SPAWN_RE.fullmatch(lines[6])
        if not found:
            return outcome
        state = found.group(1)
        details = None
        extra = lines[8:]
    if state in ("OK", "FALHA_DO_CHILD"):
        if extra != ["Não prova acesso a /usr/bin/appinst."]:
            return outcome
    elif extra:
        return outcome
    outcome["report_accepted"] = True
    outcome["local_child"] = state
    if self_probe is not None:
        outcome["self_probe"] = self_probe
    if is_v4:
        outcome["child_precheck"] = details
    outcome["appinst_metadata"] = {
        "lstat": m,
        "access_x_ok": a,
        "advisory_only": True,
    }
    if state == "PRECHECK_FAILED":
        outcome["next_step"] = (
            "A falha ocorreu antes de posix_spawn; não há prova de sandbox "
            "de execução. Confira os campos CHILD_* para localizar a etapa."
        )
    elif state == "OK":
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

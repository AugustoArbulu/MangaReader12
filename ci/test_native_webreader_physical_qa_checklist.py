#!/usr/bin/env python3
"""Native Swift-only physical QA template: all answers default to not tested."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "MangaReader12/Core/WebReaderPhysicalQAChecklist.swift"
SWIFT = r'''
import Foundation

func insist(_ value: @autoclosure () -> Bool, _ name: String) {
    if !value() { fatalError(name) }
}
let ios = OperatingSystemVersion(majorVersion: 12, minorVersion: 5, patchVersion: 8)
let report = WebReaderPhysicalQAChecklist.report(installedBuild: 69, ios: ios)
insist(report.contains("Build observada: 69 • iOS: 12.5.8"), "version correct")
insist(report.contains("Wi-Fi DESLIGADO"), "offline actual user check")
insist(report.contains("Webtoons / WeebCentral / Asura"), "source check")
insist(report.contains("Instalação automática continua BLOQUEADA?"), "helper denial check")
insist(report.contains("Backup mantido fora do iPad?"), "preserve backup")
insist(report.contains("Instalou por cima, sem remover"), "in-place update")
insist(report.contains("Fechou/reabriu o app ainda offline"), "offline relaunch")
insist(report.contains("Amostra offline: arquivos sequenciais"), "offline page inventory")
insist(report.contains("carregam integralmente?"), "real old-page reading")
insist(report.contains(".mr12backup NÃO inclui páginas offline"), "portable backup is not offline files")
insist(report.contains("Evitou restaurar backup por cima"), "no destructive restore during update")
insist(report.contains("RESTAURAR backup limpa downloads offline"), "restore hazard")
insist(report.contains("não apagar o app"), "avoid loss during failure")
insist(report.contains("não é diagnóstico automático"), "no automatic QA claim")
insist(report.contains("não lê biblioteca"), "privacy statement")
insist(!report.contains("/var/mobile/"), "no personal paths")
insist(!report.contains("PASS AUTOMATIC"), "never fake physical QA")
insist(!report.contains("APPINST ENABLED"), "no privilege enablement")
let checkLines = report.split(separator: "\n").filter { $0.contains("[SIM/NÃO/NÃO TESTADO]") }
insist(checkLines.count == 16, "all sixteen physical checks remain unanswered")
insist(report.utf8.count < 4096, "clipboard report bounded")

let invalid = WebReaderPhysicalQAChecklist.report(
    installedBuild: -1,
    ios: OperatingSystemVersion(majorVersion: 999,
                                minorVersion: 999, patchVersion: 999)
)
insist(invalid.contains("Build observada: desconhecida • iOS: desconhecido"),
       "invalid values sanitized")
print("PASS native Swift Build69 physical QA checklist: 16 unanswered checks + offline restore hazard, no install")
'''
with tempfile.TemporaryDirectory(prefix="wr69-manual-qa-report-") as tmp:
    root = Path(tmp)
    source = root / "main.swift"
    binary = root / "physical-qa-report"
    source.write_text(SWIFT)
    subprocess.run(["swiftc", "-swift-version", "5", str(SOURCE),
                    str(source), "-o", str(binary)], check=True, timeout=120)
    subprocess.run([str(binary)], check=True, timeout=45)

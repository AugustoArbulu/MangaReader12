# WebReader Build70 — Fase EG: código de saída obrigatório para estados STOP (12/11/2026)

PR #90 Draft na branch feat/chimera-updater-phase1-protocol-audit. main intocada; nenhum dispositivo foi acessado; nenhuma IPA71 emitida/entregue/instalada, nenhum arquivo de usuário criado/modificado, nenhum appinst executado.

## Falha corrigida

Os CLI das Fases EB, EC, ED, EE e EF já apresentavam estados JSON estruturados que começam por PREFIX_STOP_ quando detectavam informações incompatíveis ou inseguras. Porém esses estados gerados sem exceção terminavam o processo com exit code 0, geralmente interpretado por shell, GitHub Actions ou futuros scripts como sucesso. Exemplos: EB_STOP_COMPLETED_CHAPTER_COUNTS_DIFFER, EC_STOP_EXTERNAL_COPIES_DIFFER, ED_STOP_LIBRARY_ROWS_DIFFER, EE_STOP_EXPORTED_PREFERENCES_DIFFER e EF_STOP_HTML_OR_TRUNCATED_OFFLINE_FILES.

Agora todos esses CLI retornam exit code 2 quando status começa por PREFIX_STOP_, preservando o relatório JSON com estado e campos de autorização false. Os demais resultados, que são classificações informativas não certificadas, retornam exit code 0. A Fase EA já tratava erros com saída não zero.

IMPORTANTE: código 0 NÃO significa backup completo, identidade do iPad atestada, autorização de distribuição/instalação, disponibilidade de decodificação ou igualdade com bytes originais. Significa somente que a ferramenta não encontrou um estado STOP no material copiado submetido a ela.

## Implementação e regressão

- ci/build70_eb_copy_vs_device_text.py: STOP de contagens divergentes agora falha para shell.
- ci/build70_ec_full_container_dual_copy.py: cópias diferentes agora falham para shell.
- ci/build70_ed_portable_vs_external_library.py: divergência de registros SQLite agora falha para shell.
- ci/build70_ee_portable_preferences_plist.py: preferência diferente agora falha para shell.
- ci/build70_ef_offline_payload_triage.py: HTML/JSON e imagens truncadas agora falham para shell.
- ci/test_build70_eg_cli_fail_closed.py: subprocess real em ambientes sintéticos para os cinco CLI, com par positivo/STOP e verificações de que paths privados não vazem e nenhuma autoridade seja concedida.
- ci/test_build70_ef_offline_payload_triage.py: teste CLI anterior corrigido para exigir saída 2 para página HTML.
- .github/workflows/chimera-build70-phase-eg-cli-failclosed.yml: roda todas as regressões host-only EA–EG em Linux e macOS e confirma trigger IPA71 ausente.

O workflow não publica backups, dados ou IPAs. O processo lê apenas fixtures fictícios em diretórios temporários.

## Interpretação e limites

| Saída | Significado operacional |
|---|---|
| 0 + status informativo | Teste host terminou sem STOP detectado; NÃO comprova origem nem legitimidade do backup |
| 2 + status PREFIX_STOP_ | Falha bloqueante, requer revisão manual; não aceitar como etapa concluída |
| Exceção de parser/arquivo, saída não-zero | Falha de entrada, copiar novamente/verificar evidência, sem reparos automáticos |

Nenhum código de saída concede autorização de restauração, envio de IPA, appinst ou atualização automática. Uma futura automação deverá analisar OS DOIS: status JSON e código de saída, além de manter as decisões de consentimento e identidade independentes.

A validação macOS/Linux da revisão EG exige observar os jobs finais; não presumir sucesso antes de conferir a execução. O marcador ci/build71_owner_approved_qa_trigger.txt continua AUSENTE. productionPublicKeyX963=nil; independentlyProvisionedSPKISHA256=nil; liveInstallationEnabled=false.

A Build70 no iPad, biblioteca, favoritos, progresso e downloads permanecem intocados. A futura atualização da Build71 precisa de evidência física e aprovação separada para entrega e instalação.

# WebReader Build 64 FIX2 — identidade de atualização e QA (06/11/2026)

## Evidência física no iPad iOS 12.5.8 (Chimera + AppSync Unified)

- A IPA inicial Build64 unsigned foi rejeitada pelo Filza com erro: `Application is missing the application-identifier entitlement`.
- A Build64 FIX1 `WebReader-Build64-QA-iOS12-adhoc.ipa` tinha SHA-256 completo conferido e assinatura ad hoc com `application-identifier=WRQA000001.com.example.MangaReader12`. Filza rejeitou a atualização porque a instalação existente possui o App ID `AR5SFJC432.com.example.MangaReader12.AR5SFJC432`. Texto do Filza: `Upgrade's application-identifier entitlement string ... does not match installed application's application-identifier string ...; rejecting upgrade.`
- A rejeição não significa que o usuário uniu os fragmentos incorretamente. Também não significa que AppSync esteja ausente. O instalador faz verificação de identidade mesmo nessa configuração.

## Correção FIX2 (branch experimental, não main)

- Commit de código: `64cfe8a16ea81a98c080561db8f09edbcd63c67a`.
- Branch: `feat/chimera-updater-phase1-protocol-audit`; PR #90 permanece Draft.
- `ci/chimera_webreader_qa.entitlements`: o App ID assinado da IPA QA passa a ser **exatamente** `AR5SFJC432.com.example.MangaReader12.AR5SFJC432`, conforme informado pelo Filza no iPad.
- O empacotador `ci/package_webreader_build64_qa_ipa.sh` assina a cópia do app depois da mudança de `Info.plist` para build 64, verifica a assinatura e compara o entitlement extraído com o valor esperado. Não modifica a Build56 fonte nem a instalação física.
- `ci/test_webreader_build64_qa_ipa.py` verifica SHA-256, ZIP/IPA, bundle ID `com.example.MangaReader12`, build 64, mínimo iOS 12, arm64 Mach-O e entitlement dentro da assinatura final.
- `ci/check_build64_upgrade_compatibility.py`, já implementado, bloqueia publicação do artefato IPA se o App ID do candidato diferir da identidade instalada. `ci/test_build64_upgrade_compatibility.py` cobre aprovação da identidade correta e rejeições de identidade incorreta, assinatura não verificada, Bundle ID e build incorretos.
- Workflow `.github/workflows/chimera-build64-manual-qa.yml`: artefato esperado `WebReader-Build64-FIX2-ManualQA-iOS12` com `WebReader-Build64-FIX2-iOS12-adhoc.ipa`, SHA e relatórios; não publica release nem executa instalação.

## CI e distribuição

- Run da Build64 FIX2: https://github.com/AugustoArbulu/MangaReader12/actions/runs/42247451036
- Às 16:05 UTC de 06/11/2026: **queued**, sem resultado conclusivo nem nova IPA verificada.
- **NÃO enviar a FIX2 antes de SUCCESS e de confirmar artifact + checksum.** A FIX1 está reprovada para atualização sobre a Build56, não reutilizar.
- Preferência expressa do usuário: entregar provisoriamente a IPA testável no e-mail `gutoarbulu@icloud.com`; devido a limite de anexo de 3MB no conector Outlook, dividir em oito partes nomeadas `WebReader64FIX2.part00.bin` ... `part07.bin`, quatro partes por e-mail, comandos no corpo separados, cada linha independente.
- Instruções finais para o iPad serão geradas com o hash real da FIX2; não reutilizar o hash `ecde7...` da FIX1. O NewTerm2 do iPad suporta `sha256sum`, não `shasum`.
- Automação de acompanhamento horário condicional criada para verificar a run e avisar quando houver resultado, sem afirmar sucesso antecipado nem duplicar envio por e-mail. Conector de Outlook pode ou não disponibilizar os bytes em execução futura; não afirmar envio sem confirmação.

## Limites de segurança e QA físico

- CI testa assinatura ad hoc e **igualdade da string do App ID**, mas não comprova que o iOS 12 aceitará o upgrade; o instalado pode conter outros entitlements, certificado, `team-identifier` ou restrições não validadas neste momento.
- Filza e AppSync devem ser usados apenas para a atualização manual explícita depois de backup completo da biblioteca e dos capítulos offline.
- Nunca desinstalar Build56 como tentativa de corrigir conflito de identidade; isso poderá apagar dados.
- O usuário deve verificar abertura e biblioteca/capítulos offline após upgrade, se o Filza aceitar.
- Atualização automática via appinst permanece bloqueada no app; PING/IPC não autoriza instalação. Nenhum `main` alterado.

## Próximas ações

1. Aguardar run GitHub Actions FIX2; se falhar, analisar job/log e corrigir branch.
2. Somente após SUCCESS, obter artefato, validar hash e assinatura, enviar as partes e os comandos em linhas isoladas.
3. Teste físico voluntário depois de backup e confirmação no NewTerm de `OK`.
4. Se Filza reportar nova incompatibilidade, interromper e diagnosticar sem limpar dados nem desinstalar.

## Rechecagem de 06/11/2026 — 13h42 BRT

- A run [#42247451036](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42247451036) foi consultada novamente após o retry: job `verified-export-only`, ID `128013439234`, estado **queued**, sem steps iniciados, e a API retornou lista **vazia** de artifacts. Portanto **nenhuma IPA FIX2 verificável foi produzida** nesta consulta.
- Workflow conferido: runner `macos-15` com Xcode 16.4 e iOS SDK 18.5, build iOS12 arm64 e gate `upgradeIdentityMatch` antes de publicar a IPA. O empacotamento exige que a assinatura extraída contenha exatamente `AR5SFJC432.com.example.MangaReader12.AR5SFJC432`.
- A PR #90 permanece aberta, **Draft**, sem merge na `main`. Nenhuma mudança no app instalado, na assinatura ou no workflow foi feita nesta rechecagem.
- A página pública do GitHub Status registra interrupções recentes de Actions em 04–05/11, já resolvidas. Não há prova de que esses incidentes expliquem esta fila específica; a classificação permanece **runner pendente, causa não confirmada**.
- **Não disparar outro retry enquanto este job estiver queued; não enviar a FIX1; não inventar hash para FIX2.** Reavaliar jobs e artifacts quando o GitHub atualizar; apenas após SUCCESS e auditoria independente planejar entrega e instruções separadas para NewTerm2.

## Resultado final CI e entrega — 06/11/2026, 14h05 BRT

- **Execução definitiva:** [GitHub Actions #42255878642](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42255878642) no commit `bf110f8b515535f55c68f964e3b172bc244f2409`: job `verified-export-only` **SUCCESS**. Build iOS12 arm64, empacotamento assinado ad hoc, auditoria de identidade e upload passaram.
- **Artifact:** `WebReader-Build64-FIX2-ManualQA-iOS12` (ID `13523806218`), [download no GitHub](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42255878642/artifacts/13523806218), ZIP 17.682.268 bytes, SHA-256 `c0dc9ae80e741822948829a4520b504ef07d0451b33048c50db28ba96e3a49a7`.
- **IPA extraída:** `WebReader-Build64-FIX2-iOS12-adhoc.ipa`, 17.758.061 bytes, SHA-256 `fd4ea5ed60bee89fa12436202b5ca70cfd1108fb9ed85ad45c210465b247a0a9`. Auditoria independente: ZIP íntegro, manifesto e hash coincidentes, `Info.plist` com Bundle ID `com.example.MangaReader12`, Build `64`, iOS mínimo `12.0`, executável arm64. A assinatura ad hoc e entitlement passaram em `codesign --verify` no runner do GitHub.
- **Gate:** `upgradeIdentityMatch=true`, `application-identifier=AR5SFJC432.com.example.MangaReader12.AR5SFJC432` coincidente com a informação do Filza sobre a Build56. Isso **não garante** aceitação pelo iOS 12 em teste físico.
- **Entrega:** dois e-mails para `gutoarbulu@icloud.com`, partes `WebReader64FIX2.part00.bin` a `part07.bin` em grupos de 4, com comandos separados, anexos confirmados na pasta de mensagens enviadas do Outlook. SHA da IPA informado nas instruções. Existe também IPA integral no pacote para download direto.
- **Automação:** acompanhamento horário da Build64 FIX2 desativado após conclusão e confirmação do envio, para não duplicar entregas.
- **Próximo teste físico:** backup da biblioteca e capítulos offline; nunca desinstalar Build56; juntar as 8 partes se usar e-mail; validar SHA-256 com `sha256sum`; tentar upgrade somente manual via Filza. Se rejeitar, anotar o erro e parar, sem limpar dados ou usar FIX1.
- **Escopo:** somente branch experimental, PR #90 continua Draft. Nenhuma instalação remota, appinst automático, publicação de release ou merge em main foi executado.

# WebReader Build70 — Fase DK: integração das evidências de IPA 71 e continuidade da biblioteca

**Data:** 10/11/2026 (Brasília); a CI pode registrar 11/11 UTC. Repositório privado `AugustoArbulu/MangaReader12`. Trabalho somente em `feat/chimera-updater-phase1-protocol-audit`, PR #90 Draft. Não fazer merge na `main`. A Build70 já instalada no iPad iOS12.5.8, biblioteca, favoritos, progresso e capítulos offline continuam intocados.

## Ponto de partida

- **DI:** https://github.com/AugustoArbulu/MangaReader12/actions/runs/42935290104 — SUCCESS 2/2. O Ubuntu executou 16 testes do preflight privado 70→71 e 22 do preview DH; o macOS 16 testes host e **9 testes com codesign ad-hoc nativo sobre IPAs sintéticas descartáveis**. A DI nunca assina ou distribui o aplicativo real.
- **DJ:** https://github.com/AugustoArbulu/MangaReader12/actions/runs/42944438413 — Ubuntu 21/21 PASS; job macOS ainda em fila na última consulta. DJ verifica o texto exato das **nove contagens SQLite** do `WebReaderUpgradeContinuitySnapshot.swift`, que a Build70 já permite copiar sem alterar o banco.
- **DH:** SUCCESS 2/2, compilou Build71 **unsigned**, sem gerar IPA, checou Info.plist, iOS12.0 e ARM64. **Nenhuma Build71 foi instalada.**
- O pré-flight antigo `ci/build70_private_qa_ipa_preflight.py` continua **exclusivo para Build69→70**. O estado de aprovação da antiga build não pode ser reaproveitado como aceite para a 71.

## O que a DK entrega

O novo `ci/build70_dk_qa_evidence_bridge.py` conecta **três inspeções somente leitura** no mesmo procedimento:

1. **Código-fonte da candidata:** `inspect_dh_source()` confirma o projeto-fonte ainda na versão de origem 56, QA alvo 71, baseline físico conhecido 70, botão DG para UID/GID do próprio WebReader e os hard stops editoriais/instalação.
2. **Contagem da biblioteca:** lê o texto `--before-report` no formato canônico da Build70, iOS12.5.8 e schema v1, com todas as nove contagens e avisos de que offline exige teste real. Um `--after-report` da Build71 é opcional; se fornecido, requer a versão 71 e compara todos os nove campos. Qualquer diferença, inclusive aumento legítimo de capítulos, exige análise humana. O texto do clipboard pode ser falsificado e **não é atestado**.
3. **IPA candidata:** usa o preflight DI sobre um `--ipa` de nome fixo `WebReader-Build71-iOS12-adhoc.ipa` e o SHA fornecido em `--checksum-file` de uma única linha. O DI abre por único FD com `O_NOFOLLOW`, confere tamanho/ZIP/assinatura do snapshot imutável em memória, versão 71, minOS12, ARM64 e o entitlement histórico. A DK compara explicitamente o SHA declarado ao resultado da DI, o CDHash, tamanho e **todos os campos de permissão falsa**; qualquer inconsistência rejeita.

A DK não produz, assina ou distribui esse arquivo. Uma IPA real **ainda não existe** nesta fase. Os testes de integração usam mocks claramente identificados no Linux e **uma IPA sintética e temporária assinada pelo macOS** para testar o caminho real de `codesign`, sem salvar nem publicar a fixture.

### Estados possíveis

| Estado de observação | Significado restrito |
|---|---|
| `DK_HOST_PACKAGE_CHECKED_BASELINE_TEXT_ONLY_NO_DISTRIBUTION` | No host, DI analisou uma IPA existente e o relatório Build70 tem formato esperado. **Não** comprova que a Build70 no iPad apresentou aqueles dados |
| `DK_EQUAL_COUNT_TEXT_NOT_OFFLINE_OR_INSTALL_PROOF` | Os nove números escritos nos relatórios 70/71 são iguais. Não confirma as **linhas** do SQLite, as páginas de imagens, nem uma instalação legítima |
| `DK_STOP_COUNT_DIFFERENCE_OWNER_REVIEW_REQUIRED` | Algum número mudou; indica **apenas os rótulos alterados**, sem exportar contagens, títulos ou dados privados. Qualquer variação demanda avaliação |

Os recibos de todas as três situações mantêm **false** em `reportsIndependentlyAuthenticated`, `deviceBuild70IdentityAttestedNow`, `actualBuild71InstallationProven`, `libraryContentsVerified`, `offlinePageFilesVerified`, `physicalOfflineChapterOpened`, `beforeAfterReportsGenuinelyCapturedOnDevice`, `backupPreservedOutsideDevice`, `sameIPABytesConsumedByAppleInstaller`, `publisherIdentityTrusted`, `helperIPCAuthenticated`, `productionEditorialTrustConfigured`, `ownerDistributionApprovalRecorded`, `readyToDistributePrivateIPA`, `readyToInstall`, `installationAuthorized` e `installationPerformed`.

### Uso de auditoria (apenas quando um artefato privado tiver sido autorizado separadamente)

```sh
python3 ci/build70_dk_qa_evidence_bridge.py \
  --ipa /caminho/privado/WebReader-Build71-iOS12-adhoc.ipa \
  --checksum-file /caminho/privado/checksum.sha256 \
  --before-report /caminho/privado/contagens-build70.txt
```

O arquivo `--after-report` só fará sentido depois de um eventual teste **manualmente autorizado e instalado** e não significa que o app verifique a origem desse arquivo. Executar a auditoria antes da instalação **não produz** uma IPA, nem cria autorização de distribuí-la.

### Testes e CI

- `ci/test_build70_dk_qa_evidence_bridge.py`: 16 testes host com **mock do DI explicitamente falso** e parser real DJ: checksum e versão errados, falta de baseline, banco indisponível, aumento ou queda em qualquer contagem, falsificação de identidade/códigos de assinatura, ausência de flags de bloqueio, e garantia de que nada promove permissão de instalação. Não usar os recibos simulados como evidência de autenticação Apple.
- `ci/test_build70_dk_qa_evidence_native.py`: macOS/Xcode16.4 constrói em diretório descartável um pequeno programa iOS12 ARM64, assina ad-hoc o bundle com entitlement sintético, cria somente IPA de fixture local e exercita a **mesma API DK** com relatórios 70/71 sintéticos. Testa baseline, números iguais e diferença de downloads. `TemporaryDirectory` exclui a fixture no fim. Nenhum pacote do WebReader é assinado nem entregue.
- Workflow `.github/workflows/chimera-build70-phase-dk-evidence-bridge.yml`: Ubuntu (DK e regressão DJ) e macOS (DK e integração nativa), com `contents: read`. Não contém `upload-artifact`, release, `appinst`, IPA publicada ou gatilho de instalação.

## Verificações obrigatórias para um futuro teste físico (não executadas)

A Build70 instalada permite **Atualizações → Segurança → Copiar contagens da biblioteca para comparar**. Se houver uma nova versão QA aprovada por solicitação explícita, a comparação não substitui: (1) conferir o Bundle ID e application-identifier atual da Build70 no iPad; (2) fazer backup fora do iPad sem restaurá-lo; (3) abrir um capítulo já baixado, com Wi-Fi desligado, antes da atualização; (4) instalar **por cima**, não excluir WebReader; (5) conferir biblioteca, favoritos, progresso e contagens; (6) testar o mesmo capítulo página a página e reabri-lo ainda offline; (7) recusar qualquer re-download silencioso apresentado como preservação dos dados originais.

O backup `.mr12backup` NÃO guarda páginas de imagens; restaurar o banco pode apagar os downloads. Não sugerir restauração automática como rollback de IPA. Sem um helper real com identidade IPC autenticada, journal protegido, confiança editorial P-256 provisionada, consentimento independente e cadeia de bytes até o instalador, a **atualização automática ainda não está autorizada**.

**Travas:** `WebReaderUpdateChannel.productionPublicKeyX963=nil`; `WebReaderProductionPublisherTrust.independentlyProvisionedSPKISHA256=nil`; `WebReaderAppinstSocket.liveInstallationEnabled=false`. `main`, Build70, biblioteca, IPAs e Releases intactos.

**CI DK:** preencher resultados somente após consultar logs finais. A aprovação de testes host não equivale a prova física nem a consentimento para distribuição.

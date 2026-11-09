# WebReader — Build 69, fase BC: integridade após transferência de IPA privada

**Data:** 2026-11-09 UTC. **Branch de engenharia:** `feat/chimera-updater-phase1-protocol-audit`. **PR [#90 Draft](https://github.com/AugustoArbulu/MangaReader12/pull/90)**. Não alterar `main`, publicar GitHub Release, ativar o instalador Chimera ou substituir a Build68.

## Base confirmada

- A CI AC–BB [#42556649811](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42556649811) terminou **SUCCESS em 2/2 jobs**: Linux offline + macOS nativo, incluindo a compilação efêmera unsigned com `CURRENT_PROJECT_VERSION=69` e testes com **IPA sintética** iOS12 ARM64 assinada ad hoc em `TemporaryDirectory`.
- A Build68 permanece a referência aprovada no iPad iOS 12.5.8; biblioteca e capítulos offline não foram acessados. Na árvore experimental o Xcode ainda declara `CURRENT_PROJECT_VERSION=56`, preservado intencionalmente até haver autorização de candidata real.
- [Handoff BA](WEBREADER_BUILD69_PHASE_BA_ISOLATED_UNSIGNED_PREVIEW_2026-11-09.md) e [Handoff BB](WEBREADER_BUILD69_PHASE_BB_PRIVATE_QA_IPA_ADMISSION_2026-11-09.md). **Nenhum arquivo `.ipa` real Build69 foi produzido ou disponibilizado.**

## Problema abordado na BC

A auditoria BB aceita um arquivo IPA no **host de construção** e devolve SHA-256, tamanho, identidade assinada ad hoc, CDHash e versão. Isso **não** prova que o arquivo copiado para PC/Android/Filza seja idêntico. Um arquivo pode ser truncado, modificado, renomeado ou trocado durante uma transferência. É importante detectar isso antes da futura operação de instalação manual.

## Novo gate host de transferência

Arquivo: `ci/build69_bc_copied_ipa_recheck.py`.

Quando, *e somente quando*, existir uma IPA privada QA Build69 aprovada e auditada pelo BB, a verificação de cópia:

1. Requer um arquivo chamado exatamente `WebReader-Build69-iOS12-adhoc.ipa`, fora da árvore fonte e não symlink.
2. Requer o **recibo completo** do auditor BB (`HOST_ONLY_PRIVATE_QA_PREFLIGHT_NOT_DISTRIBUTION_APPROVAL`) e arquivo de checksum `SHA-256  filename` fornecido por um canal de confiança independente. Esses arquivos não são criados pelo gate BC.
3. Recusa JSON malformado, campos duplicados, `NaN`/`Infinity`, versões e bundle ID diferentes, assinatura ad hoc ou identidade previamente não conferidas e qualquer recibo que tente reivindicar autorização de instalação, publicação, QA física ou autenticação editorial.
4. Calcula SHA-256 de um **único descritor `O_NOFOLLOW`** do arquivo copiado, limitado a 512 MiB, com tamanho, inode e timestamps verificados antes/depois. Faz confronto entre **hash calculado**, **hash registrado no recibo** e **hash recebido separadamente**, além do tamanho exato.
5. Retorna apenas `COPIED_BYTES_MATCH_HOST_RECEIPT_ONLY` e campos de diagnóstico. `ownerChecksumIndependenceProvenByTool=false`, `hostReceiptAuthenticityProvenByTool=false`, `editorialPublisherAuthenticated=false`, `authorizedForInstallation=false`, `installationPerformed=false`. **Um checksum e um recibo forjados em conjunto podem coincidir; o script não consegue autenticar a procedência.**

Comando para uso *futuro*, após ter sido feita uma cópia autorizada:

```bash
python3 ci/build69_bc_copied_ipa_recheck.py \
  --copied-ipa /outside/repo/WebReader-Build69-iOS12-adhoc.ipa \
  --host-receipt /outside/repo/build69-BB-host-receipt.json \
  --owner-checksum-file /owner-independent/WebReader-Build69-iOS12-adhoc.ipa.sha256
```

O arquivo de recibo de origem só deve ser considerado confiável após conferência fora de banda pelo proprietário. Não colocar chaves privadas, credenciais GitHub ou PIN de login em nenhum desses arquivos. Revalidar assinatura de código e entitlements pelo auditor BB do macOS sobre a IPA real, não pelo BC no Android/PC.

## Testes negativos e CI

`ci/test_build69_bc_copied_ipa_recheck.py` roda sobre bytes **sintéticos e descartáveis**, não faz `codesign`, nem instala nada. Exercita:

- cópia exata que retorna status restrito;
- alteração de um byte com tamanho igual, truncamento, checksum errado, SHA/tamanho conflitante;
- versão 68, identidade incorreta, status de aprovação falso, assinatura ausente, alteração de flags de segurança;
- recibos com JSON duplicado, JSON truncado, número não finito, tamanho acima do limite;
- arquivo de nome diferente e symlink mesmo com nome correto.

O CI integrado `.github/workflows/chimera-build69-phase-ac-af-integrated-qa.yml` executa esse teste Linux em conjunto com toda a bateria antiga e continua fazendo compilação nativa Debug/Release/preview iOS12 sem `upload-artifact` de IPA.

[Workflow AC–BC #42562459699](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42562459699): iniciada; conferir conclusão antes de afirmar aprovação completa.

## Gates e próximos passos

| Gate | Estado |
| --- | --- |
| Código BB e CI AC–BB | **Aprovado** (2/2 jobs) |
| Teste de integridade pós-transferência BC | Implementado; resultado CI a confirmar |
| Build69 real assinado ad hoc e empacotado | **NÃO PRODUZIDO** |
| Identidade `application-identifier` idêntica à Build68 no iPad | Só contrato de teste; a IPA real ainda não existe |
| SHA de IPA privada transmitido por canal independente | Pendente |
| Confiança editorial ECDSA `production` | Não provisionada |
| Autorização do proprietário para distribuição e teste físico | Não recebida neste avanço |
| QA física de preservação de biblioteca e leitura sem Wi-Fi | Pendente |
| GitHub Release, `main`, instalador automático Chimera | **Não alterados; instalação bloqueada** |

**Cuidado com backup:** `.mr12backup` não preserva páginas offline e restaurar esse arquivo apaga downloads existentes. A futura atualização deve instalar uma IPA aprovada **por cima**, sem apagar a versão atual, seguida dos 14 testes de QA. Se houver erro, não restaurar automaticamente nem limpar a biblioteca.

Próximo trabalho sugerido: fechar CI BC e preparar o gate de revisão de uma futura **entrega privada** com recibo BB autenticado separadamente; isso é distinto da ativação do canal de produção e da futura autenticação do helper Chimera.

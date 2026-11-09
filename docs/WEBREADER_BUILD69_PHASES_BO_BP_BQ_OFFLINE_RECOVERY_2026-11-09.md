# WebReader — Build 69: fases BO, BP e BQ (retomada, inspeção em lotes, recuperação segura)

**Data:** 2026-11-09 UTC. **Branch:** `feat/chimera-updater-phase1-protocol-audit`; **[PR #90 Draft](https://github.com/AugustoArbulu/MangaReader12/pull/90)**. Não modificar `main`, nem a Build68 instalada no iPad iOS 12.5.8, nem excluir arquivos de páginas. Instalação via Chimera permanece desligada; nenhum IPA da Build69 real foi emitido.

## Ponto de partida validado

[CI AC–BN #42570725651](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42570725651) — **SUCCESS nos dois jobs**. Inclui testes Swift nativos, Debug e Release para ARM64/iOS12, compilação isolada unsigned com override `CURRENT_PROJECT_VERSION=69`, assinatura ad hoc de **uma cópia temporária do WebReader real** (não de um aplicativo fictício), conferência do `application-identifier`, CodeDirectory e eliminação da cópia. Não produziu ou distribuiu IPA. [Handoff BN](WEBREADER_BUILD69_PHASE_BN_REAL_APP_EPHEMERAL_ADHOC_REVIEW_2026-11-09.md).

As fases BH–BM já impedem páginas offline com índice faltante, arquivos vazios e links simbólicos, além de registrar a contagem esperada **só para downloads novos**. A Build68 não possuía recibos: os capítulos legados continuam legíveis sem eles.

## BO — retomada de downloads sem reutilizar links e arquivos perigosos

**Problema encontrado:** `ChapterDownloadManager.completedPagePrefix` validava uma página de transferência interrompida por `fileManager.attributesOfItem` e `size > 0`. Não exigia arquivo regular, não symlink, nem limitava tamanho. Por isso um symlink ou diretório nomeado `page-0000N.bin` poderia ser considerado uma página reaproveitável, contaminando a retomada.

**Implementação:** `MangaReader12/Downloads/WebReaderOfflineResumePrefix.swift`, compilada no target iOS12 (PBX ID 47), com `count(directory:plannedPages:fileManager:)`. A rotina:

- recusa pastas symlink, caminhos sem diretório e planos inválidos/maiores que **5.000 páginas**;
- percorre `page-%05d.bin` desde 0 e para **na primeira posição ausente, vazia, não regular, symlink ou maior que 20 MiB**;
- devolve o tamanho do prefixo válido para **rebaixar somente o índice de retomada**, nunca mover, apagar ou alterar imagens;
- não faz requests, decodificação nem reparo automático. O download já existente pode baixar de novo uma página que ficou parcial, sem considerar o placeholder como concluído.

`ChapterDownloadManager` passa a usar essa rotina onde antes usava atributos básicos. Testes `ci/test_native_webreader_offline_resume_prefix.py` (Swift real + arquivos sintéticos) e `ci/test_build69_bo_resume_prefix_policy.py` cobrem pasta ausente, índice faltando, symlink, diretório com nome de página, arquivo vazio, sequência de páginas e limite de plano. Nenhum download real é acessado.

## BP — inspecionar TODA a biblioteca offline em lotes de até 64

**Problema encontrado:** o diagnóstico BI da tela de Atualizações sempre consultava os **primeiros 64 downloads completos**. Se o usuário possuísse 500 capítulos, os demais nunca seriam avaliados pelo botão. Não havia necessidade de ler todos simultaneamente no iPad antigo.

**Implementação:**

- `WebReaderOfflinePreservationAudit.diagnostic(installedBuild:ios:sampleOffset:applicationSupportOverride:)` recebe deslocamento validado e consulta banco com `LIMIT ? OFFSET ?` e `sqlite3_bind_int64` (sem concatenar SQL). Mantém conexão `SQLITE_OPEN_READONLY`, transação consistente e `sqlite3_busy_timeout=200`. Apenas **até 64 entradas** são inspecionadas por execução.
- Para uma lista de 66 capítulos, o primeiro lote observa 64, o segundo observa 2 e o próximo retorna à posição 0. A função devolve o `nextOffset`, com o índice do lote no relatório e a quantidade que **não** entrou nele. Cabeçalhos continuam limitados e não incluem títulos, IDs, URLs ou caminhos.
- A tela **Atualizações → Segurança → Conferir presença dos capítulos offline** guarda `offlineSampleOffset` em memória e o atualiza **na thread principal**, somente após a consulta assíncrona. Toques duplicados continuam bloqueados e a leitura nunca ocupa a thread de interface.
- A antiga `report(...)` foi mantida como wrapper do lote inicial, preservando compatibilidade com testes e consumidores antigos. `sampleOffset` incorreto é rejeitado ou reinicia no 0 quando passa do número total. A execução nunca altera o banco, remove imagens ou declara que os conteúdos podem ser decodificados.

Testes: `ci/test_native_webreader_offline_preservation_audit.py` foi ampliado para lotes 0, 64 e rollover 128 em SQLite sintético com **66 registros**, incluindo URLs fictícias, páginas faltando e recibos de quantidade. `ci/test_build69_bp_offline_paging_policy.py` confirma bind parametrizado, limites, ordenação e controle assíncrono; regressão BI existente ajustada.

**Limite honesto:** se obras forem adicionadas/removidas enquanto o usuário percorre lotes, a sequência pode repetir ou deixar de mostrar algum registro, pois cada toque abre um novo snapshot. A ferramenta é diagnóstico local, **não é um inventário forense único e congelado**. Não prova conteúdo decodificável nem dispensa ler capítulos offline inteiros com Wi-Fi desligado.

## BQ — não carregar plano de recuperação corrompido sem limite

**Problema encontrado:** na inicialização, `restorePreviousSession()` usava `Data(contentsOf: planURL)` num `_download-plan.json` salvo por downloads interrompidos. Antes de validar o schema/limite de 5.000 páginas, poderia alocar um plano malformado ou enorme, ou seguir um symlink.

**Implementação:** `MangaReader12/Downloads/WebReaderOfflineRecoveryPlanReader.swift` (PBX ID 48), um leitor POSIX de metadados **somente de arquivo local**:

- abre `O_RDONLY | O_NOFOLLOW | O_NONBLOCK` e valida `fstat` para exigir arquivo **regular**; rejeita symlink, diretório, FIFO sem bloquear e arquivos vazios;
- exige tamanho máximo de **16 MiB**, lê de um único descritor em blocos de 64 KiB e compara dispositivo/inode/tamanho/mtime/ctime entre antes e depois da leitura;
- fecha o fd, não cria arquivos, não envia dados e não faz migração. Se o arquivo está alterado, truncado ou ilegível, falha e o fluxo existente mantém **as imagens do capítulo intactas** para diagnóstico e possível nova tentativa;
- conserva `JSONDecoder` e as checagens já existentes de `schemaVersion=1`, source ID, manga ID, chapter ID e máximo de 5.000 páginas.

Testes `ci/test_native_webreader_offline_recovery_plan_reader.py` compilam Swift puro em macOS, verificam dados pequenos, arquivo vazio, arquivo de 16MiB+1 bytes, diretório, symlink, FIFO sem writer e ausência de arquivo, todos temporários. `ci/test_build69_bq_recovery_plan_policy.py` assegura leitura limitada/nofollow e nenhuma operação de escrita.

## CI e segurança de entrega

Integrado em `.github/workflows/chimera-build69-phase-ac-af-integrated-qa.yml`, workflow **AC–BQ**, com testes Linux e macOS/Swift, Xcode Debug/Release e prévia unsigned 69, seguida da auditoria ad hoc efêmera da BN. A execução consolidada é [#42572758345](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42572758345). **Verificar status e corrigir falhas antes de afirmar sucesso.** Outras execuções anteriores podem aparecer como canceladas pela concorrência.

| Gate | Situação |
|---|---|
| BO–BQ na branch experimental | Implementadas |
| CI AC–BN anterior | **SUCCESS 2/2** |
| CI AC–BQ consolidada | **Em validação no momento do registro** |
| Build68 iPad, biblioteca e offline existentes | Intocados |
| Build69 IPA assinada e distribuída | **NÃO PRODUZIDA** |
| Assinatura editorial de produção e helper Chimera | Não habilitados |
| PR #90 e `main` | Draft; `main` inalterada |

A futura IPA QA privada requer aprovação específica de empacotamento/distribuição. Antes de instalá-la por cima, exportar `.mr12backup` para outro dispositivo **sem restaurá-lo**; a restauração apaga downloads porque as imagens não fazem parte do backup. O usuário deverá verificar as 16 etapas de QA e ler capítulos antigos até o final, sem Wi-Fi, inclusive após fechar/reabrir o WebReader.

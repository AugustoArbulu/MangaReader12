# WebReader Build70 — Fase FG: API de prévia somente leitura no gerenciador de downloads
Data: 13/11/2026 · PR #90 Draft

Após CI FE 250/250 Ubuntu+macOS e CI FF com 4 testes de gate aprovado, a FG expõe `ChapterDownloadManager.previewOfflineDeletionCandidates(from:)` para consumir **um snapshot de metadados fornecido pelo chamador**, sem consultar SQLite, iniciar o singleton, modificar a fila ou escrever no filesystem. Uma lista acima de 5.000 linhas é recusada. IDs de fila duplicados ou job ativo fazem **todos os candidatos afetados** exigirem revisão. A prévia usa os critérios do gate FF (completado, owner inequívoco, ausência de plano privado e preflight ER).

A estrutura `WebReaderOfflineDeletionV2AuditItem` guarda apenas os IDs e `requiresReview/provisionalCopyOnly`. Um resultado provisório torna-se obsoleto imediatamente, não é a autorização para apagar, migrar SQLite, restaurar arquivos ou certificar snapshot. Este código é adicionando à branch de desenvolvimento, **sem UI e sem chamadas de produção**.

QA FG executa código Swift extraído do método real contra fixtures temporárias, cobra ausência de `repository`, escritas, rede, filas removidas e duplicidades. A confirmação definitiva exige CI macOS com target iOS12 e compilação integral do app, sem IPA. A próxima etapa técnica é integrar o journal de cópia completo em uma rota *shadow-only*, ainda desativada.

Nenhuma alteração em `main`, Base do iPad, AppInst, trust SPKI, dados de usuário ou releases. Sem Build71 autorizada.


## CI concluído
- Fase FE, laboratório EV–FD: [#43530797187](https://github.com/AugustoArbulu/MangaReader12/actions/runs/43530797187): SUCCESS Ubuntu 24.04 + macOS 15, 250 testes da suíte EV–FD e typecheck de alvo iOS12.
- Fase FF, guarda inerte de três rotas: [#43531982100](https://github.com/AugustoArbulu/MangaReader12/actions/runs/43531982100): SUCCESS Ubuntu + macOS, quatro testes FF e typecheck iOS12.
- Fase FG, API de prévia: [#43532683927](https://github.com/AugustoArbulu/MangaReader12/actions/runs/43532683927): SUCCESS Ubuntu + macOS, três testes FG e typecheck iOS12.
- O primeiro run FG [#43532632090](https://github.com/AugustoArbulu/MangaReader12/actions/runs/43532632090) falhou pela tentativa de chamar uma função Swift throwing dentro da autoclosure não-throwing de `precondition` no *harness*; corrigido em `9cce266bfe75b4a97871d3b2c481f31c81d2e5d4` com `try!` em fixture sintética. O run subsequente passou integralmente.

**Limitação:** Estes são testes de laboratório e um typecheck isolado para iOS12, não testes físicos no iPad e não prova de integração do journal ou exclusão física. Nem a ferramenta de cópia FD nem o journal v2 estão disponíveis nas três rotas produtivas. Nenhum instalador foi autorizado.

# WebReader — Fase FA: schema v1 integral e coordenador de cópia nas três rotas

**Data:** 13/11/2026. **Natureza:** laboratório sintético; **não é patch integrável nem código iOS instalado**.

## Entregas deste bloco

1. `ci/fixture_build70_schema_v1_exact.sql`: fixture SQL transcrita da constante `SQLiteDatabase.schemaV1` em `MangaReader12/Database/SQLiteDatabase.swift`, PR #90, HEAD observado `5ce810d2a7829bf4471c982c693abad6b4018d04` (sem mudança de branch). Contém as **11 tabelas** `manga`, `library`, `chapters`, `categories`, `manga_categories`, `history`, `downloads`, `sources`, `repositories`, `source_settings`, `migration_map` e índices declarados `idx_manga_source`, `idx_chapters_manga`, `idx_downloads_state`. Ainda não é auditoria automatizada contra a versão *futura* do upstream.
2. `ci/build70_fa_full_schema_shadow.py`: cria um banco sintético v1 com registros conectados em todas as tabelas e usa o migrador EY para produzir apenas `shadow_library_v2.sqlite`. Compara estrutura, índices e linhas da versão anterior, incluindo marcação de lido, progresso, favoritos, downloads e relacionamentos; recusa drift de schema, versão futura, corrupção FK e sobreposição de cópia. Inclui WAL, rollback e `os._exit` antes de COMMIT. **Não abre `library.sqlite` real.**
3. `ci/build70_fa_copy_only_router.py`: coordenador de laboratório para `prepare_single`, `prepare_bulk` e `reindex_preview`, com consentimento explícito para simulação, verificação de job ativo, checagem de todos os capítulos do lote antes de modificar o journal, detecção de colisão de caminho e comparação de inode + *fingerprint* SHA256 de páginas fictícias antes de cada cópia. Usa o Swift EV/EZ para efetuar somente snapshot; reindex só informa, sem deletar nada.
4. `ci/test_build70_fa_full_schema_shadow.py` e `ci/test_build70_fa_copy_only_router.py`: **42 testes FA novos**, total local **151/151** EV–FA no Linux. Um teste adversarial mostrou que páginas podem mudar dentro do mesmo inode entre admissão e execução; adicionou-se fingerprint por descritores, tamanho e limites por lote. **A janela entre esta verificação e a cópia nativa permanece**, portanto isso é detecção aprimorada, não prova de atomicidade.
5. Workflow manual Ubuntu + macOS (`.github/workflows/webreader-build70-phase-fa-full-schema-copy-router.yml`) preparado mas **não executado**. `macos-15` e SDK iOS 12 ainda não verificados.

## Cobertura local

- EV: 13 (quarentena Python)
- EW: 15 (Swift fd/rename no laboratório)
- EX: 22 (journal SQLite e reconciliação)
- EY: 26 (schema parcial shadow e corrida de diretórios)
- EZ: 33 (snapshot sem delete e journal de cópia)
- FA: 42 (schema v1 integral em fixture e roteador sintético single/bulk/reindex)
- **Total: 151 / 151 testes passando** com Python 3.13.5 e Swift 6.2.1 no Linux.

## O que NÃO está resolvido

- O roteador FA usa SQLite **mínimo de laboratório**, e o teste do schema integral usa uma **outra** fixture; eles **não foram integrados entre si** ou ao verdadeiro `DownloadRepository` do WebReader.
- `ChapterDownloadManager.remove`, `removeAllConfirmed` e `DownloadRepository.removeMissingFiles` no branch continuam usando suas implementações antigas; não há feature flag ligada ao aplicativo.
- A cópia Swift EZ admite exclusivamente `page-#####.bin`: capítulos com `_download-plan.json` e recibo de conclusão devem ter proveniência e cópia verificadas antes da integração.
- Não é uma operação de exclusão efetiva: páginas originais e linhas de download continuam presentes. **Nunca transformar snapshot validado em permissão implícita para delete.**
- Nenhum teste APFS/macOS/iOS 12, nenhuma garantia durável entre banco e filesystem, nenhuma prova de rollback de app antigo após migração v2, nenhuma cópia da biblioteca física do iPad testada, nenhuma liberação de Build71.
- Operação simultânea com outra instância do app ou escritor malicioso pode surgir entre preflight e cópia. Prefixos SQL e metadados não são bloqueios de filesystem; o backend deve manter falha fechada.

## Critérios para o próximo bloco FB

1. Rodar CI Swift/APFS no macOS e compilar com a toolchain compatível com deployment target iOS 12, sem acesso à biblioteca real.
2. Integrar **em shadow-only** o schema v1 completo com um journal v2 de cópia, sem alterar o DB real e sem usar um banco sintético de formato divergente.
3. Adaptar plano de download e recibo de conclusão com verificação dos dados originais, mantendo cópia somente de arquivos reconhecidos.
4. Aplicar um adaptador Swift tipado no código real **somente atrás de feature flag desligada** após testes e revisão. Nenhuma exclusão automática por reindexação.

**Barreiras preservadas:** `main`, iPad, Build70 instalada, `library.sqlite` real, releases, IPAs, `appinst` e trust SPKI não alterados; PR #90 Draft. Artefatos localizados no ZIP da conversa, não commitados no GitHub nesta rodada.

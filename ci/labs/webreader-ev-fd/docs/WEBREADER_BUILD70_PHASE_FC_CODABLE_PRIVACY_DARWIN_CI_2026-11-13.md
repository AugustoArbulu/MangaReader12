# WebReader Build70 — Fase FC: compatibilidade Codable, privacidade e CI Darwin

**Data:** 13/11/2026. **Base:** EV–FB, 203 testes locais; **FC:** 20 testes novos. **Total local:** 223/223, Linux / Swift 6.2.1.

## Escopo real desta rodada

1. **Divergência encontrada e corrigida:** o `FBPlanEnvelope.Work.status` do laboratório aceitava qualquer `String`, enquanto `MangaStatus` no aplicativo (`MangaReader12/Core/Models.swift`) é um enum `Codable` restrito a `unknown`, `ongoing`, `completed`, `hiatus` e `cancelled`. O guard na admissão `fbInventory` agora recusa os outros valores.
2. **Cabeçalhos sensíveis:** o plano de download armazena `Page.headers: [String:String]`. Esse campo pode incluir cookies ou autorização. Para reduzir a duplicação desses dados no snapshot **do laboratório**, a admissão agora exige `plan.pages.allSatisfy { $0.headers.isEmpty }`. O plano original não é alterado; se os cabeçalhos não estão vazios, **falha fechada** antes da cópia. Isso não é um mecanismo de sanitização, criptografia ou proteção de URLs assinadas: `imageUrl` e `script` também podem conter segredos. É vedado copiar planos reais até existir uma política de privacidade provada.
3. **Compatibilidade Swift:** `ci/fixtures/FCAppCodableModels.swift` reproduz os campos/tipos `Codable` necessários dos modelos de Build70 (`Manga`, `Chapter`, `Page`, `SourceManifest`, `DownloadRecoveryPlan`) e inclui o envelope FB copiado mecanicamente do código Swift do laboratório. `ci/fixtures/FCParityRunner.swift` compila os dois decodificadores Swift e compara sua aceitação em 15 casos de teste. Essa fixture é uma **transcrição auditável**, não um import compilado diretamente do projeto Xcode ou prova de equivalência futura. Casos de rejeição adicional do laboratório (header, contiguidade, schema) são intencionais.
4. **Verificação nativa do caminho real:** os cinco testes FC restantes compilam `ci/build70_ev_fd_quarantine.swift`, criam apenas uma raiz temporária marcada e confirmam que um plano com status inválido ou cabeçalhos sensíveis é recusado **sem criar quarentena nem alterar páginas**.
5. **CI Apple real solicitado:** foi commitado **apenas um workflow não destrutivo** em `.github/workflows/chimera-build70-phase-fc-darwin-fd.yml`, commit `16b804b766a4d46823565126bea4bb1ecb89e2ec`, no PR #90 / branch `feat/chimera-updater-phase1-protocol-audit`. O workflow é disparado por `push` no próprio arquivo e permite `workflow_dispatch`. Ele compila um probe autocontido de `openat/fstatat/renameatx_np(RENAME_EXCL)` no macOS e tenta `-typecheck` para `arm64-apple-ios12.0`, sem IPA, instalação ou dados de usuário. **Ele não compila os 223 testes EV–FC do ZIP**, pois esses arquivos ainda não estão commitados no repositório. Resultado da execução deve ser lido no GitHub Actions; não inferir sucesso enquanto ainda estiver na fila.

## Execução local

```sh
cd webreader_ev_lab
PYTHONWARNINGS=ignore::ResourceWarning python3 -m unittest discover -s ci -p 'test_build70_*.py' -q
# Ran 223 tests ... OK
```

O `PYTHONWARNINGS` silencia ResourceWarning emitido por fixtures Python de laboratório anteriores. Silenciar o aviso **não corrige** conexões de testes antigos não fechadas; essa limpeza continua pendente.

## Limites de segurança / critérios de desbloqueio

- **Nenhuma exclusão, restauração ou limpeza de quarentena** no fluxo copy-only FB/FC. `stage` do laboratório antigo por `rename` permanece inseguro diante de troca do basename de origem.
- A cópia com descritores foi validada no Linux, mas não se torna atômica com o journal SQLite. Exige revisão de durabilidade, concorrência, armazenamento, confidencialidade e eventual recuperação num app real.
- `DownloadRecoveryPlan` é `private` em `ChapterDownloadManager.swift`; a fixture FC não o importa diretamente. O Xcode/iOS12 completo e os testes reais de integração continuam pendentes.
- A entrada de origem continua vulnerável a alterações concorrentes maliciosas; `fstat` e comparação de conteúdo detectam diversas divergências, mas não constituem sincronização transacional com outro processo.
- `SQLiteDatabase.currentSchemaVersion` continua **1** no aplicativo. Journal shadow v2 **não** equivale a migração real.
- O app não foi alterado, não se gerou Build71, não se executou `appinst`, não houve acesso à biblioteca do iPad; `main` não modificada.

## Referências

- [PR #90](https://github.com/AugustoArbulu/MangaReader12/pull/90)
- [Workflow macOS FC](https://github.com/AugustoArbulu/MangaReader12/actions/workflows/chimera-build70-phase-fc-darwin-fd.yml)
- [Commit de workflow, apenas branch feature](https://github.com/AugustoArbulu/MangaReader12/commit/16b804b766a4d46823565126bea4bb1ecb89e2ec)

**Próximas tarefas:** ler resultado efetivo do workflow Apple, migrar os arquivos de testes selecionados para CI sem tocar em produção, comparar serialização com source atual via compilação direta da fixture, design de secret-handling para planos/URLs, validar APFS e preparar integração inativa por feature flag somente após testes.

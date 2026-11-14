# WebReader Build70 — Fase FE: sincronização EV–FD completa e CI de regressão
Data: 13/11/2026 · PR #90 (Draft) · ambiente de laboratório, sem IPA

## O que passou a estar no GitHub
A pasta `ci/labs/webreader-ev-fd/` contém a árvore **completa de 41 arquivos** do pacote de laboratório EV–FD (fontes Python/Swift, fixtures, testes de todas as fases, documentos, checksums e propostas de workflow). Salva na branch `feat/chimera-updater-phase1-protocol-audit` pelo commit `48807e289e61880f3523449559201625468bbb02`. Não há cópia desses arquivos nas fontes do aplicativo instalado; o laboratório é intencionalmente isolado.

O README do laboratório foi atualizado para refletir FD/250 testes e o manifesto `SHA256SUMS` foi renovado após a atualização. O workflow raiz de QA `.github/workflows/chimera-build70-phase-fe-evfd-full-lab.yml` foi criado para rodar Ubuntu 24.04 + macOS 15, validar checksums, compilar/executar os 250 testes Swift+Python e realizar um `-typecheck` do núcleo Swift com o alvo `arm64-apple-ios12.0`. O workflow usa somente permissões de leitura e não instala nem gera IPA.

## Validação local FE
Uma tentativa inicial na pasta de trabalho antiga falhou porque ela continha um `build70_ev_fd_quarantine.swift` obsoleto de ~11 KB, ao passo que o pacote ZIP e o commit continham a implementação de ~40 KB. **Não era uma falha do pacote sincronizado.** Uma nova extração limpa do ZIP EV–FD foi verificada contra **40 hashes SHA-256** e executou `python3 -m unittest discover -s ci -p 'test_build70_*.py' -q` no Linux: **250 testes, OK (21,6 s)**. O teste permanece sintético, sem arquivos do iPad, sem rede e sem instalar app.

## Resultados Apple e limites
O antigo smoke Darwin da FC ([#43523192504](https://github.com/AugustoArbulu/MangaReader12/actions/runs/43523192504)) já passou, mas não exercita todo o núcleo. O novo workflow FE deve ser interpretado pelo estado do respectivo run mais recente; **não declarar macOS aprovado antes da conclusão e inspeção de jobs**. Um run FE intermediário falhou apenas em checksums porque o README tinha sido alterado sem renovar o manifesto; a correção foi commitada. `main` permanece intocada.

**A Fase FE não implementa exclusão física nem a integração no app.** O núcleo tem um modo legado `stage` por `rename` inseguro contra troca de inode: jamais usar com dados reais. O caminho `sealed` (completed-only) é apenas snapshot/cópia e não retira a origem. Ainda falta revisão de persistência real APFS/WAL, concorrência entre processos, limites de armazenamento e restauração confiável, além do consentimento do proprietário para qualquer atualização.

## Barreiras
`SQLiteDatabase.currentSchemaVersion=1`, chaves de produção nil, `liveInstallationEnabled=false`. PR #90 Draft, sem Build71 autorizada, sem `appinst`, sem alteracão de `main`, sem leitura/remoção/restauração de dados físicos do iPad.

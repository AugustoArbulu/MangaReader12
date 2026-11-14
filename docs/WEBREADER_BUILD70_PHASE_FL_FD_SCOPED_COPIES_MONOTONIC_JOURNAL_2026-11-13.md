# WebReader Build70 — Fase FL: arquivos fixados por FD e detecção cooperativa de ABA

**Data:** 13/11/2026 (Brasil), PR #90 Draft, branch `feat/chimera-updater-phase1-protocol-audit`.

## Problemas e correções experimentais

### 1. Durabilidade do descritor durante cópia, e limite de FDs

O núcleo Swift EV–FD (`ci/labs/webreader-ev-fd/ci/build70_ev_fd_quarantine.swift`) já usa `openat`/`O_NOFOLLOW`, compara a identidade `(st_dev, st_ino)`, abre os diretórios por descritor fixado, faz cópia *somente de saída* (snapshot) e verifica os bytes dos arquivos de origem e destino. Mesmo se um terceiro trocar o nome do diretório **depois** de fixar o FD, a leitura por FD permanece ligada ao inode aberto; a validação do caminho canônico final falha, preservando tanto o estrangeiro quanto o original. Isso não permite `unlink` nem `rename` condicional por inode.

**Defeito encontrado e corrigido:** `defer { close(fd) }` colocado diretamente no corpo do `for` acumulava **dois descritores abertos por página até o retorno da função Swift**. Capítulos com muitas páginas poderiam bater no limite de descritores (`EMFILE`). A Fase FL adiciona um escopo léxico `do { ... defer ... }` em torno da dupla de descritores por página, tanto em `ezCopySnapshot` quanto em `ezVerifySnapshot`. O teste reduz `RLIMIT_NOFILE` do processo Swift para 48 e copia/verifica **130 páginas** sem esgotar descritores. Testa também página final adulterada sem apagar origem. Nada foi modificado no código de produção.

Isso **não** resolve esgotamento de espaço: 130 páginas de poucos bytes são testes, não benchmark de terabytes. Continua necessário um limite agregado de bytes/quota antes de disponibilizar qualquer função de cópia real.

### 2. SQLite ABA com gatilhos de evento no shadow descartável

`ci/build70_fl_monotonic_shadow.py` cria uma **terceira cópia** `fl_shadow_v3.sqlite` por `O_CREAT|O_EXCL|O_NOFOLLOW` **dentro de uma fixture explicitamente marcada EV_SYNTHETIC_ONLY**. Obtém um backup do `shadow_library_v2.sqlite`, preservando o banco v2 e os capítulos originais. Migra apenas essa cópia para `user_version=3`, criando `fl_journal_event` com sequência `AUTOINCREMENT` e gatilhos `AFTER INSERT/UPDATE/DELETE` no journal `offline_copy_journal`, mais gatilhos que recusam `UPDATE/DELETE` dos eventos. A migração/seed de baseline é transacional.

O leitor `inspect_disposable_version_clock` abre v3 com `mode=ro`, ativa `PRAGMA query_only`, usa um snapshot SQLite consistente e lê: estado completo do journal, contagem e maior número de sequência de eventos. Duas leituras que encontrarem **as mesmas linhas** mas sequências diferentes detectam ABA de escritores **cooperativos**. Os testes confirmam transações WAL não confirmadas invisíveis, commit visível e rollback sem aumentar o contador persistido.

**Limite de segurança:** gatilhos dentro do SQLite **não são à prova de adulteração**. Um escritor que pode executar `DROP TRIGGER`, substituir o banco ou manipular o arquivo pode escapar do protocolo. A Fase FL testa explicitamente o caso `DROP TRIGGER` e o leitor recusa esse estado, mas não pode provar que um invasor deixou um esquema visualmente idêntico. O contador detecta mutações apenas enquanto os gatilhos operarem. Não cria trava de inode nem CAS atômico da fonte, não vincula atomicamente filesystem ao journal e **nunca autoriza apagar, restaurar, descartar snapshot ou alterar `chapters.downloaded`**.

### 3. Testes e limites

- Novos testes: **16** em `test_build70_fl_monotonic_shadow.py` e **4** em `test_build70_fl_fd_budget.py` = **20 novos**.
- Regressão local: FL 20 + FK 36 + FJ 30 + FI metadata 17 + EV–FD 250 = **353**; os **2 FI Swift WAL** são executados pelo workflow GitHub na árvore completa do projeto (não estavam disponíveis na cópia parcial de trabalho local). Não contar testes FF/FG/FH do aplicativo nesses totais.
- O workflow FL executa tudo em Ubuntu 24.04 + macOS 15, verifica 40 checksums da árvore EV–FD, inclui os dois FI Swift WAL e faz Swift typecheck com destino iOS 12. **Não alegar sucesso de CI antes da conclusão.**

## Bloqueios de produção

1. Fonte Swift do laboratório ainda inclui uma rota legada `stage` por rename que é *conhecidamente insegura* contra swap de inode. Nenhuma rota `stage` pode ser ligada ao aplicativo.
2. A fonte Swift faz cópias por FDs abertos e pode detectar alterações observáveis; não há exclusão de origem vinculada atomicamente ao inode.
3. Não há prova de atomicidade entre FS/APFS e SQLite/WAL nem garantias de recuperação física por reboot/queda de energia no iPad real.
4. O banco do aplicativo segue schema v1, `diagnosticCopyPreviewEnabled=false`, instalador desativado; v3 e gatilhos existem somente no laboratório sintético.
5. Ainda faltam orçamento de espaço, validade de backups, operação concorrente com outros processos e validação física em iOS 12 antes de considerar um descarte definitivo.

**Sem Build71, IPA, assinatura, instalação, releases, `appinst`, dados do iPad, alteração da `main` ou operação de exclusão real.**

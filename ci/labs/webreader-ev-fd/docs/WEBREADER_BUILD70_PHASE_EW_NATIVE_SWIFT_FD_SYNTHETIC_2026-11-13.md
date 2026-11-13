# WebReader Build70 — Fase EW: prova Swift nativa por descritores, ainda sintética

Data: 13/11/2026 · PR #90 Draft · continuação da Fase EV

## Resultado

O laboratório EV de 13 cenários Python/SQLite foi mantido sem alterações. A Fase EW acrescenta `ci/build70_ev_fd_quarantine.swift`, um executável Swift POSIX sem dependências do aplicativo. Compilou no Swift 6.2.1 Linux e passou 15/15 testes reais em `ci/test_build70_ev_native_swift_fd.py`. **São 28 verificações locais (13 EV + 15 EW), mas somente 15 exercitam Swift; não houve compilação com SDK Apple/iOS12 nem teste físico no iPad.**

O binário **só opera num diretório temporário sintético marcado** por `.webreader_ev_disposable_marker` contendo `EV_SYNTHETIC_ONLY\n`. Todas as operações percorrem a árvore controlada `synthetic_app/Downloads/<source>/<manga>/<chapter>` e `synthetic_app/Quarantine` a partir de `open`/`openat` com `O_NOFOLLOW | O_DIRECTORY`, de modo que substituição por symlinks em pais, diretórios de capítulo e arquivos de página é recusada. O teste não usa pasta da Build70, dados pessoais ou rede.

### Operações propostas

1. `inspect`: identifica `(st_dev, st_ino)` de pasta aprovada, após verificar que as páginas são arquivos regulares, não hardlinks nem symlinks, e seguem padrão `page-#####.bin`, sem entradas desconhecidas.
2. `stage`: exige a identidade já registrada pelo chamador, abre os dois pais por descritor, recusa destino ocupado e executa rename **exclusivo**; Linux: `renameat2(RENAME_NOREPLACE)`; Darwin: `renameatx_np(RENAME_EXCL)` (declarado com disponibilidade iOS 10, sujeito a suporte do volume). Seguem `fsync` dos pais e comparação pós-rename; divergência exige revisão; o programa **nunca apaga** o conteúdo.
3. `classify`: leitura do estado; retorna `at_source`, `in_quarantine` ou `needs_review`, segundo existência e identidade. Nenhuma restauração automática é feita aqui.

### Evidências e limites

- Testes Swift: sucesso; inode esperado errado; destino previamente ocupado; symlinks nos pais/folha/página; arquivo estrangeiro; marcador ausente/falsificado; componente inválido; operação sem identidade; substituições pós-movimentação; SQLite sintético rejeitando DELETE e mantendo a quarentena intacta.
- `RENAME_EXCL` evita **sobrescrever o destino**, mas **não vincula o inode de origem ao rename**. A janela TOCTOU no componente final continua. Não afirmar segurança completa contra processo adversário que modifica a árvore simultaneamente.
- **Não há journaling SQLite no núcleo Swift.** A persistência e reconciliação ainda são as do laboratório Python EV. As rotas reais `remove`, `removeAllConfirmed` e `removeMissingFiles` **continuam intocadas**.
- **Não há restauração nativa nem purge.** Isso é deliberado: restaurar com `renameat` simples poderia sobrescrever uma pasta nova, e apagar bytes antes de uma política segura de retenção/revisão violaria a meta de preservação.
- `fsync` nos diretórios não comprova transação ACID com SQLite WAL. Falhas entre as transições ainda devem ser verificadas em APFS e Swift real.
- A inspeção de arquivos do teste cobre só páginas sintéticas, **não** `_download-plan.json`, recibos nem limites/IDs exigidos pela implementação real ER/EU.
- O compilador Darwin do CI e o SDK iOS12 precisarão validar a assinatura Swift `renameatx_np`, o comportamento `RENAME_EXCL` do volume e os flags disponíveis; o sucesso em Linux não permite considerá-los aprovados.

## Reproduzir

```bash
python3 ci/test_build70_ev_recoverable_quarantine.py -v
python3 ci/test_build70_ev_native_swift_fd.py -v
```

O segundo teste compila `swiftc` para binário dentro de `TemporaryDirectory`, cria apenas capítulos fictícios e elimina a fixture ao terminar. Se `swiftc` estiver ausente, o teste é ignorado (não deve ser relatado como aprovado). Um workflow isolado da fase EW, caso aprovado, pode testar Linux e macOS sem alterar o build do app.

## Próxima etapa não autorizada para produção

Projetar/adicionar (ainda atrás de flag **desabilitada**) o journal SQLite integrado, com migração de esquema e operações por identidade exata; separação de estado `prepared`, `quarantined`, `retired_quarantined`, `needs_review`; recuperação idempotente no startup antes da fila; impossibilidade de restauração com overwrite; bloqueio de `removeMissingFiles` ao haver operações pendentes; e única política para exclusão individual/lote/reindexação. Produzir teste APFS com falhas antes/depois de cada fronteira e revisão de TOCTOU fonte. **Não habilitar exclusão real por quarentena com base na Fase EW.**

Barreiras: nenhuma alteração de `main`, instalação, Release, appinst, trust SPKI, Build71 nem dados offline do iPad. O atual protótipo continua fora do target Xcode. A fase EW **não implica autorização de alterar a Build70 instalada**.

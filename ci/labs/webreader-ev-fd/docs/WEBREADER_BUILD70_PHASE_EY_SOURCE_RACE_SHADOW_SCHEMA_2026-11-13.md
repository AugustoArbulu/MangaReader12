# WebReader — Fase EY: prova adversarial de origem e migração SQLite em *shadow*

Data: 13/11/2026 · continuação do laboratório EV/EW/EX · Build70 · PR #90 Draft

## Escopo e decisão

**Estado: laboratório sintético Linux, não produção.** A Fase EY não modifica `MangaReader12`, `SQLiteDatabase.swift`, `ChapterDownloadManager`, o banco real, a Build70 instalada, o iPad ou `main`. O código só opera sobre raízes sintéticas descartáveis com marcador `EV_SYNTHETIC_ONLY\n`. Não há rede, appinst, lançamento de build ou purge de quarentena.

A investigação confirma que `renameatx_np(RENAME_EXCL)` é **exclusivo quanto ao destino**, não um compare-and-rename vinculado ao `st_ino` da origem. Nenhuma sequência `fstatat` → `renameatx_np` consegue provar a identidade da entrada da origem **no mesmo instante** do rename. Ancorar diretórios via `openat` e manter um descritor da folha aberta melhora a detecção, mas não oferece essa garantia.

Consequência observável: um ator que troque o nome da pasta do capítulo depois do preflight ainda pode fazer a operação **movimentar uma pasta diferente**. A checagem posterior rejeita a operação (`UNSAFE`) e conserva os bytes, mas o próprio movimento equivocado ocorreu. **Portanto o método ainda não está aprovado para exclusão real.**

Referências:
- macOS `renameatx_np(2)`, `RENAME_EXCL`: https://manp.gs/mac/2/rename
- Cabeçalho XNU declara `renameatx_np` disponível a partir de iOS 10 (não é ensaio real em iOS 12): https://newosxbook.com/src.php?file=%2Fbsd%2Fsys%2Fstdio.h&tree=xnu
- SQLite `user_version` e `synchronous`/WAL: https://www.sqlite.org/pragma.html ; https://www.sqlite.org/wal.html

## Modificação no componente Swift **somente do laboratório**

Arquivo: `ci/build70_ev_fd_quarantine.swift`.

1. Em `stage`, mantém fd da pasta original aberto durante a movimentação e verifica seu inode após a operação; a verificação **não** converte o rename em operação condicional.
2. Em `withContext`, revalida por `fstatat`/`fstat` as entradas de `synthetic_app`, `Downloads`, fonte, manga e `Quarantine` antes/depois da chamada. Alteração de ancestral leva a `UNSAFE`.
3. Acrescenta o *fault gate* `WEBREADER_EY_RACE_GATE=1`, exclusivamente para fixture com marcador, suspendendo o código antes do rename até a liberação do teste. O gate nunca existe nos fontes de produção.
4. `RENAME_EXCL` impede substituir destino ocupado. Um erro **nunca executa rollback por rename comum, não exclui nem tenta limpar pastas**.

### Casos adversariais reproduzidos

| Situação induzida no instante anterior ao rename | Observação no Linux | Conclusão |
|---|---|---|
| Não ocorre troca | Pasta correta movimentada, resultado aceito | Controle positivo |
| Origem substituída por outra pasta de páginas válidas | Pasta diferente é movida à quarentena; inode diverge, operação recusada | **TOCTOU real demonstrada**, nada apagado |
| Origem substituída por symlink | O link é movido, sem seguir o destino; falha de pós-verificação | Exige revisão |
| Origem substituída por arquivo | Arquivo é movido, pós-verificação falha; bytes preservados | Exige revisão |
| Destino passa a existir | `RENAME_EXCL` falha, destino/origem preservados | Sem overwrite |
| Pasta do mangá ou Quarantine realocada | Pinagem fd opera sobre diretório antigo; revalidação de caminho rejeita | Sem commit/retirement |
| Marcador sintético alterado | A operação não inicia | Fail-closed |

A **recuperação segue read-only no filesystem** e não restaura nem limpa uma quarentena ambígua; a rota real do WebReader permanece intocada.

## Proposta de migração para journal SQLite v2 (não aplicada ao app)

Arquivo: `ci/build70_ey_shadow_schema_migration.py`.

A Build70 no PR ainda define `SQLiteDatabase.currentSchemaVersion = 1` e rejeita versões mais altas. **Não alterar esse valor nesta fase:** abrir o app antigo com banco v2 provocaria rejeição de schema; a migração da biblioteca real exige aprovação, cópia externa comprovada, código compatível e rollback de release cuidadosamente planejado.

O piloto aceita **somente** `synthetic_app/legacy_library_v1.sqlite` sob a raiz marcada, abre o banco legado em modo somente leitura (`mode=ro`) e cria `synthetic_app/shadow_library_v2.sqlite` com `O_CREAT|O_EXCL|O_NOFOLLOW` e permissões 0600. Usa `sqlite3.Connection.backup()` para uma cópia consistente, inclusive origem em WAL. A fixture reproduz a estrutura e relações **críticas** de `manga`, `chapters` e `downloads`, não todo o schema real.

No *shadow*, usa **uma** transação `BEGIN IMMEDIATE` para criar `offline_deletion_journal`, índices (um registro não resolvido por capítulo) e `PRAGMA user_version=2`, seguida de `COMMIT`. Não usa `executescript()` dentro da transação (pois este pode implicitamente finalizar uma transação pendente). Em caso de exceção, faz `ROLLBACK`; após `os._exit(86)` no meio da transação, o próprio SQLite desfaz o DDL na próxima abertura. Nunca sobrescreve um shadow existente. Valida `quick_check`, `foreign_key_check`, versão e chaves estrangeiras; não migra bases com schema desconhecido.

O journal novo tem estados `prepared`, `quarantined`, `retired_quarantined`, `aborted`, `needs_review` e um campo `owner_confirmation` que **não representa autorização real**: nesta fixture ele contém um marcador de que confirmação será exigida. Nenhum mecanismo de confirmação do aplicativo foi implantado.

**Limite de durabilidade:** validar SQLite/WAL `PRAGMA synchronous` em Darwin/iOS 12 antes de prometer persistência de intent contra queda de energia; com WAL+`synchronous=NORMAL` uma transação concluída pode ser revertida após perda de energia, conforme documentação SQLite. `fsync` de diretórios e operações APFS também dependem de validação no macOS/iOS 12. Não há ACID entre filesystem e SQLite.

## Testes

Na máquina Linux local, com Swift 6.2.1, a suíte completa do pacote EV/EW/EX/EY foi **76/76 OK**:

- EV Python: 13/13
- EW Swift nativo: 15/15
- EX bridge Swift + SQLite: 22/22
- EY shadow v1→v2: 18/18
- EY corrida de inode nativa: 8/8

Arquivos novos: `ci/build70_ey_shadow_schema_migration.py`, `ci/test_build70_ey_shadow_schema_migration.py`, `ci/test_build70_ey_source_inode_race.py` e workflow manual `.github/workflows/webreader-build70-phase-ey-shadow-native-adversarial.yml`. **Workflow macOS criado mas não executado**, sem alegação de compatibilidade iOS 12 comprovada.

Comando no diretório do pacote:

```sh
python3 -m unittest discover -s ci -p 'test_build70_*.py' -q
```

## Critérios bloqueadores para a Fase EZ

1. **Não habilitar rename destrutivo** enquanto não houver protocolo sólido para impedir que conteúdo não proprietário seja movimentado no intervalo de troca; um bloqueio cooperativo apenas entre instâncias do WebReader não defende contra ator externo/jailbreak. Alternativa mais conservadora: captura/copiação dos arquivos por fds já abertos, sem mover/apagar a origem, com hash/verificação e quarentena de cópia; avaliação de custo de armazenamento necessária.
2. Provar por execução real em **macOS/APFS** as flags `RENAME_EXCL`, retorno de `fsync`, crash/inode e resultados do fault gate; iOS 12.5.x ainda requer avaliação separada.
3. Realizar prova de migração contra **schema v1 completo** e cópia externa verificada, não apenas a fixture mínima; desenhar reversão de aplicativo antigo em caso de banco v2.
4. Unificar `remove`, `removeAllConfirmed`, `removeMissingFiles` sob um coordenador com journaling, serialização e bloqueio de reindexação até reconciliação. Nenhuma rota de produção foi modificada.
5. Comprovar recuperação de `needs_review` sem descarte automático; confirmar offline leitura de capítulo e integridade da cópia de contêiner antes de qualquer Build71.
6. Preservar `main`, PR Draft, atualização/integridade de IPA e gate de instalação desligados; nenhum procedimento com appinst no dispositivo.

**Conclusão:** Fase EY como prova de laboratório aprovada localmente; o risco de deslocamento de conteúdo indevido por corrida está **confirmado**, não resolvido. É um bloqueador explícito de integração.

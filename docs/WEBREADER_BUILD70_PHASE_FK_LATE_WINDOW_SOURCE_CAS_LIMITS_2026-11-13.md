# WebReader Build70 — Fase FK: janela final de corrida, ABA e limites de CAS do inode

**Data:** 13/11/2026 (horário local) — **PR:** #90 Draft — **branch:** `feat/chimera-updater-phase1-protocol-audit`.

## Escopo

A Fase FK amplia FJ com auditoria sintética **somente leitura** (`ci/build70_fk_late_window_evidence.py`). Ela roda o comparador duplo do journal e dos bytes originais/copiados, e repete leituras independentes do SQLite e verificações nativas por FD imediatamente depois. Cada operação passa a exigir revisão se sua origem, snapshot, metadado, recibo ou estado mudar antes da última verificação observável; discrepâncias globais do journal invalidam todas as observações. A execução é limitada a **16 operações** e exige a marca explícita `EV_SYNTHETIC_ONLY` herdada do laboratório. É um *witness* efêmero, não um mecanismo de exclusão.

Campos de retorno: `observations`, `requires_review`, distribuição de motivos, e invariantes permanentes `can_delete=false`, `can_purge=false`, `can_restore=false`, `can_mark_downloaded=false`, `source_inode_cas_available=false`, `late_race_window_remains=true`. Não há DELETE, unlink, rename, copia, restore, purge, gravação no journal nem autorização de Build71.

## Achados concretos

1. **Mudança depois da última leitura:** um adversário consegue alterar a página ou substituir o nome da pasta imediatamente após o último `verifycopysealed`. O auditor ainda pode retornar `observations=1`, pois a última leitura SQL não comprova estabilidade futura do filesystem. O teste explicita isso e verifica que o relatório **continua proibindo apagar**.
2. **ABA do journal:** uma transação pode passar de `copy_verified` para `needs_review` e depois para `copy_verified`, restaurando os mesmos valores dos campos lidos. Como não há versão de mudança monotônica protegida por todos os escritores, leituras comparadas não detectam necessariamente o evento intermediário. Um contador cooperativo seria útil para diagnóstico, mas não bloquearia escritores externos.
3. **CAS do inode de origem ausente:** `renameat2(RENAME_NOREPLACE)` no Linux e `renameatx_np(RENAME_EXCL)` no Darwin/Apple validam a **ocupação do destino**, não fazem um compare-and-swap atômico do **inode de origem** verificado anteriormente. Uma troca de basename entre preflight e rename pode mover uma pasta estrangeira; a primeira demonstração EY continua bloqueadora. *Não* promover o modo legado `stage` do laboratório.
4. **Detecção eficaz dentro da janela observável:** swaps de origem e snapshot, mutações in-place, links, recibos inválidos, plano privado injetado, drift no SQLite, interrupções e estados preparados falham fechados nos testes FK/FJ. Não se confunde isso com prova de segurança após o retorno.
5. **WAL:** estados SQLite não confirmados não ficam visíveis à conexão de leitura, que vê apenas uma versão comprometida. Isso não vincula o diretório de origem a um inode para uma futura operação destrutiva.

## Evidência e regressão

- FK: **36 testes locais Linux** (real Swift FD + SQLite shadow v2 fictício), todos aprovados.
- FI/FJ: **17 + 30 testes** novamente aprovados.
- EV–FD: **250 testes** novamente aprovados.
- Total da regressão sintética local: **333 testes** (250+17+30+36), sem contar os dois testes Swift específicos FI nem testes FF/FG/FH do aplicativo.
- `.github/workflows/chimera-build70-phase-fk-late-window-adversarial.yml` executa esses conjuntos e os 2 testes FI de Swift em **Ubuntu 24.04 + macOS 15**; o target Swift isolado também recebe `-typecheck arm64-apple-ios12.0` no macOS. **Não declarar CI aprovado até conferir os jobs.**

## Gates reais para exclusão

A cadeia “FJ/FK passou → apagar pasta” é **inválida** por TOCTOU. Antes da exclusão física, é necessário desenhar uma operação que impeça retirar **outro** diretório sob troca concorrente (ou exigir lock/cooperatividade comprovada e tratar outras aplicações/Filza como escritor externo), com journal e rollback de crash, limites de espaço/durabilidade APFS/WAL, backup real verificado e teste iOS12 físico. Uma checagem `stat()` após `rename` é insuficiente: o deslocamento não autorizado já terá ocorrido.

O código do app mantém `diagnosticCopyPreviewEnabled=false`, a versão do banco de produção é v1 e as três rotas reais ainda não usam o laboratório. Nenhuma alteração foi feita em `main`, dados do iPad, instalação ou release. A Build 71 permanece sem autorização.


## Execução GitHub Actions — resultado final
O [workflow FK #43539228012](https://github.com/AugustoArbulu/MangaReader12/actions/runs/43539228012) terminou **SUCCESS, 2/2 jobs** em 14/11/2026 UTC:
- `synthetic-no-delete (ubuntu-24.04)`: SUCCESS;
- `synthetic-no-delete (macos-15)`: SUCCESS, incluindo typecheck do Swift nativo com `arm64-apple-ios12.0`.

Cada job passou pelas suítes **FK 36 + FJ 30 + FI metadata 17 + FI Swift WAL 2 + EV–FD 250 = 335 testes**. O CI não gerou IPA nem executou exclusão ou restore. Não houve compilação do app completo nesta etapa (a última compilação integral havia passado no workflow FH). O resultado valida o laboratório, **não** o comportamento físico de APFS em um iPad com jailbreak.

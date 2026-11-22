# WebReader — Fase FD: snapshots de capítulos concluídos sem duplicar planos sensíveis
Data: 13/11/2026 · PR #90 (Draft)

## Problema corrigido no laboratório
A Fase FC negava planos com headers HTTP não vazios. Porém `_download-plan.json` também pode carregar tokens em URLs de páginas, URLs da obra, caminhos e campos futuros. Aceitar JSON apenas porque `headers={}` não prova confidencialidade.

## Nova política FD: completed-only / no-plan
- Núcleo Swift do laboratório: `inspectsealed`, `snapshotsealed`, `verifycopysealed` recusam a presença de `_download-plan.json` **antes de ler ou decodificar o arquivo**, e revalidam a ausência após copiar; não removem origem nem destino.
- Bridge SQLite shadow: opção explícita `sealed_only=True` exige `downloads.state='completed'` e `chapters.downloaded=1`, inclusive após a pré-inspeção e antes do commit do journal. Pausados/falhos ou com plano vão para revisão, sem cópia nem exclusão.
- Legacy `snapshotmeta` continua **somente para regressão sintética**; não é rota segura para produção.
- Cópia usa FD pinado de origem, `O_NOFOLLOW`, limites de páginas/recibos, cópia byte a byte e checks de vínculo. Corridas não autorizam commit.
- Nenhum DELETE do SQLite, nenhum `removeItem`, nenhum purge/restore/IPA/appinst.

## Evidência
**250/250 testes locais Linux** aprovados (EV 13, EW 15, EX 22, EY 26, EZ 33, FA 42, FB 52, FC 20, FD **27**). FD inclui plano com token em URL, header sensível, plano injetado durante cópia, swap de pasta, recibo incorreto, estados failed/paused, drift SQL, lote de dois concluídos, crash/reabertura e recuperação idempotente. Todos usam fixture sintética das 11 tabelas v1 migrada para shadow v2.

CI Apple da FC [#43523192504](https://github.com/AugustoArbulu/MangaReader12/actions/runs/43523192504): **success**, mas só validou primitivas Darwin e iOS12 typecheck do pequeno smoke test, **não o núcleo FD**. Workflow completo FD macOS/Ubuntu foi preparado no ZIP de laboratório, **não executado** no repositório.

## Bloqueios
O código da FD está no ZIP compartilhado na conversa, **não integrado nem commitado como código de app**. Falta testar o Swift FD integral no macOS/APFS, fazer integração read-only com as três rotas reais, provar durabilidade concorrente do SQLite/WAL e definir descarte físico seguro. A fonte de produção ainda declara `currentSchemaVersion=1`. Operações de exclusão existentes não foram alteradas; a rota experimental não é uma autorização de deleção.

## Barreiras
`main` intacta; PR permanece Draft, Build70 do iPad, dados offline, releases, trust SPKI e `liveInstallationEnabled=false` sem alterações. Nenhuma Build71 autorizada.

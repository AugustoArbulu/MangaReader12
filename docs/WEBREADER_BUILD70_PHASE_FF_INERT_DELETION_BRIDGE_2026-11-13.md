# WebReader Build70 — Fase FF: integração somente diagnóstica com exclusão bloqueada
Data: 13/11/2026 · PR #90 Draft · branch feat/chimera-updater-phase1-protocol-audit

## Evidência anterior
O CI FE [#43530797187](https://github.com/AugustoArbulu/MangaReader12/actions/runs/43530797187) concluiu SUCCESS tanto em Ubuntu 24.04 quanto em macOS 15, com o laboratório EV–FD sincronizado, checksums, suíte sintética 250/250 e typecheck Swift para alvo iOS 12. Isso **não** equivale a validar exclusão física ou o comportamento no iPad.

## Contrato FF
A integração FF adiciona `WebReaderOfflineDeletionV2ShadowGate` a `ChapterDownloadManager.swift` com `diagnosticCopyPreviewEnabled=false` constante e não configurável por UI, usuário ou rede. O método `previewForAudit` retorna somente `provisionalCopyOnly` ou `requiresReview`: ele exige estado completed, propriedade não ambígua, ausência de `_download-plan.json` e preflight ER. Não faz nenhum filesystem/SQLite write. O resultado **nunca autoriza apagar páginas**.

As três rotas de exclusão ou manutenção são instrumentadas para chamar `rejectLegacyDestructionWhenPreviewEnabled()` **antes** de qualquer mudança: `ChapterDownloadManager.remove`, `removeAllConfirmed` e `DownloadRepository.removeMissingFiles`. Como o modo experimental é falso, o comportamento atual não é alterado; se um desenvolvedor editar manualmente a flag para true, **as três rotas destrutivas falham fechadas**. Não há caminho experimental de gravação.

QA `ci/test_build70_ff_deletion_gate.py`: testes estáticos de prioridade da guarda e teste compilado Swift com diretório temporário descartável. A guard pode ser validada por CI macOS/iOS 12 sem compilar IPA. Este código não substitui o journal v2 real ou a implementação de cópia por FD. A integração efetiva de cópia no app permanece não implementada.

## Próximos gates
Validar compilação completa do projeto em CI Apple (sem gerar IPA ou realizar instalação), conectar um auditor read-only usando as estruturas reais, testar concorrência no armazenamento e definir descarte seguro, ainda sem habilitar a exclusão física. Mantenha `main`, dados offline, Build 70 física, trust de atualização e AppInst intactos.

# Build 53 — Backup portátil de obras fixadas

Data: 2026-11-04. Branch: `feat/build53-backup-library-pins`. Base: Build 52 / PR #82 (CI aprovado; QA física ainda pendente).

## Escopo
- Estende o **formato 1** de preferências do backup com uma codificação opcional `stringArray`; não altera o envelope SQLite, o esquema do banco nem arquivos de capítulos.
- O backup passa a incluir a chave de favoritos `library.pinned.sources.v1` da Build 51, que usa identidade estável `sourceID+mangaID`.
- Importação restaura o mesmo `UserDefaults.stringArray`, mantendo compatibilidade de arquivos anteriores que não tenham o novo campo.
- Constrain até 10.000 identidades e 2.048 bytes UTF-8 por string, sem enviar informações externas ou registrar IDs.
- A interface esclarece que obras fixadas entram no backup, mas **arquivos baixados e scripts das fontes continuam fora**.
- Em backup antigo sem a preferência, o estado de pins presente no dispositivo não é apagado automaticamente.

## Validação
- `ci/test_build53_backup_pins.py` extrai e compila a implementação Swift real do codec de preferências, verifica roundtrip de StringArray, UserDefaults, backward compatibility de formato 1 e limites de entradas.
- Todos os testes anteriores continuam no CI, incluindo Build52 e compilação iOS12 Debug/Release.
- QA física: fixar 2 obras de fontes diferentes; criar backup; restaurar em instalação de teste ou dispositivo separado; verificar pins e leitura/categorias. **Não restaurar backup de teste por cima de dados importantes sem cópia**, pois o fluxo atual substitui a base e limpa downloads antigos.
- Não inclui migração de fontes automática, dados de chapter image ou mídia no backup.

## Próximo roadmap
- Downloads: seleção múltipla com confirmação e limites; preservar lógica de fila existente.
- Biblioteca: indicadores locais e diagnósticos de atualização.
- AVIF: somente após codec compilado + testado no dispositivo iOS 12.5.8; não alegar suporte prematuramente.

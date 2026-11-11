# WebReader Build70 — Fase DT: conferência read-only de contagens e arquivos offline antes/depois de eventual Build71

**11/11/2026.** Desenvolvimento em `feat/chimera-updater-phase1-protocol-audit`, PR #90 Draft. Sem merge em `main`. Build70 física, biblioteca, favoritos, progresso, downloads, Chimera e instalação do iPad não alterados nesta fase. Nenhum pacote IPA/DEB produzido ou distribuído.

## Problema tratado

As fases DQ/DR/DS revisam os metadados **antes** de uma atualização experimental. A Fase DJ já compara nove contagens SQLite de dois relatórios (Build70 e Build71), mas **não compara** os relatórios de presença dos arquivos offline antes/depois. O diagnóstico DO audita somente a Build70 e explicitamente não aceita a Build71. Uma futura troca de IPA pode manter todas as linhas SQLite iguais, enquanto as imagens offline são perdidas ou se tornam ilegíveis. Não se deve concluir preservação a partir de uma contagem no banco de dados.

## Entrega

- `ci/build70_dt_postupgrade_offline_text_compare.py`: comparador **somente leitura** de textos explicitamente fornecidos pelo proprietário, sem acesso a aplicativos ou arquivos privados do iPad e sem escrever qualquer dado. Aceita `--before-counts`, `--after-counts`, `--before-offline` repetido por lote e `--after-offline` repetido por lote.
- A verificação DJ original exige `Build observada: 70 • iOS: 12.5.8` para o primeiro relatório SQLite e `Build observada: 71 • iOS: 12.5.8` para o segundo, com nove contagens ordenadas e rodapé fixo.
- Para os relatórios offline da Build71, uma função verifica o cabeçalho **exato** de Build71 e substitui **somente essa linha em memória**, retornando o formato Build70 para reutilizar o analisador adversarial DO existente. Isso **não altera relatórios em disco**, não relaxa a versão aceita pelo DO, não permite aceitar Build69/72 e não inventa metadados.
- Compara as contagens SQLite e os totais agregados dos lotes offline: registros completos, inspecionados, capítulos com arquivos sequenciais, recibos, legados, faltantes/inseguros, páginas presentes e capítulos não inspecionados.
- Limites de até 256 lotes de 64 capítulos; a cadeia exige os lotes ordenados, completos e não repetidos. Um relatório de texto falso ou trocado pode apresentar totais iguais: isso é tratado como **evidência não autenticada**, não como garantia de integridade.
- `ci/test_build70_dt_postupgrade_offline_text_compare.py`: regressões para perdas SQLite, diferenças em contagens de páginas offline, legado sem recibo, falhas ou lacunas, comparação parcial, zero downloads, versões inválidas, symlinks, linhas adicionais e mutações determinísticas. Qualquer resultado retornado mantém todos os campos de autoridade, preservação física e execução como `false`.
- `.github/workflows/chimera-build70-phase-dt-postupgrade-readonly.yml`: Linux/macOS, Python 3.12, validação de DT + regressões DJ e DO; guarda das três travas de produção. Sem IPA, nem artifacts, nem execução física.

## Como interpretar os status — sem alegações além dos textos

| Diagnóstico | Status |
| --- | --- |
| Qualquer contagem SQLite mudou | `DT_STOP_SQLITE_COUNTS_CHANGED_REVIEW_REQUIRED` |
| Amostra relata capítulos/páginas offline inseguros | `DT_STOP_OFFLINE_FILE_METADATA_UNSAFE_REVIEW_REQUIRED` |
| Existe capítulo legado sem recibo de páginas | `DT_REPORTED_LEGACY_CHAPTERS_REQUIRE_REAL_OFFLINE_READING` |
| Não há registros completos nos textos | `DT_REPORTED_ZERO_OFFLINE_RECORDS_NOT_PHYSICAL_PROOF` |
| Nem todos os lotes foram revisados | `DT_REPORTED_OFFLINE_BATCHES_INCOMPLETE_REVIEW_REQUIRED` |
| As contagens offline agregadas mudaram | `DT_STOP_OFFLINE_AGGREGATES_CHANGED_REVIEW_REQUIRED` |
| Todas as contagens e totais agregados coincidem textualmente | `DT_BEFORE_AFTER_TEXT_AGGREGATES_EQUAL_NOT_DATA_PROOF` |

Mesmo a última situação não prova que **os mesmos capítulos e imagens** foram preservados, porque o diagnóstico compara totais, não IDs ou hashes dos arquivos. Dois conjuntos de arquivos diferentes podem ter contagens idênticas. O relatório também pode ter origem falsa, conter dados de outro aparelho ou ter sido gerado em momentos diferentes. O teste físico de abrir **o mesmo capítulo, em modo offline e com Wi‑Fi desligado**, é indispensável para atestar a experiência real; a análise de texto não o substitui.

A presença de recibos não comprova decodificação de WebP/JPEG/PNG ou que a página contém imagem correta. Um texto Build71 reportado antes da instalação não comprova que a instalação aconteceu.

## Relação com a Fase DS e o plano de atualização

- **Antes:** DQ/DR/DS reúnem evidências de identidade, inventário e um candidato IPA71, mas não autorizam instalação ou distribuição.
- **Depois de um teste físico autorizado por cima:** DT poderá comparar os dois conjuntos de relatórios se o proprietário fornecer as saídas antes/depois. **Nada foi instalado nesta fase**, então os testes DT usam somente textos sintéticos.
- **Mesmo após DT:** faltam autenticação do editor, continuidade real dos contêineres do iPad, leitura offline física, backup externo confiável, aprovação específica e verificação dos mesmos bytes consumidos pelo instalador. A funcionalidade de atualização automática continua desabilitada.

O backup `.mr12backup` não inclui imagens de capítulos; **não restaurar automaticamente**, pois isso pode eliminar downloads. Não incluir títulos, IDs, paths, imagens privadas ou backups nos relatórios publicados no GitHub.

## Travas mantidas

`productionPublicKeyX963=nil`, `independentlyProvisionedSPKISHA256=nil`, `liveInstallationEnabled=false`. Nenhuma ação de instalar, restaurar, limpar ou publicar é executada por DT. `main` e iPad intactos.

## CI e handoff

Verificar os dois jobs da Fase DT, inclusive macOS, e investigar falhas antes de declarar aprovação. Registros positivos de fixtures de host não são evidência de execução física nem de integridade de downloads. O próximo marco real do projeto continua a observação somente leitura da identidade instalada da Build70 e uma aprovação separada para distribuir/testar uma IPA71 **real**, com backup externo e teste offline por cima.

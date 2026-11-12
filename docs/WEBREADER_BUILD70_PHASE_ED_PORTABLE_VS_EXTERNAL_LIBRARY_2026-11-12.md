# WebReader Build70 — Fase ED: comparar conteúdo da biblioteca em backup portátil e cópia externa

12/11/2026. PR #90 Draft, branch feat/chimera-updater-phase1-protocol-audit. Sem alteração da main, iPad, Build70, biblioteca, downloads, GitHub Releases ou instalador. Não foi criada nem entregue IPA71.

## Problema

O backup portátil .mr12backup contém um SQLite sanitizado e preferências, mas não contém páginas offline. BackupManager.swift limpa downloads, desmarca chapters.downloaded e remove sources da cópia portátil. Restaurá-lo substitui a biblioteca e apaga arquivos de downloads existentes. Nunca usar o backup portátil como prova de preservação dos capítulos offline.

EA/EB/EC conferem arquivos e contagens de cópias externas. A ED acrescenta uma comparação de CONTEÚDO das linhas entre o SQLite contido no .mr12backup e library.sqlite de uma cópia externa já extraída do contêiner de dados do aplicativo. Isso detecta diferenças de leitura, progresso, favoritos, histórico e categorias mesmo quando o número total de registros não muda.

## Implementação

- ci/build70_ed_portable_vs_external_library.py: host-only, somente leitura. Recebe --snapshot (raiz de uma cópia externa do data container) e --backup (arquivo .mr12backup já exportado).
- ci/test_build70_ed_portable_vs_external_library.py: testes fictícios com esquema v1 extraído do Swift de produção e com bytes de páginas sintéticas.
- .github/workflows/chimera-build70-phase-ed-portable-external-library.yml: executa regressões EA e ED no Linux/macOS, com gates contra instalação, entrega de IPA e confiança editorial.

A ED reutiliza a validação host de backup portátil de ci/build69_bf_portable_backup_baseline.py. O rótulo histórico desse parser, assumedInstalledBuildAtExport=68, NÃO atesta a build real da exportação. O backup portátil é decodificado em um banco SQLite somente em memória. O banco externo é aberto em leitura com mode=ro&immutable=1 após a EA conferir a cópia e seus arquivos offline. O SQLite da cópia tem seu hash verificado antes e depois.

São comparadas exatamente as linhas de nove tabelas do esquema v1: manga, library, chapters, categories, manga_categories, history, repositories, source_settings e migration_map. A comparação usa ordem de rowid e serialização de valores com tipo e comprimento. Nenhum título, ID, URL, caminho privado, preferência ou hash de registros privados é publicado nos resultados: são expostos somente totais e nomes genéricos de tabelas divergentes.

A tabela downloads, a tabela sources e chapters.downloaded são excluídos, pois o exportador portátil os elimina ou altera intencionalmente. A ED não compara preferências UserDefaults do dispositivo com as preferências do envelope, nem bytes de páginas offline do original contra o backup portátil, pois esse formato não os contém.

## Interpretação

ED_LIBRARY_ROWS_EQUAL_NOT_ATTESTED: as linhas das tabelas preservadas no portátil coincidem com a cópia externa, consideradas as exclusões deliberadas. Isto NÃO prova origem no iPad, mesmo instante, proteção externa efetiva ou integridade da leitura offline.

ED_STOP_LIBRARY_ROWS_DIFFER: linhas divergentes, mesmo quando as contagens permanecem iguais. Deve-se investigar antes de considerar uma atualização.

ED_STOP_UNSUPPORTED_SCHEMA, ED_STOP_PORTABLE_INVALID, ED_STOP_EXTERNAL_COPY_INVALID, ED_STOP_COPY_CHANGED e ED_STOP_DATABASE_UNREADABLE: abortar sem restaurar, normalizar, modificar ou apagar qualquer arquivo.

Os relatórios não autorizam emissão de IPA, instalação, restauração ou atualização automática. É indispensável provar identidade física e entitlements da Build70, manter backup externo íntegro dos downloads, comparar mesmo capítulo com Wi-Fi desligado antes/depois e validar bytes finais de uma eventual IPA71.

## Uso opcional futuro

Após decisão expressa do proprietário e coleta de uma cópia do contêiner de dados e de um backup portátil, ambos retidos fora do iPad, poderá ser executado no próprio computador:

python3 ci/build70_ed_portable_vs_external_library.py --snapshot "/copia/data-container" --backup "/copia/biblioteca.mr12backup"

Esses caminhos são ilustrativos: nenhuma cópia física foi recebida nesta fase. Arquivos podem divergir legitimamente se forem produzidos em momentos diferentes. Não publicar bancos SQLite, capítulos, arquivos de preferência ou backups no GitHub.

Manter ausente ci/build71_owner_approved_qa_trigger.txt e manter productionPublicKeyX963=nil, independentlyProvisionedSPKISHA256=nil, liveInstallationEnabled=false. A validação ED depende de conferir os logs Linux e macOS do GitHub Actions, sem alegar aprovação antes dos jobs terminarem.

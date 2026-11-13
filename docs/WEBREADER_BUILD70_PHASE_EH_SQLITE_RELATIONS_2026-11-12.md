# WebReader Build70 — Fase EH: integridade relacional do SQLite copiado

12/11/2026. PR #90 Draft, branch feat/chimera-updater-phase1-protocol-audit. Fase host-only; sem acesso ao iPad, sem instalação, restauração, escrita no backup, coleta ou publicação de informações privadas.

## Motivação

A EA verifica a estrutura do SQLite da cópia externa, capítulos completos, bytes das páginas e recibos. Mas PRAGMA quick_check não valida todas as relações de foreign keys. Uma cópia pode ter contagens coerentes de downloads completos, porém registros órfãos de biblioteca, histórico, categorias ou source_settings, ou possuir o campo chapters.downloaded incompatível com downloads.state.

A implementação em produção DownloadRepository.setState() marca chapters.downloaded=1 exatamente quando o download está completed; a conclusão normalmente grava progress=1. A EH audita os indicadores usando consultas SQL somente leitura. Ela NÃO altera ou tenta reparar valores históricos; casos contraditórios apenas bloqueiam a conclusão de consistência e exigem revisão.

## Arquivos

- ci/build70_eh_sqlite_relational_integrity.py: carrega um SQLite copiado previamente analisado pela EA, compara SHA-256 e desserializa bytes na memória usando as proteções da ED, com query_only.
- ci/test_build70_eh_sqlite_relational_integrity.py: fixtures sintéticos a partir do schema v1 do Swift, inclusive orphan foreign keys que passam em quick_check, estados contraditórios de download, capítulos com flags inválidas, WAL e páginas ausentes.
- .github/workflows/chimera-build70-phase-eh-sqlite-relationships.yml: CI Ubuntu e macOS com regressão EA, ED e testes EH; sem artifact/release.

## Verificações

1. PRAGMA user_version=1 e PRAGMA integrity_check completo devem ser válidos.
2. As próprias declarações FOREIGN KEY de todas as 11 tabelas da schema v1 precisam corresponder ao contrato definido no SQLiteDatabase.swift, incluindo tabela/coluna pai, coluna filha, ação ON DELETE e comportamento ON UPDATE. Ausência ou alteração dessas regras é EH_STOP_FOREIGN_KEY_SCHEMA_MISMATCH. Depois, PRAGMA foreign_key_check não deve retornar nenhuma violação, sem expor valores de chaves ou IDs.
3. chapters.downloaded deve ser estritamente 0/1 e corresponder à existência de downloads.state=completed para aquele chapter_id.
4. Qualquer registro completed deve possuir progress=1 (conforme o setState de produção).
5. is_read e bookmarked devem estar em 0/1, e last_page_read não pode ser negativo.
6. Ao final, o digest do SQLite copiado deve continuar igual ao original lido pela EA.

O relatório devolve apenas contagens agregadas, nomes de campos e um status; não revela títulos, capítulos, identificadores ou caminhos privados. Resultados com prefixo EH_STOP encerram o processo com exit code 2. Nenhum relatório produz um conserto, limpa Downloads ou concede autorização.

## Limites importantes

A EH confere também a presença do contrato das chaves estrangeiras para impedir um falso verde se o banco tiver sido recriado sem FKs. Os testes simulam um SQLite com todas as linhas e colunas preservadas, mas sem qualquer FK, que passa em quick_check e em foreign_key_check vazio e ainda assim DEVE ser recusado pela EH. A cópia pode ter sido obtida de fonte incorreta, e pode ter sido modificada antes da auditoria; uma verificação host bem-sucedida não atesta o iPad físico. Alguns estados históricos legítimos podem exigir análise manual se não correspondem às invariantes atuais — a EH não apaga nem reclassifica esses registros.

A ferramenta não confirma que as imagens decodificam no iOS 12, que todos os dados foram retidos fora do aparelho ou que uma atualização preservará o sandbox. O .mr12backup continua sem bytes das páginas e restaurá-lo remove Downloads.

## Uso futuro ilustrativo (não executado)

python3 ci/build70_eh_sqlite_relational_integrity.py --snapshot "/copia/externa-do-container"

A cópia externa deve ser criada e mantida pelo proprietário em procedimento separado; nenhum dado físico foi fornecido para EH. Nunca publicar a cópia no GitHub. Trigger ci/build71_owner_approved_qa_trigger.txt permanece ausente; productionPublicKeyX963=nil, independentlyProvisionedSPKISHA256=nil, liveInstallationEnabled=false. Nenhum resultado verde da CI constitui permissão para gerar, distribuir ou instalar a IPA71.

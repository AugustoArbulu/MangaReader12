# WebReader Build70 — Fase EA: auditoria de bytes da cópia externa (12/11/2026)

PR #90 Draft, branch feat/chimera-updater-phase1-protocol-audit. Sem merge na main, sem IPA71 entregue, instalação, restauração ou acesso aos dados físicos do iPad nesta fase.

## Achado confirmado

Em MangaReader12/Core/BackupManager.swift, createBackupFile() salva somente um SQLite sanitizado e preferências no .mr12backup. A cópia elimina a tabela de downloads, desmarca capítulos baixados e remove fontes. NÃO inclui imagens. restoreBackup() substitui o banco ativo e remove recursivamente Application Support/MangaReader12/Downloads. Esse backup portátil não protege os arquivos offline. Não restaurá-lo como parte normal de uma atualização por cima.

## EA implementada

- ci/build70_ea_external_copy_audit.py: ferramenta Python SOMENTE LEITURA para computador externo. Audita uma pasta que JÁ seja cópia extraída do DATA CONTAINER iOS, nunca copia nem acessa o aparelho.
- ci/test_build70_ea_external_copy_audit.py: casos adversariais sintéticos, sem dados privados.
- .github/workflows/chimera-build70-phase-ea-external-copy-readonly.yml: execução Linux/macOS; sem empacotar IPA, instalar ou publicar Release. Conferir jobs reais antes de declarar CI aprovada.

O argumento --snapshot é a raiz da cópia extraída do contêiner de dados: nela deve existir Library/Application Support/MangaReader12/library.sqlite e, quando aplicável, a árvore de Downloads. Não é a pasta MangaReader12.app nem um arquivo .mr12backup.

O auditor exige banco SQLite v1 regular, limitado a 256 MiB, sem symlinks ou WAL não vazio. Qualquer WAL não vazio é recusado: SQLite aberto com mode=ro&immutable=1 poderia ignorar transações ainda não incorporadas ao arquivo principal. NÃO apagar nem truncar WAL original para satisfazer o auditor. Obter, por método apropriado, uma cópia SQLite coerente e somente depois revisar a cópia.

A base copiada é aberta em modo SQLite somente leitura, com query_only, trusted_schema desativado e PRAGMA quick_check. Todos os registros downloads.state='completed' são reconciliados com manga e chapters; downloads.local_path persistido NÃO é aceito como caminho físico, já que UUIDs de contêiner podem mudar. A pasta offline é reconstruída a partir dos IDs pelo modelo de sanitização do Swift. São recusadas colisões de caminho sanitizado, páginas não regulares, symlinks, páginas vazias, sequências com lacunas, recibos incorretos e alterações de arquivo durante a leitura.

Todas as páginas completas da cópia são efetivamente lidas em blocos e hashadas por SHA-256. O relatório informa somente contagens e dois hashes agregados (SQLite e conteúdo offline), sem imprimir títulos, IDs, URLs, conteúdo de imagens ou caminhos privados. Se IDs não ASCII forem encontrados, o status requer teste real porque Python isalnum não garante equivalência integral com Foundation CharacterSet.alphanumerics.

## Semântica dos status

EA_COPIED_SQLITE_AND_OFFLINE_BYTES_COHERENT_NOT_DEVICE_PROOF: bytes e recibos dos capítulos marcados completos na cópia são coerentes. Não prova origem, retenção externa ou decodificação de imagens.

EA_LEGACY_OR_NONASCII_IDS_REQUIRE_DEVICE_READING: capítulos sem recibo ou IDs Unicode; validação física continua necessária.

EA_NO_COMPLETED_DOWNLOADS_NOT_DEVICE_PROOF: zero registros completos na cópia, sem inferir ausência de downloads no iPad.

EA_STOP_NONEMPTY_WAL_NEEDS_CONSISTENT_SQLITE_SNAPSHOT: não ignorar nem apagar sidecars; obter snapshot consistente.

Outros EA_STOP_*: aborto sem qualquer modificação, reparo, instalação ou restauração. Os códigos não contêm paths privados.

A ferramenta verifica apenas arquivos associados a capítulos COMPLETOS no SQLite. Não atesta que o contêiner inteiro foi copiado, que downloads pendentes foram preservados, que todas as preferências estão presentes, que o original era idêntico, que as imagens são válidas ou que os mesmos capítulos abrirão em iOS12. Os hashes não autenticam a origem do iPad; servem para comparar cópias locais. Um backup com zero registros completos também não comprova que o aparelho estava vazio.

## Procedimento físico FUTURO, não autorizado nesta fase

1. Preservar a Build70 instalada. Para eventual backup, encerrar completamente o app antes de copiar o contêiner de DADOS completo via Filza/WebDAV, para armazenamento sob controle do proprietário fora do aparelho. Não substituir os dados originais nem confundir data container com app bundle.
2. Conferir se existe WAL não vazio. Se houver, parar; obter snapshot SQLite consistente por método que não destrua nem modifique a instalação original. A EA não faz checkpoint.
3. Sobre a pasta já copiada e extraída, em computador com Python e a branch apropriada, executar: python3 ci/build70_ea_external_copy_audit.py --snapshot "/caminho/local/para/copia-do-data-container".
4. Guardar resultados localmente, sem publicar banco, arquivos de capítulos ou hashes associáveis ao acervo no GitHub. A EA não cria cópia nem relatório em disco.
5. Antes de eventual IPA71 privada, continuam necessários DQ/DO/DR no aparelho, conferência de entitlement e assinatura da IPA FINAL, backup externo realmente verificado e teste de leitura do MESMO capítulo offline com Wi-Fi desligado antes/depois de qualquer instalação por cima. Entrega e instalação requerem autorizações distintas.

Em TODO status: nenhuma autorização de instalação, restauração ou atualização automática é concedida. O acionador ci/build71_owner_approved_qa_trigger.txt deve permanecer ausente. Trust editorial deve permanecer nil e liveInstallationEnabled=false. O app do iPad não foi tocado por esta etapa.

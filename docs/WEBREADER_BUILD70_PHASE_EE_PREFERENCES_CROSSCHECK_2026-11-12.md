# WebReader Build70 — Fase EE: conferência das preferências exportadas (12/11/2026)

PR #90 permanece Draft na branch feat/chimera-updater-phase1-protocol-audit; não mexer na main, iPad, biblioteca, downloads, fontes, releases ou instalador. Todos os testes e arquivos da fase são host-only e sintéticos.

## Motivação

A fase ED confere o conteúdo das tabelas da biblioteca entre um backup portátil .mr12backup e o SQLite de uma cópia externa do contêiner de dados. Porém BackupManager.swift também exporta 14 chaves conhecidas do UserDefaults para o campo preferences do envelope. Uma biblioteca pode estar íntegra, mas o modo de leitura, tema ou ajustes terem sido perdidos.

A fase EE acrescenta a comparação de tais chaves com o arquivo de preferências de uma cópia externa já extraída, no caminho Library/Preferences/com.example.MangaReader12.plist. O domínio foi obtido do histórico do Bundle ID da Build70 e não foi atestado novamente no iPad nesta fase. Se o plist não existir ou não puder ser lido, o resultado é INDISPONÍVEL, não "sem preferências".

## Código e validação

- ci/build70_ee_portable_preferences_plist.py: somente leitura, consome os bytes .mr12backup já exportados e o plist da cópia externa.
- ci/test_build70_ee_portable_preferences_plist.py: fixtures SQLite v1 e páginas fictícias já usados pela ED, acrescentando plist binário, strings, booleanos, inteiros, doubles, dados base64 e arrays de fontes; divergências e arquivos inválidos.
- .github/workflows/chimera-build70-phase-ee-preferences-crosscheck.yml: Linux/macOS, sem artifacts, IPA, transferência ou publicação.

O código reutiliza o parser estrito do .mr12backup para validar envelope, SQLite sanitizado e limites; nunca restaura o backup. Verifica a lista exata de 14 chaves contra BackupManager.swift. Usa plistlib da biblioteca Python, com máximo de 4 MiB para a cópia do plist. Recusa symlinks nos componentes de caminho e qualquer arquivo não regular. Compara SOMENTE valores explicitamente exportados na allowlist. Valores não exportados de UserDefaults, preferências padrão não persistidas, dados ocultos do cfprefsd e registros de outras aplicações não podem ser verificados com esse método.

## Status

- EE_EXPORTED_PREFERENCES_EQUAL_NOT_ATTESTED: valores explicitamente salvos no envelope portátil conferem com os do plist copiado. Não atesta mesma origem, mesmo instante ou preservação física de preferências.
- EE_STOP_EXPORTED_PREFERENCES_DIFFER: um ou mais valores/chaves divergentes. Saída contém apenas os nomes públicos das chaves, NUNCA valores privados.
- EE_STOP_UNKNOWN_EXPORTED_PREFERENCE, EE_STOP_INVALID_PREFERENCE_VALUE, EE_STOP_MISSING_PREFERENCE_VALUE, EE_STOP_AMBIGUOUS_PREFERENCE_VALUE e EE_STOP_UNSUPPORTED_PREFERENCE_KIND: o registro do envelope viola o contrato conhecido.
- EE_STOP_INVALID_BACKUP_OR_PLIST, EE_STOP_EXTERNAL_COPY_INVALID ou EE_STOP_EXTRACTED_PREFERENCES_UNAVAILABLE: não comparar, não preencher defaults automaticamente e não restaurar.

Um UserDefaults ativo pode ainda ter valores no cache do cfprefsd que não foram sincronizados ao plist no instante da cópia. Encerrar o app ajuda, mas NÃO comprova snapshot ou flush completo do sistema. Um resultado positivo jamais equivale a prova física da instalação.

## Uso somente após coleta voluntária futura

python3 ci/build70_ee_portable_preferences_plist.py --snapshot "/copia/data-container" --backup "/copia/biblioteca.mr12backup"

Os caminhos são placeholders e nenhum dado físico foi obtido. Não publicar preferências, bancos, imagens ou backups no GitHub. O .mr12backup continua sem as páginas offline; restaurá-lo apagaria Downloads. Para uma futura atualização por cima da Build70, ainda faltam identidade instalada, backup externo verificado, consentimentos separados para entrega/instalação da IPA71 e teste sem Wi-Fi do MESMO capítulo antes/depois.

Barreiras de produção mantidas: ci/build71_owner_approved_qa_trigger.txt ausente; productionPublicKeyX963=nil; independentlyProvisionedSPKISHA256=nil; liveInstallationEnabled=false. Todos os status mantêm instalação, restauração e distribuição não autorizadas. O resultado Linux/macOS desta fase só pode ser declarado quando os dois jobs concluírem no GitHub Actions.

# HANDOFF TÉCNICO — WebReader iOS 12, Build70 → Build71, Fases EA–EE

**Data:** 12/11/2026. **Repositório:** AugustoArbulu/MangaReader12. **PR:** #90 (Draft). **Branch:** feat/chimera-updater-phase1-protocol-audit. **Head auditado antes deste handoff:** 529289ad9d665719dd90240628941c480b0b741a. **main:** 1283a0614acf3a267e3daddcdafc6c0d0cf335a7 (intocada).

## REGRAS E ESTADO FÍSICO

- Não modificar a main, instalar em iPad ou gerar/distribuir uma IPA71 automaticamente. Não criar ci/build71_owner_approved_qa_trigger.txt por um comando genérico de continuidade.
- iPad com Chimera/iOS 12.5.8 e Build70 relatada como instalada. Não foram coletados dados físicos nesta rodada, não foi feito backup externo físico, não houve instalação/reinstalação nem leitura offline real observada pelo assistente.
- A PR #90 mantém productionPublicKeyX963=nil, independentlyProvisionedSPKISHA256=nil e liveInstallationEnabled=false. O marcador owner-approved da Build71 está AUSENTE na branch. Nenhuma permissão para assinatura editorial, appinst ou atualização automática foi concedida.
- Arquivos privados, banco SQLite, preferências, títulos, identificadores, imagens e backups do usuário não são enviados ao GitHub. As CI usam apenas fixtures fictícios.

## RESULTADOS E FASES

EA — auditoria de cópia externa de data container, ci/build70_ea_external_copy_audit.py. Lê e hasheia bytes de páginas em Downloads, valida SQLite v1 e recibos; rejeita WAL ou rollback journal não vazios, links simbólicos, páginas com lacunas, colisões de caminhos e relatórios inseguros. Testes 21/21 no Ubuntu e macOS (run 43155425953). Não cria backup nem autentica a cópia.

EB — ci/build70_eb_copy_vs_device_text.py. Compara texto existente das nove contagens SQLite e lotes offline da Build70 com totais contidos na cópia externa EA. CI Linux + macOS aprovadas: 21 EA + 28 DO + 10 EB = 59 testes por plataforma (run 43156234511). Contagens iguais NÃO significam imagens idênticas.

EC — ci/build70_ec_full_container_dual_copy.py. Confere conteúdo de TODOS os arquivos regulares (inclusive vazios e ocultos) de duas cópias externas, não apenas capítulos. A V1 passou em ambos os sistemas (33 testes, run 43157785486), mas foi substituída pela EC V2, que ancora percursos por file descriptors e O_NOFOLLOW para reduzir janelas TOCTOU. EC V2: 21 EA + 17 EC = 38 testes Linux aprovados (run 43309654650); macOS estava na fila na última consulta. Hash do inventário V2 não é comparável ao V1. Não compara ACLs, xattrs, propriedade de arquivos nem autentica proveniência.

ED — ci/build70_ed_portable_vs_external_library.py. Nova verificação do CONTEÚDO das linhas SQLite em nove tabelas: manga, library, chapters (exceto downloaded), categories, manga_categories, history, repositories, source_settings e migration_map. Compara .mr12backup sanitizado com cópia externa, sem divulgar registros privados. A tabela downloads, sources e o campo chapters.downloaded são excluídos porque o exportador portátil os elimina/resetta. Reforço: os bytes de library.sqlite são comparados ao hash EA e desserializados em SQLite na memória; não se abre a cópia novamente pelo caminho após a auditoria. Caso adversarial de troca entre leitura EA e desserialização. Última CI Linux: 21 EA + 20 ED = 41 testes aprovados (run 43312413312); macOS ainda na fila. Não prova mesmo instante ou origem.

EE — ci/build70_ee_portable_preferences_plist.py. Confere as 14 chaves explícitas de UserDefaults que BackupManager.swift exporta para o .mr12backup contra o arquivo do domínio histórico Library/Preferences/com.example.MangaReader12.plist da cópia externa, sem expor valores privados. Inclui checagem de tipos, bytes data, arrays, chaves e arquivos/links. Última CI Linux 21 EA + 18 ED (revisão anterior) + 16 EE = 55 testes aprovados (run 43312031908); macOS na fila. Depois disso ED recebeu endurecimento de leitura em memória, ainda não exercitado pelo workflow EE naquela execução; nova validação conjunta seria desejável sem publicar dados privados.

## ALERTA SOBRE BACKUP/RESTAURAÇÃO

MangaReader12/Core/BackupManager.swift: createBackupFile() usa backup SQLite numa cópia temporária que é sanitizada com DELETE FROM downloads, UPDATE chapters SET downloaded = 0 e DELETE FROM sources. O arquivo .mr12backup NÃO inclui arquivos page-*.bin. restoreBackup() substitui banco vivo e clearExcludedDownloadFiles() apaga Application Support/MangaReader12/Downloads. NÃO restaurar .mr12backup como procedimento normal de atualizar por cima. Uma cópia externa do contêiner de dados íntegro e coerente é necessária para tentar preservar os arquivos offline, mas ainda não foi feita nem verificada fisicamente nesta conversa.

## ROTEIRO PENDENTE ANTES DE QUALQUER IPA71

1. Coletar opcionalmente a identidade efetiva da Build70 instalada no iPad com DQ (bundle, versão e application-identifier), sem presumir que os dados históricos do CI são o entitlement do aparelho.
2. Capturar as contagens SQLite e os lotes offline com ações somente leitura já presentes na Build70. Fazer teste REAL do MESMO capítulo offline com Wi-Fi desligado, inclusive após reiniciar o app.
3. Se proprietário desejar preparar upgrade físico, manter backup portátil externo e cópia EXTERNA CONSISTENTE do contêiner de dados completo, incluindo SQLite sidecars, Downloads, preferências e arquivos de fontes. Não apagar WAL/journal no original. As ferramentas EA–EE podem validar aspectos dos arquivos já copiados no computador, mas não realizam transferência.
4. Comparar físico, dados e bundle real com a futura IPA71 FINAL (assinatura, entitlements, SHA/CDHash, compatibilidade iOS12 e mesma identidade do container). A geração de UMA IPA privada é decisão com autorização explícita separada de sua instalação. O workflow DY continua inerte.
5. Só após decisão posterior e distinta de instalação, atualizar por cima sem desinstalar/restaurar e comparar novamente dados e o mesmo capítulo offline. Nunca ativar updater automático por CI verde; dependências de confiança editorial, helper/IPC e consentimento permanecem fechadas.

## LIMITAÇÕES QUE NÃO DEVEM SER APAGADAS

Resultados de testes com fixtures de host não são execução física no iPad. Hash local sem referência confiável não atesta origem. Duas cópias iguais podem vir de um original incompleto ou corrupto. Os parsers não verificam decodificação WebP/JPEG/PNG. EC compara nomes/tamanhos/conteúdo regular, não todos os metadados de restauração (ACL, xattrs, proprietário, file protection). EE só vê valores explicitamente exportados e um plist que pode estar desatualizado em relação ao cache cfprefsd. Nenhum status favorável concede readyToInstallIPA ou installationAuthorized.

## PRÓXIMA AÇÃO RECOMENDADA

Conferir se os macOS jobs EC V2, ED endurecida e EE finalizaram; corrigir apenas falhas concretas, sem relaxar gates. Se CI ficar na fila, documentar o bloqueio e não inventar sucesso. Em seguida revisar as instruções do backup físico e a cadeia de custódia para a futura validação no dispositivo, sem executar nada no iPad até receber autorização específica.

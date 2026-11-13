# HANDOFF COMPLETO — WebReader Build70 / Build71: auditorias EA a EK

**Data:** 13/11/2026 UTC. **Repo:** AugustoArbulu/MangaReader12. **Branch:** feat/chimera-updater-phase1-protocol-audit. **PR:** #90 Draft. **Commit imediatamente anterior ao handoff:** c89ad1296e60248d0db06078a6684080c8aafc1f. **main verificada:** 1283a0614acf3a267e3daddcdafc6c0d0cf335a7, intacta.

## Situação física e regras inegociáveis

A Build70 do WebReader já estava instalada no iPad iOS 12.5.8 com Chimera, mas **não foi tocada por estas fases de auditoria**. Nenhuma cópia privada física do data container, SQLite real, arquivos de páginas ou dados de UserDefaults foram fornecidos ao GitHub Actions. Os testes usam apenas fixtures sintéticos.

A PR #90 continua Draft; não mesclar na main. Não gerar, publicar ou entregar IPA71 nem instalar/reinstalar/desinstalar/restaurar a Build70 somente porque o usuário disse "continue". A entrega e a instalação exigem autorizações **específicas e separadas**. O gatilho ci/build71_owner_approved_qa_trigger.txt deve continuar **AUSENTE**, e estes gates devem continuar bloqueados: WebReaderUpdateChecker.productionPublicKeyX963=nil; WebReaderProductionPublisherTrust.independentlyProvisionedSPKISHA256=nil; WebReaderAppinstSocket.liveInstallationEnabled=false.

**Perigo confirmado:** o backup portátil .mr12backup não contém arquivos offline page-*.bin. O exportador sanitiza uma cópia SQLite apagando downloads, zerando chapters.downloaded e apagando sources; restoreBackup substitui o banco ativo e remove Downloads. Não usar o restore portátil como passo para fazer upgrade.

## Fases implementadas e finalidade

**EA — auditoria da cópia EXTERNA já extraída:** ci/build70_ea_external_copy_audit.py. Confere SQLite v1, WAL/journal não vazios, sequência de capítulos completos, recibos, bytes/hash das páginas; rejeita symlinks, páginas esparsas e mudanças detectáveis. Vincula os bytes da cópia SQLite ao SHA-256, desserializando-os na memória. 23 testes atuais.

**EB — contagens Build70 versus cópia:** compara relatórios textuais de diagnóstico com totais de dados, nunca atesta bytes originais do iPad. 10 testes.

**EC V2 — duas cópias externas integrais:** compara nomes e bytes de arquivos (inclusive ocultos e vazios) usando descritores de diretório e O_NOFOLLOW. Não prova origem, ACLs, xattrs ou cópia atômica. 17 testes; houve success Linux/macOS no run 43309654650 para revisão anterior.

**ED — banco portátil versus biblioteca copiada:** igualdade de linhas em nove tabelas SQLite entre .mr12backup e cópia externa, com leitura hash-bound em memória; exclui corretamente o que o formato portátil omite/resetta. 20 testes; success Linux/macOS numa execução anterior, run 43312413312.

**EE — preferências:** compara 14 chaves exportadas do UserDefaults no backup portátil com plist copiado; não prova estado de cache do sistema. 16 testes; success Linux/macOS em revisão anterior, run 43312031908.

**EF — triagem de páginas completas:** identifica por cabeçalho/rodapé formatos JPEG/PNG/WebP/GIF plausíveis, HTML/JSON e truncamentos óbvios. Não decodifica nem atesta imagens no iOS 12. 17 testes.

**EG — códigos de saída fail-closed:** estados EB–EF iniciados por PREFIX_STOP_ agora retornam exit 2 para impedir falsos sucessos em shell/CI; 6 testes de subprocessos reais.

**EH — integridade relacional SQLite:** PRAGMA integrity_check, foreign_key_check, exigência das definições FOREIGN KEY da schema v1, compatibilidade downloaded/state e flags de leitura. 17 testes.

**EI — inventário de TODOS os Downloads:** relaciona capítulos completos e incompletos, arquivos _download-plan.json, páginas de downloads pausados/falhos, pasta de fonte/obra/capítulo vazia ou órfã, arquivos aninhados, symlinks e colisões. Percorre usando directory FDs, com limites e sem excluir nada. Um download não completo requer revisão e exit 2, sem presumir corrupção. 24 testes.

**EJ — metadados dos planos de retomada:** valida _download-plan.json (máximo 16 MiB), JSON coerente, schemaVersion 1, IDs fonte/obra/capítulo, manifest.id, ordem de fila, 1–5.000 páginas e tipos dos headers. Não vaza URLs/tokens, não executa Swift JSONDecoder e não prova possibilidade de retomada. 30 testes.

**EK — NOVA fase, páginas parciais versus plano:** ci/build70_ek_partial_prefix_metadata.py. Confere se as páginas já salvas de um trabalho não completo formam um PREFIXO CONTÍNUO de page-00000.bin em diante dentro do total anunciado pelo plano. Rejeita por revisão manual páginas vazias, maiores que 20 MiB, páginas fora do plano, lacunas, folhas inesperadas e planos inválidos. Usa metadados dos arquivos e nunca decodifica, altera, renumera ou apaga uma página. Para job failed sem plano opcional, a contagem de páginas é explicitamente desconhecida, não falsamente "não contígua". Mesmo um prefixo totalmente sequencial retorna status EK_STOP_PARTIAL_PREFIX_NEEDS_IOS12_READING, exit 2: jamais afirmar que a imagem é válida ou que a retomada vai funcionar. 23 testes novos.

## CI diretamente verificada na rodada

- **EK individual:** https://github.com/AugustoArbulu/MangaReader12/actions/runs/43341054466 — Ubuntu completed/success, 23 EA + 20 ED + 24 EI + 30 EJ + 23 EK = **120 testes**. macOS queued na última consulta.
- **Regressão integrada EA–EK:** https://github.com/AugustoArbulu/MangaReader12/actions/runs/43341167810 — Ubuntu completed/success, **203 testes**: EA23 + EB10 + EC17 + ED20 + EE16 + EF17 + EG6 + EH17 + EI24 + EJ30 + EK23. O gate confirmou ausência de autorização de IPA/install. macOS queued na última consulta.
- **EJ anterior:** run 43338928854, Ubuntu completed/success, 97 testes; macOS queued.
- **EI anterior:** run 43338211519, Ubuntu completed/success, 67 testes; macOS queued.
- macOS de EC V2, ED e EE passou em execuções anteriores, mas esse sucesso NÃO substitui aprovação das revisões recentes EA–EK. Não alegar aprovação multiplataforma até ver logs reais concluídos.

## O que continua sem evidência

Nenhuma fase comprova proveniência da cópia externa, identidade instalada (application-identifier/entitlements/assinatura), bytes reais presentes no iPad, completude do backup físico, decodificação das páginas no iOS 12, retomada de um download em andamento, atualização in-place sem perda, ou aprovação para distribuir/instalar IPA71.

Os status bem-sucedidos só descrevem os arquivos sintéticos de CI ou uma cópia local fornecida. Downloads incompletos, planos antigos e pastas órfãs são material que deve ser preservado, e não lixo seguro para apagar.

## Continuação correta

1. Conferir os macOS jobs pendentes, principalmente EK 43341054466 e integrado EA–EK 43341167810. Falhas reais devem ser corrigidas na branch de trabalho.
2. Evitar criar fases adicionais apenas para aumentar a contagem; priorizar revisão do fluxo real de atualização e da evidência física quando houver consentimento.
3. Se o usuário autorizar especificamente a inspeção, primeiro executar diagnósticos somente leitura DQ/DO/DR na Build70 instalada, conferir Bundle ID/entitlements e abrir o MESMO capítulo sem Wi-Fi antes de qualquer intervenção.
4. Só depois, mediante procedimento voluntário seguro, preservar uma cópia externa CONSISTENTE do data container completo: SQLite e sidecars, preferências, fontes, capítulos completos e parciais, planos e diretórios ocultos. Não apagar WAL ou rollback journal do iPad para satisfazer auditoria e não enviar dados privados ao GitHub.
5. Auditar a assinatura e identidade da IPA71 FINAL e comparar hashes/contagens com evidência física. **Aprovação para entrega** e **aprovação para instalação por cima** são etapas distintas. Nunca desinstalar a Build70 para atualizar, não restaurar o .mr12backup e não ligar o appinst de produção automaticamente.
6. Após uma instalação devidamente autorizada, comparar a biblioteca, favoritos, progresso, preferências e mesmos arquivos offline e repetir a leitura do MESMO capítulo sem Wi-Fi. Só então discutir habilitar um canal de atualização assinado.

A branch main não deve ser alterada. O gatilho de build71 continua ausente e as flags de publisher/installer continuam bloqueadas.

# HANDOFF WebReader iOS 12 — Fases EA a EH

**Data:** 12/11/2026 (última rodada iniciou às 23h56 UTC; algumas CI concluíram em 13/11 UTC). **Repo:** AugustoArbulu/MangaReader12; **PR #90:** Draft; **branch:** feat/chimera-updater-phase1-protocol-audit; **main:** não alterar.

## Objetivo e limite

Preparar verificações de preservação de dados da Build70 instalada no iPad iOS 12.5.8 antes de eventual Build71. Nenhuma captura física ou cópia do banco do aparelho foi realizada nesta rodada. Não gerar, publicar, distribuir ou instalar IPA71 sem autorização específica; entrega e instalação são decisões separadas. Nunca restaurar .mr12backup por cima como mecanismo de migração dos downloads.

## Estado e proteção

- ci/build71_owner_approved_qa_trigger.txt deve permanecer AUSENTE.
- WebReaderUpdateChecker.productionPublicKeyX963=nil; WebReaderProductionPublisherTrust.independentlyProvisionedSPKISHA256=nil; WebReaderAppinstSocket.liveInstallationEnabled=false.
- PR #90 permanece Draft, main não deve ser alterada.
- Dados da Build70, biblioteca, favoritos, progresso, capítulos offline e fontes do iPad não foram tocados.
- Todas as CI de auditoria usam exclusivamente diretórios temporários e dados sintéticos; não enviar banco, arquivos de imagens, relatórios privados ou preferências ao GitHub.

## Fases

**EA** — auditoria read-only de cópia externa: verifica SQLite v1, ausência de WAL/journal não vazios, registros completed, diretórios reconstruídos, sequência de páginas, recibos e hash de bytes. **Reforço desta rodada:** lê o SQLite copiado por FD sem seguir symlinks, valida digest e identidade do arquivo e desserializa os bytes em memória, sem reabrir o caminho para SQL. Teste adversarial de alteração do SQLite entre hash e leitura. **23 testes aprovados Linux** no run 43334082386; macOS aguardava conclusão na última consulta.

**EB** — confronto de contagens/diagnósticos textuais Build70 com cópia externa. Não compara bytes originais do iPad.

**EC V2** — dupla conferência integral de cópias externas usando hashes de nomes e conteúdo regular, incluindo ocultos/vazios, com travessia por FDs e O_NOFOLLOW. **38 testes aprovados Linux/macOS** no run 43309654650. Não verifica ACLs, xattrs ou origem física.

**ED** — igualdade de linhas de nove tabelas SQLite entre .mr12backup sanitizado e cópia externa, excetuando downloads, sources e chapters.downloaded (intencionalmente excluídos do formato portátil). Confere cópia hash-bound em SQLite na memória.

**EE** — 14 chaves explicitamente exportadas do UserDefaults entre .mr12backup e plist externo; não confere cache cfprefsd. **55 testes aprovados Linux/macOS** no run 43312031908, com ED de uma revisão anterior à sua proteção de leitura em memória.

**EF** — triagem de cabeçalhos/rodapés JPEG, PNG, GIF, WebP em páginas offline copiadas; detecta HTML/JSON e truncamento evidente. Não decodifica imagem, mesmo com status plausible; precisa leitura real no iPad.

**EG** — estados PREFIX_STOP_ nas fases EB–EF saem com código 2; demais estados informativos retornam zero sem autorizar nada. Testes executam subprocessos reais.

**EH** — auditoria integral e relacional do SQLite de cópia externa. PRAGMA integrity_check, foreign_key_check, e conferência das próprias DEFINIÇÕES das foreign keys contra schema v1 do Swift. Também compara downloads.state com chapters.downloaded e progresso completed=1; recusa flags inválidas de leitura e páginas negativas. Testa banco com mesmas linhas/colunas, mas todas as FKs removidas, que quick_check e foreign_key_check vazio não detectariam. **58 testes Linux aprovados** na revisão EH anterior à última mudança da EA, run 43333705934.

## Regressão integrada desta rodada

Workflow .github/workflows/chimera-build70-phase-eg-cli-failclosed.yml agora acompanha alterações nas auditorias EA e EH e executa todas as suites EA–EH.

**Run 43334172111**: Linux completed/success com **126 testes**, distribuídos EA 23, EB 10, EC 17, ED 20, EE 16, EF 17, EG 6 e EH 17. O log confirma também PASS EG: all EA-EH audited, every STOP nonzero; no IPA, install or trust. **macOS estava na fila** na última verificação; não converter sucesso Linux em aprovação multiplataforma.

## Principal perigo para capítulos offline

MangaReader12/Core/BackupManager.swift cria o .mr12backup com banco sanitizado (DELETE FROM downloads, UPDATE chapters SET downloaded=0, DELETE FROM sources), sem incluir page-*.bin. Ao restaurar esse formato, restoreBackup() substitui o banco e clearExcludedDownloadFiles() remove Downloads. Isso torna o backup portátil INSUFICIENTE para preservar capítulos offline.

Nenhuma auditoria EA–EH consegue provar sozinho o conteúdo original do iPad, sua identidade/entitlement, que cópias externas foram efetivamente retidas, a decodificação de cada página no iOS 12 ou a segurança de instalar uma IPA final.

## Próximos passos sem autorização destrutiva

1. Observar os jobs macOS pendentes da regressão integrada (43334172111), da EA atualizada (43334082386) e, conforme necessário, de outras fases. Não inventar sucessos.
2. Se o proprietário decidir fazer validação física, utilizar diagnósticos somente leitura existentes na Build70 para registrar bundle instalado, contagens da biblioteca e metadata offline, e testar o MESMO capítulo sem Wi-Fi antes de qualquer instalação.
3. Fazer, mediante decisão futura e procedimento seguro, cópia externa consistente do data container completo, incluindo SQLite, sidecars, preferências, fontes e Downloads. Não apagar WAL/journal do dispositivo nem publicar arquivos privados.
4. Auditar a futura IPA71 FINAL (entitlements, identidade, assinatura, hash, compatibilidade iOS12) e confrontar evidências. Só após consentimento específico de entrega considerar IPA privada. Instalação por cima exige outro consentimento distinto, sem desinstalar nem restaurar .mr12backup.
5. Após eventual instalação autorizada, reproduzir o MESMO capítulo offline e comparar biblioteca, favoritos, progresso, preferências, imagens e identidade. Automatic updater permanece desligado.

**Regra final:** nenhum teste de host ou status sem STOP habilita publisher trust, distribuição, restauração, appinst ou atualização automática.

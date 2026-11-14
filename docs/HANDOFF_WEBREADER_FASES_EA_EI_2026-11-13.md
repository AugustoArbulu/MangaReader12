# HANDOFF — WebReader iOS 12, auditorias EA–EI (13/11/2026 UTC)

Repositório: AugustoArbulu/MangaReader12. PR #90 Draft na branch feat/chimera-updater-phase1-protocol-audit. Branch main confirmada sem alterações: 1283a0614acf3a267e3daddcdafc6c0d0cf335a7. HEAD antes deste handoff: 52f0ebce7284a79a1c03d717c2c7da58dc123ca8.

## Regras preservadas

A Build70 instalada no iPad iOS 12.5.8 com Chimera **não foi acessada, atualizada, reinstalada, desinstalada ou restaurada**. Não há cópias físicas reais do iPad disponíveis na CI. Não houve release nem distribuição da IPA71. NÃO criar ci/build71_owner_approved_qa_trigger.txt sem aprovação do proprietário; não modificar main nem converter a palavra "continue" em autorização de instalação. productionPublicKeyX963=nil; independentlyProvisionedSPKISHA256=nil; liveInstallationEnabled=false. Nenhuma CI deve realizar appinst ou acessar conteúdos privados.

## Fases existentes

EA: audita SQLite v1, páginas de downloads completos e recibos de uma cópia EXTRAÍDA do data container. Rejeita WAL/journal não vazio, symlinks, páginas esparsas e mudanças detectáveis. O SQLite é lido por descritor sem seguir symlinks, hash verificado e desserializado em memória. Testes sintéticos: 23.

EB: compara contagens e texto de diagnósticos da Build70 com dados agregados da cópia externa. Não compara os bytes do iPad. Testes: 10.

EC V2: percorre e compara duas cópias externas inteiras, com conteúdos de arquivos regulares, ocultos e vazios, por hashes e file descriptors. Não comprova ACLs, xattrs, proveniência nem restauração. Testes: 17. Linux/macOS success no run 43309654650 (21 EA antigos + 17 EC).

ED: compara 9 tabelas SQLite com backup .mr12backup sanitizado, inclusive favoritos, progresso e histórico; downloads, sources e chapters.downloaded são excluídos pela sanitização do exportador. SQLite da cópia conferido por hash e aberto na memória. Testes: 20. Linux/macOS success no run 43312413312 (21 EA antigos + 20 ED).

EE: compara 14 preferências exportadas no portátil com plist externo, sem revelar valores. Não verifica cache do cfprefsd. Testes: 16. Linux/macOS success no run 43312031908, com revisão ED anterior.

EF: classifica apenas assinaturas/trailers de JPEG, PNG, GIF, WebP, detectando HTML/JSON e truncamentos visíveis na cópia externa; não decodifica imagens. Testes: 17.

EG: todos os estados PREFIX_STOP_ de EB–EF retornam exit code 2 em vez de falsos sucessos. Testes reais via subprocessos: 6.

EH: PRAGMA integrity_check, foreign_key_check e validação das próprias FOREIGN KEYs declaradas contra SQLite schema v1, além de consistência de download/chapter e flags de leitura. Detecta banco que mantém linhas e colunas mas teve suas foreign keys removidas. Testes: 17.

EI (NOVA): inventaria TODOS os arquivos em Downloads, incluindo arquivos de download incompleto, pausado, falho e arquivos de retomada _download-plan.json. Compara diretórios de capítulos com TODOS os registros SQLite de downloads, não só completed; detecta páginas e arquivos órfãos, arquivos armazenados em níveis não previstos, symlinks e colisões de caminho sanitizado entre estados diferentes. Caminha por FDs e O_NOFOLLOW, limita diretórios e arquivos e impede listagem sem limites. Não lê bytes integrais dos arquivos não completos e não elimina ou restaura nenhum. Testes sintéticos: 18. A presença de material parcial/ID Unicode é EI_STOP_NONCOMPLETED_OR_UNICODE_REQUIRE_OWNER_REVIEW com **exit 2**, sem alegar corrupção. Arquivos órfãos ou não classificados: EI_STOP_UNREFERENCED_OR_UNCLASSIFIED_DOWNLOAD_FILES, exit 2. Valores e caminhos privados não impressos.

## CI recente diretamente verificada

- Fases EA–EI integradas, Linux: **144 testes aprovados** (23 EA + 10 EB + 17 EC + 20 ED + 16 EE + 17 EF + 6 EG + 17 EH + 18 EI) no workflow https://github.com/AugustoArbulu/MangaReader12/actions/runs/43336609397 .
- EI isolada antes do reforço fail-closed: **60 testes aprovados** (23 EA + 20 ED + 17 EI) no run 43336341642. Após o teste adicional e reforço fail-closed, a EI é exercitada na regressão integrada acima. Workflow EI final iniciado: run 43336643329.
- As execuções macOS mais recentes da regressão integrada e EI ainda estavam **queued** nas últimas consultas. Não afirmar aprovação antes dos logs. EC V2, ED e EE mais antigas passaram em macOS em seus respectivos commits, mas isso não valida automaticamente as revisões mais recentes de EA/EI.

## Limite principal da Build71

BackupManager.swift cria .mr12backup contendo SQLite sanitizado e preferências, mas **NÃO** imagens. O exportador faz DELETE FROM downloads, UPDATE chapters SET downloaded=0 e DELETE FROM sources na cópia portátil. RestoreBackup substitui banco e remove Downloads: **não usá-lo como técnica de migração por cima**.

Nada nas Fases EA–EI comprova um backup externo físico, identidade/entitlement real da Build70, preservação/decodificação de WebP/JPEG/PNG no iOS12, nem que uma instalação por cima será segura. O material órfão ou incompleto detectado pela EI deve ser preservado e revisado, não apagado.

## Próximas etapas

1. Verificar jobs macOS pendentes, sobretudo a regressão EA–EI 43336609397 e EI 43336643329. Corrigir falhas reais sem enfraquecer gates.
2. Não gerar IPA71 automaticamente. Se o proprietário decidir validar fisicamente, obter primeiro observações DQ/DO e teste real do MESMO capítulo com Wi-Fi desligado, sem operação destrutiva.
3. Só após decisão futura coletar cópia externa consistente do contêiner de DADOS completo, incluindo SQLite e sidecars, Downloads (com páginas parciais/órfãs), fontes, preferências, arquivos ocultos. Não apagar WAL/journal do dispositivo nem subir dados ao GitHub.
4. Para uma futura IPA71 FINAL, verificar assinatura, application-identifier, bundle, entitlements, build e SHA da IPA exata. A autorização de entregar uma IPA QA e a autorização de instalar são **separadas**. Não desinstalar a Build70 nem restaurar .mr12backup como etapa de upgrade. Updater automático de produção segue desabilitado.

Documentação de cada fase em docs/WEBREADER_BUILD70_PHASE_*. A PR #90 continua Draft e main deve permanecer intocada.

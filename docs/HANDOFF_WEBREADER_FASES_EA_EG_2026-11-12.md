# HANDOFF WebReader — EA a EG, 12/11/2026

Repo: AugustoArbulu/MangaReader12. PR #90 Draft; branch feat/chimera-updater-phase1-protocol-audit; main intacta. Último head antes deste handoff: 458902cbd1a3478fabd394c438f9dc1a45b07900.

## Estado físico e regras

Build70 no iPad iOS12.5.8 com Chimera: não modificada nesta etapa. Sem coleta de banco, arquivos privados, downloads, preferências ou identidade instalada. Sem instalação, restauração ou limpeza de dados no aparelho. Trigger ci/build71_owner_approved_qa_trigger.txt AUSENTE na branch. productionPublicKeyX963=nil; independentlyProvisionedSPKISHA256=nil; liveInstallationEnabled=false. Não criar trigger por um pedido genérico "continue"; entrega de IPA71 e instalação são aprovações separadas.

## Código entregue

EA: ci/build70_ea_external_copy_audit.py. Valida SQLite e presença/recibos de downloads completos, leitura/hashes de bytes de páginas na CÓPIA EXTERNA, recusa symlinks, WAL/journal e sequências incompletas. Sem prova do original físico.

EB: ci/build70_eb_copy_vs_device_text.py. Cruza contagens dos relatórios Build70 e conteúdo da cópia externa. Números iguais NÃO atestam bytes idênticos.

EC V2: ci/build70_ec_full_container_dual_copy.py. Compara duas cópias externas integrais via hashes de arquivos, incluindo ocultos e vazios, com leitura baseada em file descriptors e no-follow. Não prova proveniência, ACLs ou restauração.

ED: ci/build70_ed_portable_vs_external_library.py. Compara conteúdos das linhas de nove tabelas da biblioteca entre SQLite copiado e .mr12backup; progresso/favoritos/histórico incluídos, não apenas contagens. Os bytes do SQLite externo são verificados contra hash EA e desserializados em memória. Downloads/sources e chapters.downloaded excluídos porque o formato portátil os remove/resetta.

EE: ci/build70_ee_portable_preferences_plist.py. Compara as 14 preferências exportadas com um plist copiado; não divulga valores. Cache UserDefaults e origem física não comprovados.

EF: ci/build70_ef_offline_payload_triage.py. Faz triagem dos cabeçalhos/rodapés das páginas offline na cópia, reconhecendo plausibilidade de JPEG/PNG/WebP/GIF e identificando HTML/JSON e truncamentos. Não decodifica imagens nem atesta leitura no iOS12. 17 testes próprios de EF incluem casos sintéticos deliberadamente não decodificáveis.

EG: corrigiu CLI de EB, EC, ED, EE e EF: estados PREFIX_STOP_ agora encerram processo com código 2. Estados informativos sem STOP continuam com código 0, que NÃO atesta origem, segurança de instalação nem backup íntegro. ci/test_build70_eg_cli_fail_closed.py exercita subprocessos reais e verifica as cinco transições.

## CI verificada

EA e EB: Linux/macOS success (runs 43155425953 e 43156234511).
EC V2: Linux/macOS success, 38 testes por plataforma (run 43309654650).
ED endurecida: Linux success, 41 testes; macOS pendente na última consulta (run 43312413312).
EE: Linux success, 55 testes na versão ED anterior; macOS pendente (run 43312031908).
EF: Linux success, 58 testes; macOS pendente (run 43330371307).
EG: Linux success, 107 testes EA–EG; macOS pendente (run 43330881244).

Sucesso de EC no macOS não significa que outros jobs macOS foram aprovados. Conferir os logs antes de declarar conclusão multiplataforma.

## Atenção ao backup portátil

BackupManager.swift salva .mr12backup sanitizado SEM arquivos page-*.bin. Na restauração, sobrescreve SQLite e apaga Downloads. Nunca usá-lo como suposto backup dos capítulos offline ou restaurar como passo regular de atualização por cima.

## Próxima etapa

Primeiro: conferir CI macOS de ED, EE, EF, EG. Depois: obter somente se o proprietário solicitar relatórios DQ/DO/DR do app instalado e uma cópia externa consistente dos DADOS do contêiner, sem apagar WAL/journal ou desinstalar. Confirmar Bundle ID e entitlement da Build70 física e da IPA71 FINAL, copiar toda biblioteca e downloads com validação independente, testar o MESMO capítulo sem Wi-Fi antes/depois. O workflow DY de IPA71 privada e a instalação via appinst seguem inativos e dependem de autorizações específicas independentes.

Todos os códigos e testes deste handoff rodaram apenas em CI com dados sintéticos; nenhum resultado autoriza produzir/entregar/instalar IPA71, fazer restauração, nem ativar atualização automática.

# WebReader iOS12 — laboratório de transporte CHECK_ONLY independente

Data local: 20/11/2026 (America/Sao_Paulo).
Branch experimental: feat/chimera-updater-phase1-protocol-audit. PR #90 Draft.

## Evidência física e decisão

O usuário quer atualizar o WebReader por dentro do app sem usar PC/Filza a cada versão. No iPad iOS 12.5.8/Chimera, no NewTerm 2, confirmou:

- command -v appinst: encontrou /usr/bin/appinst;
- ls -l /usr/bin/appinst: bits de execução presentes (-rwxr-xr-x), root:wheel;
- dpkg -l: ai.akemi.appinst 2.1.1 e ai.akemi.appsyncunified 116.0 instalados;
- appinst --help: respondeu 'usage: appinst <path to IPA file>'.

Isso comprova que o binário AppInst inicia no terminal, não que uma IPA real foi instalada ou que uma atualização preservou dados por esse comando.

A Build5 diagnóstica no app sandbox encontrou SELF_MAIN=REGULAR_EXEC e SPAWN_SELF=NEGADO (1 (Operation not permitted)). O self-spawn falhou mesmo com bits de execução. Esse retorno não é uma tentativa de executar AppInst.

O laboratório Build61 FIX1 (docs/WEBREADER_BUILD61_PERSISTENT_PING_2026-11-06.md) já havia mostrado comunicação via serviço externo no Chimera: PONG após fechar NewTerm e o app de teste. Isso demonstra persistência entre sessões, mas não comprova funcionamento após reboot/rejailbreak, tampouco instalação.

## Entrega: primeira união entre a política CW e um transporte independente

Arquivos novos:
- ci/webreader_chimera_checkonly_service.c: servidor C mobile UID/EUID 501 (iOS), vinculado somente a 127.0.0.1:38973. Nunca root. Nada de IPA, appinst, subprocessos, download, arquivos ou mudanças no dispositivo.
- ci/test_webreader_chimera_checkonly_service.py: testes reais no host com sockets, concorrência, payload malicioso, quadros divididos, truncados, limites e reinício.
- .github/workflows/chimera-checkonly-transport-lab.yml: CI Linux/macOS e compilação preview ARM64 iOS12, SEM assinatura, IPA, DEB, Release, upload de binário ou instalação.

O servidor reutiliza ci/build70_cw_checkonly_core.c/.h e ci/build70_cw_shared_dispatch.c/.h, evitando uma política paralela.

### Protocolo e significado exato

O cliente não autenticado envia SOMENTE os sete bytes ASCII WRCHK2 seguidos de LF e faz shutdown(SHUT_WR), indicando fim do frame. Qualquer byte adicional — mesmo depois de um prefixo correto — invalida a mensagem.

Respostas exatas de oito bytes:
- WRNOTE2 + LF: um aviso de checagem FOI ACEITO apenas pelo modelo. NÃO é uma consulta HTTP, lançamento de updater, publisher verificado ou instalação.
- WRRATE2 + LF: rate limit de 60 segundos, medido num único processo de servidor com relógio monotônico e gate CW compartilhado.
- WRDENY2 + LF: mensagem inválida ou erro sem aprovação.

Recepção limitada a oito bytes e timeout de 2 segundos por chamada de leitura. Conexões atendidas de forma serial. Mensagens inválidas não consomem o intervalo. Todo WR_CW_Decision mantém false para caller_authenticated, publisher_verified, artifact_selected_by_client, installer_authorized, installation_performed.

### Limites, bloqueios e próximos gates

O servidor não está instalado no iPad. Não lê Releases ou manifesta versões, não possui chave de publisher e não permite instalar. Clientes maliciosos locais podem pedir avisos de checagem; a limitação no processo não é persistente e não impede múltiplas instâncias; uma implementação real precisa impor recursos globais e não transformar o sinal em instalação.

Um serviço futuro para instalar precisa escolher origem fixa por si próprio, verificar manifesto assinado e versão, obter os bytes da IPA sob custódia do helper, validar digest/code-seal e consentimento proprietário independente, mitigando TOCTOU. O usuário local não pode fornecer URL, caminho, hash ou autorização. LOCAL_PEERTOKEN falhou fisicamente no laboratório CM e não é autenticação estabelecida.

Antes de ação de instalação: teste em aplicativo descartável, assinatura do publisher provisionada fora do GitHub/chat, rollback e preservação de dados documentados. Não produzir outra IPA de diagnóstico de self-spawn sem hipótese nova.

Hard stops permanecem: PR #90 Draft, main e Build70 intactas, liveInstallationEnabled=false, productionPublicKeyX963=nil, independentlyProvisionedSPKISHA256=nil, nenhum comando AppInst real, nenhuma Build71/Release/IPA/DEB publicada, sem modificar SQLite, biblioteca ou offline.

## Resultado da primeira integração — 21/11/2026 UTC

[GitHub Actions #44849062382](https://github.com/AugustoArbulu/MangaReader12/actions/runs/44849062382): **SUCCESS, três jobs** no commit 0cba2fd0692549c7a1bf4adbd86df9723bce0c25.

- Linux Ubuntu: host-checkonly-no-installer SUCCESS (servidor real e teste concorrente de clientes, fragmentos e comandos rejeitados; além de regressão do core CW).
- macOS 15: host-checkonly-no-installer SUCCESS (mesmos testes independentes).
- macOS 15 / Xcode 16.4: compile-ios12-arm64-no-package SUCCESS (Mach-O ARM64 iOS12, auditoria de símbolos sem AppInst, spawn ou instalador e verificação das travas existentes no projeto).

Uma execução anterior falhou somente no macOS/iOS devido à visibilidade da constante INADDR_LOOPBACK sob os macros de cabeçalhos Darwin; corrigido ativando _DARWIN_C_SOURCE no código do serviço. O Linux já havia aprovado. O pipeline final passou sem precisar modificar componentes de produção.

**Nenhum artefato IPA/DEB foi criado ou distribuído**: não existe pacote novo para o proprietário instalar nesta fase. A Build70 física e o PING Build61 FIX1 já instalados permanecem intactos.

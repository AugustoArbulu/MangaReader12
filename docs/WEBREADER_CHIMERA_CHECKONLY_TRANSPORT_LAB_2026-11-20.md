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


## Fase CY — cliente Swift de CHECK_ONLY separado da instalação (21/11/2026 UTC)

O arquivo de produção já existente MangaReader12/Core/WebReaderAppinstSocket.swift agora contém uma API opt-in chamada checkOnlyConnection(completion:) e um enum próprio CheckOnlyResult. Não há chamada de interface nem gatilho automático no app. O caminho não depende de posix_spawn na sandbox e não usa o código preexistente de install(...).

- Conexão exclusivamente a 127.0.0.1:38973, limites de envio/recepção de 3 segundos, socket SO_NOSIGPIPE.
- Envia unicamente os sete bytes fixos WRCHK2+LF e executa shutdown(SHUT_WR), atendendo à regra de EOF da fase CX. Não existe URL, caminho, versão, hash, escolha de IPA, publisher ou consentimento no protocolo do cliente.
- Recebe exatamente oito bytes, exige EOF sem byte adicional e interpreta apenas WRNOTE2+LF, WRRATE2+LF ou WRDENY2+LF; qualquer outra resposta é rejeitada. Mesmo WRNOTE2 somente registra um aviso aceito por um serviço local não autenticado, não significa Release consultada.
- O helper pode ser qualquer processo local capaz de responder; não há autenticação do servidor. Nenhum método cria autorização de instalação, executa AppInst, baixa/manipula IPA, modifica arquivos da biblioteca ou publica Release.
- Somente WEBREADER_HOST_TEST compila hostCheckOnlyProbe(port:) para injeção de porta efêmera nos testes macOS; a porta de produção é fixa em 38973.

ci/test_native_webreader_checkonly_transport.py compila o mesmo arquivo Swift real num harness macOS e comunica-se com o serviço C da fase CX compilado no host. Cenários: aviso, rate limit, servidor ausente, frame literal com half-close, respostas desconhecidas/forjadas, bytes extras, truncamento e invariantes sem instalador. O workflow chimera-checkonly-transport-lab.yml executa essa suíte no macOS e valida também o servidor C em Linux/macOS e compilação ARM64/iOS12. O workflow MVP do atualizador recompila o app para iOS12 sem produzir IPA.

Nenhum pacote para iPad é entregue nesta fase. O serviço CX permanece laboratório; o PING físico Build61 FIX1 não foi modificado. A integração UI e download real com publisher confiável ficam para outro gate. Esta fase não autoriza ativar WebReaderAppinstSocket.install, WRINST1 ou publicar Build71/Release. A Build70 física permanece preservada.


### Validação CY (21/11/2026 UTC)

GitHub Actions #44850850358: SUCCESS, 3/3 jobs.
https://github.com/AugustoArbulu/MangaReader12/actions/runs/44850850358

- Linux e macOS: serviço C CX com framing, EOF, rate-limit e inputs adversariais passou.
- macOS: o arquivo Swift real WebReaderAppinstSocket.swift foi compilado contra um harness e conectado ao processo C real. Foram exercitadas confirmações, limites, ausência de servidor, envio fixo seguido de shutdown(SHUT_WR), respostas sintéticas truncadas/forjadas/com sufixo adicional e invariantes sem instalação.
- macOS/Xcode: serviço nativo prévia ARM64 para iOS12 compilado, sem assinatura/distribuição.

A primeira tentativa do cliente Swift falhou por exclusividade de acesso ao array de resposta dentro de withUnsafeMutableBytes; corrigido movendo o cálculo de remaining para fora da closure. A execução final acima passou. O workflow MVP separado compila o app inteiro para iOS12 sem IPA (resultado próprio a consultar antes de declarar aprovação integral).

Este resultado NÃO é ensaio físico iOS12/Chimera, não significa disponibilidade do serviço no iPad, não autentica o peer e não concede qualquer permissão de instalação. A UI do app não chama ainda a nova função.


## Fase CZ — pacote físico CX isolado para Chimera (21/11/2026 UTC)

Depois das fases CX (servidor) e CY (cliente Swift compilado e testado no macOS), esta fase prepara um pacote Debian de laboratório que somente o proprietário poderá escolher instalar. Nenhuma instalação no iPad é feita pelo GitHub Actions.

### Artefatos e isolamento

- ci/com.example.webreader.checkonlylab.plist: LaunchDaemon identificado como com.example.webreader.checkonlylab, com processo executado como mobile, RunAtLoad, KeepAlive e caminho /usr/local/libexec/webreader-checkonly, argumento serve.
- ci/package_chimera_checkonly_deb.py: reutiliza o empacotador Build61 FIX1, incluindo diretórios pais para evitar erro anterior do dpkg no Chimera. Produz WebReader-Chimera-CheckOnly-CX-iOS12-QA.deb, sem arquivos do leitor e sem tocar no AppInst.
- ci/test_chimera_checkonly_deb.py: audita estrutura ar/tar, extrai para diretório descartável, valida arquivos e propriedades exatas, checksum, entitlements assinados, permissões e scripts postinst/prerm, sem instalar o pacote.
- ci/webreader_chimera_checkonly_service.c: novo argumento CLI probe; conecta somente à porta local 38973, envia WRCHK2+LF e apresenta WR_CX_PROBE=NOTE_ONLY_NO_RELEASE_CHECK_NO_INSTALL, WR_CX_PROBE=RATE_LIMITED_NO_INSTALL ou falha. Não lê IPA nem executa processos.
- Workflow chimera-checkonly-transport-lab.yml: job macOS compila e assina o binário ad hoc ARM64/iOS12, valida o pacote e disponibiliza unicamente artifact QA .deb e checksum. Nenhuma Release, IPA de produção ou instalação é publicada.

O novo pacote NÃO substitui o PING Build61 FIX1. Tem nome, plist, binário e porta diferentes (CX 38973, PING 38971). A assinatura usa somente o entitlement sem contêiner do laboratório já estabelecido na Build61; não concede autoridade para instalar.

### Gate físico opcional depois da CI aprovada

A instalação do .deb modifica o sistema do jailbreak e depende de aprovação do proprietário. Antes disso, baixar e conferir SHA-256 e manter backup adequado. Se ele optar pelo ensaio:

1. Transferir o .deb por Filza para um caminho conhecido, como /var/mobile/Documents/.
2. Instalar somente o pacote com.example.webreader.checkonlylab pelo gerenciador jailbreak ou NewTerm com permissões apropriadas, sem remover o PING antigo nem o WebReader.
3. Confirmar status com: dpkg -s com.example.webreader.checkonlylab.
4. No NewTerm como mobile, executar duas vezes, em menos de 60 segundos: /usr/local/libexec/webreader-checkonly probe. A primeira resposta pode ser NOTE, a segunda RATE. Não há consulta de versão nem instalação de IPA.
5. Se for necessário remover, desinstalar apenas com.example.webreader.checkonlylab pelo gerenciador ou dpkg -r com.example.webreader.checkonlylab com as permissões apropriadas. O prerm descarrega somente seu job launchd.

A CI verde ainda NÃO prova que o job launchd funciona no dispositivo físico, que o processo inicia após rejailbreak, que clientes sandboxed conseguem acessar a porta ou que o AppInst pode ser usado pelo serviço. O Swift checkOnlyConnection ainda não está ligado à interface da Build70.

### Ajuste de teste para porta efêmera

O comando probe usa porta fixa 38973 em binário iOS. Apenas no host, sob a macro WR_CX_HOST_TEST_PORT, os testes podem fornecer porta efêmera como terceiro argumento; o código exclui explicitamente esse recurso no target iPhone. O primeiro workflow encontrou um falso erro UNAVAILABLE porque o probe mirava porta zero no host, corrigido sem alterar o contrato iOS.

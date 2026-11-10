# WebReader Build70 — Fase CW: núcleo nativo CHECK_ONLY com equivalência Python/C

**Data:** 10/11/2026. **Branch:** `feat/chimera-updater-phase1-protocol-audit`. **PR:** #90 em Draft, sem merge na `main`. **iPad:** Build70 instalada, biblioteca, favoritos e downloads offline não modificados.

## Hipótese e decisão

Fases CN e CM estabeleceram que o processo que envia uma mensagem local não pode ser autenticado de modo confiável no iOS12/Chimera com as APIs testadas: os três diagnósticos físicos de token resultaram em `TOKEN_UNAVAILABLE AUTHORIZATION=DENIED`. Fases CR–CV confirmaram que passar um arquivo por nome/FD ao instalador ainda não elimina comprovadamente todas as cópias, trocas de pathname e mutações tardias.

Para que um futuro helper possa trabalhar apesar de um aplicativo cliente **não confiável**, precisamos de um protocolo com propriedades verificáveis **antes de qualquer socket/serviço privilegiado**:

- O cliente só pode emitir exatamente os **7 bytes ASCII** `WRCHK2\n`, sem parâmetro, URL, caminho, SHA, versão, chave ou consentimento.
- O receptor local não concede identidade a quem enviou os bytes. Isso **não** é autenticação nem autorização de instalação.
- Cada instância só admite uma solicitação de checagem em intervalos de pelo menos **60.000 ms** medidos com contador monotônico fornecido pelo futuro serviço, rejeitando recuo de tempo e evitando overflow de `uint64`.
- `WRINST1`, sequências extras, bytes nulos, comandos de instalação e grandes payloads são rejeitados sem consumir o orçamento da consulta.
- Mesmo em um evento válido, todos os campos de autenticação editorial, escolha de artefato e permissão de instalação permanecem falsos.

## Entrega

`ci/build70_cw_checkonly_core.h` e `ci/build70_cw_checkonly_core.c` implementam uma função C pura:

```c
WR_CW_Decision wr_cw_offer(
    WR_CW_Gate *gate,
    const uint8_t *packet,
    size_t length,
    uint64_t monotonic_ms
);
```

A função não abre arquivos, não cria listener, não acessa rede, não invoca comandos externos, não escreve em dados do usuário e **não** recebe nome de IPA. O recibo contém apenas `REJECTED`, `CHECK_NOTICE_ACCEPTED` ou `RATE_LIMITED`; todos os indicadores de autoridade são `false`.

`ci/test_build70_cw_checkonly_core.py` compila uma biblioteca C **descartável no runner** e executa:
- casos de bytes exatos, injeção de URL/caminho/consentimento, tamanho incorreto e `WRINST1`;
- limiares 60.000 ms, recuo de relógio, `uint64` próximo do máximo, ponteiro de estado nulo;
- validação de oito testes, incluindo **1.300 casos determinísticos** comparando comportamento do núcleo C com a política CN Python existente;
- demonstração proposital de que duas instâncias de `WR_CW_Gate` permitem cada uma um aviso no mesmo instante: isto **não é** um rate limiter global, e portanto o código não pode ser conectado a um listener real isoladamente.

Workflow `.github/workflows/chimera-build70-phase-cw-native-checkonly.yml` executa testes C/Python em Linux e macOS e compila o núcleo C para um **objeto Mach-O ARM64 iOS12** com Xcode 16.4, sem gerar executável de helper, IPA ou DEB e sem enviar artifacts. Também verifica ausência de símbolos de instalação ou IPC no objeto compilado e mantém as travas de produção.


## Complemento CW: coordenador concorrente em um único processo

Após o primeiro núcleo de protocolo, foram acrescentados:
- `ci/build70_cw_shared_dispatch.h` e `ci/build70_cw_shared_dispatch.c`: um objeto opaco de dispatcher com **mutex pthread** e um único `WR_CW_Gate` compartilhado entre threads. Todas as chamadas são serializadas; erros de lock/unlock retornam somente rejeição, nunca autoridade. O núcleo continua sem socket, instalação, rede ou acesso a IPA.
- `ci/test_build70_cw_shared_dispatch.py`: **6 testes** com biblioteca nativa descartável. Um burst de **128 chamadas concorrentes** no mesmo timestamp aceita só uma checagem e limita outras 127; 80 frames `WRINST1` concorrentes são rejeitados sem consumir a quota; verifica recuo de relógio, handle nulo e ausência de APIs privilegiadas.

**Limites importantes:** um segundo dispatcher (ou um segundo processo) ainda pode aceitar outra checagem simultânea. A quota é compartilhada **somente entre threads que utilizam o mesmo objeto**; não é um serviço global de sistema, não persiste após reinício e não garante segurança contra corrida se o dispatcher for destruído enquanto houver threads ativas. O chamador precisa encerrar todas as threads antes de liberá-lo. Um futuro serviço deve impor fila e orçamento globais em sua única autoridade, em processo protegido e com monotonicidade do sistema, além de limites de rede e download.

A CI CW agora inclui os testes concorrentes em Linux/macOS e compila **os dois módulos C** para objetos Mach-O ARM64 alvo iOS12, verificando símbolos e ausência de capacidades de instalação. Nenhum helper executável foi ativado ou distribuído.

## O que ainda NÃO foi implementado

1. Nenhum serviço persistente, launchd, socket real, escuta TCP, operação em background ou atualização pelo WebReader foi criado. O núcleo C é um **componente puro de política**, e o testador Python não pode ser usado como uma autorização real.
2. O limite de 60 segundos agora pode ser compartilhado por threads mediante o dispatcher CW, mas **não é persistente nem global entre processos**. O serviço futuro terá que impor um orçamento global, controle de fila, timeout, quotas e condições de falha, sem permitir spam/reinício deliberado.
3. A solicitação não escolhe uma Release. A seleção de origem fixa, assinatura editorial production-v2, pin público sob custódia independente, SHA-256 da IPA, code seal Apple, antirreplay e antidowngrade continuam responsabilidades **independentes do helper**.
4. O caminho de instalação não está comprovado: o appinst público de referência faz uma segunda cópia por pathname; o uso direto de LSApplicationWorkspace é API privada cujo entitlement e comportamento real iOS12 ainda não foram validados. Não podemos derivar autorização de uma assinatura de selector.
5. O consentimento proprietário requer um **canal independente**. Nunca transformar `WRCHK2\n`, mesma UID, HMAC pareado, `LOCAL_PEERTOKEN` indisponível, ou um relatório de testes em permissão para instalar.
6. Uma auditoria de conservação da biblioteca, backups e offline, recuperação pós-falha e conclusão efetiva pelo instalador é obrigatória antes de ativar o fluxo automático.

## Estado e próximos gates

`WebReaderAppinstSocket.liveInstallationEnabled=false`; `WebReaderUpdateChannel.productionPublicKeyX963=nil`; `WebReaderProductionPublisherTrust.independentlyProvisionedSPKISHA256=nil`; `main`, GitHub Releases, Build70, dados locais e appinst instalado não foram modificados.

**Próximo trabalho útil:** especificar o boundary nativo de um helper independente, com orçamento e quota **globais** entre conexões, identidade e diretório protegidos no iOS 12, origem editorial fixa e autorização independente. A etapa concorrente entre threads deste laboratório está coberta, mas não substitui teste de múltiplos processos nem instalação física. O runtime iOS12/Chimera e a identidade do binário instalado permanecem perguntas separadas para testes físicos futuros somente com aprovação.

**CI:** ainda não afirmar SUCCESS; atualizar este arquivo somente após checar os jobs Linux/macOS do commit atual. Não publicar IPA ou DEB nesta fase.

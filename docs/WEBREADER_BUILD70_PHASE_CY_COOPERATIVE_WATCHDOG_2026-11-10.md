# WebReader Build70 — Fase CY: supervisão de checagem com timeout cooperativo, lease e backoff

**Data:** 10/11/2026. **Branch:** `feat/chimera-updater-phase1-protocol-audit`. **PR #90 Draft**, sem merge. **Build70 física:** intocada no iPad iOS12.5.8, biblioteca/favoritos/offline preservados.

## Decisão central: timeout não é término do trabalhador

A Fase CX produziu uma fila de checagem-only com **uma tarefa ativa e uma pendente**, limite de 60 segundos entre inícios, tickets internos e cancelamento de estado. O risco residual era concluir que uma tarefa expirou e imediatamente iniciar outra, mesmo se o processo/rotina antiga continuasse trabalhando.

**CY muda isso:** após atingir o prazo, o supervisor sinaliza `cancel_requested`, mas **mantém o trabalhador como possivelmente ativo**. A fila só pode voltar a iniciar tarefas depois que o trabalhador confiável confirmar que parou pela chamada interna `wr_cy_ack_cancel(ticket)`. Sem ACK, o sistema permanece fechado mesmo que centenas de avisos cheguem ou milhões de milissegundos passem.

A confirmação é uma **asserção do harness confiável**, não autenticada criptograficamente pelo código atual. Não pode ser exposta via IPC a um cliente sem identidade de processo; o helper real deve garantir join/conclusão efetiva antes de ACK. Timeout não encerra thread, network stack nem instalação.

## Implementação host-only

Os novos módulos `ci/build70_cy_supervisor.h` e `ci/build70_cy_supervisor.c` encapsulam um `WR_CX_Scheduler` e um mutex. Não abrem sockets, arquivos, rede, instâncias de `LSApplicationWorkspace`, IPAs ou processos. Não fazem trabalho assíncrono. Todas as transições recebem um `monotonic_ms` sintético vindo do harness, que **no dispositivo terá de ser lido pelo próprio serviço protegido**.

Parâmetros para o **laboratório**, ainda não recomendados como valores definitivos de rede:
- `WR_CY_TIMEOUT_MS = 15.000`: tempo máximo sintético da tarefa.
- `WR_CY_INITIAL_BACKOFF_MS = 30.000`: primeira janela de retry após falha.
- `WR_CY_MAX_BACKOFF_MS = 240.000`: teto após falhas repetidas.
- `WR_CX_MIN_START_INTERVAL_MS = 60.000`: janela mínima entre inícios herdada de CX.
- `WR_CX_MAX_PENDING = 1`: limite de pendências herdado de CX.

### Transições

1. `wr_cy_offer` admite só `WRCHK2\n` (exatos 7 bytes). URL, IPA, caminho, `WRINST1`, consentimento, chave ou extras não entram. Quando permitido, a CX inicia um trabalhador lógico ou coalesce uma notificação pendente.
2. `wr_cy_poll` pode iniciar o único pendente após cooldown, mas **nunca** enquanto houver tarefa ativa, pedido de cancelamento ou backoff.
3. `wr_cy_watchdog` sinaliza `TIMEOUT_CANCEL_REQUESTED` ao alcançar 15.000 ms. `offer`/`poll`/`complete` também recusam trabalho vencido caso o watchdog ainda não tenha sido chamado. O worker **continua marcado ativo**.
4. `wr_cy_complete(ticket, success)` só aceita o ticket local atual, antes do prazo e sem pedido de cancelamento. Quando falha, limpa a fila e começa backoff; quando conclui bem, zera o contador de falhas. Um `complete(success=true)` tardio não elimina um timeout.
5. `wr_cy_ack_cancel(ticket)` só é aceito com cancelamento solicitado e ticket atual; registra falha, descarta fila e aplica backoff. **O chamador confiável deve garantir que o trabalhador realmente terminou antes dessa chamada**.
6. Falhas consecutivas usam 30 s, 60 s, 120 s e 240 s, com teto de 240 s. Uma conclusão bem-sucedida reinicia a contagem.
7. `wr_cy_cancel_pending` não interrompe o ativo. `wr_cy_shutdown` recusa novas transições, mas preserva no recibo `worker_may_still_be_running=true` se existia trabalho. O chamador deve fazer join de todas as threads antes de liberar a estrutura; destruir o objeto enquanto há tarefas em execução continua inseguro.

A estrutura `WR_CY_Receipt` possui `status`, ticket local, janela de backoff, pending 0/1, contador de falhas, `worker_may_still_be_running` e `cancel_requested`. Todos os campos `caller_authenticated`, `publisher_verified`, `ipa_bytes_authenticated`, `owner_consent_verified`, `installation_authorized`, `installation_performed` permanecem **false em qualquer resultado**, inclusive sucesso ou ACK.

## Testes adversariais

`ci/test_build70_cy_supervisor.py` compila biblioteca nativa descartável host Linux/macOS e valida:

- Uma execução ativa + uma solicitação pendente sem expansão.
- Prazo no limite exato, negação de nova checagem sem ACK e sucesso tardio rejeitado.
- ACK incorreto/obsoleto, tentativa de completar como sucesso depois de vencido.
- Exponential backoff com limite; sucesso zera sequência de falhas.
- Falhas limpam pendências; cancelamento de pendência mantém ativo.
- **250 avisos concorrentes**: um início, um coalescido e os demais recusados por fila cheia.
- Recuo de relógio, limites de `uint64`, pacotes malformados e comandos `WRINST1`.
- Encerramento sem fingir que o trabalhador parou, argumentos nulos, duas instâncias independentes e ausência de símbolos instaladores.

Workflow `.github/workflows/chimera-build70-phase-cy-cooperative-watchdog.yml`: Linux e macOS 15 rodam testes C/ctypes; macOS/Xcode16.4 compila **objetos ARM64 com mínimo iOS12**; nenhum binário instalável, IPA/DEB ou asset de Release é publicado.

## Bloqueios que CY NÃO resolve

- Não existe daemon, helper privilegiado, launchd, cron, listener ou download em produção. A fila/backoff existe apenas enquanto o objeto C vive; reiniciar processos apaga as observações e o rate-limit. O serviço real precisará de uma única instância confiável, quotas globais, monitoramento de recursos, proteção contra reinícios abusivos e política de rede separada.
- A simulação não consegue interromper um socket bloqueado nem verificar fisicamente se uma thread antiga terminou; depende de ACK correto do componente que gerencia o worker. Não há isolamento comprovado iOS12/Chimera e o cliente continua **não autenticado** (`LOCAL_PEERTOKEN` negado no dispositivo).
- A origem editorial fixa, confiança real da chave P-256 do proprietário, pin público conferido independentemente, manifesto production-v2, código assinado, integridade até o serviço `installd`, proteção anti-replay e consentimento local individual são gates **separados e ainda ausentes**.
- O `LSApplicationWorkspace` de interface privada foi somente compilado como probe na CV, sem prova runtime/entitlement; `appinst` público de referência tem segunda cópia baseada em pathname e não tem prova de custódia dos bytes finais.
- Não usar valores de timeout de laboratório como SLA em dispositivo. Não inserir ferramenta de instalação real no wrapper.

**Travamentos permanentes:** `WebReaderAppinstSocket.liveInstallationEnabled=false`, `WebReaderUpdateChannel.productionPublicKeyX963=nil`, `WebReaderProductionPublisherTrust.independentlyProvisionedSPKISHA256=nil`. PR #90 Draft, `main` intacta, Build70 física preservada.

**Próxima decisão técnica:** concentrar-se numa arquitetura de **worker check-only com cancelamento cooperativo real em um harness de host**, com slot único, deadline controlado e resolução de falha/reinício; em paralelo registrar o design do helper com identidade/custódia independentemente verificáveis. Não instalar nada no iPad até todos os gates de segurança.

**CI:** resultado final a acrescentar após validação dos três jobs. Não pressupor SUCCESS antes dos logs.

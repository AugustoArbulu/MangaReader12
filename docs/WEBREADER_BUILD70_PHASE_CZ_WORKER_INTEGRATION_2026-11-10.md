# WebReader Build70 — Fase CZ: integração real de threads sintéticas com o supervisor CY

**Data:** 10/11/2026. **Branch:** `feat/chimera-updater-phase1-protocol-audit`, **PR #90 Draft**. Sem merge na `main`. Build70 do iPad iOS12.5.8, biblioteca, favoritos, downloads offline, Releases e binário `appinst` não foram alterados.

## Por que CZ é diferente das fases anteriores

CW demonstrou a política nativa C para o comando exato `WRCHK2\n`. CX adicionou limite de uma checagem ativa + uma pendência. CY implementou timeout e cancelamento **cooperativo**, negando nova checagem até o trabalhador sinalizar que realmente encerrou. Essas fases ainda exercitavam a máquina de estados de forma isolada.

Em CZ, uma biblioteca nativa temporária (composta dos fontes C das fases CX+CY) é usada por um *harness Python* no host. A classe `SyntheticCheckRuntime` mantém um supervisor nativo, um relógio virtual controlado **pelo harness**, um mutex de chamada e uma única thread trabalhadora sintética. Isso permite observar threads reais aguardando sinais de conclusão ou cancelamento, **sem rede, IPA, serviço privilegiado ou execução no iPad**.

## Implementação

- `ci/build70_cz_synthetic_worker_runtime.py`: integra um único supervisor CY à thread `CZ-SYNTHETIC-NOT-NETWORK`; a thread não consulta GitHub, não abre arquivo de IPA, não instala e não implementa IPC. Só aguarda eventos locais do harness.
- `ci/test_build70_cz_synthetic_worker_runtime.py`: compila a biblioteca C no runner de teste e usa as chamadas CY via `ctypes`. Testa passagem de conclusão normal com uma pendência, trabalho travado, cancelamento cooperativo, falha + backoff, 256 frames em concorrência, inserção de `WRINST1`/URL/caminho, estado após reinício desconhecido e uso incorreto de relógio.
- `.github/workflows/chimera-build70-phase-cz-synthetic-worker.yml`: testes host em Linux e macOS; reexecuta também 18 testes da CY; garante os três gates Swift de produção bloqueados. Um job Xcode16.4 recompila os objetos C nativos para ARM64/iOS12, sem criar executável distribuível.

## Contrato de segurança demonstrado em laboratório

1. **Um único comando cliente.** `offer_untrusted(packet)` aceita somente objetos bytes. Todos os comandos são revalidados pelo núcleo C CY, que aceita somente `WRCHK2\n`. Nenhum dado de assinatura, versão, IPA ou consentimento vem do cliente.
2. **Um relógio separado do comando.** `advance_host_clock` e `poll_host_queue` são controles do harness, não campos de IPC. Na futura implementação nativa, só o serviço poderá ler o tempo monotônico do kernel.
3. **Sem trabalho paralelo.** A rotina de teste só cria uma nova thread quando a CX/CY retornam `STARTED` e não há outra thread atribuída ao slot. Em concorrência, os avisos válidos se reduzem a uma tarefa ativa, uma pendência e vários estados de fila cheia.
4. **Deadline não mata thread.** Quando o tempo virtual alcança 15.000 ms, o CY retorna `TIMEOUT_CANCEL_REQUESTED` e o harness marca o evento `cancelled`. Um trabalhador no modo *blocked* continua vivo, mesmo após tempo virtual muito maior. Nenhuma nova tarefa é permitida enquanto não houver confirmação de saída.
5. **ACK depois do encerramento comprovado no próprio host.** A rotina `reap_finished_worker` só chama `wr_cy_ack_cancel(ticket)` depois que a thread sinaliza `finished` e `join()` confirma que ela não está mais viva. Mesmo quando uma thread já entregou um resultado de sucesso, uma expiração anterior invalida o resultado.
6. **Falha limpa pendência e aplica backoff; sucesso reinicia o contador de falhas.** A CY continua controlando esse fluxo e os tickets locais não são expostos pelo único método de entrada cliente.
7. **Encerramento sem use-after-free no harness.** `close()` solicita parada, sinaliza saída, aguarda `join()` e só então chama `wr_cy_shutdown`/`wr_cy_free`. Isso é uma propriedade do fixture, não um contrato de segurança com threads arbitrárias.
8. **Reinício desconhecido permanece um problema real.** O laboratório possui um `recovery_required=True` injetado explicitamente que recusa checagens até uma chamada separada de `reconcile_quarantine_host_only()`; ambos são controles de teste **não autenticados nem persistidos**. Outro teste cria duas instâncias e demonstra que ambas podem iniciar uma checagem simultânea sem estado durável compartilhado. Logo, isto NÃO é proteção real contra reset, crash, rollback, reinício do daemon ou acesso pelo mesmo UID.

## O que a Fase CZ NÃO comprova

A thread faz trabalho sintético local e não pode provar cancelamento de `URLSession`, proteção de descritores reais, integração com `launchd`, isolamento de UID ou entitlement Chimera, fila global compartilhada entre processos, raiz editorial aprovada, pin/assinatura de produção, replay journal protegido, consentimento do proprietário ou vínculo dos bytes da IPA até `installd`.

Até novo desenvolvimento e QA física, a política em C/Python não deve ser conectada a uma porta TCP de instalação ou a um helper privilegiado. A experiência manual via Filza/NewTerm/`appinst` permanece o fallback validado, e **nenhum teste CZ autoriza instalação**.

## Próximos gates

Para a fase seguinte, definir uma política de recuperação **durável e independente do aplicativo**, que bloqueie automaticamente um serviço após reinício desconhecido e só permita reabilitar checagens quando um supervisor realmente puder comprovar ausência de tarefas antigas e estado editorial protegido. A recuperação não deve usar um token HMAC do aplicativo como substituto para identidade do processo. Separadamente, resolver confiança editorial real e a transição de arquivo para o serviço Apple antes da instalação automatizada.

**Hard stops:** `WebReaderAppinstSocket.liveInstallationEnabled=false`, `WebReaderUpdateChannel.productionPublicKeyX963=nil`, `WebReaderProductionPublisherTrust.independentlyProvisionedSPKISHA256=nil`. PR #90 Draft, `main` intocada. Nenhum IPA, DEB, nova Build71 ou Release produzidos.

## Evidência final — GitHub Actions

**SUCCESS 3/3:** https://github.com/AugustoArbulu/MangaReader12/actions/runs/42774135947

- **Ubuntu:** 14/14 testes de integração CZ aprovados, mais 18/18 testes de regressão CY.
- **macOS15:** 14/14 testes CZ aprovados, mais 18/18 testes CY.
- **Xcode16.4 / iOS12 ARM64:** dois objetos Mach-O arm64 das fases CX/CY compilados e inspecionados; não foram executados no iPad. Não houve geração de executável de helper, IPA, DEB ou asset de Release.
- A CI também confirmou `liveInstallationEnabled=false`, `productionPublicKeyX963=nil`, `independentlyProvisionedSPKISHA256=nil`.

**O que o verde significa:** o harness host com thread sintética está funcionando nos dois sistemas e a parte C da política continua compilável para ARM64/iOS12. **Não** significa que o iOS12 tenha um serviço seguro, que o cliente esteja autenticado, que um download de rede possa ser cancelado ou que o instalador receba uma IPA imutável.

**Decisão:** a futura implementação de serviço deve iniciar em quarentena em casos de reinício sem reconciliação independente de estado durável; não reutilizar `reconcile_quarantine_host_only()` como mecanismo produtivo. Em paralelo, demonstrar a custódia editorial e o consumo exato dos bytes pela instalação, com autorização local explícita antes de destravar qualquer caminho de instalação.


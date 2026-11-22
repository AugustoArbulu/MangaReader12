# WebReader Build70 — Fase CX: fila limitada de checagens, ciclo de vida e cancelamento

**Data:** 10/11/2026. **Branch experimental:** `feat/chimera-updater-phase1-protocol-audit`. **PR #90 Draft.** `main`, releases, Build70 no iPad, biblioteca, favoritos e capítulos offline preservados.

## Contexto e problema

A Fase CW entregou o núcleo C que aceita apenas `WRCHK2\n` e rejeita qualquer instrução de instalação/URL/path; a versão concorrente CW serializa um único estado por processo. Ainda faltava modelar explicitamente **a sobreposição de uma consulta em andamento com múltiplas novas solicitações**, limites de fila, conclusão e cancelamento do trabalho sem permitir que um cliente controle o recurso.

Esta Fase CX não é o helper instalador. Ela cria uma máquina de estados em memória, **somente host, não privilegiada**, para uma eventual política global de *checagem somente leitura* mantida por uma única instância protegida do futuro serviço.

## Arquivos

- `ci/build70_cx_bounded_scheduler.h`, `ci/build70_cx_bounded_scheduler.c`: tipo opaco de scheduler, mutex pthread, apenas uma checagem ativa e **no máximo um aviso pendente**, independente do número de callers. Não aloca fila arbitrária nem guarda URL, digest, IPA, chave ou identidade de caller.
- `ci/test_build70_cx_bounded_scheduler.py`: **15 testes host**, que compilam o C como biblioteca descartável e chamam os estados por `ctypes`, com 512 triggers concorrentes, formas inválidas, cancelamentos, tickets obsoletos, overflow de tempo, recuo de relógio, cooldown, encerramento e ausência de APIs de instalação.
- `.github/workflows/chimera-build70-phase-cx-bounded-check-queue.yml`: CI Linux/macOS com testes host e compilação de **objeto ARM64 para iOS12, não executável**, mais verificações de travas em Swift.

## Máquina de estados

1. `wr_cx_offer` aceita somente os 7 bytes `WRCHK2\n`. Rejeita `WRINST1`, qualquer sufixo, URL/caminho e bytes nulos. Frames rejeitados não consomem quota de checagem.
2. Se não houver consulta ativa nem intervalo de segurança pendente, retorna `STARTED` com *ticket local para o trabalhador interno*. O ticket **não é e nunca deve ser repassado a um cliente IPC**.
3. Com consulta ativa, ou cooldown de menos de 60.000 ms desde o último início, um pedido válido apenas estabelece `pending=true`. Dez ou mil pedidos adicionais são coalescidos no **mesmo** indicador, sem expansão da fila.
4. `wr_cx_finish(ticket)` só libera trabalho ativo com o ticket interno atual. Ticket antigo ou errado retorna `STALE`, mantendo o novo trabalho intocado.
5. `wr_cx_poll` só inicia o pedido pendente quando não há consulta ativa e o cooldown expirou. Não faz nenhuma checagem de versão por conta própria.
6. `wr_cx_cancel_pending` cancela somente a fila. `wr_cx_cancel_active(ticket)` invalida o ativo e descarta a fila. `wr_cx_shutdown` descarta todos os estados e recusa novos trabalhos.
7. Monotonicidade: o relógio deve ser fornecido **pelo próprio serviço confiável**, nunca pelo caller do IPC; retrocessos são recusados. A implementação usa subtração protegida para impedir overflow nos limites de uint64.

O recibo `WR_CX_Receipt` é **somente informativo**: registra status, ticket do trabalhador interno, estado da fila 0/1 e checagem ativa. Mantém explicitamente todos os campos de autenticação, assinatura editorial, escolha de IPA, custódia, consentimento e instalação em false. Nem `STARTED` nem `FINISHED` significam instalação ou download.

## Limitações e ameaças não resolvidas

- **Não existe socket, daemon, serviço launchd, conta isolada, quota global entre processos ou rede.** Dois schedulers separados ainda podem iniciar uma checagem cada. Um serviço real deve impor uma única instância de autoridade, controle de flood, budget de conexões, recursos, timeout, backoff de HTTP e antiabuso.
- Cancelar um estado de laboratório **não interrompe automaticamente** um download, instalação ou operação de outro processo; a futura execução real terá de verificar cancelamento cooperativo, recursos e cleanup. Nunca interpretar cancelamento como reversão de instalação.
- A política não autentica o editor nem escolhe uma origem de release. Chave P-256 real do proprietário, pin compilado independentemente, envelope production-v2 assinado, code seal da IPA e anti-replay/anti-rollback continuam bloqueados.
- **Não há instalador.** A interface privada `LSApplicationWorkspace` não foi validada no runtime iOS12, seu entitlement não é conhecido, e o problema da mutação dos bytes até consumo efetivo não foi resolvido; usar o appinst de referência por pathname também não dá essa garantia.
- `pthread_mutex` cobre somente as transições deste objeto. O caller deve sincronizar e aguardar o fim dos trabalhadores antes de liberar a instância; não existe proteção contra uso-após-free de um objeto destruído em outra thread. O ID da operação não é uma credencial criptográfica.
- `monotonic_ms` é um parâmetro injetado para ensaio: o próprio serviço precisará obtê-lo de uma fonte do sistema, nunca do app.

## Gates para um helper de verdade

Antes de qualquer rede/download: escolher origem fixa no helper, provar limite global/recursos, endurecer autenticação do canal/editor e provar separação de leitura/gravação. Antes de instalação: dados reais do proprietário, liberação de confiança de editor, integridade dos mesmos bytes até Apple installd, consentimento local confiável, diário durável e recuperação com biblioteca intacta. Os testes do scheduler não são autorização para eliminar esses gates.

**Hard stops:** `WebReaderAppinstSocket.liveInstallationEnabled=false`; `WebReaderUpdateChannel.productionPublicKeyX963=nil`; `WebReaderProductionPublisherTrust.independentlyProvisionedSPKISHA256=nil`. Nenhuma IPA/DEB/Release, nenhum pedido físico ao usuário nesta fase.

## Resultado de execução — CI verificada em 10/11/2026

**SUCCESS 3/3:** https://github.com/AugustoArbulu/MangaReader12/actions/runs/42771220119

- **Ubuntu:** 15/15 testes aprovados, incluindo 512 solicitações concorrentes (uma ativa, uma pendente, 510 coalescidas sem novos slots), replay de ticket vencido, cancelamento e monotonicidade.
- **macOS 15:** 15/15 testes aprovados, a mesma bateria host, sem acesso privilegiado.
- **Xcode 16.4:** objeto `Mach-O 64-bit object arm64` para target iOS 12.0 compilado e inspecionado, sem criação ou publicação de executável do helper e sem símbolos de instalação.
- As validações estáticas também verificaram que `productionPublicKeyX963=nil`, `independentlyProvisionedSPKISHA256=nil` e `liveInstallationEnabled=false`.

**Significado preciso:** o scheduler nativo de *checagem somente leitura* é consistente nos laboratórios de host e compatível com a compilação de objeto ARM64/iOS12. Isso não comprova permissões, isolamento de helper, consumo da IPA pelo serviço Apple ou qualquer comportamento no iPad físico. Nenhuma autoridade de instalação foi concedida ou habilitada.

**Próxima decisão:** limitar a implementação a um processo de serviço único e defensivo e especificar sua infraestrutura de supervisão (tempo de tarefa, cancelamento cooperativo, quotas globais, backoff, inicialização e recuperação). Separadamente, o projeto segue bloqueado pela cadeia editorial real + origem fixa + staging imutável até o consumidor + consentimento local seguro. Não ativar rede ou instalação até revisão independente e testes físicos.

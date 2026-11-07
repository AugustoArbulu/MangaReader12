# WebReader / MangaReader12 — Fase I: bytes acumulados versus identidade de quem escreveu

**Data:** 2026-11-07 UTC  
**Repositório:** `AugustoArbulu/MangaReader12`  
**Branch de desenvolvimento:** `feat/chimera-updater-phase1-protocol-audit`  
**PR:** [#90](https://github.com/AugustoArbulu/MangaReader12/pull/90), **Draft**, sem merge na `main`.  
**App estável instalado:** Build 65, iPad iOS 12.5.8 com Chimera; biblioteca e arquivos offline preservados.

## Descoberta principal — NÃO usar o token lido após recv() como autoria de bytes

A Fase H observou A → B → A quando cada remetente enviou sua mensagem e recebeu um ACK **antes** da mensagem seguinte. A Fase I removeu deliberadamente essa serialização.

O experimento macOS compila três executáveis independentes, assinados ad hoc: servidor S, origem A, segundo remetente B. A abre um `AF_UNIX SOCK_STREAM`, escreve `WRHELLO1`, transfere o **mesmo descritor conectado** a B por `SCM_RIGHTS`; B escreve outro `WRHELLO1`. O servidor S não lê **nenhum** byte até B ter terminado a segunda escrita e A abrir uma conexão de controle separada (barreira/gate). Só então S faz uma das duas leituras:

1. **SPLIT:** dois `recv(...,8,MSG_WAITALL)` seguidos, cada um com uma consulta separada de `LOCAL_PEERTOKEN` → `csops_audittoken(CS_OPS_CDHASH)`.
2. **BATCH:** um `recv(...,16,MSG_WAITALL)`, com uma consulta de token para os dois quadros.

Cada variante é executada com a referência CDHash verificada de A e depois com a de B, sem imprimir hashes, PID ou tokens. Os papéis de A e B também são invertidos. O servidor retorna apenas resultados de laboratório; nenhuma instalação.

### Resultado confirmado

O workflow [Phase I #42347031829](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42347031829) terminou **SUCCESS nos jobs Linux e macOS**, no commit `1890d567`:

| Ensaio macOS | Rodadas | Observação |
| --- | ---: | --- |
| SPLIT, duas leituras de 8 bytes já enfileirados | 3/3 | **B, B**: ambas as consultas retornaram código de B, ainda que o primeiro quadro tenha sido enviado por A |
| BATCH, uma leitura de 16 bytes | 3/3 | **B**, uma única consulta: impossível atribuir cada quadro individualmente |
| Papéis invertidos | 1/1 de cada modo | O código observado acompanhou o **último remetente** nos dois modos |
| Parser de relatórios no Linux/macOS | 28 testes por job | Aprovados |
| Regressão Fase H, mensagens serializadas A → B → A | 3/3 + inversão | Continuou aprovada |
| Travas de produção | ambas presentes | `liveInstallationEnabled = false`, `productionPublicKeyX963 = nil` |

**Interpretação:** em um fluxo `SOCK_STREAM` com dados de processos diferentes já enfileirados, o token consultado após o `recv()` pode referir-se ao **último processo que escreveu no socket**, não ao autor dos bytes recém-lidos. O resultado é uma demonstração controlada **no runner macOS**, não uma afirmação universal sobre XNU, iOS12 ou qualquer interleaving arbitrário. Ainda assim invalida o uso desse token, sem outro vínculo criptográfico, como prova da autoria de cada pedido/byte de instalação.

A observação de identidade temporal A → B → A da Fase H era verdadeira para o caso de mensagens serializadas, mas **insuficiente para generalizar** a autorização em condições com buffer.

O classificador Python nunca emite `stream_frames_authenticated=True`, `installation_authorized=True` ou `ios12_verified=True`. A suíte nativa foi reforçada posteriormente para exigir explicitamente as observações de B/B e B/sem segunda amostra; uma alteração de comportamento do kernel deve aparecer como falha, não como um PASS silencioso. Essa revalidação posterior deve ser consultada separadamente.

## Arquivos do lote

- `ci/build66_scm_rights_handoff_lab.c`: novos modos `origin-queued`, `receiver-queued`, `serve-queued-split` e `serve-queued-batch`; sem elevação/instalador.
- `ci/build66_queued_peer_report.py`: parser e classificações não-autoritativas, somente texto ASCII estrito.
- `ci/test_build66_queued_peer_report.py`: 28 casos, relatórios forjados, erros de kernel, ordem errada e flags indevidas.
- `ci/test_build66_queued_scm_rights_lab.py`: programa de reprodução macOS com dois executáveis assinados, gate, inversão de papéis e asserções explícitas de resultados.
- `.github/workflows/chimera-build66-queued-stream.yml`: validação Linux/macOS, rerun da Fase H, checagem das travas Swift.

## Decisão arquitetural

**Não usar `LOCAL_PEERTOKEN` amostrado após `recv` para autorizar um opcode `INSTALL` ou atribuir autoria criptográfica a bytes do stream.** É inadequado pressupor que um CDHash observado represente cada solicitação lida, mesmo se a referência de código for confiável.

Alternativa segura para avançar sem esse vínculo: a interface do WebReader pode pedir somente `CHECK_ONLY`, sem fornecer URL/IPA/chave/comando; o componente independente escolhe metadados e valida manifesto assinado, hashes e versão. Instalação **não** decorre de `CHECK_ONLY`. Uma instalação futura, caso aprovada, depende de gesto presencial/consentimento confiável, pacote de release validado de forma independente, bytes imutáveis revalidados no executante e proteção contra replay/rollback.

Não substituir a autenticação por token obtido via texto do cliente, PID, UID, nome do app, HMAC temporário ou CDHash de executável copiado. Um hash ad hoc compatível não autentica editor/publicador.

## Próximo teste útil: iPad real, sem novas fases de laboratório

O diagnóstico separado da Fase E já compila para **ARM64/iOS12** e não tem instalador, daemon ou `appinst`. Na execução [Fase E #42347031802](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42347031802), ambos os jobs passaram e foi publicado o artifact **`WebReader-Build66-CSOpsTokenProbe-CLI-only-iOS12`**, ID **`13563589894`** (disponível no GitHub Actions, prazo de retenção configurado de 14 dias). Dentro dele: `WebReader-Chimera-CSOpsTokenProbe66-iOS12.deb` e checksums. A execução real no iPad ainda **não ocorreu**.

Para QA físico, **somente após a decisão do proprietário**:

1. Baixar o artifact da execução citada, conferir o checksum SHA-256 do arquivo DEB contra o manifesto no ZIP.
2. Opcionalmente extrair o DEB para pasta separada usando ferramenta compatível; não há necessidade técnica de instalar o pacote inteiro para fazer o `selftest` da CLI.
3. Executar **como mobile, não root** o binário `webreader-csopsprobe66 selftest` e recolher as **sete linhas de saída**, preservando o status de retorno. O binário recusa root e não imprime dados de processos/segredos.
4. Interpretar `UNIX_PEERTOKEN`, `CSOPS_TOKEN_BINDING` e presença de símbolos. Mesmo `MUTATION_REJECTED` no iPad significaria **somente capacidade da API em um processo filho controlado**, não autenticação do WebReader nem autorização de instalação.

A disponibilidade de `fork`/socket e `csops_audittoken` no Chimera com assinatura ad hoc continua uma **incógnita de runtime**. Não exigir root para forçar sucesso, não alterar o serviço PING da Build 61 nem substituir o app estável.

**Estado:** a Build 65 e o backup da biblioteca permanecem intocados; nenhuma IPA Build 66 instalável foi gerada; PR #90 continua Draft; `main` sem merge; instalação automática segue bloqueada.

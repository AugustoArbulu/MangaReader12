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

O classificador Python nunca emite `stream_frames_authenticated=True`, `installation_authorized=True` ou `ios12_verified=True`. A suíte nativa foi reforçada posteriormente para exigir explicitamente as observações de B/B e B/sem segunda amostra; uma alteração de comportamento do kernel deve aparecer como falha, não como um PASS silencioso. Essa revalidação **passou nos dois jobs** do workflow [Phase I #42347135891](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42347135891): as asserções explícitas de B/B e B/sem segunda amostra foram aprovadas, juntamente com a regressão da Fase H e as travas Swift.

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

## Diagnóstico físico no iPad — primeiro resultado confirmado

O diagnóstico separado da Fase E já compila para **ARM64/iOS12** e não tem instalador, daemon ou `appinst`. Na execução [Fase E #42347031802](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42347031802), ambos os jobs passaram e foi publicado o artifact **`WebReader-Build66-CSOpsTokenProbe-CLI-only-iOS12`**, ID **`13563589894`** (disponível no GitHub Actions, prazo de retenção configurado de 14 dias). Dentro dele: `WebReader-Chimera-CSOpsTokenProbe66-iOS12.deb` e checksums. O SHA-256 **do DEB**, confirmado no log de empacotamento dessa execução, é `71457b449ee16b602c0141beec309023141802795d57dec71f35a2c0f3775266` (não confundir com o checksum do ZIP do artifact). A execução física no iPad **ocorreu em 2026-11-07**, conforme transcrição observada enviada pelo proprietário; resultados documentados na seção seguinte.

Para QA físico, **somente após a decisão do proprietário**:

1. Baixar o artifact da execução citada, conferir o checksum SHA-256 do arquivo DEB contra o manifesto no ZIP.
2. Opcionalmente extrair o DEB para pasta separada usando ferramenta compatível; não há necessidade técnica de instalar o pacote inteiro para fazer o `selftest` da CLI.
3. Executar **como mobile, não root** o binário `webreader-csopsprobe66 selftest` e recolher as **sete linhas de saída**, preservando o status de retorno. O binário recusa root e não imprime dados de processos/segredos.
4. Interpretar `UNIX_PEERTOKEN`, `CSOPS_TOKEN_BINDING` e presença de símbolos. Mesmo `MUTATION_REJECTED` no iPad significaria **somente capacidade da API em um processo filho controlado**, não autenticação do WebReader nem autorização de instalação.

A execução da CLI em `mobile` no Chimera foi confirmada; contudo, **`LOCAL_PEERTOKEN` não forneceu um token utilizável**, impedindo o ensaio `csops_audittoken` nesse dispositivo. A indisponibilidade observada não demonstra que toda API alternativa de identidade de processos seja impossível no iOS 12. Não exigir root para forçar sucesso, não alterar o serviço PING da Build 61 nem substituir o app estável.

### Saída física recebida — iOS 12.5.8 / Chimera, usuário `mobile`

Comando usado: `/usr/local/bin/webreader-csopsprobe66 selftest`.
O usuário comprovou `whoami = mobile`. O diagnóstico terminou e voltou
ao prompt normal do NewTerm 2, com estas **sete linhas observadas**:

```text
WEBREADER_BUILD66_CSOPS_AUDITTOKEN_CAPABILITY: non-root, read-only
PROBE UNIX_PEERTOKEN=UNAVAILABLE AUTHORIZATION=DENIED
PROBE CSOPS_TOKEN_BINDING=NOT_TESTED AUTHORIZATION=DENIED
PROBE SECURITY_SecCodeCreateWithAuditToken=MISSING AUTHORIZATION=DENIED
PROBE SECURITY_SecCodeCopyGuestWithAttributes=MISSING AUTHORIZATION=DENIED
PROBE SECURITY_SecCodeCreateWithPID=MISSING AUTHORIZATION=DENIED
FINAL_INSTALL_AUTHORIZATION=DENIED
```

**Interpretação do resultado real:**

- `UNIX_PEERTOKEN=UNAVAILABLE`: `getsockopt(SOL_LOCAL, LOCAL_PEERTOKEN)`
  não retornou uma estrutura `audit_token_t` válida na conexão controlada.
  Esse estado agrega falha da chamada e tamanho inválido; **não inclui errno**.
  Não presumir a causa específica (por exemplo, `ENOPROTOOPT`, `EPERM`).
- `CSOPS_TOKEN_BINDING=NOT_TESTED`: o diagnóstico não tentou `csops_audittoken`
  porque não havia token utilizável. **Não afirmar** que a syscall foi negada.
- Três símbolos `Security_...=MISSING`: as três funções procuradas por
  `dlsym` não foram encontradas no framework carregado nesse ambiente.
  Isso **não elimina** todos os mecanismos possíveis de autorização no iOS12.
- `FINAL_INSTALL_AUTHORIZATION=DENIED` é resultado esperado: nenhuma
  instalação realizada, nenhum `appinst` acionado.
- `alpine: command not found` e a mensagem inicial do zsh mostradas antes
  da execução são independentes deste diagnóstico e não alteram os resultados.
- O resultado físico **contrasta com o macOS**, onde a mesma família
  de consultas era acessível no laboratório. A CI macOS é útil para
  investigar semântica, mas não pode determinar disponibilidade no Chimera.

**Decisão de projeto:** não usar `LOCAL_PEERTOKEN` +
`csops_audittoken` como autenticação obrigatória do helper no iOS12 nas
condições atuais. Não tentar privilégio root para forçar o diagnóstico.
Priorizar atualização `CHECK_ONLY`, assinatura editorial de manifesto,
hash da IPA, consentimento independente, e fluxo manual de instalação
enquanto não houver método de autorização de origem confiável demonstrado.

**Próximo diagnóstico opcional e limitado:** se necessário, desenvolver
novo utilitário **não-root, read-only** que classifique o erro real de
`getsockopt` e diferenças de ambiente iOS12, sem habilitar instalações
ou consultar processos de terceiros. Não solicitar novos testes nem
instalar outra IPA automaticamente.

**Estado:** a Build 65 e o backup da biblioteca permanecem intocados; nenhuma IPA Build 66 instalável foi gerada; PR #90 continua Draft; `main` sem merge; instalação automática segue bloqueada.

# WebReader / MangaReader12 — Fase H: SCM_RIGHTS e autoria das mensagens

**Data:** 2026-11-07 UTC  
**Branch:** `feat/chimera-updater-phase1-protocol-audit`  
**PR:** #90, Draft, base `main`. Não modificar a `main`.  
**Versão instalada:** Build 65, iOS 12.5.8/Chimera, biblioteca e arquivos offline preservados.

## Motivação — lacuna de segurança das Fases F/G

A Fase G foi aprovada no macOS com **servidor e cliente executados separadamente**, assinados ad hoc, permitindo detectar um código de cliente diferente por CDHash. Entretanto, ainda faltava verificar o que acontece quando o cliente que **abriu** o socket não é o processo que **escreve** uma mensagem nele. Um descritor pode ser entregue a outro processo por `SCM_RIGHTS` em `sendmsg/recvmsg`. A transferência pode invalidar a hipótese de que `LOCAL_PEERTOKEN` identifique o autor de **cada mensagem subsequente**.

Não é permitido usar resultados de correspondência de CDHash como autorização de instalação. Este laboratório é um ensaio macOS com processos de teste controlados, sem iOS, aplicativo real, download, sistema de arquivos do usuário, servidor permanente ou serviço root.

## Desenho do ensaio

1. Compilar e assinar ad hoc três executáveis distintos: servidor S, cliente A e cliente B, todos executados sem root.
2. Construir uma linha de base com A conectado diretamente a S e com B conectado diretamente a S. A assinatura estática de A é conferida pelo `codesign` antes da execução; as referências do cliente são fornecidas pelo **harness**.
3. A abre a conexão de aplicação com S, mas **não escreve bytes da mensagem**.
4. B é executado de maneira independente, abre um segundo socket UNIX de controle com A e recebe de A o descritor *já conectado* da aplicação usando `SCM_RIGHTS`.
5. **Apenas B** escreve os oito bytes `WRHELLO1` na conexão de aplicação transferida. S lê os bytes, interroga `LOCAL_PEERTOKEN` e consulta `csops_audittoken(CS_OPS_CDHASH)`. O PID do processo associado ao token e o CDHash são usados apenas em memória e nunca impressos.
6. Repetir o cenário de origem A/remetente B, alternando a referência do código de A e de B. Repetir com os papéis invertidos B/A. Adicionar um executável A copiado byte a byte com o mesmo CodeDirectory.
7. Encerrar os processos, fechar todos os descritores, remover os sockets e emitir somente um status sem dados pessoais.

### Classificação obrigatória

| Origem A corresponde | Remetente B corresponde | Interpretação |
| --- | --- | --- |
| Sim | Não | `ORIGIN_STICKY_AFTER_FD_TRANSFER`: o token descreve o **conector original**, não quem escreveu a mensagem |
| Não | Sim | `SENDER_CODE_OBSERVED_AFTER_FD_TRANSFER`: observou-se ligação com o remetente no ambiente de teste; ainda não é prova geral de autoria por mensagem |
| Sim | Sim | `AMBIGUOUS_BOTH_REFERENCES_MATCH`: inconclusivo, bloquear autorização |
| Não | Não | `NEITHER_REFERENCE_MATCHES`: inconclusivo, bloquear autorização |
| Qualquer erro/indisponibilidade | Qualquer | `INCONCLUSIVE_KERNEL_CAPABILITY`: inconclusivo, bloquear autorização |

Um programa capaz de apresentar `LOCAL_PEERTOKEN` e um CDHash legítimos em **uma conexão compartilhada** não prova que o autor de uma mensagem individual seja o executável esperado. Também não demonstra assinatura de editor, consentimento do usuário ou custódia do binário instalado.

## Artefatos de código

| Arquivo | Papel |
| --- | --- |
| `ci/build66_scm_rights_handoff_lab.c` | Aplicação de ensaio C com `serve-once`, `client-once`, `origin-pass`, `receiver-once`. Passa descritor de socket de aplicação por `SCM_RIGHTS`. Nenhum modo de instalação. |
| `ci/test_build66_scm_rights_handoff_lab.py` | Harness macOS; compila e assina três executáveis distintos, lança S/A/B, verifica que só B envia a mensagem, compara os dois hashes, troca papéis e testa cópia byte a byte. |
| `ci/build66_fd_handoff_findings.py` | Classificador estritamente de relatório, com `current_writer_authenticated=False`, `installation_authorized=False`. |
| `ci/test_build66_fd_handoff_findings.py` | **25 testes** com falhas de API, ambiguidades, relatos falsificados e as quatro interpretações possíveis. |
| `ci/build66_independent_peer_report.py` | Parser legado de 3 linhas da Fase G, ainda não autoritativo. |
| `.github/workflows/chimera-build66-fd-handoff.yml` | CI Linux/macOS, com testes negativos, compilação assinada ad hoc e confirmação das travas Swift. |

## Segurança e restrições

- O código é **não-privilegiado e macOS-only**, e sequer constrói IPA/DEB: todas as assinaturas são efêmeras e ad hoc do runner.
- Não importa chave privada do WebReader, não consulta dados de outros processos e não captura/imprime PID, UID, token ou CDHash.
- Um CDHash igual em uma cópia de executável não autentica editor, origem de publicação, installation identity nem consentimento do usuário.
- `liveInstallationEnabled = false`, `productionPublicKeyX963 = nil`, sem `appinst`, sem operação de instalação e sem mudança em Build65.
- Diferenciar **identidade de conexão**, **identidade do processo que efetivamente escreveu a mensagem** e **autorização independente do helper**.
- Mesmo que o token seja ligado ao processo que abriu a conexão, a autorização de instalação precisa de um fluxo separado: conteúdo de release assinado por chave editorial confiável, download escolhido pelo helper, verificação de bytes imutáveis e consentimento presencial/one-shot.

## Status dos testes

- Workflow **Phase H #12**, run `42345912881`: **SUCCESS em Linux e macOS**.
  [Ver execução](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42345912881).
- Linux/macOS: **82 testes Python por job**: 25 casos da classificação de transferência,
  30 casos do parser de transcritos e 27 do parser temporal.
- Teste macOS A-conecta/B-escreve: **3/3** observações
  `SENDER_CODE_OBSERVED_AFTER_FD_TRANSFER`, confirmadas também com
  papéis A/B invertidos.
- Teste temporal com um único socket, mensagens seriadas e ACKs entre as
  etapas: **3/3** observações
  `A_B_A_MESSAGE_SENDER_REBINDING_OBSERVED`, além da ordem invertida.
  O receptor B permaneceu com o descritor transferido ABERTO enquanto A
  enviou a terceira mensagem.
- Cliente diferente com CDHash incorreto foi rejeitado; uma cópia com
  código idêntico preservou o CDHash, como esperado. Nenhuma verificação
  elevou `installation_authorized`.

## Teste ampliado A → B → A — observação e alcance

O experimento ampliado introduziu `serve-three`, `origin-three` e
`receiver-hold` no programa de teste C, mais:
`ci/build66_temporal_peer_report.py`,
`ci/test_build66_temporal_peer_report.py` (27 testes),
`ci/test_build66_temporal_scm_rights_lab.py` e a integração de CI.

A ordem do fluxo é a seguinte: A escreve `WRHELLO1` e recebe ACK de S;
A transfere seu descritor conectado a B; B escreve o segundo `WRHELLO1`,
recebe ACK e notifica A; **B continua mantendo seu descritor aberto**; A
escreve o terceiro `WRHELLO1` e recebe ACK; só então A notifica B para
fechar o descritor. O servidor consulta o token imediatamente após cada
`recv` e antes do ACK seguinte. Para cada ensaio, o harness roda novamente
com a referência do CDHash de A e com a de B, obtidas previamente por
`codesign --verify` e `codesign -d --verbose=4`.

**Resultado no macOS:** o CDHash identificado acompanhou A/B/A, mesmo com
o descritor de B ainda aberto. O resultado não foi causado simplesmente
pelo fechamento do descritor de B após escrever.

**Limites remanescentes críticos:** a sequência usa mensagens com ACKs
serializados. Não se testou ainda um processo A e um B enfileirando
mensagens antes de um único `recv`; em `SOCK_STREAM` os limites de
mensagens não são preservados. Portanto, a consulta de `LOCAL_PEERTOKEN`
após `recv` **não foi demonstrada como identidade criptograficamente
vinculada aos bytes lidos**, e a observação não é uma autenticação por
mensagem em condições concorrentes. A implementação futura do helper,
se existir, não deve atribuir privilégio ao emissor a partir desse
resultado isolado. O comportamento no Chimera/iOS 12.5.8 ainda é
desconhecido.

## Próximos gates

1. Validar as observações A-conecta/B-escreve e B-conecta/A-escreve no macOS, com execução de binários assinados e relatório não autorizativo.
2. Confirmar opcionalmente suporte de `LOCAL_PEERTOKEN` / `csops_audittoken` no iOS 12.5.8/Chimera por CLI separado e não-root; **nenhum teste físico ocorreu ainda**.
3. Não aproveitar `SCM_RIGHTS`, PID, UID ou CDHash da conexão como permissão de instalar. A arquitetura futura deve manter a consulta de atualizações independente do solicitante (somente `CHECK_ONLY`) e exigir autorização verificada por outro canal para a execução.
4. Definir política de chave editorial de produção, controle antirreplay/rollback em armazenamento protegido do helper e validação da mesma IPA que seria entregue ao instalador. Persistem bloqueios antes de ativar qualquer `appinst`.

**Não há nova IPA do WebReader. Build65, biblioteca e downloads não foram alterados.**

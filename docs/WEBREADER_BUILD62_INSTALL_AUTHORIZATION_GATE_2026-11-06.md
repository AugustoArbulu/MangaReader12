# WebReader Build62 — Portão de autorização do atualizador (iOS 12 / Chimera)

## Resultado comprovado e escopo

- **Build60 SignedQA:** usuário confirmou instalação real da v1 descartável, atualização v1→v2 pelo `appinst` e preservação de registro `NSUserDefaults` no iOS 12.5.8. Não comprova migração dos bancos SQLite/downloads do WebReader.
- **Build61 FIX1:** `launchd` manteve o helper **PING-only** ativo enquanto o usuário fechou e reabriu NewTerm e IPC Test Build59; cliente voltou a receber PONG. Reinício completo do iPad não testado.
- Os dois experimentos são independentes: nenhum serviço TCP persistente tem permissão de instalar IPA.

## Achado da revisão de código da Build62

A UI experimental de atualizações continha um botão "Instalar atualização (Chimera)" que podia enviar um pedido `WRINST1` pelo `WebReaderAppinstSocket` usando a procedência `publicGitHubRelease`. O hash SHA-256 da IPA era proveniente da **mesma Release do GitHub**. O cliente verificava consistência, mas não havia autenticação independente do editor, do processo solicitante ou da intenção do usuário do ponto de vista do instalador.

Esse caminho estava **inseguro para ser conectado a um helper com poder de instalação**, mesmo que a tela exigisse confirmação. A Build61 atual não expunha um instalador na porta TCP; a revisão é uma medida preventiva na branch.

## Mudanças efetivas Build62

1. A interface `WebReaderAppUpdatesViewController.swift` deixa de oferecer ou invocar o botão de instalar e deixa de copiar comandos `appinst`; as duas linhas agora explicam que a instalação está indisponível por falta de assinatura editorial e validação de identidade.
2. Continua possível **consultar releases públicos**, baixar IPA com verificação de hash/ZIP/Info.plist e **compartilhar/exportar o arquivo**. Nenhuma dessas ações é uma autorização do helper.
3. `WebReaderAppinstSocket.install` sempre devolve `.rejected` no cliente real, sem enviar bytes para socket, mesmo se a tela for contornada.
4. O gerador de mensagens `WRINST1`, sua frase de confirmação e o teste `hostInstall` são compilados **apenas** com a macro `WEBREADER_HOST_TEST`. O target normal iOS não possui o serializador da solicitação de instalação.
5. O harness macOS usa `-D WEBREADER_HOST_TEST` explicitamente, ainda executando protocolo com **appinst falso** e IPA sintética não instalável.
6. `ci/test_chimera_build62_install_admission.py` compila o cliente no modo normal e confirma que a chamada de instalação é negada, que a saída compilada não contém o opcode `WRINST1`, que os métodos `hostInstall` não são compiláveis sem a macro e que a UI não tem action/clipboard para instalação.
7. O workflow exclusivo `.github/workflows/chimera-build62-install-security.yml` executa os testes anteriores e compila o **projeto iOS 12 Release** sem assinatura ou instalação, publicando **somente relatório de CI**, não uma IPA potencialmente confundível com Release.

## Fronteiras de confiança que faltam antes da atualização em um toque

| Fronteira | Estado |
|---|---|
| `appinst` instala app descartável e preserva registro | Aprovada no iPad |
| Serviço PING ativo sem terminal | Aprovada no iPad |
| Continuidade após reboot + reativação Chimera | Não testada |
| Identidade/autorização do solicitante no helper | **Não comprovada** |
| Chave de produção P-256 independente do GitHub | **Não provisionada** (`productionPublicKeyX963=nil`) |
| Assinatura/manifesto verificados no **helper**, não só no app | **Não implementados** |
| Consentimento confiável, explícito, ligado a uma transação única | **Não implementado** |
| Controle de replay/TOCTOU e destino de instalação restrito | **Não demonstrado** |
| Atualização do WebReader real com backup e SQLite/downloads | **Não testada** |

### Investigação técnica para a próxima etapa

O kernel Darwin expõe mecanismos próprios de identificação de pares, mas é necessário **provar disponibilidade efetiva no iOS 12.5.8/Chimera** antes de adotar qualquer um. `LOCAL_PEERPID` é associado a sockets AF_UNIX — já tivemos falhas de acesso ao socket no sandbox iOS12. O header XNU também declara `TCP_PEER_PID` como opção **privada**, sem garantia pública de disponibilidade no dispositivo. **Um PID isolado não autentica assinatura/identidade**: pode se tornar obsoleto/reutilizado.

Pistas públicas para pesquisa (não garantias de compatibilidade):
- [XNU tcp.h, TCP_PEER_PID sob PRIVATE](https://github.com/apple/darwin-xnu/blob/main/bsd/netinet/tcp.h)
- [xpc_connection_get_pid — Apple, advertência sobre reutilização de PID](https://developer.apple.com/documentation/xpc/xpc_connection_get_pid(_:))
- [LOCAL_PEERPID em Darwin, discussão de implementação Go](https://github.com/golang/go/issues/27613)

O modelo apropriado precisa de evidência de credencial/audit token da conexão com validação de assinatura compatível com o iOS 12 **ou** de protocolo de consentimento independente resistente a clientes forjados. Não assumir que PONG, HMAC temporário ou `localhost` comprovem essas propriedades.

## Decisão de integração

O serviço persistente Build61 permanecerá **PING-only**. O CLI de instalação descartável Build60 permanecerá um laboratório manual. Eles não serão mesclados num daemon instalador sem cumprir os requisitos acima. A próxima etapa de código poderá medir somente a disponibilidade de mecanismos de identidade do peer, sem poder executar `appinst`. A `main` e o WebReader Build56 ficam intocados; PR #90 continua Draft.

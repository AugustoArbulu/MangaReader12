# Build 63 — Laboratório isolado de identidade do cliente IPC no iOS 12

**Data:** 06/11/2026  
**Branch:** `feat/chimera-updater-phase1-protocol-audit`, PR #90 Draft  
**Proteção:** `main` e WebReader Build56 preservados.

## Objetivo

Após a aprovação física do PING persistente Build61 FIX1 e da instalação **descartável e manual** v1→v2 via `appinst` na Build60, investigar se o kernel Darwin expõe **dados confiáveis sobre a origem de uma conexão IPC**. Uma resposta PONG ou pareamento HMAC não autentica a identidade do app solicitante.

**Build63 NÃO é instalador.** É um programa de linha de comando separado do WebReader, que aceita somente `selftest`, recusa UID 0, inicia duas conexões locais efêmeras entre processos de teste e termina. O executável não executa outros programas, não faz downloads, não acessa IPA, não expõe serviço persistente, não tem comando appinst.

## Fontes pesquisadas e limites de compatibilidade

- Código fonte XNU: `LOCAL_PEERPID` = `0x002` em `sys/un.h`, `SOL_LOCAL` = 0. https://newosxbook.com/src.php?file=%2Fbsd%2Fsys%2Fun.h&tree=xnu
- Código fonte XNU: `TCP_PEER_PID` = `0x204`, definido sob `#ifdef PRIVATE`; **API privada**, não há garantia de acesso no iOS 12. https://github.com/apple/darwin-xnu/blob/main/bsd/netinet/tcp.h
- Apple Security Code Signing Services: há interfaces para identificar e verificar *código* em execução, mas um PID isolado não fornece identidade estável de código ou certificado de editor. https://developer.apple.com/documentation/security/code-signing-services
- A implementação atual de Security da Apple declara `SecCodeCreateWithPID` como sujeita a *race* e recomenda audit token. **Não assumir** que as mesmas rotinas ou entitlements existem no iOS 12/Chimera. https://github.com/apple-oss-distributions/Security/blob/main/OSX/libsecurity_codesigning/lib/SecCode.cpp

## Artefatos

- `ci/webreader_chimera_peer_probe63.c`: prova isolada, somente `selftest`, processado como usuário não-root.
- `ci/test_chimera_peer_probe63.py`: quatro rodadas no macOS com conexões TCP loopback e AF_UNIX; coleta apenas disponibilidade e correspondência de PID do processo filho **controlado**, sem dados identificadores persistidos.
- `ci/package_chimera_peer_probe63.py`: cria pacote `.deb` **CLI-only**, sem `postinst`, `launchd`, `plist` ou serviço.
- `ci/test_chimera_peer_probe63_deb.py`: verifica estrutura, assinatura ad-hoc e pasta de extração em filesystem vazio, evitando o problema físico da Build61 0.1.0.
- `.github/workflows/chimera-build63-peer-probe.yml`: compila no macOS e ARM64 iOS12, assina com entitlement mínimo `com.apple.private.security.no-container`, audita e disponibiliza pacote, mas não instala nem executa nada no iPad.

## Interpretação rigorosa das saídas

Cada transporte relata `PEER_PID=MATCH`, `UNAVAILABLE` ou `MISMATCH`; em todos os casos o relatório traz `AUTHORIZATION=DENIED`. A mensagem final é sempre `FINAL_INSTALL_AUTHORIZATION=DENIED`.

- `MATCH`: apenas confirma que, nesse ambiente, o servidor obteve o PID esperado **na conexão efêmera controlada**; não autentica que o solicitante foi o WebReader.
- `UNAVAILABLE`: opção ausente, proibida ou sem PID válido, sem inferir a causa exata. Não tentar permissões extras automaticamente.
- `MISMATCH`: metadado inesperado; não reutilizar o método sem investigação. Nunca autoriza instalação.
- `TRANSPORT=FAILED_N`: o teste local não completou; diferenciar restrição de `fork`, falha de caminho/sandbox ou socket. Não enfraquecer as permissões para fazer passar.

## QA no iOS, somente quando solicitada

Depois que o CI gerar o `WebReader-Chimera-PeerProbe63-iOS12.deb`, o usuário poderá optar por instalá-lo no jailbreak e executar `webreader-peerprobe63 selftest` **como mobile**, sem `su`. O pacote não inicia processos em segundo plano, altera o serviço Build61 ou instala IPAs. **CI verde no macOS não comprova acesso a APIs privadas no iOS.**

Este programa é uma medição do kernel no processo CLI, **não uma prova de que o WebReader sandboxed conseguirá usar AF_UNIX**. As tentativas anteriores de socket de arquivo do projeto falharam com erro de acesso no contêiner do app. Nenhuma alteração no app principal será feita só por esses testes.

## Próximo gate

Investigar um transporte com credencial/audit token vinculado ao descritor IPC, autorização explícita resistente a clientes locais forjados e chave P-256 de editor independente do GitHub, além de revalidar IPA com descritor retido. `SecCodeCreateWithPID` não deve ser usado como autenticador de produção por causa de race/reutilização PID.

Aprovação da Build63 significa exclusivamente capacidade diagnóstica. **Proibido conectar a Build61 PING-only ou a Build63 diretamente ao appinst.** O PR permanece Draft até os demais gates e QA física.

## CI concluído e auditoria de pacote — 06/11/2026

GitHub Actions run [#42186712949](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42186712949) **SUCCESS**, commit testado `96203ec11012018847b61fbc3f5dbc4d0fef6a53`.

- macOS: quatro rodadas com `TCP_LOOPBACK PEER_PID=MATCH` e `UNIX_LOCAL PEER_PID=MATCH`, sempre `AUTHORIZATION=DENIED`.
- Assinatura ad-hoc do binário ARM64/iOS12 verificada; alvo iOS mínimo 12.0 e sem fixups incompatíveis.
- `data.tar.gz` inclui explicitamente `./usr/`, `./usr/local/`, `./usr/local/bin/` e um único binário. `control.tar.gz` contém somente `control`: **nenhum postinst, launchd, daemon, executor de appinst ou IPA**.
- Artifact `WebReader-Chimera-Build63-PeerProbe-QA-iOS12`, ID `13488525539`.
- Arquivo `WebReader-Chimera-PeerProbe63-iOS12.deb`, 4.674 bytes; SHA-256 `d38a398af4d663eec167f8ec6911e4fcf3311fc45558d498603e127eda0e732c`.
- Auditoria separada no Linux: `dpkg-deb --info` versão 0.1.0 e arquitetura iphoneos-arm, `dpkg-deb --contents` validou estrutura e `dpkg-deb --extract` em diretório vazio gerou executável correto.

**Importante:** essas verificações não demonstram disponibilidade de `TCP_PEER_PID` no iOS 12, nem compatibilidade do `fork()` na execução móvel. Ainda não há aprovação física no iPad.

### Instrução para QA física opcional

Se o usuário desejar testar: salvar o pacote em `/var/mobile/Documents/WebReader-Chimera-PeerProbe63-iOS12.deb`. Instalar somente o diagnóstico, por NewTerm2, como root:

```sh
dpkg -i /var/mobile/Documents/WebReader-Chimera-PeerProbe63-iOS12.deb
```

Depois sair do root (`exit`) e executar como **mobile**:

```sh
/usr/local/bin/webreader-peerprobe63 selftest
```

Guardar a saída das linhas `PROBE TCP_LOOPBACK` e `PROBE UNIX_LOCAL`. A saída deve terminar com `FINAL_INSTALL_AUTHORIZATION=DENIED`. Se `fork`, socket ou permissão falhar, tratar como falha **de diagnóstico**, sem elevar privilégios ou alterar o helper Build61. Remoção: `dpkg -r com.example.webreader.peerprobe63` com privilégios do gerenciador, quando solicitado.

Este pacote tem objetivo exclusivamente de leitura e não atende ao requisito de instalação de IPA diretamente pelo app.

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

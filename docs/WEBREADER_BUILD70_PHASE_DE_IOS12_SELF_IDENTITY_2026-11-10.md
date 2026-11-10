# WebReader Build70 — Fase DE: diagnóstico read-only de identidade de processo, pronto para compilação iOS12

**Data:** 10/11/2026. **Repositório:** `AugustoArbulu/MangaReader12`. **Branch:** `feat/chimera-updater-phase1-protocol-audit`. **PR #90:** Draft, sem merge na `main`. Build70 no iPad iOS12.5.8, biblioteca, favoritos, capítulos offline, GitHub Releases e appinst instalado **não alterados**.

## Motivação: o que DC e DD não comprovaram

As Fases DC/DD inspecionam a linha de diretórios sob fixtures de host. Os testes da DD verificaram inclusive os ancestrais desde `/`, e reduziram os riscos de symlink e permissão transitória, mas ambos recebem uma **suposição de UID** do cliente. Nenhum `stat` em uma pasta Linux/macOS pode demonstrar que o WebReader e um hipotético helper persistente do Chimera executam realmente sob identidades distintas.

A validação física que poderia reduzir essa incerteza exige separar **identidade observada do próprio processo** de **identidade comprovada do peer**. Um processo sabe seus próprios `getuid/geteuid/getgid/getegid`, mas não consegue declarar por isso que está autorizado a representar o WebReader ou que possui entitlements adequados. Nem dois números distintos apresentados em texto livre bastam como autenticação.

## Implementação concreta

- `ci/build70_de_ios12_self_identity_probe.c`: programa C de diagnóstico **sem argumentos**, sem IPC, sem URLs, sem acesso à biblioteca ou downloads. Exibe apenas UID/GID real/efetivo, PID/PPID, grupos suplementares, família do kernel e UID/modo do **próprio executável**, quando essa leitura está disponível. Não exibe nomes de usuários nem paths de executáveis, não abre IPAs nem checa arquivos de outros aplicativos.
- Compilado em dois perfis de **rótulo**: `WR_DE_MOBILE_ROLE` emite `DE_ROLE=MOBILE_CANDIDATE`; `WR_DE_HELPER_ROLE` emite `DE_ROLE=HELPER_CANDIDATE`. Estes rótulos **não** são assinaturas, entitlements, prova de conta separada ou implantação de um helper. O binário se recusa a executar qualquer argumento.
- `ci/build70_de_self_identity_report.py`: leitor host de relatórios com **exatamente 21 campos obrigatórios** e ordenados, limite 4 KiB, ASCII estrito, inteiros de 32 bits e nenhum campo de autoridade positivo. Um par `MOBILE_CANDIDATE`/`HELPER_CANDIDATE` com EUIDs iguais retorna `SAME_EUID_SELF_REPORTED_NOT_ISOLATED`; se diferentes, `DISTINCT_EUID_SELF_REPORTED_UNATTESTED`. Valores textuais podem ser falsificados: **nenhum resultado prova identidade de peer ou autoriza instalação**.
- `ci/test_build70_de_self_identity_report.py`: testes host em Linux/macOS compilam e executam os dois perfis, comparam valores à própria execução, rejeitam opções e frames de instalação, inspecionam casos forjados, incompatibilidades de kernel, campos duplicados/extra/truncados, inteiros inválidos e executam **350 mutações determinísticas** sem permitir promoção de autoridade.
- `.github/workflows/chimera-build70-phase-de-self-identity.yml`: CI Linux/macOS host e um job macOS/Xcode16.4 que **compila e linka dois executáveis CLI ARM64 com destino mínimo iOS12.0**, sem assiná-los para distribuição, sem gerar IPA/DEB, sem Release, sem instalação e sem disponibilizar os binários como artifacts. Este avanço é além de um simples objeto compilado: o código pode ser linkado para a plataforma-alvo, mas ainda não foi executado nem validado em um iPad.

## Formato e interpretações proibidas

O relatório contém campos como:
```text
DE_SCHEMA=1
DE_ROLE=MOBILE_CANDIDATE
DE_SELF_UID=<UID observado no processo>
DE_SELF_EUID=<EUID observado no processo>
...
DE_PROCESS_IDENTITY_SCOPE=SELF_ONLY
DE_SELF_BINARY_SIGNING_VERIFIED=NO
DE_IPC_PEER_AUTHENTICATED=NO
DE_IOS12_HELPER_ISOLATION_VERIFIED=NO
DE_APP_WRITE_DENIAL_VERIFIED=NO
DE_OWNER_INSTALL_CONSENT_VERIFIED=NO
DE_INSTALLATION_AUTHORIZED=NO
DE_INSTALLATION_ATTEMPTED=NO
```

**Não inferir** que o próprio rótulo `HELPER_CANDIDATE` identifica o futuro serviço; um binário executado no NewTerm como mobile mede o UID daquela execução do NewTerm. Para medir identidade de um helper real seria preciso executar um binário read-only **dentro do contexto efetivo do serviço**, assinado/provisionado e verificado separadamente. Essa implantação, identidade, canal de relatório e sandbox ainda não existem nesta fase. Igualmente, medir o UID do executável não prova que os diretórios de proteção estejam fora do alcance de escrita do WebReader.

O par de relatórios pode ajudar a priorizar inspeção posterior, mas não é código para autenticar IPAs, liberar instalação nem transformar HMAC/UID em credenciais. O teste físico prévio `LOCAL_PEERTOKEN` continuou `TOKEN_UNAVAILABLE AUTHORIZATION=DENIED`; nenhuma descoberta em host altera esse diagnóstico.

## Proibições e gates

`WRCHK2\n` permanece aviso de checagem não autenticado e nunca aceita path, versão, URL, SHA, PID, UID ou autorização vinda do cliente. O CLI DE também não aceita argumentos. Não foi introduzido serviço em background, socket, launchd, conta nova, alteração de entitlements ou helper instalador.

Continuam faltando, de maneira independente:
- Contexto de helper iOS12 real, identidade e sandbox medidos sob aprovação específica, e teste de *não escrita* do aplicativo em diretório separado efetivamente protegido;
- Diário de recuperação durável sob posse do helper, sem rollback pelo app, e reconciliação somente após comprovar ausência de workers anteriores;
- Chave pública editorial P-256 e fingerprint SPKI conferido independentemente, assinatura production-v2 real e restrição a origem imutável;
- Cadeia de custódia do mesmo conteúdo de IPA até o serviço Apple, especialmente possíveis cópias por pathname no appinst e instalação nativa;
- Consentimento local do proprietário em canal independente, prevenção de replay/rollback e preservação de biblioteca/offline.

**Hard stops Swift:** `WebReaderAppinstSocket.liveInstallationEnabled=false`, `WebReaderUpdateChannel.productionPublicKeyX963=nil`, `WebReaderProductionPublisherTrust.independentlyProvisionedSPKISHA256=nil`. Não modificar `main`, publicar Release, IPA/DEB ou realizar instalação.

## Handoff

A próxima etapa tecnicamente substantiva é uma **proposta de fixture físico estritamente read-only**, com modo de execução, requisitos mínimos de assinatura do CLI, comparação auditável de `getuid/geteuid` entre processo do WebReader e serviço independente e uma área de teste inteiramente fora dos diretórios de biblioteca. Como ainda não há um helper real isolado, não tratar um par de CLIs executados no NewTerm como prova de arquitetura. Um teste físico deve ocorrer apenas com aceite específico do usuário e sem abrir caminho para instalação. Alternativa: continuar investigando isoladamente um serviço de verificação que consiga provar identidade de peer em iOS12/Chimera.

**CI DE:** pendente de logs Linux/macOS e cross-link até confirmação. Os jobs Apple da Fase DD/DC permaneciam em fila na última consulta e isso deve ser registrado sem inventar resultado verde.

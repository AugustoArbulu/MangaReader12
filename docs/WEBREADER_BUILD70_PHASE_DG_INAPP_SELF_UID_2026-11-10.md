# WebReader Build70 — Fase DG: diagnóstico real da identidade do processo do aplicativo (somente leitura)

**Data:** 10/11/2026. **Branch experimental:** `feat/chimera-updater-phase1-protocol-audit`, **PR #90 Draft**. `main` e a **Build70 efetivamente instalada no iPad iOS12.5.8 não são modificadas**. Sem nova Build71, IPA/DEB, Release, instalação, serviço persistente ou escrita de dados de leitura.

## 1. Por que DG é diferente das fases DC–DF

DC e DD inspecionam hierarquias de diretórios a partir de fixtures de host; DE mede os UIDs de **executáveis sintéticos** em Linux/macOS, e DF prepara a validação do formato Mach-O ARM64 dos CLIs iOS12 ligados no Xcode. Até então, nenhum teste podia medir o UID efetivo do **próprio aplicativo WebReader** executando dentro do sandbox real.

DG acrescenta ao **código do aplicativo**, em sua tela de atualizações já existente, uma ação mínima de diagnóstico. Quando uma futura Build de QA for criada e instalada sobre a versão estável com aprovação explícita, essa ação poderá fornecer UID/GID do **processo que executa o próprio WebReader**, via `Darwin.getuid/geteuid/getgid/getegid`. Esse é um dado mais relevante do que um CLI rotulado `HELPER_CANDIDATE` executado via NewTerm. Isso **não prova identidade de um helper**, sandboxes separados ou autorização de IPC.

Nenhuma Build de QA é produzida/distribuída pela DG; o código só está na branch experimental.

## 2. Implementação concreta na tela

Modificado somente `MangaReader12/UI/WebReaderAppUpdatesViewController.swift` (não há arquivo Swift novo que exija atualização do projeto Xcode).

- Em **Atualizações do WebReader → SEGURANÇA**, nova nona linha: **“Copiar identidade do processo WebReader”**.
- A linha é acionada **somente após toque explícito**. A tela de IPC descartável não exibe o diagnóstico e a ação também verifica `!isIPCDiagnostic`.
- `copyOwnProcessIdentityReport()` produz texto pequeno com Build, versão iOS, UID/EUID/GID/EGID do próprio app. Copia via `UIPasteboard.general.string` e apresenta aviso ao usuário; não coleta nem exibe diretórios, nomes de arquivo, obras, informações da biblioteca, IPAs, dados de backup, credenciais ou endereços.
- Não executa `appinst`, `posix_spawn`, `getpeereid`, `socket`, leitura de outro processo, métodos de instalação ou requisições à rede. O botão não altera o funcionamento das demais oito linhas de segurança nem as guias de biblioteca.
- O reporte é explicitamente **SELF_ONLY** e inclui `HELPER_PROCESS_IDENTITY=NOT_TESTED`, `IPC_PEER_AUTHENTICATED=NO`, `IOS12_SANDBOX_SEPARATION_PROVEN=NO`, `APP_WRITE_DENIAL_TO_HELPER_VAULT_PROVEN=NO`, `INSTALLATION_AUTHORIZED=NO` e `INSTALLATION_ATTEMPTED=NO`.

**Privacidade:** o relatório contém os IDs Unix locais (numéricos) de execução do app, que não precisam ser tratados como credencial. Não inclui `getpid/getppid` ou identificadores de diretórios de contêiner. Não sugerir ao usuário executar comandos como root para obter esse dado; o próprio app é o contexto correto quando a versão contendo esse botão estiver instalada.

## 3. Testes e CI

- `ci/test_build70_dg_inapp_self_identity.py`: 11 testes de contrato garantem que a opção tem seção/linha e dispatch corretos; usa somente APIs Darwin do próprio processo; mantém marcações de confiança negativa; cópia sob ação do usuário; não abre arquivos ou rede; preserves offline e biblioteca; confirma três hard stops.
- `ci/test_app_updates_screen.py`: reexecuta testes existentes de compatibilidade e de botão de instalação bloqueado.
- `.github/workflows/chimera-build70-phase-dg-inapp-self-identity.yml`: job Ubuntu para os testes estáticos e um job macOS que prepara o libwebp 1.6.0 de source SHA-256 pinado e o ícone aprovado, depois executa `xcodebuild -project MangaReader12.xcodeproj -scheme MangaReader12 -configuration Debug -sdk iphoneos -destination 'generic/platform=iOS' CODE_SIGNING_ALLOWED=NO CODE_SIGNING_REQUIRED=NO clean build`. O app compilado fica no armazenamento **temporário do runner**, sem codesign, IPA, upload, distribuição ou execução física.

**CI DG:** pendente de logs finais. A compilação do app para iOS12 não é prova de sua execução no dispositivo ou de helper seguro.

## 4. Gates antes de eventual teste físico

Nenhum comando no NewTerm fornece uma prova de identidade do processo WebReader se executado como um shell externo. O teste proposto deve ser apenas: uma versão futura e manualmente aprovada do WebReader com a nova linha instalada **por cima** (bundle ID e contêiner preservados), abrir Atualizações → Segurança → Copiar identidade do processo, e compartilhar o texto curto. Antes de qualquer atualização é obrigatório preservar biblioteca/offline, comparar a identidade do IPA e avaliar as obrigações de re-download de imagens previamente observadas em versões anteriores.

Mesmo depois de medir o UID/EUID do app, faltariam: (a) processo helper real independentemente provisionado, com identidade e assinatura comprovadas; (b) vault efetivamente inacessível ao app e ancestrais auditados no iOS12; (c) autenticação de peer em iOS12/Chimera (o teste anterior de `LOCAL_PEERTOKEN` deu `TOKEN_UNAVAILABLE AUTHORIZATION=DENIED`); (d) journal protegido contra mutação, restart, root e rollback; (e) publisher-trust production-v2 real, consentimento local seguro, mesmo conteúdo da IPA consumido pelo instalador.

## 5. Estado e próximos passos

O correto é **não promover** `APP_SELF_EUID` a autorização. A contribuição material de DG é permitir medir o app em seu contexto real quando houver uma Build de QA segura, sem usar um CLI externo como substituto.

Após CI, um avanço de escopo reduzido seria preparar uma Build candidata de QA com **verificação completa de continuidade da biblioteca** e retenção de identidade de assinatura, mas sem publicá-la como release nem alterar a Build70 no iPad até a aceitação explícita para instalar. Alternativamente, estudar como um serviço read-only pode provar um UID independente e proteção de vault antes de qualquer instalação automática.

**Hard stops mantidos:** `WebReaderAppinstSocket.liveInstallationEnabled=false`; `WebReaderUpdateChannel.productionPublicKeyX963=nil`; `WebReaderProductionPublisherTrust.independentlyProvisionedSPKISHA256=nil`. PR #90 Draft, `main` e dados físicos intocados.

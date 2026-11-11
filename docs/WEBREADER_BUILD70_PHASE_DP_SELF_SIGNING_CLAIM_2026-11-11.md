# WebReader Build70 — Fase DP: identificação da assinatura do próprio processo com SecTask (iOS12)

**11/11/2026.** Repositório `AugustoArbulu/MangaReader12`, branch `feat/chimera-updater-phase1-protocol-audit`, PR #90 Draft. A Build70 já instalada no iPad iOS12.5.8, sua biblioteca, histórico, favoritos e capítulos baixados **não foram acessados nem modificados**. `main` não foi alterada; nenhum IPA/DEB ou Release foi criado.

## Motivo da fase

A nova Fase DO verificou por testes Linux/macOS os relatórios existentes da Build70 — nove contagens SQLite e até 64 capítulos offline por lote — sem acessar páginas, banco real ou identificar o app instalado. A Fase DL demonstrou a assinatura ad-hoc de **uma cópia completa** da futura Build71 em CI, mas não a compatibilidade real da assinatura com o bundle atualmente instalado no iPad.

A Fase DG adicionara uma opção de relatório do **próprio processo**, contendo UID/EUID/GID/EGID, porém isso não mede o `application-identifier` presente nos entitlements assinados.

A Fase DP amplia **somente a opção DG**, ainda na branch experimental, para consultar os metadados da própria tarefa via `SecTask` do framework Security. Essas funções são documentadas pela Apple:
- [SecTaskCreateFromSelf](https://developer.apple.com/documentation/security/sectaskcreatefromself(_:)) cria uma referência à tarefa atual;
- [SecTaskCopySigningIdentifier](https://developer.apple.com/documentation/security/sectaskcopysigningidentifier(_:_:)) lê o signing identifier da tarefa;
- [SecTaskCopyValueForEntitlement](https://developer.apple.com/documentation/security/sectaskcopyvalueforentitlement(_:_:_:)) consulta um único entitlement.

**Importante:** mesmo quando uma futura Build71 estiver instalada, consultar seu `SecTask` confirma **somente uma observação daquele processo**, não uma assinatura editorial confiável, não a identidade da Build70 anterior, não a autenticidade da conexão IPC, não a preservação do contêiner e não permissão de instalação. No iOS12/Chimera as APIs podem retornar `nil`; o código usa `UNAVAILABLE` e não presume sucesso.

## Implementação concreta

Em `MangaReader12/UI/WebReaderAppUpdatesViewController.swift`:
- Mantida a nona linha **Atualizações → Segurança → Copiar identidade do processo WebReader**; sem nova linha de UI, tabela ou arquivo Swift adicional.
- Adicionado `import Security` e ampliado `copyOwnProcessIdentityReport()`. **Só depois do toque** em uma tela de app normal, coleta UID/EUID/GID/EGID, `Bundle.main.bundleIdentifier`, signing identifier retornado por `SecTaskCopySigningIdentifier`, e apenas o entitlement `application-identifier` do próprio processo.
- Todos os IDs são limitados a ASCII alfanumérico, ponto, hífen e underscore, até 256 bytes. Qualquer erro, tipo inesperado, caractere indevido ou `SecTask` indisponível produz `UNAVAILABLE`. Não há caminhos privados, nomes de obras, páginas, IP, arquivo, pasta, lista de outros processos ou dados de assinatura secreta.
- Relatório **DG/DP** deixa explícitos `APP_SELF_IDENTITY_SCOPE=SELF_ONLY`, `APP_SELF_SIGNING_CLAIM_SCOPE=OBSERVATION_ONLY_NOT_VERIFIED`, `INSTALLED_PREVIOUS_BUILD_IDENTITY_ATTESTED=NO`, `HELPER_PROCESS_IDENTITY=NOT_TESTED`, `IPC_PEER_AUTHENTICATED=NO`, `INSTALLATION_AUTHORIZED=NO` e `INSTALLATION_ATTEMPTED=NO`.
- A UI só usa a área de transferência por solicitação do usuário; não dispara rede, escrita de arquivo, instalação de IPA, `appinst`, ativação de helper, `codesign`, `posix_spawn`, troca de UID ou chamada para qualquer processo externo.

## Analisador estrito do texto — apenas após eventual Build71 física

`ci/build70_dp_inapp_signed_identity_report.py` consome somente o **texto não autenticado** de uma futura Build71 em iOS 12.5.8 e verifica o formato canônico de todos os 20 campos. Valida números Unix de 32 bits, Bundle ID, string de signing identifier e `application-identifier`, comparando **textualmente** com a referência histórica `AR5SFJC432.com.example.MangaReader12.AR5SFJC432`.

Resultados possíveis (todos sem autorização):
- `DP_REPORTED_SELF_IDENTITY_TEXT_MATCHES_NOT_ATTESTED`: texto do app reporta bundle, signing identifier e entitlement que coincidem com o esperado. **Não prova nem autenticidade do relatório nem identidade física da Build70 anterior.**
- `DP_SELF_SIGNING_API_UNAVAILABLE_REVIEW_NO_INSTALL`: `SecTask` não expôs os dados; **não usar valor histórico no lugar**;
- `DP_REPORTED_BUNDLE_MISMATCH_REVIEW_NO_INSTALL`, `DP_REPORTED_ENTITLEMENT_MISMATCH_REVIEW_NO_INSTALL` e `DP_REPORTED_SIGNING_ID_DIFFERENT_REVIEW_NO_INSTALL`: texto declara identidade diferente; revisar antes de qualquer atualização.

`ci/test_build70_dp_inapp_signed_identity_report.py` testa relatórios sintéticos, `UNAVAILABLE`, identidades divergentes, campos duplicados/invertidos, formatação/Unicode inválidos, números fora dos limites, ações de UI acionadas somente por toque e negativas de autoridade; 250 mutações de bytes não podem promover autenticação, distribuição ou instalação.

## Testes de build iOS12 e limites

`.github/workflows/chimera-build70-phase-dp-sectask-self-identity.yml` inclui:
1. Ubuntu — testes DP, regressão DG e `ci/test_app_updates_screen.py` antigo; hard stops verificados;
2. macOS Xcode16.4 — prepara libwebp 1.6.0 SHA-pinado e ícone original, executa build completo WebReader **Build71 Release** para `generic/platform=iOS` com `CODE_SIGNING_ALLOWED=NO`, audita o `.app` unsigned via preflight DH. **Nenhum IPA, assinatura, distribuição, Release ou instalação.**

O teste de compilação valida a disponibilidade das APIs no SDK da versão selecionada e sua vinculação. **Não verifica** se `SecTask` retorna um entitlement legível no iPad com Chimera; isso exige execução física futura e aceite separado do proprietário para uma IPA de QA. Mesmo a execução futura não reatesta a identidade da versão 70 que existia *antes* de instalar 71.

## Escopo restante da atualização 70→71

A Build70 física já contém os botões de contagens e de presença offline e o roteiro físico; pode-se estabelecer sua linha de base sem atualizar. Para a identidade de assinatura **da Build70 instalada agora**, ainda é necessário um método externo **somente leitura** no próprio dispositivo (por exemplo, inspeção do binário instalado/entitlements via ferramenta de jailbreak verificada e disponível), ou outro recibo independente autorizado, **antes** de qualquer substituição. A DP sozinha é um diagnóstico da versão futura; nenhum dos relatórios é um passe de instalação.

Continuam faltando: aprovação do proprietário para preparar/distribuir a IPA Build71, SHA/CDHash e entitlement da IPA final, comparação da identidade física da Build70, plano de backup que **não restaure** sobre Downloads, testes de capítulo previamente baixado com Wi-Fi desligado antes e depois, instalação por cima e validação do contêiner. Para o instalador automático faltam ainda identidade de helper/IPC autenticada, vault/journal imutáveis, chave pública editorial independente e consentimento local.

**Travas inalteradas:** `WebReaderUpdateChannel.productionPublicKeyX963=nil`; `WebReaderProductionPublisherTrust.independentlyProvisionedSPKISHA256=nil`; `WebReaderAppinstSocket.liveInstallationEnabled=false`.

**CI DP:** não afirmar aprovação até conferir os jobs e logs finais do GitHub Actions.

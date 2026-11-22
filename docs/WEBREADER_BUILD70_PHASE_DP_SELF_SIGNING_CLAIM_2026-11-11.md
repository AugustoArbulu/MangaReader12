# WebReader Build70 — Fase DP: descoberta de limite do SDK iOS12, relatório autoidentificação honesto

**11/11/2026.** Branch `feat/chimera-updater-phase1-protocol-audit`; PR #90 Draft. `main` preservada. A Build70 instalada no iPad iOS12.5.8 e seus dados de biblioteca/offline não foram alterados. Nenhuma IPA distribuída ou instalada.

## Objetivo e descoberta concreta

A Build70 física já consegue gerar relatórios somente leitura de **nove contagens SQLite** e de presença de capítulos offline em lotes de até **64** (Fase DO, SUCCESS 2/2). Para atualizar por cima sem perder o contêiner, também precisamos confirmar o **application-identifier efetivamente assinado** da versão instalada. A Fase DG tinha adicionado um relatório de UID/GID do próprio processo para uma futura Build71, mas essa informação não atesta a assinatura.

Investigamos uma rota via framework Security: `SecTaskCreateFromSelf`, `SecTaskCopySigningIdentifier` e `SecTaskCopyValueForEntitlement` aparecem nas referências de Code Signing Services da Apple. **O teste real no SDK `iphoneos` Xcode 16.4 falhou na compilação Swift**: `cannot find 'SecTaskCreateFromSelf' in scope`, assim como as outras duas funções. Execução: https://github.com/AugustoArbulu/MangaReader12/actions/runs/42970050984 (job macOS, falha inicial observada, não promoção). Documentação genérica Apple não basta para inferir disponibilidade dessas APIs na plataforma iOS.

**Decisão:** remover inteiramente as chamadas `SecTask` da futura Build71. Não importar símbolo de forma privada, usar `@_silgen_name`, `dlsym` ou fazer fallback que invente o entitlement histórico. A implementação ajustada usa somente `Bundle.main.bundleIdentifier` e `Darwin.getuid/geteuid/getgid/getegid` — disponíveis no app — e escreve explicitamente:

```text
APP_SELF_SIGNING_ID=UNAVAILABLE_IOS12_PUBLIC_SDK
APP_SELF_APPLICATION_IDENTIFIER_ENTITLEMENT=UNAVAILABLE_IOS12_PUBLIC_SDK
APP_SELF_SIGNING_CLAIM_SCOPE=OBSERVATION_ONLY_NOT_VERIFIED
INSTALLED_PREVIOUS_BUILD_IDENTITY_ATTESTED=NO
```

Isso é uma **observação de metadados locais**, não conferência da assinatura. A futura Build71 não está instalada; ainda falta confirmar os dados no iPad.

## Implementação

1. `MangaReader12/UI/WebReaderAppUpdatesViewController.swift`: conserva exatamente a **nona linha** em `Atualizações → Segurança → Copiar identidade do processo WebReader`. Após toque explícito, copia o relatório UID/GID, versão, Bundle ID da tarefa atual e os campos de indisponibilidade de assinatura. Não executa nada no helper, não faz requisição HTTP, não lê imagens, banco, caminhos privados, chaves, senhas ou arquivos de terceiro e não instala IPA. A tela de probe descartável continua sem a linha.
2. `ci/build70_dp_inapp_signed_identity_report.py`: parser estrito do texto gerado por futura Build71 em iOS12.5.8. Requer todas as frases de negativa de privilégio/instalação e **rejeita** qualquer texto que passe a declarar um signing identifier ou entitlement real a partir da API pública inexistente. Compara somente o **Bundle ID textual** com o esperado; nunca retorna sinal de distribuição aprovada.
3. `ci/test_build70_dp_inapp_signed_identity_report.py`: regressões host contra valores alterados, adulteração de UID/GID, versão, mensagens de autorização e falsificação do entitlement, além de 250 mutações determinísticas sem autoridade. Reexecuta testes DG da UI e regressão do painel de atualizações.
4. `.github/workflows/chimera-build70-phase-dp-sectask-self-identity.yml`: nome histórico de arquivo mantido por estabilidade, com teste Linux e compilação macOS **Release Build71 unsigned para `generic/platform=iOS`**, sem codesign, IPA, publicação ou instalação. O nome de apresentação do workflow foi ajustado para refletir a implementação pública realmente suportada.

## Resultado interpretado corretamente

`DP_IOS12_SIGNING_ENTITLEMENT_UNAVAILABLE_NO_INSTALL` significa apenas que um **texto não autenticado** reportou o Bundle ID esperado e que não foi possível obter os entitlements com essas APIs públicas. `DP_REPORTED_BUNDLE_MISMATCH_NO_SIGNING_ATTESTATION` exige revisão mesmo se a UI continuar funcionando. Uma tentativa de forjar `APP_SELF_SIGNING_ID` ou `APP_SELF_APPLICATION_IDENTIFIER_ENTITLEMENT` com outro valor é **rejeitada**, não convertida em teste aprovado.

Todos os campos de autenticação de editor, integridade do código, identidade da versão física anterior, helper, preservação de biblioteca, offline, consentimento e instalação são permanentemente **false**. Um relatório do próprio aplicativo não é atestado criptograficamente e não pode autorizar distribuição ou instalação automática.

## Bloqueio físico ainda existente

Para obter o **application-identifier da Build70 instalada agora**, a próxima etapa útil deverá ser uma **inspeção externa somente leitura dos bytes de assinatura do aplicativo instalado no iPad**. Como o ambiente usa jailbreak Chimera, poderá ser avaliado um diagnóstico específico, sem root e sem modificar o app, mas **não presumir** que `ldid`, `plutil` ou outra ferramenta esteja instalada nem que a leitura seja permitida. O instrumento deverá comprovar seus próprios pré-requisitos e aceitar `UNAVAILABLE` como resultado seguro. Não executar scripts invasivos ou transferir documentos pessoais.

Mesmo após obter o entitlement físico, ainda seriam necessários consentimento explícito do proprietário para preparar/distribuir IPA Build71, checksum SHA-256 e code seal da **IPA final**, backup externo, atualização por cima manual e teste offline do mesmo capítulo antes/depois. O `.mr12backup` não contém imagens e restaurá-lo pode apagar os downloads.

**Hard stops de produção mantidos:** `productionPublicKeyX963=nil`, `independentlyProvisionedSPKISHA256=nil`, `liveInstallationEnabled=false`; PR #90 continua em rascunho. **CI DP corrigida:** verificar jobs e logs finais antes de afirmar aprovação; a execução de falha inicial não deve ser ocultada.

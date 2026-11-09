# WebReader — Fases CE–CF: assinatura v2 de produção + IPA real, somente leitura

**09/11/2026 · Branch experimental:** `feat/chimera-updater-phase1-protocol-audit`, PR #90 Draft, `main` preservada. **Baseline física:** Build70 relatada pelo proprietário como funcionando no iPad iOS 12.5.8; o ajuste do Webtoon deitado foi incluído na Build70. **Estes commits são posteriores à IPA70 já entregue e instalada**, não mudam o aplicativo físico até uma nova compilação/instalação deliberada.

## Problema efetivamente corrigido (CE)

O verificador nativo `WebReaderSignedIPAReview.inspectReadOnly` encadeia duas verificações: assinatura editorial ECDSA P-256 sobre o manifesto v2 e SHA/ZIP/identidade da IPA local a partir de um descritor aberto uma vez. Até agora, o verificador de manifesto era invocado sem explicitar o canal, de modo que seu valor padrão **development** impediria verificar um manifesto v2 de **production**.

Agora aceita `expectedChannel: String = "development"` e passa a exigência explícita ao gate ECDSA antes de verificar o ZIP. O padrão preserva a compatibilidade dos testes de desenvolvimento já existentes; usar `"production"` exige assinatura válida de claims que também declarem esse canal, não basta editar a URL ou o campo na resposta.

### Teste com a IPA70 *real*, não sintética

O workflow macOS isolado [Build70 CE — real signed IPA lab](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42712666573) baixa o **artefato exato** de QA Build70 do run [#42705903886](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42705903886) e exige:
- commit origem `ae931abb725977a417a1fcb20b79c82af825dd55` e checksum imutável `526291cc77203c3881e5f3f1c75904e8863dbde3b3bd9df7e1185c3229fb4fc1`;
- preflight de assinatura ad hoc, entitlements instalados, ARM64, código nativo e min. iOS12 com `build70_private_qa_ipa_preflight.py`;
- geração apenas dentro de `TemporaryDirectory` de uma **chave EC P-256 descartável**, diferente da chave editorial real inexistente;
- assinatura por OpenSSL de um **manifesto production-v2 de laboratório** que referencia exatamente tamanho/SHA dos bytes reais da IPA70; Python verifica ECDSA/claims e Swift Security.framework confere assinatura, canal e arquivo aberto;
- rejeição nativa de canal default development, canal inválido, pin errado/ausente, assinatura alterada, IPA adulterada, arquivo symlink e versão não superior.
- eliminação da chave privada ao fim, sem publish, sem envio do manifesto, sem download pelo app, sem Release e sem appinst.

A execução dessa CI **não confere nenhuma identidade editorial real**: seu pin é fornecido por um harness temporário e nunca inscrito no WebReader. Um sucesso do laboratório demonstra compatibilidade técnica do protocolo sobre uma IPA real e testes de negativas, não autorização de instalação nem garantia de que o usuário possa chegar ao asset privado sem autenticação.

## Gate de produção fail-closed (CF)

Novo arquivo no target iOS12: `MangaReader12/Core/WebReaderProductionSignedIPAReview.swift`, exportando `inspectReadOnly(envelopeData:localIPAURL:installedBuild:installedIOS:)`.

O código de produção **não aceita chave pública, pin, canal ou geração como parâmetros**. Antes de interpretar manifesto ou abrir IPA exige `WebReaderProductionPublisherTrust.isProvisioned == true`, depois lê apenas as constantes de **chave pública e SPKI SHA-256 independentemente aprovadas e embutidas no app**, e invoca a verificação conjunta com `expectedChannel: "production"`.

Hoje as constantes são propositalmente:
- `WebReaderUpdateChannel.productionPublicKeyX963 = nil`;
- `WebReaderProductionPublisherTrust.independentlyProvisionedSPKISHA256 = nil`;
- `WebReaderProductionPublisherTrust.productionTrustGeneration = 0`.

Portanto a entrada de produção rejeita com `noProvisionedOwnerTrust` **antes de consultar o arquivo**, sem autenticação/instalação. O teste `ci/test_native_webreader_production_signed_ipa_review.py` compila fontes Swift reais e confirma três entradas malformadas, IPA ausente, e negação imediata. O workflow integrado [Build70 AC–CF](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42712990625) compila Debug/Release iOS12 e executa o teste nativo.

## Barreiras que permanecem, em ordem

1. **Canal de distribuição:** os artifacts privados/temporários do GitHub Actions exigem autenticação e expiram; para OTA sem token no iPad o app precisará de Release e manifesto em endpoint público permanente, com aprovação explícita do proprietário sobre visibilidade da IPA. Não usar PAT/token de GitHub no cliente.
2. **Identidade editorial real:** gerar e custodiar **fora do GitHub e do app** uma chave privada ECDSA P-256 do proprietário; conferir o hash SPKI público independentemente e revisar uma nova IPA com o trust root público compilado. Não improvisar pin a partir do manifesto ou de um próprio Release.
3. **Verificação da IPA baixada:** aplicar o fluxo v2 de produção e uma auditoria nativa real de assinatura ad hoc, sem confiar apenas em SHA/ZIP e sem reabrir caminho mutável para instalar.
4. **Helper Chimera:** autenticar o processo solicitante *vinculado ao socket recebido*, validar o manifesto e a IPA de forma independente, proteger o estado durável contra replay/rollback e usar handle imutável/sem TOCTOU. PING/PONG, UID, HMAC de pareamento, código ad hoc e provas macOS são insuficientes para iOS12.
5. **Consentimento explícito por instalação:** o servidor não deve aceitar simples string de consentimento enviada pelo app como prova suficiente; amarrar ação de usuário, geração, digest, identidade e instalação one-shot no helper. Até isso: `WebReaderAppinstSocket.liveInstallationEnabled = false`.

**Estado:** CE e CF implementadas em código; CI nativas devem ser consultadas antes de marcar verificadas. Nenhuma IPA posterior à Build70 foi produzida por este lote. Nenhuma biblioteca, backup, arquivo offline, `main` ou instalação física foi alterada.

# WebReader — Build68 experimental / Fase S: prévia nativa de Release v2 assinado (sem instalação)

**Data:** 2026-11-08
**Branch:** `feat/chimera-updater-phase1-protocol-audit`
**PR:** [#90 Draft](https://github.com/AugustoArbulu/MangaReader12/pull/90), base `main`, sem merge.
**Build 66:** última aprovada fisicamente no iPad iOS 12.5.8.
**Build 67:** IPA manual disponível; sem aprovação física registrada.
**Build 68:** código experimental; nenhuma IPA distribuída.

## Objetivo

A Fase R demonstrou em laboratório a correspondência entre o SHA-256 do DER
SubjectPublicKeyInfo (SPKI) da chave pública EC P-256 e os 65 bytes X9.63
consumidos pelo Security.framework. A Fase S move a verificação dessa
correspondência para **código Swift real do target iOS12**, sem configurar
uma chave de produção e sem ativar qualquer instalador.

A pergunta respondida pelo laboratório é restrita:
> "Um fingerprint de SPKI previamente confiável corresponde à chave X9.63,
> e um manifesto v2 foi assinado por essa mesma chave?"

Mesmo que a resposta seja positiva, isso **não comprova** que uma chave
arbitrária fornecida pelo usuário ou pelo GitHub pertença ao editor.
A confiança inicial não pode vir do arquivo de release, de um checksum
publicado ao lado dele nem do próprio app sem provisionamento prévio.

## Arquivos implementados

- `MangaReader12/Core/WebReaderSignedReleaseTrustGate.swift`
  — novo código nativo, incluído no projeto Xcode.
- `MangaReader12.xcodeproj/project.pbxproj`
  — registro da fonte no target real da aplicação.
- `ci/test_native_webreader_signed_release_trust_gate.py`
  — executa o código Swift com Security.framework e CommonCrypto do macOS.
- `ci/test_build68_signed_trust_gate_policy.py`
  — impede regressão para instalação, configuração de chaves e inicialização implícita.
- `.github/workflows/chimera-phase-s-native-signed-preview.yml`
  — suítes Linux, macOS e compilação Release ARM64/iOS12 sem gerar IPA.

## Contrato do verificador nativo

`WebReaderSignedReleaseTrustGate.inspectReadOnlyV2` recebe:
`envelopeData`, `publicKeyX963`, `independentlyTrustedSPKISHA256`,
`installedBuild` e `installedIOS`.

1. Se faltar o pin confiável externo, recusa imediatamente.
2. Aceita somente SHA-256 com 64 caracteres hex minúsculos.
3. Aceita somente a chave pública X9.63 não comprimida, 65 bytes e prefixo 04.
4. Constrói localmente o DER SPKI P-256 canônico e calcula SHA-256 com CommonCrypto.
5. Compara com o pin que o proprietário deveria ter provisionado
   previamente por um **canal separado** do release.
6. Recusa envelopamento legado v1, booleano, versão fracionária e JSON com
   chave duplicada (por `WebReaderStrictJSON`).
7. Reutiliza `WebReaderUpdateManifestVerifier.verify` do iOS12 para conferir
   assinatura ECDSA, estrutura v2, identidade de aplicativo, build crescente,
   versão mínima iOS, nome/caminho HTTPS do asset e SHA declarado.
8. Retorna apenas um objeto `WebReaderSignedReleasePreview` **não autorizador**.

O recibo mantém explicitamente falsos: identidade editorial estabelecida
pelo dispositivo, assinatura nativa da IPA verificada, identidade do peer,
consentimento, instalação autorizada e instalação executada. Ele não contém
caminho privilegiado, instalador, rede, UI de confirmação ou comandos appinst.

### Limites importantes

- O pré-visualizador **não faz download nem lê os bytes da IPA**; por isso
  não certifica sua integridade real nem a assinatura ad hoc do executável.
- `WebReaderUpdateChannel.productionPublicKeyX963 = nil` continua inalterado.
  A UI do aplicativo não chama o novo verificador; nem uma chave de fixture
  nem um pin injetado em teste podem ativar o canal de produção.
- `WebReaderAppinstSocket.liveInstallationEnabled = false`.
- Mesmo após configurar uma chave editorial, o uso de appinst dependerá de
  autorização do processo solicitante, uma decisão de consentimento confiável,
  replay/downgrade e comparação **no helper** com os mesmos bytes imutáveis
  da IPA que ele entregará ao instalador.
- Um jailbreak permite ambientes diferentes do sandbox macOS: os testes
  executados em macOS não são prova de identidade do solicitante em Chimera.

## Suíte de segurança

Os testes nativos cobrem: assinatura válida v2, negativa de pin ausente,
pin errado, chave alterada, chave comprimida/inválida, v1 validamente assinado
mas rejeitado, assinatura adulterada, downgrade ou mesmo build instalado,
envelope vazio, versão booleana e fracionária, além de todas as flags de
não autorização.

A CI exige também os testes legados do verificador e da auditoria de IPA,
seguida de compilação Release do aplicativo completo para ARM64/iOS12, mas
**não publica uma IPA**.

**Workflow:** https://github.com/AugustoArbulu/MangaReader12/actions/runs/42450721996
**Estado final: SUCCESS** no commit de código `bc52bc8dec4d66ca8295b6703f38119bf88d2b59`. Dois jobs aprovados: política Linux; teste nativo Security.framework/CommonCrypto, auditoria de IPA e compilação integral **Release ARM64/iOS12** no macOS. Nenhuma IPA foi publicada ou instalada. Não constitui teste físico em iPad.

## Próximos passos após validar Fase S

- Provisionamento da **chave pública editorial** por uma origem independente
  com identidade do proprietário comprovada; nunca publicar chave privada.
- Em etapa separada, ligar a prévia assinada ao checker **somente para
  exibição**, garantindo que GitHub Releases público sem assinatura não
  seja rotulado como origem autenticada.
- Para Chimera, continuar pesquisando identidades e auditoria do solicitante
  verificáveis pelo sistema, não por PID/UID/HMAC informados pelo próprio app.
  Manter a negação de instalação até um método seguro funcionar no iOS12 real.

**Nenhum teste desta fase toca a biblioteca ou os capítulos offline do iPad.**

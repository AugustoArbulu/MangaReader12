# WebReader Build70 — Fase CQ: assinatura editorial criptografada -> macOS codesign -> Swift iOS12

**Data:** 10/11/2026. **Branch:** `feat/chimera-updater-phase1-protocol-audit`. **PR #90 Draft**. `main`, Releases e Build70 física no iPad não foram alteradas.

## Evidência da validação integrada

**GitHub Actions:** https://github.com/AugustoArbulu/MangaReader12/actions/runs/42759188323 — **SUCCESS 2/2**.

- **Linux (offline-adversarial):** testes regressivos CO/CP, P-256 privada criptografada, assinatura e invariantes de segurança, entradas maliciosas e ausência de instalador.
- **macOS 15 / Xcode 16.4 (macos-real-native-synthetic-archive):** construiu localmente um arquivo de teste **sintético** contendo um executável Mach-O thin ARM64 compilado com deployment target iOS 12.0, empacotado em um bundle com identificadores e entitlement de teste compatíveis com o contrato do WebReader, selado com `codesign -` ad hoc.
- Gerou **somente chave descartável P-256** sob diretório temporário fora do repo, a privada criptografada por senha de laboratório; verificou sua parte pública e hash SPKI.
- Chamou a ferramenta CP **com essa chave privada criptografada**, criando manifesto `production` v2 sintético (Build71 fictícia) que cobre o SHA-256, tamanho, URL esperada, bundle, version e applicationIdentifier do pacote.
- O validador Python legado `webreader_update_manifest.validate` confirmou a assinatura ECDSA e claims v2; `build69_production_release_preflight.review_production_release` verificou assinatura editorial + identidade do arquivo + selo Mach-O e entitlement com **`codesign` nativo em macOS**, sem distribuir IPA.
- Por fim compilou a implementação real Swift Security.framework, `WebReaderSignedIPAReview.inspectReadOnly`, `WebReaderNativeIPAAuditor.inspect` e seus parceiros para consumir o **mesmo envelope** e o pacote de laboratório. As verificações de assinatura contra pin público, SHA-256 do arquivo aberto com `O_NOFOLLOW` e metadados ZIP funcionaram; negativos com fingerprint errado, pin ausente, downgrade, canal de lançamento errado, IPA adulterada e assinatura alterada foram rejeitados.

Código: `ci/test_build70_cq_owner_encrypted_native_signed_roundtrip.py`. Pipeline: `.github/workflows/chimera-build70-phase-cq-encrypted-native-roundtrip.yml`. Nenhuma chave real foi lida, gerada, exposta, persistida em artifact ou enviada para GitHub; o teste usa somente a chave efêmera gerada no próprio job que desaparece com o runner.

### Falha inicial corrigida

No primeiro CI CQ o `tempfile` do runner macOS usou caminho com componente symlink `/var` -> `/private/var`. A cerimônia CO corretamente recusa qualquer symlink na cadeia de diretórios para não confiar em caminhos ambíguos. Corrigimos **somente o diretório temporário do teste**, passando `dir=Path(tempfile.gettempdir()).resolve(strict=True)`. Não reduzimos a política de segurança da CO. Depois disso a **execução #42759188323 aprovou os dois jobs**.

## Limites e não objetivos

**A IPA sintética Build71 criada no laboratório não é uma versão do WebReader**. O executável é apenas um `main` de teste, mesmo que o Info.plist/entitlement tenham a identidade esperada. É intencional: o teste verifica compatibilidade criptográfica e dos analisadores, não funcionalidade, origem editorial real nem assinatura real do app. Nenhum .ipa criado por esse pipeline é distribuído ou disponibilizado como artifact.

Uma assinatura **ad hoc** prova integridade dos executáveis verificados por `codesign`, **não quem os criou**. A garantia editorial depende de uma chave P-256 **real sob custódia do proprietário**, cujo fingerprint público seja incorporado ao app em Build revisada, depois de consentimento. O teste CQ usa pin público derivado de chave efêmera, **sem provar cadeia de proveniência** da identidade real do proprietário.

O recibo Swift é somente leitura: `nativeExecutableSignatureChecked=false` porque esse validador Swift não executa `codesign`, apesar de uma verificação separada no macOS do protocolo; `peerAuthenticated=false`, `fileLockedForLaterUse=false`, `consentForInstallVerified=false`, `installationAuthorized=false` e `installationPerformed=false`. O check macOS não prova que o iPad possa instalar; teste com `appinst` e armazenamento de bytes exatos permanece separado.

Os testes CM do iPad retornaram `TOKEN_UNAVAILABLE` nos três casos, o que motivou arquitetura CN em que um pedido local não autenticado pode apenas solicitar uma verificação limitada, jamais escolher IPA ou disparar install. O helper que teria controle privilegiado ainda não foi implementado. Fluxo automático permanece **bloqueado** por ausência de:
1. Chave pública editorial de produção aprovada/provisionada em uma nova IPA; chave privada editorial real sob guarda exclusiva do proprietário;
2. Primeira release pública, imutável, auditada editorialmente com manifesto v2 real e IPA assinada e testada;
3. Helper que busque, valide e conserve bytes independentes sem depender de pedido não confiável, sem permitir troca entre verificação e `appinst`;
4. Consentimento seguro, controle de downgrade/replay, confirmação de preservação da biblioteca e recuperação de falhas;
5. Verificação física no iPad iOS 12.5.8.

## Situação no GitHub

PR #90 permanece Draft e sem merge. Nenhuma alteração `main`, Release ou build instalado. `WebReaderProductionPublisherTrust.independentlyProvisionedSPKISHA256=nil`, `WebReaderUpdateChannel.productionPublicKeyX963=nil`, `WebReaderAppinstSocket.liveInstallationEnabled=false`. Biblioteca, download offline, backups e Build70 do usuário permanecem intactos.

**Próxima decisão:** não repetir laboratório de assinatura ad hoc sem hipótese nova. Preparar a etapa real de bootstrap do editor/UX e revisão de release/rollback com consentimento, usando os gates existentes, e solicitar ações do proprietário **apenas quando** houver necessidade de guardar uma chave real ou instalar uma IPA física manualmente.

# WebReader — Fase BB: preflight offline de uma futura IPA privada

**Data:** 2026-11-09 UTC. **Branch:** `feat/chimera-updater-phase1-protocol-audit`. **PR #90 Draft**. Nenhum Release, IPA Build69 de distribuição, novo trust root ou instalação foi autorizado neste avanço.

## Objetivo e limites

Preparar a verificação de integridade de **uma única IPA privada Build69**, se o proprietário **autorizar futuramente** seu empacotamento. Este passo não produz a IPA, não assina o WebReader, não modifica `main`, não cria artefatos de download e não chama `appinst`/Chimera. Ele também não autentica o editor por assinatura de código ad hoc.

A [Fase BA](WEBREADER_BUILD69_PHASE_BA_ISOLATED_UNSIGNED_PREVIEW_2026-11-09.md) exercita uma compilação isolada `.app` unsigned com `CURRENT_PROJECT_VERSION=69` passado **apenas ao Xcode no runner**, preservando a origem Xcode `build=56`. Uma compilação isolada aprovada **não é** a IPA que será instalada.

## Implementação BB — conferência por snapshot imutável

Novo `ci/build69_bb_private_qa_ipa_preflight.py`, para execução **somente no host macOS** sobre um arquivo IPA externo, real e **já** assinado ad hoc, quando existir:

1. Exige nome exato `WebReader-Build69-iOS12-adhoc.ipa`, baseline instalada = **Build68**, arquivo regular e SHA-256 de um arquivo de checksum fornecido **separadamente** (`<64 hex minúsculos>  WebReader-Build69-iOS12-adhoc.ipa`). A ferramenta não consegue comprovar quem forneceu esse checksum.
2. Usa `build66_ipa_preflight.inspect_ipa` em um único descritor `O_NOFOLLOW`, com snapshot e digest da **mesma versão dos bytes**. Rejeita ZIP ambíguo, arquivo regravado, versão <=68, identidade incorreta, iOS incompatível e arquivos fora do bundle.
3. Exige **CFBundleVersion = 69 exatamente**, `MinimumOSVersion=12.0`, `CFBundleIdentifier=com.example.MangaReader12`, executável `MangaReader12` e um Mach-O **ARM64 iOS12 real** (não aceitar Mach-O macOS disfarçado por Info.plist iOS).
4. Reutiliza `build66_code_signature_gate.audit_code_signature_snapshot` sobre **os mesmos bytes snapshot** para conferir `codesign --verify`, entitlements ad hoc **exatamente** `application-identifier = AR5SFJC432.com.example.MangaReader12.AR5SFJC432` e CDHash estático. A assinatura ad hoc prova integridade do código, **não** a identidade do editor.
5. Retorna um relatório com SHA-256, tamanho, CDHash e identidade verificados, mas **sempre** `publisherAuthenticatedByCodeSignature=false`, `deviceInstallationCompatibilityProven=false`, `qaPhysicalTestCompleted=false`, `backupAndOfflineLibraryPreservationProven=false`, `ownerDistributionApprovalRecorded=false`, `readyForDistribution=false`, `installationAuthorized=false`.

Comando **futuro, somente quando a IPA real existir e a distribuição privada tiver sido autorizada**:

```bash
python3 ci/build69_bb_private_qa_ipa_preflight.py \
  --ipa /outside/repo/WebReader-Build69-iOS12-adhoc.ipa \
  --sha256-file /outside/repo/WebReader-Build69-iOS12-adhoc.ipa.sha256 \
  --installed-build 68
```

Não passar chave privada ou credenciais. Os argumentos são apenas caminhos a arquivos locais. O sucesso é **parecer técnico do host**, não aprovação física, nem autorização para instalar.

## Validação técnica

- `ci/test_build69_bb_private_qa_contract.py` (Linux): verifica formato de checksum, filename, ausência de permissões e fail-closed.
- `ci/test_build69_bb_private_qa_ipa_preflight.py` (macOS): compila uma **pequena aplicação C descarte para iOS12 ARM64** com SDK do Xcode, aplica assinatura ad hoc **de teste**, monta ZIP/IPA temporário **sintético** com identidade contratual e roda o auditor real. Verifica rejeição de assinatura ausente, entitlements errados, binário iOS13 com plist iOS12, versão errada, IPA alterada, SHA falso, baseline incompatível e symlink. Essa fixture não é o WebReader instalado e não é enviada ao usuário.
- O workflow `.github/workflows/chimera-build69-phase-ac-af-integrated-qa.yml` inclui esses testes e a compilação BA isolada. [CI AC–BB #42556649811](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42556649811): resultado a verificar; jobs anteriores são canceláveis pela concorrência, não equivalem a sucesso.

## O que **não** foi feito

- `main`: inalterada; PR #90 permanece Draft.
- Build 68: não removida, recompilada ou instalada novamente no iPad.
- Build69 `.ipa` de WebReader: **não emitida, nem disponibilizada**; a CI BA cria apenas `.app` unsigned e a BB cria apenas uma fixture de teste temporária.
- Chave privada editorial P-256 real: não criada ou carregada no CI.
- Feed de produção assinado: não ativado. `productionPublicKeyX963=nil`, `independentlyProvisionedSPKISHA256=nil`, `productionTrustGeneration=0`.
- Instalação privilegiada: **bloqueada** (`liveInstallationEnabled=false`).

## Próximo marco

Após CI macOS/Swift/BA/BB verde, aguardar autorização expressa do proprietário para a **geração e distribuição privada de uma IPA QA real Build69**. Assinar ad hoc com a identidade já instalada; obter SHA do artefato final; submeter ao auditor BB; transferir ao iPad por Android/PC/Filza sem desinstalar; validar os 14 itens de QA, especialmente páginas offline e biblioteca. **Restaurar `.mr12backup` remove os capítulos offline e não deve ser usado como atualização.**

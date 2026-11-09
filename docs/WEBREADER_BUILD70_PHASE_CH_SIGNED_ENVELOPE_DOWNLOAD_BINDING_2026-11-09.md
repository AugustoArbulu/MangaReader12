# WebReader — Fase CH: vinculação da assinatura editorial ao download e à exportação

**09/11/2026.** Branch `feat/chimera-updater-phase1-protocol-audit`. PR #90 Draft; `main` sem alterações. Referência física: Build70 relatada como funcional no iPad com iOS12.5.8. **A IPA70 já entregue não é alterada** por esta fase. Nenhum acesso à biblioteca ou aos capítulos offline.

## Lacuna resolvida

A UI de atualizações **já** usava `WebReaderProductionSignedReleaseChecker` para descobrir releases assinados e permitir staging/manual export, mas o limite entre operações ainda dependia sobretudo de `WebReaderVerifiedUpdate.provenance == .signedManifest` e de que alguma chave de produção estivesse provisionada. Essa marca é informação interna, não os bytes do manifesto assinados. O downloader `WebReaderIPAStager` recebia apenas o objeto metadata, não uma prova verificável vinculando o objeto ao manifesto real. Assim, após futura provisão editorial, esse caminho não revalidaria criptograficamente *os exatos claims* antes de abrir a transferência.

CH preserva a arquitetura existente e fecha essa lacuna sem criar capacidades privilegiadas.

## Implementação

1. `WebReaderProductionSignedReleaseChecker.swift`: depois de a chave editorial compilada e o SPKI independente verificarem o manifesto v2 de produção, o checker retém **somente os bytes autenticados** em memória, sob `NSLock`, e disponibiliza `verifiedEnvelopeCopy()`. Limpa o cache em nova consulta, resultado não bem-sucedido ou versão atual. Não armazena chave privada nem PIN de rede.
2. **Novo:** `WebReaderSignedProductionEnvelopeBinding.swift`. O método de produção `matchesCompiledOwnerRootReadOnly` exige o root **compilado** e revalida assinatura ECDSA P-256, canal production, versão, iOS, URL, tamanho, SHA-256, data e notas. O verificador puro `matchesReadOnly` permite testes nativos com chave pública descartável; nenhum resultado autoriza instalação.
3. `WebReaderAppUpdatesViewController.swift`: mantém `authenticatedSignedEnvelopeData` apenas para a candidata assinada atualmente selecionada; limpa ao consultar canal diferente. O botão de download exige novamente a correspondência entre manifesto e candidata. Ao iniciar, passa os bytes da assinatura ao stager. **Antes de compartilhar a IPA ou copiar seu recibo**, confere novamente a vinculação do manifesto e executa o auditor SHA/ZIP local já existente. A UI diferencia explicitamente proveniência do Release público sem assinatura e do manifesto ECDSA autenticado.
4. `WebReaderIPAStager.swift`: se o release vem marcado como assinado e não está num harness `URLProtocol` de teste, exige os bytes reais de manifesto ECDSA de produção e seus claims **antes** de criar arquivo/diretório ou iniciar `URLSession`. Nenhuma alteração ao comportamento manual do Release público. Transportes de teste injetados são isolados e nunca instalam aplicativo.
5. `MangaReader12.xcodeproj`: inclui o novo componente Swift no target iOS12.

## Testes

- `ci/test_native_webreader_signed_production_envelope_binding.py`: geração **efêmera** de P-256/OpenSSL em pasta temporária, manifesto v2 de produção, e execução da verificação Swift Security.framework real. Positivo para todos os claims e negativos: build, min. iOS, URL, size, SHA, timestamp, notas, provenance pública/local, assinatura adulterada, pin ausente/incorreto, build repetido, manifesto vazio. A função com root compilado, ainda `nil`, deve recusar até mesmo manifesto tecnicamente válido.
- `ci/test_build70_signed_envelope_download_policy.py`: testes Linux para ordem de validação (assinatura antes de rede/arquivo), propagação até o downloader, rechecagem na exportação e controle do código de instalação desativado.
- Harness Swift `ci/test_native_webreader_ipa_stager.py` e os harnesses isolados de importação/armazenamento local foram atualizados para compilar os três módulos nativos que o stager passou a utilizar. O teste Linux exige essa lista para detectar regressões futuras. A CI AC–CH anterior evidenciou dependência ausente num harness de importação local; corrigida antes da nova execução.
- Harness Swift `ci/test_native_webreader_ipa_stager.py` recebeu as dependências reais do novo gate; teste da descoberta assinada exige que um canal sem chave não tenha bytes autenticados em cache.
- Workflow integrado [AC–CH](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42722375067): Python/Linux, testes Swift/macOS e compilação completa iOS12 ARM64 Debug/Release **sem gerar uma IPA nova**.

## Limites e próximas dependências

* A Build70 instalada tem chave/pin editorial ausentes. A nova implementação será usada **somente por uma futura candidata** que contenha uma chave pública editorial revisada; não ativa downloads de produção por conta própria.
* A assinatura do manifesto autentica os bytes relativos ao root previamente confiável, **não** prova a custódia real da chave: o proprietário ainda precisa aprovar e custodiar sua chave privada fora da CI/GitHub/IPA.
* O auditor de SHA/ZIP iOS12 não substitui a assinatura ad hoc executável examinada no macOS, nem assegura que o helper instale exatamente o mesmo descritor de arquivo. A instalação permanece manual.
* A validação de cliente Chimera ainda carece de identidade de processo vinculada ao socket no iOS12, ledger antirreplay/antirrollback, consentimento direto no helper e imutabilidade do arquivo. Até lá: `WebReaderAppinstSocket.liveInstallationEnabled = false`.
* O repositório está público, mas nenhuma Release nem `main/updates/channel-production-v2.json` foi publicada. Nunca colocar token GitHub no cliente.

**Próximas tarefas úteis:** obter um root editorial real aprovado fora de banda; adicionar canal de releases público assinado v2; depois testar download físico com SHA/ZIP e somente por último permitir uma instalação auditada. Não fundir PR #90 nem alterar main sem revisão apropriada.

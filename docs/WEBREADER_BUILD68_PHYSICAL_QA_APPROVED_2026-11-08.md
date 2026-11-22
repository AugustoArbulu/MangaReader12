# WebReader Build 68 — checkpoint de QA física confirmado

**Data do relato:** 2026-11-08 (UTC).
**Dispositivo:** iPad, iOS 12.5.8, Chimera / instalação manual pelo Filza.
**Status:** **aprovada fisicamente no escopo confirmado** — execução do aplicativo, biblioteca existente e leitura de capítulos baixados sem Wi-Fi.
**PR:** [#90 Draft](https://github.com/AugustoArbulu/MangaReader12/pull/90). `main` não modificada.

## Evidências e histórico do usuário

O proprietário reportou após receber o pacote da Build 68:

1. **"está funcionando"** após instalar a nova IPA de QA.
2. Questionado se a biblioteca e os capítulos baixados permaneciam funcionando, **inclusive com Wi-Fi desligado**, respondeu **"s" (sim)**.

Essas observações aprovam o teste físico do ciclo de atualização manual e da
preservação da biblioteca/leitura offline. **Não** presumir que o proprietário
executou todas as opções do checklist: filtros, fontes, download interrompido,
recibo de integridade, limites de espaço e replay do atualizador ainda não
têm confirmação física individual nesta etapa.

## Identidade exata da Build aprovada

- Commit de candidata: `605f607b08d714d8eabfd3270516b77dfaf673e0`.
- GitHub Actions: [run #42453792657 — SUCCESS](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42453792657).
- Artefato: `WebReader-Build68-PRIVATE-ManualQA-Filza-iOS12` (Actions artifact ID `13607280532`; retenção original de 14 dias).
- IPA: `WebReader-Build68-iOS12-adhoc.ipa`.
- SHA-256: `fb8263573a5b46a94bab74f91c2a25b08de6aa9ac327f078339f1ff77ae5d841`.
- Bundle ID: `com.example.MangaReader12`.
- Application-identifier: `AR5SFJC432.com.example.MangaReader12.AR5SFJC432`.
- CFBundleVersion: `68`, arquitetura ARM64, mínimo iOS 12.0.
- Assinatura: ad hoc; **não** estabelece identidade editorial de produção.

## Estado das versões

- **Build 68:** nova referência física aprovada para uso de leitor, biblioteca e offline.
- **Build 66:** manter como referência histórica e opção potencial de recuperação, **mas não executar downgrade automaticamente**, pois alterações de dados ou migrações futuras podem ser incompatíveis.
- **Build 67:** candidata anterior cuja validação física não foi confirmada; não é pré-requisito para a Build 68.
- Código experimental posterior ao commit da IPA não faz parte da Build 68 aprovada automaticamente. Para novos testes, usar nova identificação de candidata e auditar seus próprios bytes.

## Bloqueios preservados

- `WebReaderUpdateChannel.productionPublicKeyX963 = nil`.
- `WebReaderProductionPublisherTrust.independentlyProvisionedSPKISHA256 = nil`.
- `WebReaderAppinstSocket.liveInstallationEnabled = false`.
- Instalação automática baseada em helper Chimera **não aprovada**.
- PR #90 permanece Draft; não mesclar com `main` apenas porque testes físicos parciais passaram.
- Nenhum backup ou arquivo da biblioteca foi removido pelo GitHub Actions.

**Próximo trabalho:** abordar os itens ainda não testados fisicamente e
planejar a próxima versão experimental sem alterar o pacote Build 68 aprovado.

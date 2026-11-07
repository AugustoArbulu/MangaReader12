# WebReader Build 66 — Fase F: CDHash assinado × csops_audittoken (07/11/2026)

**Repositório:** `AugustoArbulu/MangaReader12`  
**Branch de trabalho:** `feat/chimera-updater-phase1-protocol-audit`  
**PR:** [#90](https://github.com/AugustoArbulu/MangaReader12/pull/90), **Draft**; `main` preservada  
**Dispositivo estável:** iPad iOS 12.5.8 / Chimera, WebReader Build65 aprovada. Não foi alterado.

## Objetivo e fronteira de confiança

A Fase E comprovou no runner **macOS** que `LOCAL_PEERTOKEN` e
`csops_audittoken(pid, CS_OPS_CDHASH, ..., token)` responderam ao processo
filho controlado, rejeitando tokens com `pidversion` alterado e token do filho
apresentado com PID do pai. O resultado **não autenticou WebReader** nem
comprovou suporte do iOS 12.5.8.

A Fase F avança da disponibilidade da API para um **teste independente de
identidade de código**, ainda em host/macOS: primeiro assinar ad hoc um
executável de ensaio, extrair seu `CDHash` com `codesign`, então consultar
via `csops_audittoken` o CDHash de um filho feito com `fork()`. Não imprimir
hash/kernel token/PID em logs; comparar somente internamente. Rejeitar
propositalmente a referência alterada.

A referência do ensaio é fornecida por variável de ambiente **somente em uma
compilação de teste macOS**. Não é mecanismo de autenticação, pois tal variável
pode ser controlada pelo processo. O binário iOS é compilado sem
`WEBREADER_HOST_CDHASH_REF`; CI proíbe os marcadores dessa interface no
executável distribuído. A operação continua sendo somente `selftest`.

## Arquivos revisados/adicionados

| Caminho | Função |
| --- | --- |
| `ci/webreader_chimera_csops_token_probe66.c` | Modo extra `WEBREADER_HOST_CDHASH_REF`: compara CDHash retornado pelo kernel com referência estática obtida pelo harness. A versão iOS não compila essa interface. |
| `ci/test_chimera_csops_signed_cdhash66.py` | Compila, assina ad hoc e verifica o mesmo binário macOS; obtém CDHash com `codesign -d --verbose=4`, executa quatro consultas positivas e negativas de referência, com autorização sempre DENIED. |
| `ci/build66_code_signature_gate.py` | Extrai também o CDHash estático da IPA previamente aprovada; registra `runtimePeerCodeDirectoryHashVerified=False`. |
| `ci/test_build66_code_signature_gate.py` | Exige CDHash estático em formato hexadecimal de 20 bytes e comprova ausência de verificação de peer em runtime. |
| `ci/audit_build65_signed_artifact.py` | Compara também o CDHash estático com referência independente fixada a partir da IPA QA aprovada, sem consultar o iPad. |
| `.github/workflows/chimera-build66-csops-probe.yml` | Testes nativos macOS adicionais e garantia de que o binário iOS não contém referência de teste. |

## Baseline do artefato original Build65

O pacote **WebReader-Build65-iOS12-adhoc.ipa** original foi aprovado nos
testes físicos da Build65 e auditado independentemente em GitHub Actions.
Valores de referência da **IPA arquivada**, NÃO observação do app no iPad:

- SHA-256 da IPA: `798d2bc9472e626eea9dd9c794fb7d6053b4eac01d288e86d0f04a3c092af10a`
- CDHash estático do aplicativo (20 bytes): `026feebdc48cc425eac9e1d30ba1c983b053f6f1`
- Application identifier: `AR5SFJC432.com.example.MangaReader12.AR5SFJC432`
- Arquitetura: thin ARM64. MinimumOSVersion: 12.0.
- A verificação não demonstra identidade do publicador: assinatura ad hoc.

Auditoria fonte:
[Build65 archived identity workflow](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42342762368).
O hash estático foi observado no log da execução e fixado em
`ci/audit_build65_signed_artifact.py` para detectar divergências futuras.
A hipótese de que **o processo realmente em execução no iPad** tenha este
CDHash ainda precisa ser testada no dispositivo.

## Critérios de aprovação e interpretação

- `HOST_CDHASH_MATCH`: no macOS, token do processo filho e assinatura
  verificada do executável de teste correspondem. **Não prova publisher**.
- `HOST_CDHASH_MISMATCH`: referência propositalmente errada; o ensaio deve
  rejeitar a correspondência.
- `MUTATION_ACCEPTED_UNSAFE`, `CROSS_PID_ACCEPTED_UNSAFE` ou `CALL_DENIED`:
  bloqueadores para confiança de identidade.
- Todas as saídas terminam em `FINAL_INSTALL_AUTHORIZATION=DENIED`.

A compilação do **binário iOS 12 ARM64** e sua assinatura ad hoc não equivale
a teste runtime iOS 12.5.8. O diagnóstico no iPad só será considerado
após um ensaio opcional e supervisionado executado como usuário `mobile`,
sem root. Nenhuma saída de token bruta deve ser copiada.

## Estado da CI

- Fase E com teste PID incorreto: [workflow #9](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42342000103) **SUCCESS**.
- Fase F: novo workflow
  [csops CDHash](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42342926608);
  verificar resultado macOS antes de considerar o ensaio aprovado.
- Auditoria da IPA Build65 com CDHash pinado:
  [workflow #82](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42342926603);
  o hash extraído no workflow anterior #80 fundamenta a constante.
- Nenhum pacote atualizável Build66 IPA foi produzido.
- Nenhum `appinst`, helper root, instalação, rede Comix ou publicação de release
  foi executada por estes testes.

## Próxima etapa útil

Só após os testes macOS e um teste opcional de disponibilidade no iOS12,
elaborar política de identidade de código em runtime: origem confiável para
CDHash esperado, vinculação ao descritor/socket e à assinatura do app em
execução, antirreplay/rollback no armazenamento exclusivo do helper,
consentimento por operação e verificação dos bytes usados pelo `appinst`.

**Condições de segurança mantidas:**
`WebReaderAppinstSocket.liveInstallationEnabled = false`;
`WebReaderUpdateChannel.productionPublicKeyX963 = nil`;
PR #90 continua Draft; `main` e Build65 instalados não foram alterados.

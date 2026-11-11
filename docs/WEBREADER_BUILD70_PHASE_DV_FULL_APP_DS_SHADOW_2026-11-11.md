# WebReader — Fase DV: validar a Build71 COMPLETA pela cadeia DS antes de qualquer entrega

**11/11/2026.** Branch `feat/chimera-updater-phase1-protocol-audit`, PR #90 Draft. Não modifica `main`, não implanta aplicativo, não publica Release e não instala IPA no iPad. A Build70 física e seus downloads não são acessados.

## Por que esta fase existe

A Fase DL já compilava o projeto inteiro WebReader em Release ARM64 com versão temporária 71, assinava uma **cópia descartável ad hoc** dentro do runner macOS e executava DI/DK sobre o ZIP temporário. A Fase DS acrescentou cruzamento rígido entre a assinatura do candidato e relatos de identidade/biblioteca/offline, mas tinha sido exercitada apenas com um aplicativo mínimo sintético. A DV liga **DS ao aplicativo COMPLETO**, usando a mesma IPA temporária da DL, sem transformá-la em distribuição.

## Mudanças concretas

- `ci/build70_dl_full_app_signed_shadow.py` agora chama `inspect_ds_preupgrade_candidate` após DI/DK, antes de o contexto `TemporaryDirectory` destruir a IPA temporária. A DS verifica mais uma vez os bytes SHA256, arquitetura, versão iOS, entitlement declarado e selo ad hoc da Build71 e confronta-os com a linha de base textual DQ/DO/DR.
- Os relatórios DQ e DO/SQLite usados são **propositalmente FICTÍCIOS**. A DQ inclui o texto histórico `com.example.MangaReader12`, build 70 e entitlement histórico, mas **não veio do iPad**. O SQLite artificial contém 2 obras, 5 capítulos e 3 downloads; o inventário artificial contém 3 capítulos sequenciais e 6 páginas. Números criados exclusivamente para testar formatos e a cadeia de validação, nunca um retrato da biblioteca do proprietário.
- Uma divergência, assinatura inválida ou status de autoridade inesperadamente promovido bloqueia o ensaio. A aplicação é re-hasheada após as verificações em host para identificar mudanças nos bytes durante a execução. Isso não garante que um instalador futuro consumiria os mesmos bytes.
- `ci/test_build70_dv_shadow_ds_integration.py` cria sete regressões de contrato sobre fixtures, negativa de autorização, DQ incorreta, inventário offline divergente, chamada DS e nenhuma publicação. O workflow DL executa esses testes no Linux e preserva a compilação/signature-check no macOS.
- DL passa a cancelar as execuções anteriores da **própria** fase ao receber revisão mais recente (`cancel-in-progress: true`). Isso pode evitar builds completos obsoletos, mas não altera as demais filas e não reduz a exigência de validar a revisão vigente.

## Condições de aprovação

Só considerar a DV validada se o job **Linux** e o job **macOS que compila o WebReader inteiro** terminarem com `success`. Um build de IPA sintética mínima (DS) não substitui o full-app build DL. Uma conclusão verde valida apenas a compilação de um projeto completo e os selos de uma cópia descartável no runner.

Não foi gerado artifact transferível, build usuário, upload de IPA/DEB, assinatura de editor de produção nem atualização do aplicativo real. **Não afirmar que a Build71 foi produzida e disponibilizada para instalação.**

## Gates físicos ainda exigidos

Antes de um teste privado autorizado: constatar os metadados do bundle realmente instalado da Build70, inclusive entitlement e identidade de assinatura por método apropriado; validar a IPA final e sua relação com a versão instalada; preservar backup externo sem sobrescrever downloads; obter autorização específica; testar atualização por cima e o mesmo capítulo offline antes/depois sem Wi-Fi. Os relatórios de texto não autenticam um dispositivo e contagens iguais não provam integridade de páginas.

`productionPublicKeyX963=nil`, `independentlyProvisionedSPKISHA256=nil`, `liveInstallationEnabled=false` continuam inalterados. A atualização automática permanece desabilitada.

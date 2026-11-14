# WebReader Build70 — IPA QA gerada, auditada e entregue para teste físico

**Data:** 2026-11-09 UTC. **Origem:** commit imutável `ae931abb725977a417a1fcb20b79c82af825dd55`. **Branch:** `feat/chimera-updater-phase1-protocol-audit`. PR #90 permanece Draft; main não foi alterada.

## Entrega confirmada

- [CI integrada AC–CC — SUCCESS 2/2](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42703266813) para a mudança de escala Webtoon.
- [CI integrada AC–CD — SUCCESS 2/2](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42705574337) para auditoria host de Build70 + testes de app iOS12.
- [GitHub Actions Build70 QA — SUCCESS](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42705903886), incluindo compilação Xcode, assinatura ad hoc em cópia, auditoria ZIP/Mach-O/entitlement, preflight duplo, SHA e upload.
- Artifact **WebReader-Build70-OwnerApproved-iOS12-QA-Filza** (ID `13713972242`), retenção até 23/11/2026. [Página do artifact](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42705903886/artifacts/13713972242).

| Atributo | Valor |
| --- | --- |
| IPA | `WebReader-Build70-iOS12-adhoc.ipa` |
| Tamanho em bytes | `17845463` |
| SHA-256 | `526291cc77203c3881e5f3f1c75904e8863dbde3b3bd9df7e1185c3229fb4fc1` |
| CFBundleVersion | 70 |
| Bundle ID | `com.example.MangaReader12` |
| MinimumOSVersion | 12.0 |
| Build instalada de referência | 69 |
| Identidade ad hoc | `AR5SFJC432.com.example.MangaReader12.AR5SFJC432` |
| Build para instalação automática | **NÃO** |

O arquivo ZIP de QA foi baixado em ambiente de execução e o mesmo arquivo IPA foi reaberto e verificado com SHA-256 idêntico ao recibo, Info.plist com Build70/iOS12 e auditoria de assinatura do runner marcada como aprovada. **Autenticação editorial de produção não provisionada; não há instalação testada pelo app.**

## Teste indispensável antes de instalar

Com a **Build69 ainda instalada**, abra Atualizações → QA local → Conferir IPA local, informe **Build 70** e o SHA-256 exato acima, selecione a IPA70 e confira a mensagem **SHA-256, ZIP e identidade conferidos**. Em seguida copie/revalide o hash e compare. Isso finaliza o 10º teste pendente da Build69; o mecanismo **rejeita a mesma versão após instalar 70**.

Não clique para instalar nesse verificador — ele não instala; a IPA QA é instalada separadamente via Filza.

## Teste da escala depois de instalar manualmente

- Instalar Build70 **por cima da Build69**, nunca desinstalar, restaurar `.mr12backup` ou excluir downloads. O backup não contém imagens offline.
- Webtoon em pé: 100% do viewport no modo Adaptável. Deitado: 75%, centralizado, scroll vertical, sem cortes nem separações entre páginas.
- Em Opções → Largura Webtoon, testar 100%, 85%, 75%, 60% e Adaptável; verificar preservação da posição ao girar.
- Conferir preferências em Configurações → Leitor, depois reabrir o aplicativo e testar páginas offline preexistentes sem Wi-Fi.
- Instalação automática Chimera continua **bloqueada**; nenhuma publicação de GitHub Release de produção foi executada.

## Limitação

CI aprovada e recibos de host validam **o pacote**, não o resultado físico. A primeira QA no iPad deitado será realizada pelo proprietário; registrar problemas sem limpar biblioteca, cache de downloads ou reinstalar.

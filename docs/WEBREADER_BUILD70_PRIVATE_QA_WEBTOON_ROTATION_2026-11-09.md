# WebReader Build 70 — QA da escala Webtoon em paisagem

**Data:** 09/11/2026. **Branch:** `feat/chimera-updater-phase1-protocol-audit`. PR #90 Draft. Build69 instalada no iPad iOS12.5.8; usuário relatou **9/10** checks positivos, nenhum negativo, 1 pendente (importação de uma IPA futura). A Build69 e sua biblioteca não foram alteradas por estes commits.

## Objetivo

A primeira Build70 de teste incorpora a configuração de largura do Webtoon:
- **Adaptável (padrão):** tira 100% da largura em retrato; 75% em paisagem, sem recortar a arte.
- **Manuais:** 100%, 85%, 75% e 60%, independentes das escalas do modo Páginas.
- **No leitor:** `Opções → Largura Webtoon`, sem sair do capítulo. Em Configurações → Leitor → Webtoon, preferência persistente.
- Altura do item = largura real de imagem × proporção da página; centralização horizontal e rolagem vertical contínua com `UICollectionView`.
- Transição de orientação/troca de largura preserva índice e fração da tira atual, sem downloads extras, alterações aos arquivos offline ou gravação forçada de progresso.

## Geração isolada de QA

Workflow **dedicado, de uso único**, em `.github/workflows/chimera-build70-owner-approved-one-shot-qa.yml`. Somente push de um arquivo de autorização com **SHA exato do commit fonte pai**, na branch experimental; a mudança do gatilho tem de alterar **exatamente um arquivo**. O trabalho é executado num macOS temporário, com cópia imutável `git archive` para compilação e testes.

O app é compilado com `CURRENT_PROJECT_VERSION=70` apenas na execução, mantendo o Xcode versionado no 56. É exigido ARM64 iOS12, bundle ID `com.example.MangaReader12`, entitlement `AR5SFJC432.com.example.MangaReader12.AR5SFJC432`, assinatura ad hoc, SHA-256 exato e auditoria de CodeDirectory/CDHash sobre o ZIP IPA antes e depois de publicá-lo por links exclusivos. A auditoria de Build70 exige baseline **69**.

Artefato esperado se todas as etapas passarem:
- `WebReader-Build70-iOS12-adhoc.ipa`
- `.sha256` correspondente
- recibos de auditoria e proveniência
- prazo máximo de 14 dias no Actions, **não** GitHub Release público

O workflow e o empacotador não usam GitHub Release, não provêm assinatura editorial de produção, não modificam main, não chamam appinst, não instalam no iPad e não habilitam o Chimera.

## Procedimento de QA física — ordem crítica

### Antes da instalação (com Build69 ainda instalada)

1. Confirmar presença de capítulos offline e biblioteca na Build69. Manter um `.mr12backup` externo, sabendo que ele **não contém imagens offline**.
2. Transferir a IPA70 ao iPad via Filza/Arquivos.
3. Na **Build69**, abrir área de Atualizações → seção de QA local → **Conferir IPA local**. Informar **Build 70** e o SHA-256 da entrega e selecionar a IPA70. Esperado: `SHA-256, ZIP e identidade conferidos`.
4. Usar opção de copiar/revalidar SHA e confirmar que corresponde ao recebido. **Este fluxo não instala** e conclui o 10º teste pendente da Build69.

### Depois de instalar manualmente por cima da Build69

5. Instalar a IPA70 sem desinstalar a Build69, sem restaurar backup, limpar downloads, mover biblioteca ou reindexar.
6. Abrir capítulo Webtoon em retrato. Padrão Adaptável deve manter 100% da largura.
7. Girar o iPad deitado. A tira deve ficar centralizada com largura de 75%, mantendo o ponto de leitura e a sequência contínua de imagens.
8. Em **Opções → Largura Webtoon**, testar as opções 60%, 85%, 100%, 75% e Adaptável no mesmo capítulo, sem saltos de posição.
9. Conferir em **Configurações → Leitor → Webtoon** a preferência; fechar/reabrir o app, confirmar persistência.
10. Retornar a Páginas (Tela, Largura, Altura e Original), verificar que os controles não foram alterados.
11. Desligar Wi-Fi, abrir capítulos offline **baixados antes da Build69**, verificar páginas, biblioteca, progresso e continuidade depois de fechar e reabrir ainda sem rede.
12. Confirmar que o instalador automático continua bloqueado.

Se qualquer teste falhar: **não excluir nem restaurar a biblioteca para tentar corrigir**. Relatar apenas sintoma (escala, rotação, posição, imagem, mensagem de erro) e qual opção foi usada.

## Limites de inferência

A CI verifica código, build e assinatura no host; não prova funcionamento físico no iPad, nem compatibilidade absoluta das páginas baixadas. A Build70 só recebe o status físico após retorno do proprietário. A Build69 continua a referência aprovada até então.

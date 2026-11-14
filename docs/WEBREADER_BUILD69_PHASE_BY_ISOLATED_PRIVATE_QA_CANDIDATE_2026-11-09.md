# WebReader Build69 — Fase BY: candidata privada construída de um commit revisado

**Data:** 2026-11-09. **Branch:** `feat/chimera-updater-phase1-protocol-audit`. PR #90 continua **Draft**, `main` intacta. Build68 e biblioteca no iPad preservadas. **Nenhuma IPA real Build69 foi gerada, distribuída ou instalada nesta fase.**

## Problema e decisão

A fase BX verifica a integridade de um checkout e o hash do `HEAD`, mas o empacotador BK historicamente aceitava um `.app` previamente construído por qualquer procedimento. Checkout limpo não comprova que o binário veio do commit revisado.

A geração dos ícones do WebReader e da libwebp 1.6.0 cria arquivos locais de preparação. Se executada no mesmo checkout, a política estrita BX pode recusar o empacotamento devido a arquivos não rastreados. Não reduzir a exigência BX ou ignorar arquivos gerados.

## BY — preparação isolada e bloqueada por padrão

Novo script `ci/build69_by_private_qa_candidate_mac.sh`:

1. Recusa execução sem consentimento textual **específico de IPA privada** e o SHA completo `WR69_PRIVATE_QA_REVIEWED_COMMIT`. Recusa CI/GitHub Actions, root, não-macOS, nome de IPA inesperado, destino dentro do repositório e arquivos já presentes.
2. Executa BX antes de tocar o build. Usa **git archive do SHA revisado** para uma árvore fonte descartável fora do checkout, em vez de copiar arquivos locais não revisados.
3. Gera os ícones aprovados, compila a libwebp de fonte com SHA-256 fixado e executa Xcode Release ARM64/iOS12, com `CURRENT_PROJECT_VERSION=69` apenas em argumento e `CODE_SIGNING_ALLOWED=NO`.
4. Audita o `.app` unsigned via BA e reexecuta BX para verificar que o checkout de revisão permaneceu limpo e na mesma revisão.
5. Somente em macOS pessoal, com aprovação expressa já fornecida pelo proprietário, chama o **empacotador privado BK/BL** existente, que assina apenas uma cópia temporária, verifica versão, código e entitlements, e escreve a IPA e checksum de forma atômica em diretório externo.
6. Apaga a fonte/artefatos temporários ao sair. Não publica Release, não usa `appinst`, não instala no iPad e não mescla `main`.

## Limites da evidência

O wrapper vincula **procedimentalmente** a compilação a um snapshot Git específico, reduzindo a possibilidade de selecionar um `.app` antigo por engano. Não é reprodução bit a bit independente: versões de Xcode/CMake/macOS e cadeia de ferramentas podem variar; a proveniência da dependência libwebp depende também do SHA-256 fixado. `codesign` ad hoc e SHA não autenticam um editor de produção e não comprovam compatibilidade física com a instalação existente.

A fase BY **não é autorização** para gerar/distribuir IPA, acionar Chimera ou restaurar backup. O proprietário ainda precisa escolher o SHA revisado por canal confiável e expressar consentimento específico para a candidata. Nenhuma dessas ações foi executada nesta fase.

## Validação sem IPA real

`ci/test_build69_by_private_qa_candidate_mac.py` cobre sintaxe Bash, ausência de aprovação, bloqueio em `CI` e `GITHUB_ACTIONS`, fluxo ordenado de archive → preparo → Xcode → BA → BK, exclusões de comandos de publicação/instalação e proteção contra sobrescrita. Workflow integrado ampliado para **AC–BY**. Testes no CI são somente de política e build temporário já existente, **não executam o wrapper BY com aprovação**, não geram pacote Build69.

## Próximo marco

Verificar CI integrada AC–BY completa; revisar SHA final e ambiente macOS de build; obter autorização explícita para empacotamento privado antes da primeira IPA QA. Na QA física, exportar backup Build68 fora do iPad, anotar capítulos completos e instalar por cima **manualmente**, sem restaurar backup e sem apagar a pasta offline. Os 16 checks no iPad são obrigatórios antes de qualquer ativação do instalador automático.

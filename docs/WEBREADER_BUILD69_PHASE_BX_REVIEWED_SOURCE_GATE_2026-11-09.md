# WebReader Build69 — Fase BX: commit revisado e checkout limpo antes da IPA privada

**09/11/2026.** Branch experimental \`feat/chimera-updater-phase1-protocol-audit\`; PR #90 **Draft**, \`main\` intocada. Build68 e biblioteca offline do iPad iOS12.5.8 permanecem preservadas. **Nenhuma IPA real Build69 foi gerada, distribuída ou instalada.**

## Problema observado

O empacotador privado BK exigia consentimento textual e a branch experimental, mas **não vinculava explicitamente o checkout local a um commit integral de 40 caracteres previamente revisado pelo proprietário**, nem recusava um checkout com alterações locais ou arquivos não rastreados. Isso permitiria, numa execução futura autorizada, empacotar a partir de uma árvore fonte local diferente da revisão considerada pronta para QA.

## Mitigação BX

- \`ci/build69_bx_reviewed_source_gate.py\`: somente leitura, sem rede e sem escrita, exige \`--checkout\` como raiz Git real, branch experimental, SHA-1 de 40 caracteres minúsculos igual ao \`HEAD\` e \`git status --porcelain=v1 --untracked-files=all\` vazio.
- \`ci/package_webreader_build69_private_qa_ipa.sh\` passa a exigir a variável **\`WR69_PRIVATE_QA_REVIEWED_COMMIT\`**, fornecida conscientemente pelo proprietário, além do consentimento BK já existente. A validação ocorre **antes** da inspeção BA e antes de qualquer arquivo de saída.
- \`ci/test_build69_bx_reviewed_source_gate.py\` cobre repositórios Git sintéticos: SHA truncado/errado, outra branch, HEAD destacado, arquivos editados, staged, untracked, raiz incorreta e revisão nova não coberta pelo SHA antigo.
- Workflow integrado AC–BX passa a executar a suíte BX no Linux e mantém a compilação iOS12 + assinatura ad hoc **efêmera**, sem IPA no CI.

## Limites importantes

Um commit limpo **não prova que o binário \`.app\` foi compilado daquele commit**: a compilação/inspeção BA, os bytes finais, o \`codesign\` ad hoc, os entitlements, o CDHash e o checksum da IPA precisam de verificação independente depois de uma eventual autorização. O dono deve escolher o SHA revisado por canal confiável; o programa não autentica o dono, não concede aprovação de pacote/distribuição e não substitui os 16 testes físicos.

**Continuam bloqueados:** geração/entrega de IPA sem autorização específica, merge em \`main\`, publicação editorial/produção, trust root real, instalação automática Chimera, reindexação ou limpeza de arquivos de capítulos existentes.

**Próximo marco real:** em ambiente macOS apropriado, após autorização expressa para a candidata privada, compilar Build69 exatamente a partir do commit revisado, checar a origem e gerar pacote isolado; executar BB/BC, transferir bytes com SHA independente e testar manualmente *in-place* sem restaurar backup ou apagar páginas.

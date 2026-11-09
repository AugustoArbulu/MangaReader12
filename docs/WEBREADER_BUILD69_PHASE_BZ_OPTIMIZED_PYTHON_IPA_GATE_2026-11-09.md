# WebReader Build69 — BZ: impedir bypass de validações em Python otimizado

**Data:** 09/11/2026. Branch experimental `feat/chimera-updater-phase1-protocol-audit`; PR #90 Draft, main intocada. Build68 e seus downloads no iPad não foram modificados. **Nenhuma IPA verdadeira Build69 produzida ou instalada.**

## Revisão pós-BY

CI AC–BY [#42663840060](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42663840060) encerrou com SUCCESS **2/2** jobs: Linux e macOS, incluindo o build ARM64 iOS12 e a assinatura ad hoc de cópia efêmera do aplicativo real — sem gerar IPA.

Uma revisão do empacotador privado BK/BL revelou que duas rotinas Python embutidas no Bash usavam `assert` para verificar:
- entitlements e campos de `Info.plist`;
- tamanho limite da IPA, Build69/iOS12, integridade da assinatura ad hoc, identidade instalada e Mach-O arm64.

**Problema concreto:** o Python pode remover todas as instruções `assert` quando `PYTHONOPTIMIZE` está definido ou quando o interpretador executa com `-O`. Essas invariantes nunca devem depender de flags de otimização. Embora outros validadores tenham verificações próprias, não é aceitável que as verificações finais do empacotador desapareçam silenciosamente.

## Correção BZ

- Em `ci/package_webreader_build69_private_qa_ipa.sh`, substituídas as instruções `assert` por verificações explícitas `if ...: raise SystemExit("BLOCKED: ...")`; o erro interrompe a geração antes da publicação do nome final.
- Entitlements ad hoc agora são comparados com o dicionário exato; `Info.plist` mantém os campos de versão 69, bundle ID, executável, nome e iOS mínimo 12.0.
- Auditoria final exige tamanho positivo limitado, Build 69, mínimo iOS 12.0, CodeDirectory validado, identidade compatível e binário ARM64.
- Os testes BK existentes foram adaptados às verificações permanentes.
- Novo `ci/test_build69_bz_optimized_python_admission.py` extrai as rotinas Python reais do empacotador, proíbe nós `ast.Assert` e executa os validadores com `-O` e `PYTHONOPTIMIZE=2` contra dados sintéticos e módulos de preflight simulados. Identidades incorretas, versão 68, iOS 13, tamanho inválido, assinatura inválida e identidade ARM64 reprovada devem continuar falhando. Nenhum código de assinatura nativo, IPA real, upload ou instalação é executado por esses testes.
- Workflow integrado atualizado de AC–BY para **AC–BZ**, com a regressão Linux e compilação macOS/iOS12 preexistentes.

## Restrições mantidas

A correção de um bypass de validação **não é uma aprovação** para gerar, enviar ou instalar IPA. O empacotador continua exigindo consentimento explícito específico, Mac pessoal, commit fonte revisado, checkout limpo, destino externo e permissões não privilegiadas; não roda em GitHub Actions.

A assinatura ad hoc verifica a consistência de código, não autentica editor de produção. Ainda são necessárias verificação do SHA-256 da cópia por canal independente e QA física de 16 itens após autorização separada. O caminho de atualização automática Chimera fica desativado.

## Próximo marco

Confirmar a conclusão da CI AC–BZ; registrar o SHA final de revisão e avaliar o caminho real de empacotamento privado num macOS controlado, sem confundir validação do código-fonte e de um `.app` efêmero com uma IPA já existente.

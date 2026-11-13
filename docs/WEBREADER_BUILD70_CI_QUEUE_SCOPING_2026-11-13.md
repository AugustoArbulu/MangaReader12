# WebReader — redução de congestionamento do CI na PR #90 (13/11/2026)

## Diagnóstico fundamentado

A PR #90 Draft apresenta **650 caminhos alterados**, inclusive **86 workflows**, e o HEAD anterior gerava aproximadamente **45 workflow runs** em um único commit. Os arquivos sob pull_request podem combinar com filtros paths pelo diff acumulado de toda a PR, mesmo quando o commit mais recente contém somente auditorias Python. Mais duas rotinas legadas (`build.yml` e `appinst-direct-test.yml`) tinham push não restrito, iniciando compilações macOS e uploads de **IPAs diagnósticas** por alterações sem relação com elas. Isso contribui para trabalho desnecessário. Não foi verificada a causa interna de falta de runners macOS nem a situação de cotas; **queued não é sucesso**.

## Mudança na branch de trabalho, sem mudar main

- `.github/workflows/appinst-direct-test.yml`: preserva workflow_dispatch e limita push a `ci/appinst_direct_probe/**`, script de embalagem, seu teste e definição do próprio workflow. **Mudanças apenas em EA–EK não geram um novo IPA de diagnóstico do appinst.** Um push com alterações na ferramenta de diagnóstico ainda o valida automaticamente.
- `.github/workflows/build.yml`: mantém push, pull_request, workflow_dispatch e build macOS 14, mas ignora commits em que **todos** os caminhos estejam em `docs/**`, `ci/build70_e*.py`, `ci/test_build70_e*.py` e workflows fase E. Mudanças de Swift, assets, scripts nativos e o próprio build.yml continuam acionando o workflow. Jobs pull_request de uma PR Draft são pulados; ao marcar Ready for Review, podem executar normalmente; push com alterações nativas continua executando. Os builds antigos não são apagados.
- `chimera-build70-phase-eg-cli-failclosed.yml`, `...ei-all-downloads.yml` e `...ek-partial-prefix.yml`: concurrency por workflow+branch, cancel-in-progress=true. Uma execução nova substitui a anterior do mesmo audit, sem cancelar outros workflows; a matriz **Linux + macOS** permanece, bem como todas as verificações de assinatura/instalação bloqueada.

## Limites e testes

`ci/test_build70_ci_scope.py` exerce sete cenários de gatilhos, escopo de paths, botão manual, matriz Linux/macOS, grupos isolados e flags de produção desabilitadas. É incluído na regressão integrada. São testes ESTÁTICOS; não comprovam cotas, latência dos runners, ou a implementação do filtro de path pelo GitHub. A conferência final depende dos futuros workflow runs no GitHub.

A mudança reduz execuções futuras que não fazem sentido. Não cancela necessariamente jobs históricos enfileirados. Não cria, publica, distribui ou instala IPA71; o `ci/build71_owner_approved_qa_trigger.txt` deve seguir ausente. PR #90 continua Draft e main intacta. Uma eventual compilação de IPA diagnóstica por trabalho nativo é distinta de IPA71 de produção; não utilizar nenhum artefato de CI como autorização física de instalação.

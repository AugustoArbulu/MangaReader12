# WebReader Build69 — Fases BL/BM: publicação local atômica e quantidade de páginas offline

**Data da engenharia:** 2026-11-09 UTC. **Branch:** `feat/chimera-updater-phase1-protocol-audit`; **[PR #90](https://github.com/AugustoArbulu/MangaReader12/pull/90) Draft**. Não alterar `main`, não reinstalar/desinstalar a Build68 no iPad, não publicar GitHub Releases, não ligar o instalador Chimera. Nenhuma IPA Build69 real foi produzida nesta etapa.

## Baseline técnico comprovado

O workflow AC–BK [#42567641859](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42567641859) terminou **SUCCESS em ambos os jobs**: Linux offline e macOS Swift/Xcode ARM64 iOS12. Isso inclui QA sintética dos arquivos offline, recibos de assinatura ad hoc de fixtures temporárias e uma compilação de preview `CURRENT_PROJECT_VERSION=69` **unsigned** apenas em diretório temporário. O Xcode da branch ainda declara versão 56; preview não é IPA instalável.

## BL — jamais expor um pacote parcialmente construído como IPA pronta

**Achado:** `ci/package_webreader_build69_private_qa_ipa.sh` da BK usava `zip` diretamente no nome de saída `WebReader-Build69-iOS12-adhoc.ipa` **antes** de concluir auditoria de SHA/ZIP/código assinado. Se a máquina ou processo interrompesse, poderia ficar uma IPA parcial com nome final no disco.

**Correção implementada:**

1. A rotina privada continua **bloqueada por padrão**, exigindo aprovação humana explícita via `WR69_PRIVATE_QA_PACKAGE_APPROVAL`, na branch experimental, como usuário não-root; também recusa execução em ambiente automatizado `CI` ou `GITHUB_ACTIONS`, ainda que receba o marcador.
2. O `mktemp -d` agora cria um diretório privado **dentro da pasta de saída externa**, no mesmo filesystem da futura IPA. O app `.app` é copiado e assinado ad hoc **dentro da área temporária**; o ZIP é montado sob um **nome temporário**, nunca sob o nome final.
3. Primeiro valida a estrutura ZIP, SHA-256, versão 69, identidade e `codesign` da **cópia assinada**. O SHA preliminar é calculado em streaming, com limite `MAX_IPA_BYTES`, não por leitura prévia ilimitada de `ipa.read_bytes()`.
4. Calcula um checksum `WebReader-Build69-iOS12-adhoc.ipa.sha256` apenas na área temporária, mencionando **exatamente o nome final** no conteúdo.
5. **Publicação em duas fases com `os.link` de criação exclusiva:** cria primeiro o checksum externo; cria o nome da IPA final **por último** e somente após toda a auditoria. `os.link` falha se o destino já existir, inclusive symlink; não sobrescreve backups ou arquivos anteriores. Falha no segundo link remove somente o checksum que foi criado por esta tentativa. A limpeza remove a pasta temporária, não o app original do proprietário.
6. **Limite:** uma interrupção entre os dois hard links ainda pode deixar um checksum isolado, mas **nunca uma IPA incompleta exposta com nome final**. Esse checksum não autoriza instalar nada e a próxima tentativa deve recusar sobrescrita até o proprietário verificar. O arquivo final não é um artefato GitHub, não é uma autenticação editorial de produção e **não é distribuído automaticamente**.

`ci/test_build69_bk_private_qa_packaging_gate.py` foi reforçado para bloquear execução em CI mesmo com marcador correto e exigir staging/auditoria/exclusividade. `ci/test_build69_bl_atomic_private_delivery.py` extrai e **executa apenas a etapa atômica de publicação** em arquivos sintéticos pequenos (não IPA): prova que uma saída anterior não é sobrescrita; que symlink/collision falham; e que uma falha simulada no segundo link reverte o checksum criado. O empacotador completo **não** é executado em CI.

## BM — recibo de quantidade de páginas para downloads novos, preservando legados

**Achado:** o inventário BH verifica lacunas internas, arquivos vazios e symlinks, mas sem quantidade original gravada é impossível identificar se a **última** página foi removida após um download ter sido concluído. Ex.: um capítulo com 20 páginas termina com 19 arquivos sequenciais válidos, sem lacunas detectáveis.

**Implementação:**

- Nova classe iOS12 `MangaReader12/Downloads/WebReaderOfflineCompletionReceipt.swift`: nome local oculto `.webreader-completion-v1`, com conteúdo simples `WR-OFFLINE-COMPLETE-V1:<quantidade>\n`. Não armazena URLs, IDs, nomes de obras, imagens, chaves ou preferências.
- `ChapterDownloadManager.downloadNextPage` ao terminar a fila **primeiro** exige que todos os arquivos `page-%05d.bin` existam, sejam regulares, não vazios e sequenciais, **e que seu número seja exatamente `job.pages.count`**. Só então grava o recibo atomicamente e muda o estado do SQLite para `completed`. Caso alguma verificação falhe, preserva os arquivos presentes e não declara o capítulo completo.
- `ChapterDownloadManager.localPages` ao abrir um capítulo `completed` exige o inventário BH e, **quando o recibo existir**, verifica se a quantidade gravada é igual à quantidade de arquivos realmente presentes. Recibo inválido, symlink, diretório no lugar do recibo, contagem errada ou recibo maior que 64 bytes = capítulo incompleto, sem apagá-lo.
- **Compatibilidade crítica:** downloads feitos na Build68 não possuem esse arquivo oculto. Se estiver ausente, `verifyIfPresent` retorna `false` e **permite o capítulo legado** após as validações BH. Nenhuma página antiga é regravada ou marcada como inválida somente por falta do recibo.
- A auditoria BI de até 64 capítulos agora também diferencia **quantos válidos possuem recibo** e **quantos válidos são legados sem recibo**. Conta recibos inválidos como falhas; nunca mostra títulos, caminhos ou imagens.
- **Limite:** recibo comprova a quantidade esperada **do plano de download local**, não autentica a contagem de páginas no servidor, nem prova que o arquivo é uma imagem decodificável. A prova final continua sendo abrir o capítulo inteiro com Wi-Fi desligado.

### Testes e CI

- `ci/test_native_webreader_offline_completion_receipt.py`: executa Swift em diretório descartável, validando legado sem recibo, novo recibo válido, ausência da última página, página excedente, recibo vazio, manipulado, grande demais, symlink e diretório no lugar do recibo.
- `ci/test_build69_bm_completion_receipt_policy.py`: confirma a ordem arquivos → recibo → SQLite `completed`, validação no leitor antes de rebind de caminho e ausência de operações destrutivas.
- `ci/test_native_webreader_offline_preservation_audit.py`: valida novo contador de recibos com SQLite v1 sintético, inclusive IDs fictícios e nenhuma divulgação de dados.
- CI integrado **AC–BM** [#42570180542](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42570180542): Linux e macOS/Swift + Xcode iOS12. Consultar o resultado; não afirmar sucesso antes da execução mais recente.

## O que falta para uma IPA privada real

A Build68 instalada e os arquivos offline permanecem intocados. A fonte Xcode ainda contém `CURRENT_PROJECT_VERSION=56`; a compilação isolada override69 é apenas um teste e não foi distribuída.

Para gerar uma IPA QA real, será necessária aprovação específica de empacotamento e distribuição privada, depois da CI verde. O empacotador só poderá ser acionado **manualmente em macOS externo** com `.app` Build69 já compilado, e a IPA final precisará passar por BB (ZIP/entitlements/SHA) e BC (transferência, SHA/size). Nem assinatura ad hoc nem checksum gerado pela mesma máquina autenticam o editor de produção. Não existe autorização para instalar, mesclar `main` ou ativar a ponte Chimera.

No teste físico futuro, preservar o app anterior, exportar backup `.mr12backup` para outro dispositivo (esse backup **não** preserva imagens offline), instalar por cima e executar o roteiro de **16 verificações manuais**, abrindo capítulos legados inteiros sem Wi-Fi. Nunca restaurar backup automaticamente durante o upgrade: isso apagaria os downloads existentes.

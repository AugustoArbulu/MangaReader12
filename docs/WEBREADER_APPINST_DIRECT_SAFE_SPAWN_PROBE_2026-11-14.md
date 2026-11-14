# WebReader — diagnóstico de execução local antes de AppInst
Data: 14/11/2026 (UTC). Branch `feat/chimera-updater-phase1-protocol-audit` · PR #90 Draft.

## Problema concreto
O objetivo final é instalar uma IPA já verificada a partir do WebReader, sem Filza. O laboratório Swift/C fake comprova o formato do protocolo, mas não se a sandbox do Chimera permite iniciar `/usr/bin/appinst` de dentro do app. A antiga IPA diagnóstica podia testar `appinst --help` após consentimento; a ferramenta de referência pode fazer limpeza de sessões temporárias até nessa invocação. Não há resultado físico confirmado desse teste.

## Menor experimento sem instalar e sem chamar appinst
A IPA **totalmente separada** `com.example.WebReaderAppinstDirectProbe` agora mostra dois botões independentes:

1. **Testar processo local (sem appinst)**: executa somente `WRSpawnChild`, um ARM64 compilado do arquivo `ci/appinst_direct_probe/spawn_child.c` no próprio bundle e assinado ad hoc. Este child apenas retorna zero. O app obtém `posix_spawn`/exit code, com timeout, e informa `SPAWN_LOCAL=OK/NEGADO` e `APPINST_EXECUTADO=NAO`. **Não usa IPA, appinst, downloads, WebReader, shell ou redes**.
2. **Testar appinst --help (opcional)**: mantém o comportamento diagnóstico anterior, com alerta explícito. Mesmo sem instalar IPA, appinst pode limpar sessões temporárias antigas. **Não é pré-requisito para o primeiro botão**. Use apenas em avaliação física consciente e sem outra instalação em andamento.

Ambos exigem o bundle ID independente; EUID root é recusado. O pacote agora é `WebReader-Appinst-Direto-iOS12-adhoc.ipa` (Build **3 do teste**, nunca Build71 do WebReader), com o app e o child assinados ad hoc. O app não possui chaves de produção ou acesso ao banco de mangás. Artifact fica nos GitHub Actions; não é Release ou instalação automática.

## Interpretação
- `SPAWN_LOCAL=OK`: a sandbox permitiu executar **esse child assinado**, no contexto testado. Não prova que o caminho externo `/usr/bin/appinst` funcione; ainda faltam autorização, acesso ao pacote, assinatura e prova de preservação.
- `SPAWN_LOCAL=NEGADO`: esse child não iniciou, o que orienta investigar políticas de execução, assinaturas ou helper — **não prova que toda execução direta seja impossível**.
- O teste opcional de `appinst --help` só avalia lançamento do comando, não instalação real e não segurança da atualização.

## QA
`.github/workflows/appinst-direct-test.yml` compila o bundle/child ARM64 para iOS12, assina ambos ad hoc, audita IPA isolada e entrega somente artefato de diagnóstico. Nenhuma IPA do WebReader real é criada ou instalada. O resultado do Actions deve ser confirmado antes de alegar que a IPA de teste está pronta.

## Preservação
`main`, Build70, Downloads, SQLite e iPad intocados. PR #90 Draft. `WebReaderAppinstSocket.liveInstallationEnabled=false`; nenhum install IPC; nenhuma Build71/Release. Depois de revisar o relatório **do primeiro botão**, decidir se faz sentido prosseguir com execução direta ou se a ponte Chimera autenticada é indispensável.


## Resultado validado no GitHub Actions
[Execução #43552863939](https://github.com/AugustoArbulu/MangaReader12/actions/runs/43552863939): **SUCCESS** (macOS 15). Compilação iOS12 ARM64 de `WRAppinstDirect` e `WRSpawnChild`, assinatura ad hoc de ambos com `codesign --verify`, auditoria de ZIP, Bundle ID `com.example.WebReaderAppinstDirectProbe`, `CFBundleVersion=3`, Mach-O ARM64 e restrições de escopo. Artefato de Actions **`WebReader-Appinst-Direto-iOS12-TEST`**, id `14096369777`, contendo `WebReader-Appinst-Direto-iOS12-adhoc.ipa` e SHA-256. Não é um GitHub Release e não substitui o WebReader instalado.

**Não foi executado** no iPad. O próximo dado necessário é a saída de `Testar processo local (sem appinst)`, copiada do aplicativo de diagnóstico. Não usar o resultado para autorizar instalação. Nenhum AppInst real foi executado na CI; somente `codesign`, compilação e ZIP.

Observação: o teste `posix_spawn` de `WRSpawnChild` demonstra apenas uma classe de execução sob a assinatura do arquivo e o sandbox do diagnóstico. Não substitui um teste de permissão para execução de `/usr/bin/appinst` nem o requisito de conferir o pacote antes da instalação.

## Incremento do diagnóstico (14/11/2026)
O primeiro botão também registra `APPINST_META_LSTAT`, `APPINST_META_XOK` e `APPINST_META_ADVISORY=YES`. Ele chama **somente** `lstat` e `access(X_OK)` em `/usr/bin/appinst` — **não executa** o comando; a sandbox pode ocultar esses dados, então `ERRNO` não prova que `posix_spawn` seria impossível. A consulta é incluída na mesma ação do child local, para evitar solicitar uma execução desnecessária de `appinst --help`.

O empacotamento de diagnóstico agora **confere o entitlement efetivamente gravado na assinatura** (`application-identifier=WRTEST0001.com.example.WebReaderAppinstDirectProbe`) antes de criar a IPA, além de validar as duas assinaturas ad hoc com `codesign --verify`. Identidade sintética específica do app de testes, sem vínculo com a Build70. O CI reexecuta os contratos de primeiro botão sem AppInst e audita a IPA assinada. O resultado de CI não demonstra instalação física nem permissões no iPad.

## Nova validação (14/11/2026, metadata-only)
[GitHub Actions #43555724305](https://github.com/AugustoArbulu/MangaReader12/actions/runs/43555724305) **SUCCESS** em macOS 15. O teste de pacote incluiu os novos contratos do primeiro botão: `lstat` e `access(X_OK)` de `/usr/bin/appinst` apenas para metadados, execução exclusivamente de `WRSpawnChild` e **nenhuma invocação de AppInst** nesse percurso. O pipeline verificou também o entitlement assinado, não apenas o arquivo-fonte de configuração: `WRTEST0001.com.example.WebReaderAppinstDirectProbe`.

**Novo artefato** `WebReader-Appinst-Direto-iOS12-TEST`, ID **14098076811**. Contém a IPA de diagnóstico ARM64/iOS12 e SHA-256. Prefira esse artefato ao da execução anterior (ID 14096369777), pois a versão nova inclui `APPINST_META_LSTAT`, `APPINST_META_XOK` e os controles de assinatura adicionais.

Ainda não existem resultados físicos em Chimera, não há instalação de IPA efetuada nem método de atualização em um toque habilitado. O botão opcional `appinst --help` continua separado e não é necessário para a primeira validação.

## Interpretador offline do relatório (sem novas ações no iPad)
O novo `ci/appinst_probe_report.py` recebe **somente texto copiado** do primeiro botão. Exige cabeçalho exato, um resultado `SPAWN_LOCAL`, metadados `APPINST_META_*` coerentes e marcador `APPINST_EXECUTADO=NAO | INSTALACAO=NAO`. Recusa texto truncado, duplicado, incompleto, de outro botão ou com formato inesperado. Classifica execução do **child local**, não do appinst. Em todos os retornos: `direct_appinst_execution_verified=false`, `installer_authorized=false` e `installation_performed=false`. Nenhum dado da biblioteca é lido e nenhum processo é executado.

Exemplo de uso no checkout, após copiar o relatório para um arquivo de texto local do proprietário: `python3 ci/appinst_probe_report.py resultado.txt`. É opcional; também é possível colar o texto diretamente no chat para análise. O CI macOS executa os casos sintéticos antes de montar a IPA diagnóstica. Não representa um novo instalador nem depende de publicar uma Release.

## Interpretador validado no macOS
[GitHub Actions #43558301424](https://github.com/AugustoArbulu/MangaReader12/actions/runs/43558301424) **SUCCESS**. Executou os 13 testes sintéticos do parser de relatório e compilou/assinou/auditou novamente a IPA diagnóstica iOS12 ARM64 (sem chamar AppInst). Artefato `WebReader-Appinst-Direto-iOS12-TEST` ID `14099590502`. **O código do app de teste não mudou** nessa execução; a adição foi apenas para analisar o texto copiado e negar interpretações inseguras. Continua pendente o relatório físico do iPad.

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

## Retorno físico em 20/11/2026 (iPad iOS 12.5.8; Build3 diagnóstica)

O proprietário testou **somente o primeiro botão**, com o relatório literal:

```text
WebReader • Spawn local sem appinst
iOS: 12.5.8
UID: 501 | EUID: 501
APPINST_META_LSTAT=ERRNO_1
APPINST_META_XOK=ERRNO_1
APPINST_META_ADVISORY=YES
RESULTADO: child inválido ou não executável.
```

**Interpretação estrita:** o código encerrou **antes de** `posix_spawn`, na validação conjunta de `pathForResource`, `lstat`, `S_ISREG` e bits `0111`. Portanto, o resultado NÃO prova que o iOS/Chimera bloqueia lançamento do filho, nem que o `appinst` é inexequível. O `ERRNO_1` para metadados de `/usr/bin/appinst` é consultivo e não diz qual etapa do filho falhou. Conferência local da IPA original Build3: `Payload/WRAppinstDirect.app/WRSpawnChild` estava presente no ZIP e a entrada registrava modo Unix `0100755`. Isso não garante atributos/visibilidade do arquivo **após instalar no iPad**.

### Correção diagnóstica Build4 (branch PR #90; ainda requer CI e retorno físico)

- O primeiro botão, *sem appinst*, produz agora campos independentes `CHILD_PATH`, `CHILD_LSTAT`, `CHILD_MODE_EXEC`, `CHILD_ACCESS_XOK`, `SPAWN_LOCAL` e marcador `APPINST_EXECUTADO=NAO | INSTALACAO=NAO`, inclusive quando o pré-teste falha.
- `access(X_OK)` apenas informa uma observação consultiva. Se `lstat` identifica arquivo regular com bits executáveis, o aplicativo ainda tenta `posix_spawn` do *filho local*, mesmo que `access(X_OK)` seja negado. Não altera permissões do bundle e não executa `/usr/bin/appinst`.
- `ci/appinst_probe_report.py` distingue exatamente a falha anterior Build3, o pré-teste Build4 e o lançamento do filho, recusando relatórios manipulados e qualquer promoção a autorização de instalação. Testes sintéticos incluem as variantes e negativas.
- `ci/test_appinst_direct_probe.py` passa a exigir modo executável do filho dentro da IPA, além dos demais invariantes. Build da IPA diagnóstica incrementada de 3 para **4**, com bundle ID separado da Build70.
- **Nenhuma Build71, Release pública ou atualização do WebReader foi criada.** Permanecem `main` intacta, PR Draft, `liveInstallationEnabled=false`, banco/biblioteca/arquivos offline não alterados. Próximo passo físico apenas com a IPA diagnóstica Build4 depois de CI verde: executar o primeiro botão e copiar o relatório. O segundo botão opcional continua desnecessário.

### Build4 CI e pacote verificados (21/11/2026 UTC)

- GitHub Actions [#44845878702](https://github.com/AugustoArbulu/MangaReader12/actions/runs/44845878702): **SUCCESS**, parser histórico + Build4, clang ARM64/iOS12, `codesign`, contrato de não execução do AppInst pelo primeiro botão, verificação de ZIP/entitlements e upload de artifact.
- Artifact `WebReader-Appinst-Direto-iOS12-TEST` ID `14682527986`. IPA `WebReader-Appinst-Direto-iOS12-adhoc.ipa` de 18.156 bytes; SHA-256 `db3682dc58506864edfc9b2441ec18a293fd32e5f4922f7e9c99e07c293d7b3e`, conferido com `.sha256` após extração do arquivo do workflow. `CFBundleVersion=4`, `MinimumOSVersion=12.0`, ID isolado `com.example.WebReaderAppinstDirectProbe`; `WRSpawnChild` modo Unix `0100755` no ZIP.
- **Ainda falta teste físico Build4.** A Build3 encerrou no pré-teste; nenhum AppInst foi executado. O comportamento de `posix_spawn` e do bundle instalado no iPad continua desconhecido. Instale Build4 *apenas como diagnóstico separado* e execute o primeiro botão.

## Retorno físico da Build4 e controle Build5 — 20/11/2026 (America/Sao_Paulo)

O iPad **iOS 12.5.8 / UID 501 mobile** executou o primeiro botão da **Build4** e produziu:

```text
WebReader • Spawn local sem appinst
iOS: 12.5.8
UID: 501 | EUID: 501
APPINST_META_LSTAT=ERRNO_1
APPINST_META_XOK=ERRNO_1
APPINST_META_ADVISORY=YES
CHILD_PATH=FOUND
CHILD_LSTAT=REGULAR
CHILD_MODE_EXEC=NO
CHILD_ACCESS_XOK=ERRNO_1
SPAWN_LOCAL=PRECHECK_FAILED
APPINST_EXECUTADO=NAO | INSTALACAO=NAO
```

**Fato confirmado:** após instalação, o `WRSpawnChild` é arquivo regular, mas não tinha bits `0111` de execução; logo a Build4 **não chamou `posix_spawn`**. O ZIP da IPA Build4 continha o filho com bit de execução; a diferença é evidência de que os metadados não se mantiveram entre pacote e observação do aplicativo, mas **não identifica com precisão o mecanismo que os alterou**, nem comprova a possibilidade/impossibilidade de executar outros processos no iOS 12.

### Próximo controle independente: Build5 diagnóstica

A Build5 preserva os relatórios de `WRSpawnChild` e acrescenta duas linhas **ao final** do primeiro botão:

- `SELF_MAIN=REGULAR_EXEC/REGULAR_NOEXEC/NOT_REGULAR/MISSING/ERRNO_n`: observação consultiva de `lstat` para o **exato executável principal do app de teste**, obtido de `NSBundle.mainBundle.executablePath`.
- `SPAWN_SELF=OK/NEGADO/FALHA_DO_SELF/WAITPID_INDISPONIVEL/TIMEOUT/PRECHECK_FAILED`: tenta somente `posix_spawn` do próprio binário assinado instalado, com argumento fixo `--wr-safe-self-child`. Quando chamado com **exatamente** esse argumento, `main()` retorna zero imediatamente, **sem UIKit, sem acesso a arquivos, sem uso de AppInst e sem instalação**.

Esse segundo controle é útil porque o executável principal já inicia normalmente pela SpringBoard, ao contrário do `WRSpawnChild` auxiliar que perdeu bits. **Mesmo `SPAWN_SELF=OK` não prova que `/usr/bin/appinst` pode iniciar, nem que instalar uma IPA seja seguro ou autorizado.** O arquivo de teste continua ad hoc com identidade isolada; não altera permissões, não usa `chmod`, não copia binários, não publica Release e não toca na Build70 ou em dados do usuário.

O parser offline passa a tratar as duas linhas como resultado separado; nenhum desfecho marca `installer_authorized`, `direct_appinst_execution_verified` ou `installation_performed` como verdadeiro. Testes sintéticos cobrem o relatório físico exato da Build4, sucessos e falhas da Build5, estados contraditórios e tentativas de acrescentar autorização falsa.

**Dependências:** checar sucesso do workflow `appinst-direct-test.yml` da Build5, integridade do artifact de diagnóstico e depois solicitar teste físico **somente do primeiro botão**, sem usar `appinst --help`. `main`, PR Draft, `liveInstallationEnabled=false`, Build70, biblioteca e dados offline preservados.

### Build5 — CI aprovada, artifact de diagnóstico confirmado (21/11/2026 UTC)

- [GitHub Actions #44846854127](https://github.com/AugustoArbulu/MangaReader12/actions/runs/44846854127): **SUCCESS**. O job macOS compilou ARM64 com iOS mínimo 12.0, assinou ad hoc o aplicativo isolado, verificou o entitlement efetivo, executou regressões do parser e auditoria estática da distinção entre `WRSpawnChild`, self-spawn e caminho opcional `appinst --help`.
- Artifact `WebReader-Appinst-Direto-iOS12-TEST`, ID `14683820118`, incluía `WebReader-Appinst-Direto-iOS12-adhoc.ipa` (**18.723 bytes**) e `WebReader-Appinst-Direto-iOS12-adhoc.ipa.sha256`. SHA-256 verificado após download: `719bb054e279bdbc55c30067acfd5f5dc9bf4ce37b5eaf3b31fbc2b90ae6a92a`.
- Verificação independente do pacote ZIP: `CFBundleVersion=5`, `MinimumOSVersion=12.0`, `CFBundleIdentifier=com.example.WebReaderAppinstDirectProbe`; executável principal e `WRSpawnChild` contêm modo Unix `0755` **no ZIP**, o que não demonstra permissões pós-instalação.
- `main` e o WebReader Build70 real não foram alterados. Próximo teste permitido no iPad: instalar apenas a IPA diagnóstica Build5 e tocar **1. Testar processo local (sem appinst)**; copiar o relatório completo, inclusive `SELF_MAIN` e `SPAWN_SELF`. Não clicar no segundo botão. Mesmo resultado positivo de self-spawn não autoriza execução do AppInst ou instalação de IPA.

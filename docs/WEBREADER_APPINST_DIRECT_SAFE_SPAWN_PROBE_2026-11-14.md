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

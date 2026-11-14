# WebReader Build70 — Fase DA: evidência durável de checagem pendente e quarentena conservadora

**Data:** 10/11/2026. **Branch de trabalho:** `feat/chimera-updater-phase1-protocol-audit`. **PR #90 Draft**, sem merge na `main`. A Build70 instalada no iPad iOS12.5.8, biblioteca, backups, favoritos e capítulos offline continuam sem alterações.

## Por que a CZ não resolve reinícios

O laboratório CZ juntou os componentes CX/CY com uma thread Python sintética, garantindo que um trabalhador só recebe ACK quando terminou de fato (`join`). Mas uma nova instância criada sem diário de estado poderia iniciar uma nova checagem enquanto a instância anterior ou outro processo ainda existisse. O sinal `recovery_required` do harness é apenas injetado pelo teste e se perde quando o processo fecha.

A Fase DA produz **um primeiro modelo nativo de evidência de trabalho pendente no disco**, propositalmente mais conservador que um produto final. Ele não instala, não baixa, não conecta a GitHub nem inicia qualquer worker.

## Implementação

Arquivos:
- `ci/build70_da_crash_quarantine.h` e `ci/build70_da_crash_quarantine.c`: laboratório nativo C/POSIX com mutex, `openat`, `O_NOFOLLOW`, `O_CREAT|O_EXCL`, `flock(LOCK_EX|LOCK_NB)` e `fsync`.
- `ci/test_build70_da_crash_quarantine.py`: testes host compilando biblioteca nativa descartável, simulando encerramento abrupto de processo e colisões entre threads/processos, além de condições adversariais de sistema de arquivos.
- `.github/workflows/chimera-build70-phase-da-crash-evidence.yml`: jobs Linux/macOS mais compilação **somente objeto ARM64/iOS12** sob Xcode16.4.

O harness fornece um **diretório previamente criado**, pertencente ao usuário do job, com modo **exato 0700**. O código C abre o diretório por FD com `O_DIRECTORY|O_NOFOLLOW`, cria/abre o nome fixo `wr-da-review.lock` em modo 0600 e exige arquivo regular de um único link, sem escrita de grupo/outros e tamanho zero. Um `flock` não bloqueante impede duas instâncias cooperantes de usar o mesmo lock enquanto uma estiver viva.

Uma notificação válida contém **exatamente 7 bytes `WRCHK2\n`**. A primeira faz criação exclusiva de `wr-da-check.pending` com conteúdo fixo `PENDING-READ-ONLY-CHECK\n`, usando `openat` no diretório já aberto, gravação completa, `fsync` do FD e do diretório, e só então retorna **`WR_DA_MARKED`**. A marca é escrita **antes** de o futuro chamador poder iniciar uma tarefa. Se falhar qualquer etapa, a chamada rejeita; uma marca parcialmente criada não é apagada e torna a abertura seguinte conservadoramente bloqueada.

Se qualquer entrada existir com o nome de marcador (arquivo regular, vazio, parcial, symlink ou diretório), uma nova instância **entra em quarentena e não aceita solicitações**. A própria instância também só marca **uma** vez. Não existe função para remover, trocar, reconhecer conclusão, ignorar, reiniciar ou reconciliar a marca: **a Fase DA aceita ficar permanentemente bloqueada após a primeira execução**. Isso é intencional para testar a direção fail-closed sem inventar uma autoridade de reconciliação.

## Cobertura e limitações

Os testes adversariais exercitam: primeira marca; reabertura após fechamento normal; subprocesso que chama `os._exit(0)` após criar marcador e libera lock ao morrer; segundo handle recebe BUSY durante lock; 128 solicitações concorrentes à mesma estrutura produzem uma única marca; frames `WRINST1`/URLs/consentimento rejeitados sem consumir o marcador; diretórios 0755/0777, symlinks, hardlinks no lock, lock alterado, marcador pré-existente vazio/malformado e argumentos nulos.

**Contraexemplo obrigatório:** o mesmo UID, ou root, pode **apagar o arquivo `wr-da-check.pending`** e provocar uma abertura que parece limpa. A DA **não é** uma proteção antirrollback, tampouco isola o journal do app cliente. `flock` é uma trava consultiva entre processos cooperantes e não impede quem tem acesso ao diretório de trocar ou editar arquivos. Nem `0700` nem `0600` provam uma conta isolada no iOS12. A validação não percorre nem autentica todos os ancestrais do caminho, e o FD do diretório pode apontar para uma hierarquia que outro processo com privilégio também altera.

Um `fsync` bem-sucedido no host é uma boa condição de durabilidade de gravação, mas a CI **não simula perda de energia nem comprova garantias do filesystem APFS/jailbreak iOS12**. O encerramento abrupto testado acontece após retorno de uma gravação sincronizada. Não chamar a Fase DA de serviço persistente seguro, proteção contra corrupção real ou prova de ausência de trabalho antigo.

### Campos de autoridade sempre negados

`WR_DA_Receipt` mantém permanentemente **false** para `caller_authenticated`, `publisher_verified`, `editor_pin_provisioned`, `ipad_uid_isolation_proven`, `protected_against_same_uid_tamper`, `can_reconcile_pending_install`, `installation_authorized` e `installation_performed`.

Nenhum código de instalação, canal de rede, auto-download ou daemon foi adicionado. O diretório de laboratório não é nem deve ser compartilhado com um listener que aceite caminho do cliente; não existe interpretação de `WRCHK2\n` como consentimento.


### Reforço de testes: flock entre processos e troca do próprio lock

Foram adicionados dois casos adicionais, elevando a bateria para **23 testes**: (1) um subprocesso independente tenta abrir o mesmo journal enquanto outro processo mantém o lock, devendo receber **BUSY**; (2) o mesmo usuário do teste **desvincula o nome do arquivo de lock** enquanto o primeiro FD continua aberto e preso. Um novo processo/handle pode então criar **outro inode** com o mesmo nome e adquirir um lock independente. O teste exige que isso seja observado como **vulnerabilidade de custódia da pasta** e nunca seja convertido em permissão de instalação.

Portanto, não basta manter `flock` entre processos cooperantes: a autoridade que mantém a pasta/nomes deve estar fora do alcance de escrita do aplicativo. Ainda não existe essa prova para o WebReader/iOS12; esta fase preserva todos os campos de autenticação/isolamento em `false`.

## Decisão para a próxima fase

Depois dos testes DA, será necessário **projetar um journal com custódia real do helper**, protegido contra a escrita do próprio aplicativo e contra reinícios/rollback, mais uma reconciliação segura baseada em comprovação independente de que todos os workers anteriores morreram, com identidade do processo nativo e estados de release/editor verificados. Não conectar essa API de laboratório ao WebReader como autorização de instalação ou como mecanismo de resgate de quarentena. Também seguem independentes os bloqueios de chave editorial de produção, pin público, custódia exata da IPA até o serviço Apple e consentimento proprietário local.

**Hard stops preservados:** `WebReaderAppinstSocket.liveInstallationEnabled=false`; `WebReaderUpdateChannel.productionPublicKeyX963=nil`; `WebReaderProductionPublisherTrust.independentlyProvisionedSPKISHA256=nil`. PR #90 Draft, `main` intacta. Nenhuma Release, nova IPA/DEB, Build71 ou modificação do iPad.

**CI:** preencher somente após verificar os resultados dos três jobs; compilação ARM64/iOS12 não é execução no dispositivo.

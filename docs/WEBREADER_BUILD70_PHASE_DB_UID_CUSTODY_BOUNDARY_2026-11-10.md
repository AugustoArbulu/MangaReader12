# WebReader Build70 — Fase DB: barreira real entre UIDs no host, não no iOS12

Data: 10/11/2026. Repositório: `AugustoArbulu/MangaReader12`; branch `feat/chimera-updater-phase1-protocol-audit`, PR #90 Draft. **Não** alterar `main`, Releases, Build70 instalada no iPad, favoritos, biblioteca ou offline.

## Antecedente crítico — correção DA

A validação anterior da DA **não estava verde**: Ubuntu passara, mas a compilação macOS e o cross-compile iOS12 falharam porque o código ativava `_POSIX_C_SOURCE` sem expor as extensões BSD/Darwin `O_NOFOLLOW` e `flock` nos headers da Apple. A correção no commit `96ae645d66f03b5ec956f801ebe99a9fb7509d9f` ativa `_DARWIN_C_SOURCE` somente em Apple e preserva `_POSIX_C_SOURCE` em Linux. Nova CI DA **SUCCESS 3/3**: https://github.com/AugustoArbulu/MangaReader12/actions/runs/42898477695. A correção é só de compatibilidade de compilação; não adicionou privilégios ou instalação.

## Problema DB

DA escreve `wr-da-check.pending` antes de qualquer checagem sintética e entra em quarentena após reinício se o marcador existe. Mas DA mostrou dois contraexemplos: um processo com **mesmo UID** pode apagar o marcador, e pode desvincular o **arquivo de lock** e criar outro lock com o mesmo nome. O sistema não tem segurança de recuperação se a aplicação cliente também consegue escrever no diretório do futuro helper.

A Fase DB verifica, em **host Linux com dois UIDs reais**, se as permissões POSIX de um diretório 0700 impedem um cliente de UID diferente de abrir, ler, sobrescrever ou apagar os arquivos sintéticos do journal. É uma prova limitada do sistema operacional Linux, não uma prova de entitlements do iOS12 ou do Chimera.

## Implementação

`ci/build70_db_host_uid_boundary.py` é um *probe de laboratório deliberadamente limitado a fixtures sintéticos* sob diretório pai absoluto com prefixo `wr-db-fixture-`, uma folha fixa `wr-db-helper-private` e nomes fixos `wr-da-check.pending`, `wr-da-review.lock`, `wr-db-synthetic-created.fake`. O pai precisa ter modo 0755. O probe coleta UID real do processo com `os.geteuid()` e UID real do diretório com `stat`, sem confiar em dados do suposto cliente.

O laboratório testa seis operações POSIX: abrir o diretório, abrir o marcador para leitura, abrir para escrita, apagar marcador, apagar lock e criar arquivo novo. Se uma operação for autorizada, **ela pode modificar apenas o fixture descartável** criado pelo próprio teste; nunca executá-lo em dados reais, fora de CI, ou como um serviço privilegiado. O resultado `DBHostProbe` registra UID, modo e recusas efetivas, mas todos os campos iOS12/editor/consentimento/instalação ficam permanentemente `false`.

`ci/test_build70_db_host_uid_boundary.py` testa:
- Linux Ubuntu: subprocesso como usuário real `nobody` via `sudo -n -u nobody` contra diretório sintético 0700 pertencente ao UID do runner; todas as operações precisam ser negadas, sem modificar marcador ou lock. A CI falha, **não pula**, se `sudo` não estiver funcional no runner Linux.
- Linux Ubuntu: o mesmo usuário `nobody` diante de pasta `0777` consegue apagar marcadores e lock, **mesmo quando os arquivos estão em modo 0600**. Isto mostra que proteção de escrita do diretório é independente das permissões do arquivo.
- Linux/macOS: o UID proprietário consegue apagar/modificar seus próprios dados 0700/0600; se o app e helper forem o mesmo UID, a proteção não existe contra a aplicação cliente.
- Ambos: rejeição de path arbitrário, symlinks, pai em modo incorreto, campos de autoridade sempre falsos e auditoria de ausência de processos/instaladores no probe.

Workflow `.github/workflows/chimera-build70-phase-db-host-uid-custody.yml`: Linux executa todos os testes, inclusive os dois de UIDs reais; macOS executa apenas os controles negativos do mesmo UID (os testes `nobody` são explicitamente Linux-only e não podem ser descritos como validação física macOS/iOS12). A CI não distribui executável, IPA ou DEB. Nenhuma operação é executada no iPad.

## Resultado NÃO autorizado a provar

Um resultado de `sudo -u nobody` negado demonstra que o **kernel Linux** impôs permissões POSIX na configuração exata do fixture host. **Não** prova que o WebReader iOS12 usa UID diferente do futuro helper, que o helper terá diretório protegido por conta independente ou sandbox apropriado, que os ancestrais são não mutáveis, que o dispositivo não é root, ou que a entidade Apple MobileInstallation consumirá bytes verificáveis. `root` ainda pode agir sobre ambos os diretórios; a queda do helper, rollback/restore de backups e rotinas jailbreak podem alterar os estados.

Para desenvolvimento produtivo, é preciso identificar de modo seguro e read-only a identidade real do app e de qualquer serviço proposto, com políticas de entitlements, ownership de ancestral/arquivo e o que a aplicação ainda consegue alterar. **Não** fornecer ao processo do WebReader nenhuma API que aceite URL, caminho, digest, instalação ou reconciliação do journal como argumento de cliente. `WRCHK2\n` permanece um aviso não autenticado, sem instalação.

## Gates independentes ainda faltantes

A chave editorial de produção P-256 e o pin independentemente verificado permanecem ausentes. Também faltam custódia de IPA contra mutação até o instalador, consentimento local de proprietário via canal confiável, diário anti-replay protegido e recuperação da biblioteca/offline. Os testes host DB não satisfazem esses gates.

**Travas de produção inalteradas:** `WebReaderAppinstSocket.liveInstallationEnabled=false`; `WebReaderUpdateChannel.productionPublicKeyX963=nil`; `WebReaderProductionPublisherTrust.independentlyProvisionedSPKISHA256=nil`. PR #90 em Draft. `main`, Build70 física e Releases intactos. Nenhum appinst executado, nenhum IPA/DEB gerado, nenhum novo teste físico solicitado.

**Resultado CI DB:** atualizar somente após confirmar os logs finais dos jobs Linux/macOS. Não confundir testes host com iOS12.

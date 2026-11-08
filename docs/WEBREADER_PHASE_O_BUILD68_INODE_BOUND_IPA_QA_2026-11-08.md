# WebReader — Fase O | Cópia de IPA vinculada a inode e QA sem privilégio (2026-11-08)

**Repositório privado:** AugustoArbulu/MangaReader12  
**Branch de trabalho:** feat/chimera-updater-phase1-protocol-audit  
**Pull request:** https://github.com/AugustoArbulu/MangaReader12/pull/90 — Draft, sem merge na main  
**Commit verificado no CI:** b90fe9b65cfb05b47e85d215e3631011764472f9  
**CI final verde:** https://github.com/AugustoArbulu/MangaReader12/actions/runs/42447628219  
**Build atualmente aprovada em iPad real:** 66. **Build 67:** IPA de QA já entregue, ainda sem aprovação física documentada. **Build 68:** apenas código experimental e testes, sem IPA nova nesta fase.

## 1. Decisão de arquitetura

A Build 66 é a referência física confirmada pelo proprietário em iOS 12.5.8 com Chimera: instalação manual, biblioteca intacta e capítulos anteriormente baixados abrem offline.

Build 67 introduziu a conferência de IPA local de Arquivos/Filza por Build/SHA-256 informado e auditoria ZIP; a Fase N reforçou o auditor nativo com abertura O_NOFOLLOW, fstat, segundo SHA-256, verificação do mesmo descritor e reserva de espaço.

A Fase O resolve outro problema de TOCTOU: uma cópia local criada por FileManager.copyItem baseada em pathname pode depender de um arquivo ou diretório que mudam entre a checagem e a cópia. Da mesma maneira, a exclusão ou compartilhamento de um caminho previamente conferido pode atuar sobre outro arquivo (inclusive uma substituição byte-a-byte idêntica). **O mesmo SHA-256 não garante que o inode ainda é aquele originalmente conferido.**

A solução é continuar no **sandbox não privilegiado do WebReader**: jamais transformar a auditoria de IPA numa autorização para appinst, executar comandos root ou usar o diagnóstico LOCAL_PEERTOKEN para autenticar instaladores. Não instalar, não migrar biblioteca, não excluir capítulos.

## 2. Implementação no código Swift

Arquivo: MangaReader12/Core/WebReaderIPAStager.swift, tipo WebReaderLocalIPAReviewer.

### Importação de arquivos externos

1. Recebe apenas URL file:// com extensão .ipa, Build esperado estritamente maior que o instalado, SHA-256 com 64 caracteres e limite máximo de 512 MiB.
2. Abre a **origem uma única vez**, usando Darwin.open com O_RDONLY|O_CLOEXEC|O_NOFOLLOW|O_NONBLOCK. fstat confirma arquivo regular, tipo, tamanho e identidade.
3. Cria (se necessário) e abre o diretório restrito Application Support/WebReaderLocalQAImports. O diretório usa O_DIRECTORY|O_NOFOLLOW e é amarrado a um file descriptor: um link simbólico como componente final não é seguido.
4. Calcula reserva adicional de 16 a 64 MiB de espaço livre antes de começar.
5. Cria arquivo novo usando Darwin.openat no FD desse diretório com O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW, nome com Build+UUID e permissões 0600. **Nunca substitui um arquivo já existente**.
6. Copia em blocos de 64 KiB com read/write nos FDs abertos, tratamento de EINTR, checagem de tamanho exato e fsync na cópia terminada.
7. Compara fstat da origem antes/depois da cópia (dev, inode, tamanho, mtime/ctime) e fstat do destino; falhas limpam exclusivamente o novo arquivo com unlinkat no descritor original de diretório.
8. Usa WebReaderNativeIPAAuditor.inspect na cópia, conferindo SHA-256, ZIP, Info.plist, Bundle ID, Build e iOS mínimo. Verifica por fstatat que o caminho ainda aponta para o **mesmo inode de destino** depois da auditoria.
9. Produz WebReaderLocalIPAReview com o SHA, Build, tamanho e novos campos imutáveis stagingDevice/stagingInode, para poder recusar a substituição da cópia posteriormente.

### Compartilhamento e descarte

- Antes do UIActivityViewController, recheck abre a cópia com O_NOFOLLOW, confere dev+inode contra o recibo, executa novamente a auditoria nativa do conteúdo, confere metadados no FD e compara a identidade do pathname atual via lstat. Uma substituição por outro arquivo byte-a-byte igual deve ser **recusada**.
- discard valida que o nome é exatamente Build+UUID+.ipa, que está dentro da pasta de QA, abre o diretório com O_DIRECTORY|O_NOFOLLOW, usa fstatat com AT_SYMLINK_NOFOLLOW e só executa unlinkat se **dev+inode** coincidirem com o recibo. Uma cópia estranha colocada no mesmo caminho não deve ser apagada.
- O original escolhido pelo usuário no Filza/Arquivos jamais é movido ou eliminado por esses comandos. A operação não toca em arquivos de biblioteca, backup, banco ou capítulos.

### Modelo de confiança

- O recibo da cópia confirma a integridade dos bytes e a continuidade da identidade local do arquivo, **não a autenticidade de quem publicou a IPA**.
- Os campos publisherAuthenticated=false, installationAuthorized=false e installationPerformed=false permanecem invariáveis.
- Em apps com jailbreak, outros processos com acesso ao sandbox ainda podem competir pela modificação/substituição **depois** que recheck retorna e antes que outro aplicativo consuma o arquivo. Para instalar, um futuro executante deve revalidar os bytes que realmente abriu, com assinatura editorial independente, consentimento explícito e proteção anti-replay/rollback.
- A checagem antes de unlinkat não é uma transação atômica universal para um diretório gravável por adversários; o helper privilegiado futuro não deve herdar essa política de exclusão sem revisão dedicada.
- LOCAL_PEERTOKEN ficou UNAVAILABLE no diagnóstico do iPad com Chimera; nunca atribuir autoria criptográfica de uma mensagem a um token amostrado no socket em um stream multiplexado.
- WebReaderAppinstSocket.liveInstallationEnabled = false e WebReaderUpdateChannel.productionPublicKeyX963 = nil continuam bloqueados em produção.

## 3. Testes novos e regressões

**ci/test_native_webreader_local_ipa_review.py:**

- Rejeita IPA de Build antiga, bundle incorreto, iOS incompatível, hash errado, extensão errada, arquivo inexistente, link simbólico, fonte FIFO sem escritor e arquivo acima de 512 MiB.
- Verifica a reserva de armazenamento, permissões 0600 e que a pasta de QA não é um symlink para pasta simulada de Library.
- Confere uma importação de fixture ZIP válida e seu recheck; altera os bytes da cópia depois de aprovado e exige falha.
- Substitui uma cópia local por link simbólico; discard não segue o link nem apaga a origem.
- Renomeia a pasta de QA e coloca no caminho antigo um symlink apontando para pasta simulada de biblioteca, com arquivo de nome coincidente: discard não apaga o arquivo da biblioteca; após restaurar a pasta legítima, o descarte seguro funciona.
- **Novo teste essencial:** troca a cópia conferida por uma segunda cópia com os mesmos bytes e SHA, porém diferente inode. recheck e discard são recusados. Restaurando o inode original, a rechecagem e o descarte voltam a funcionar.
- Total indicado pela suíte Swift: **19 casos negativos** mais verificações positivas de cópia, compartilhamento read-only, recusa de mutações e limpeza; sem appinst, sem conexão com Comix/GitHub e sem instalação.

**ci/test_build68_native_audit_contract.py:**

- Agora 18 testes estáticos de segurança da Fase N+O: FD único, O_NOFOLLOW, O_NONBLOCK para FIFO, O_EXCL/openat, fstat, read/write limitados, EINTR, fsync, segunda checagem do SHA, dev+inode do recibo, recheck de pathname e unlinkat restrito.
- Confirma ausência de credenciais, root e instalação automática e que os workflows anteriores de QA das Builds 66/67 estão congelados.

**ci/test_build67_local_ipa_screen.py:** 14 testes, atualizados para exigir criação por descritor e limpeza restrita, além da seleção explícita pelo usuário e da interface de SHA.

## 4. Execução final verificada no GitHub Actions

Workflow independente, para não depender da fila/cancelamento de jobs antigos:
**WebReader Phase O — Inode-bound QA Transfer + iOS12 Full Compile**
https://github.com/AugustoArbulu/MangaReader12/actions/runs/42447628219

- **STATUS FINAL: SUCCESS — dois jobs concluídos com sucesso** no commit b90fe9b65cfb05b47e85d215e3631011764472f9.
- Job Linux: **18 + 14 = 32 testes** de contrato/segurança aprovados, além das regressões de UI, biblioteca e compatibilidade offline previstas no job.
- macOS: todos os testes Swift reais de auditoria nativa, importação local com **19 casos negativos**, staging de download simulado, verificação de releases/manifestos e recusa de appinst aprovados.
- **Debug completo ARM64 para iOS 12 — BUILD SUCCEEDED.**
- **Release completo ARM64 para iOS 12 — BUILD SUCCEEDED.**
- Verificação da identidade padrão do aplicativo e das travas de instalação sem autorização concluída.
- **Nenhum IPA executável foi enviado como artefato**, nenhum GitHub Release foi criado, nenhum dispositivo físico foi usado e nenhuma atualização automática foi realizada.

Alguns jobs do workflow anterior Build68 foram substituídos/cancelados durante revisões consecutivas. O workflow independente acima registra o estado final desta fase, e não as execuções interrompidas.

## 5. Estado do projeto e próximos marcos

A fase concluiu mudanças de código, documentação, QA estática, QA nativa macOS e compilação iOS12, sem alterar a main. PR #90 permanece Draft.

**Não dizer que Build68 foi aprovada no iPad**: ela ainda não foi distribuída. A Build67 já foi disponibilizada ao usuário, mas falta confirmação física; Build66 continua sendo a última versão com biblioteca/offline aprovados.

Próximas linhas de trabalho:
1. Com confirmação do proprietário, validar primeiro Build67 sobre Build66 sem desinstalar, depois biblioteca e offline; exportar backup para outro dispositivo antes de trocar o aplicativo.
2. Para uma futura IPA Build68, empacotar a versão exata do código testado com ID original, SHA-256 verificado e assinatura ad hoc apenas como compatibilidade; publicar só como QA privada manual se o usuário desejar.
3. Trabalhar em UX do gerenciamento local: permitir revisar espaço usado e descartar somente cópias antigas do módulo, sem tocar Library/Downloads; não oferecer um botão que execute instalação privilegiada.
4. Separadamente, planejar a distribuição com manifesto assinado por chave editorial de produção cuja custódia seja estabelecida independentemente, autorização robusta do helper compatível com Chimera/iOS12, revalidação de bytes pelo executante, consentimento e proteção contra rollback/replay.

**Resultado principal:** a cópia de IPA e seu recibo são mais resistentes a troca de caminhos e arquivos, mas continuam **apenas suporte ao QA manual não privilegiado**.

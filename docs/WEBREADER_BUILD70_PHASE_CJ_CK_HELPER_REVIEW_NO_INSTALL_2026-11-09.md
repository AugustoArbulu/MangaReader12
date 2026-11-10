# WebReader Build70 — Fases CJ–CK: bloqueio do CLI legado e cópia de IPA somente para revisão

**Data:** 09/11/2026, horário de São Paulo. **Branch experimental:** `feat/chimera-updater-phase1-protocol-audit`, PR #90 Draft. **Base física:** Build70 reportada como funcional no iPad iOS12.5.8. `main` e o app instalado seguem intocados.

## Diagnóstico encontrado em CJ — risco de TOCTOU

O antigo `ci/webreader_appinst_bridge.c` trazia **dois caminhos que podiam invocar instalador**: o comando de terminal `install-confirmed <IPA_PATH> <SHA256> I-CONFIRM-INSTALL` **e o opcode de socket UNIX `WRINST1` no modo `serve-once`**. Embora nenhum fosse chamado pela UI do WebReader, ambos admitiam dados vindos de caminho mutável, verificavam SHA e **fechavam** o descritor antes de passar **o pathname original** ao `posix_spawn(/usr/bin/appinst)`. Entre auditoria e instalador, outro processo com permissão sobre a pasta poderia trocar os bytes. O check de mesmo UID no socket, o nome de pasta e a frase fixa não comprovam identidade de processo, assinatura editorial, consentimento no helper nem autorização one-shot.

**Alteração:** o executável C padrão agora se limita a `selftest`, `inspect` e `serve-once` (PING/negação). O comando `install-confirmed` retorna `INSTALL_DISABLED` sem abrir a IPA ou iniciar instalador. **O socket também recusa `WRINST1` com `WRFAIL1` até quando o peer tem UID igual**; apenas `WRPING1` recebe `WRPONG1`. Nem o caminho real `/usr/bin/appinst`, nem a confirmação estática, nem um símbolo externo `posix_spawn` devem aparecer no binário padrão. A implementação antiga é compilada **somente** no fixture macOS explicitamente optado `WEBREADER_FAKE_APPINST_QA`, com root sintético e comando fictício controlado pela CI. O compilador nega a opção no SDK iOS via `TARGET_OS_IPHONE`.

**Isso NÃO altera a ferramenta `appinst` já instalada pelo proprietário** ou o Filza e não revoga o procedimento de instalação manual que funcionou nas Builds 69–70. A alteração afeta apenas o **código-fonte futuro do bridge próprio**. O PING-only permanece separado e incapaz de instalar.

### Cobertura CI CJ

- `ci/test_webreader_appinst_bridge.py` compila duas versões no macOS: read-only padrão e a opção de laboratório fake. A padrão é examinada com `nm -u` para garantir ausência de `posix_spawn`, e por bytes para garantir ausência de texto `/usr/bin/appinst` e frase de consentimento. `inspect` funciona, mas `install-confirmed` é negado com arquivo realmente presente, SHA correto e frase correta.
- O fake exercita o antigo caso positivo, erros, troca de arquivo, symlink, hardlink e exit code da ferramenta falsa; nunca instala um app real.
- O teste de socket cria um listener UNIX real como processo separado, confirma PING positivo, rejeição de `WRINST1` e encerramento sem executar a ferramenta falsa; o código-fonte mantém o antigo protocolo somente dentro do fixture macOS explicitamente optado.
- Macros malformadas (sem diretório ou fake tool) são recusadas na compilação. `ci/test_build70_chimera_unsafe_cli_lock.py` exige o mesmo contrato estaticamente na CI Linux.

## CK — laboratório de cópia por descritores, somente revisão

`ci/webreader_helper_review_snapshot.py` demonstra como produzir uma segunda cópia de **revisão**, sem reabrir o arquivo de origem por nome depois de iniciar a leitura:

- FD de origem com `O_NOFOLLOW | O_CLOEXEC | O_NONBLOCK`; `fstat` validando UID, arquivo regular, um link, limites, tamanho e permissões.
- Diretório pré-existente 0700 do usuário aberto com `O_DIRECTORY | O_NOFOLLOW`. Cópia em nome derivado da Build e do SHA com `O_EXCL`, impossível sobrescrever normalmente.
- SHA-256 calculado durante a leitura; verifica tamanho, identidade inode, datas de origem e filename antes/depois. Reabre a **cópia** para conferência de hash independente, reduz permissões da cópia para 0400, e chama `fsync` no descritor e diretório.
- Em falhas após a criação, deixa tombstone parcial no diretório controlado para evitar retry silencioso com o mesmo nome; nunca remove uma entidade por pathname após perder identidade.
- Recibo imutável `ReviewSnapshotReceipt` declara todos os fatos de autorização como `false`, inclusive assinatura editorial, imutabilidade do handle, autenticação do peer e instalação.

`ci/test_webreader_helper_review_snapshot.py` verifica cópia correta, integridade da origem, não sobrescrita, hashes/tamanhos/Build inválidos, hardlinks, symlinks, pastas permissivas, alterações durante a cópia e substituição do nome original. Nenhuma IPA válida é construída; dados são sintéticos e **nunca** instalados.

### Limitações de segurança explicitamente não resolvidas

**0400 não é arquivo imutável.** O mesmo proprietário pode `chmod` e reescrever; root também. A pasta de destino no laboratório não tem garantias sobre todos os ancestrais e sua origem não equivale a um diretório privado de um helper de sistema. O arquivo transferido ainda seria um **pathname mutável** se `appinst` o abrisse depois. A cópia demonstra apenas propriedades verificáveis dos bytes **neste momento**, não elimina por si o TOCTOU do processo instalador.

As cinco condições ainda obrigatórias, antes de instalar diretamente:
1. Chave privada editorial real guardada fora do GitHub e do app + root público/pin aprovado independentemente na próxima IPA, com QA física.
2. Canal GitHub Release público e manifesto v2 assinado, com readback imutável real e hash verificado.
3. Peer autenticado **diretamente sobre a conexão** no iOS12/Chimera, com verificação de assinatura/código do binário do WebReader e defesa contra encaminhamento de FD.
4. Uma mesma cópia efetivamente imutável (ou FD verificado e preservado) analisada pelo helper e consumida sem troca pelo instalador, com validação nativa de identidade/code seal.
5. Estado durável de anti-replay/anti-rollback e consentimento real e individual coletado no helper, não uma flag ou frase enviada pelo app.

**Estado atual:** `WebReaderAppinstSocket.liveInstallationEnabled = false`; nem a UI nem esta fase chamam instalador. Nenhuma produção publicada e nenhuma nova IPA Build71 gerada. A Build70 física permanece intacta; biblioteca, favoritos, capítulos offline, backups e leitura não sofreram alterações.

**CI AC–CK:** [execução](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42731621679). Confirmar resultado antes de marcar a fase validada.

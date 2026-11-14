# WebReader — Fase CL: diagnóstico físico opcional de executáveis assinados no iOS 12/Chimera

**Registro:** 09–10/11/2026. **Branch:** `feat/chimera-updater-phase1-protocol-audit`; PR #90 Draft. **Baseline física preservada:** WebReader Build70 aprovado pelo proprietário no iPad iOS12.5.8.

## Por que esta fase existe

A Fase CK eliminou os dois comandos inseguros que podiam chamar `appinst` a partir do bridge padrão, inclusive `WRINST1` no socket. A CI AC–CK foi aprovada. Os estudos antigos G/H/I tinham verificado observações de `LOCAL_PEERTOKEN` e `csops_audittoken` com clientes distintos **no macOS**, mas nunca no próprio iPad com Chimera. Não devemos extrapolar resultados macOS para um iOS12 com sandbox e jailbreak.

Esta fase **não** tenta instalar. Cria uma prova física controlada e opcional com **três binários executáveis separados**, todos assinados ad hoc para ARM64 e deployment iOS12, para descobrir se o sistema permite vincular *um socket AF_UNIX aceito* ao CDHash de um executável diferente do servidor.

## Entrega criada

`ci/package_chimera_signed_peer_cl.py` produz um DEB opcional `WebReader-Chimera-PhaseCL-SignedPeer-iOS12.deb` somente a partir de binários que a CI compilou e assinou separadamente. O pacote possui **somente**:

- `/usr/local/bin/webreader-peercl-server`: listener AF_UNIX one-shot e inspeção OS kernel `LOCAL_PEERTOKEN` + `csops_audittoken(CS_OPS_CDHASH)`.
- `/usr/local/bin/webreader-peercl-allowed` e `/usr/local/bin/webreader-peercl-foreign`: dois clientes independentes, com `CodeDirectory`s e CDHashes distintos.
- `/usr/local/bin/webreader-peercl-report`: shell POSIX *sob demanda*, sem parâmetros externos, que cria diretório curto e privado em `/tmp`, coordena três sessões com sockets isolados, sanitiza resultados, apaga arquivos de teste e encerra. Rejeita execução como root.

Os dois CDHashes esperados são gerados por `codesign -d --verbose=4` **dos executáveis já assinados**, e são incorporados ao script apenas como **referências do laboratório**. O resultado não prova identidade editorial e não permite atualizar qualquer aplicativo.

### Três observações e interpretação

| Observação | Executor real | Referência no servidor | Se o macOS for reproduzido no iOS12 |
|---|---|---|---|
| `a` | cliente allowed | CDHash allowed | `MATCH_ONLY_NO_AUTH` |
| `b` | cliente foreign | CDHash allowed | `MISMATCH_REJECTED` |
| `c` | cliente foreign | CDHash foreign | `MATCH_ONLY_NO_AUTH` |

O programa só envia `WRHELLO1`, lê `R` de volta e encerra. Os relatórios exibem apenas palavras de status; **não incluem UID, PID, audit token, hashes, caminhos privados nem identidade pessoal**. `FINAL_INSTALL_AUTHORIZATION=DENIED` está sempre presente.

O parser `ci/build71_cl_signed_peer_report.py` e seus testes `ci/test_build71_cl_signed_peer_report.py` exigem um relatório ASCII de exatamente 10 linhas, três observações a/b/c na ordem correta e `FINAL_INSTALL_AUTHORIZATION=DENIED`. Detectam manipulações de estados, duplicatas, campos de autorização injetados, outros caracteres e respostas que extrapolam limites. Mesmo a observação positiva retorna `webreader_process_authenticated=false`, `publisher_authenticated=false` e `install_authorized=false` — o texto é **um diagnóstico não confiável**, não uma credencial do kernel.

Mesmo com o padrão esperado nas três linhas, isso seria **somente evidência de compatibilidade de um laboratório de CLI**, e **não** a autenticação do aplicativo WebReader por um helper. O App WebReader pode não conseguir acessar o mesmo socket por sandbox, como ocorreu com as primeiras sondagens UNIX; TCP loopback funcionando não possui o mesmo vínculo de audit token. A prova da identidade de assinatura editorial real exige a chave pública/pin de propriedade do usuário e teste com o processo do próprio app.

### Compatibilidade e segurança

A CI usa `xcrun --sdk iphoneos clang -arch arm64 -miphoneos-version-min=12.0`, assina cada executável com `codesign -s -` + o entitlement mínimo `com.apple.private.security.no-container` do diagnóstico anterior, audita `LC_BUILD_VERSION`/versão mínima e proíbe `LC_DYLD_CHAINED_FIXUPS`. O auditador independente confere os três CodeDirectories, os hashes diferentes, a assinatura, entitlement e os conteúdos exatos do arquivo .deb.

O pacote **não inclui** `postinst`, `prerm`, `launchd`, serviço contínuo, binário privilegiado, comando de instalação, extensão ou aplicativo. Apenas Sileo/Filza instalaria o próprio pacote se o proprietário optar futuramente; instalar esse DEB é ação separada e **não ocorre pela CI**.

**GitHub Actions:** [Fase CL, primeira compilação aprovada](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42734601209): **SUCCESS 2/2**, com os 3 binários ARM64 assinados ad hoc e o DEB auditado. [CI final CL com parser de relatório adicional](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42734874273): **SUCCESS 2/2**. Artifacts opcionais CLI-only com três Mach-O arm64 assinados, `.deb` + SHA-256, até **24/11/2026**. O arquivo opcional fica nos **artifacts temporários** (14 dias); não há Release nem publicação de IPA para uso diário.

## Pacote compilado e segunda auditoria independente

A [CI final CL #42734874273](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42734874273) passou **SUCCESS 2/2**. O artifact temporário `WebReader-PhaseCL-ThreeSignedPeers-CLI-only-iOS12` contém o DEB e seu arquivo de hash, válido no GitHub Actions até 24/11/2026. Identificador do artifact: `13725764376`.

O arquivo foi recuperado e inspecionado novamente, independentemente da auditoria CI:

- `WebReader-Chimera-PhaseCL-SignedPeer-iOS12.deb`, **14.036 bytes**
- SHA-256: `7bd2571a9cc4d9b093ddac4963eb859273f5e41238433070c4421101f58ec6cb`
- O SHA corresponde **exatamente** à linha do arquivo `.deb.sha256`.
- Estrutura ar: somente `debian-binary`, `control.tar.gz`, `data.tar.gz`; controle tem só `./control` — sem `postinst`, `prerm`, `preinst` ou `postrm`. O `data.tar.gz` contém exclusivamente três executáveis ARM64 e o runner em `/usr/local/bin/`, com os diretórios-pai explícitos.
- Os binários têm cabeçalho Mach-O ARM64, não contêm `/usr/bin/appinst` nem `WRINST1`. Os dois CDHashes de cliente embutidos no runner são distintos, e o arquivo termina com a negação explícita de instalação.
- **Limite:** essa inspeção local dos bytes é complementar à verificação Apple `codesign` executada no macOS Actions, não a substitui. A integridade do pacote não prova que executará no Chimera físico.

Nenhum componente é instalado automaticamente quando se baixa o pacote, e a execução do comando não instala nenhuma IPA. Instalar o **próprio DEB** no sistema seria uma ação explícita do proprietário pelo gerenciador de pacotes.

## Fluxo de teste físico opcional e único (não requerido agora)

Se algum dia for relevante medir o iOS12 real, o proprietário pode transferir e instalar **somente o DEB previamente auditado**, usando o gerenciador do jailbreak, e executar **manualmente** em NewTerm 2, como usuário `mobile`:

O fluxo recomendado é transferir o DEB do Android/PC para o iPad usando o método de transferência já aprovado no Filza, abri-lo no Sileo, confirmar que o pacote se chama `com.example.webreader.peercl` e então executar o comando a seguir. **Não remover ou reinstalar o WebReader**; este laboratório é independente do app.

```sh
webreader-peercl-report
```

Se `id -u` for zero, o runner recusa. Não copiar hashes nem detalhes do socket; basta repassar as linhas `OBSERVATION_a/b/c`. Nenhuma Build nova do WebReader é necessária para executar esses binários externos. **Não exigir esse teste antes de concluir as demais tarefas de desenvolvimento.**

## Bloqueios intactos após CL

- Sem root público editorial provisionado em Build70 nem manifest production-v2/Release real.
- Sem autenticação verificada do processo WebReader conectado ao helper no iOS12/Chimera.
- Sem vínculo de cada requisição a *exatamente* os bytes IPA aceitos pelo instalador.
- Sem consentimento confiável, único e local no helper, ou ledger privilegiado persistente contra replay/rollback.
- `WebReaderAppinstSocket.liveInstallationEnabled = false` preservado.

**Nenhum conteúdo do iPad, biblioteca, favoritos, capítulos offline, backups ou progresso foi alterado; nenhuma nova IPA WebReader foi criada; `main` continua intocada.**

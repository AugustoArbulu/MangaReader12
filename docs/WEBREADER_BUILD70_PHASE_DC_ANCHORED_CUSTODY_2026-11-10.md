# WebReader Build70 — Fase DC: auditoria de linhagem de diretórios, isolamento de identidade e gates do helper iOS12

**Data:** 10/11/2026. **Branch:** `feat/chimera-updater-phase1-protocol-audit`. **PR #90 Draft**, sem merge na `main`. Build70 instalada no iPad iOS12.5.8, biblioteca, favoritos, capítulos offline, GitHub Releases e o appinst instalado não foram modificados.

## 1. Contexto DA/DB

A DA introduziu marcador persistente de quarentena para uma checagem sintética; seus ensaios revelaram que o mesmo UID pode apagar tanto o marcador quanto o lock de `flock` e abrir um novo inode de lock. A primeira versão DA falhou no macOS por esconder `O_NOFOLLOW`/`flock` com `_POSIX_C_SOURCE`; a correção por `_DARWIN_C_SOURCE` foi aprovada na CI https://github.com/AugustoArbulu/MangaReader12/actions/runs/42898477695, sem habilitar instalação.

A DB realizou um teste Linux real como usuário `nobody`: um diretório pertencente ao runner com modo 0700 bloqueia acessos do outro UID, mas um diretório 0777 deixa `nobody` apagar arquivos de modo 0600. A CI DB da implementação foi **SUCCESS 2/2**, https://github.com/AugustoArbulu/MangaReader12/actions/runs/42899594792: Linux 10 testes PASS, macOS 8 testes PASS e 2 intencionalmente ignorados por serem somente Linux. O resultado continua estritamente HOST e não comprova separação de entitlements/UID no iOS12.

## 2. A lacuna endereçada pela DC

Não basta conferir o modo do último arquivo de lock. Se algum dos **diretórios pais** for substituível pelo app, um arquivo privado no interior também poderá ser substituído. Não basta ver `getuid`: esse é o UID do *próprio processo*, não a autenticação de um cliente IPC. Tampouco basta passar o UID suposto do cliente por um argumento de função: um atacante poderia fornecer um UID fictício.

A DC fornece **dois artefatos de observação somente leitura**, sem ativar serviços:

- `ci/build70_dc_custody_lineage.h` e `ci/build70_dc_custody_lineage.c`: inspecionam a cadeia fixa `base/wr-dc-private/state/wr-da-review.lock` relativamente a descritores de diretórios. O argumento `base` é explicitamente um *anchor presumido confiável pelo harness*, não autenticado pelo inspector. `asserted_client_uid` é uma hipótese de laboratório, **não** um UID de peer verificado no kernel.
- `ci/build70_dc_self_credential_readonly.c`: utilitário nativo que imprime apenas `getuid()`, `geteuid()`, `getgid()`, `getegid()` do **seu próprio processo**, acompanhados de `DC_IPC_PEER_AUTHENTICATED=NO`, `DC_IOS12_HELPER_ISOLATION_PROVEN=NO` e `DC_INSTALLATION_AUTHORIZED=NO`. Compilar isso para iOS12 **não** quer dizer executá-lo no dispositivo nem descobrir a identidade do WebReader ou do helper que ainda não existe.

## 3. Contrato de inspeção

O auditor C exige que:
1. `base` seja um caminho absoluto de fixture, sem `..`, `.` como componente ou barra final; há limite de comprimento. `base` abre com `O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC`; **seus ancestrais não são auditados**.
2. `base`, `wr-dc-private` e `state` sejam diretórios de modo **exato 0700**, pertencentes ao UID efetivo do processo observador; os dois descendentes são abertos com `openat` e comparados com `fstatat(AT_SYMLINK_NOFOLLOW)`.
3. O lock tenha modo **exato 0600**, tamanho zero, seja arquivo regular, com apenas um hardlink, sob mesmo UID efetivo, e corresponda ao inode consultado pelo nome.
4. Se qualquer objeto ocupar o nome `wr-da-check.pending` — arquivo comum, parcial, vazio, symlink ou diretório — a observação retorna `WR_DC_QUARANTINED`. Não tenta ler, seguir, apagar ou reinterpretar esse objeto.
5. Se o lock e a cadeia do fixture estiverem conformes e nenhum marcador existir, retorna **`WR_DC_HOST_METADATA_REVIEWED`**, nunca algo semelhante a `authorized` ou `safe-to-install`.
6. Um `asserted_client_uid` igual ao UID do observador ou root é recusado. **Isso não autentica o valor fornecido**, e um cliente malicioso não deve sequer poder fornecer um UID em produção.

Não existe escrita, chmod, remoção, renomeação, socket, download, appinst, ação de `LSApplicationWorkspace` ou chamada instaladora.

O recibo `WR_DC_Receipt` permite reportar fatos limitados de metadados POSIX vistos no host, mas mantém explicitamente **false** para: `anchor_ancestry_independently_attested`, `real_ios12_process_identity_attested`, `app_write_access_denied_on_ios12`, `helper_entitlements_checked_on_ios12`, `immune_to_root_or_same_uid_mutation`, `protected_from_journal_rollback`, `publisher_identity_verified`, `owner_install_consent_verified`, `installation_authorized` e `installation_performed`.

## 4. Testes adversariais e limites

`ci/test_build70_dc_custody_lineage.py` compila um módulo nativo C temporário no runner para testar: diretórios 0700; modos permissivos de diretório/lock; symlinks de vault/state/lock e do marcador; hardlink de lock; nomes errados; cliente suposto do mesmo UID; marcador inválido/quarentena; arquivo de lock com bytes imprevistos; nenhuma mutação pela auditoria; e o **contraexemplo de que o mesmo UID pode remover marker/lock após uma inspeção e forjar uma inspeção limpa**. Outro caso troca o inode do lock após a observação. Os testes também destacam que um componente ancestral do anchor pode ser symlink, pois só os diretórios abertos via FDs do anchor são auditados.

Workflow `.github/workflows/chimera-build70-phase-dc-anchored-custody.yml`: Linux/macOS compilam e testam os mesmos casos; ambos executam no host o programa de identidade *própria* e verificam que não declara autoridade. macOS/Xcode16.4 compila apenas **dois objetos Mach-O ARM64/iOS12**, que não são publicados nem executados no iPad, e audita símbolos para impedir operações instaladoras.

## 5. Design de helper futuro — ainda não implementado

**Fronteiras separadas:**

| Fronteira | Requisito e prova faltante |
|---|---|
| Cliente WebReader | Só enviar `WRCHK2\n` com 7 bytes; nunca URL, IPA, SHA, chave, path, consentimento, PID/UID declarado ou comando de instalação |
| Superfície de IPC | O teste `LOCAL_PEERTOKEN` em iOS12 resultou `TOKEN_UNAVAILABLE AUTHORIZATION=DENIED`; não inferir peer confiável do mesmo UID, código ou HMAC do app |
| Helper de checagem | Identidade própria verificável no iPad e único serviço responsável por origem editorial fixa e quotas; idealmente sandbox/UID distinto e armazenamento protegido do cliente |
| Estado de recuperação | Diretório e ancestrais realmente não alteráveis pelo app, journal durável, proteção contra substituição de nome, rollback e procedimento de reconciliação baseado em verificação independente do término de workers |
| Editor da release | Chave de produção exclusiva do proprietário, fingerprint público conferido e manifesto v2 assinado; nunca usar trust artificial da CI |
| Entrega ao instalador | IPA com digest e code seal nativos conferidos e bytes protegidos até serem consumidos pelo serviço Apple, incluindo cópias internas |
| Consentimento | Autorização real de uso único no canal confiável do proprietário, independente do frame `WRCHK2\n`, antirreplay e rollback |
| Segurança operacional | Recuperação da biblioteca, favoritos/offline, logs mínimos, erros de rede e rollback de atualização falha |

**Decisão:** não converter `WR_DC_HOST_METADATA_REVIEWED` em permissão para baixar ou instalar. A próxima prova material deve vir de um helper iOS12 **somente leitura** que identifique UID, sandbox, entitlements, proprietários de diretórios e o isolamento real contra um cliente sem privilégios — sem tocar nas bibliotecas nem instalar pacote. Os valores impressos por um binário genérico só seriam evidência de identidade **daquele binário**, não de outro serviço.

## Estado de produção

A Build70 permanece a versão instalada e aprovada; PR #90 em rascunho e `main` intacta. `WebReaderAppinstSocket.liveInstallationEnabled=false`, `WebReaderUpdateChannel.productionPublicKeyX963=nil` e `WebReaderProductionPublisherTrust.independentlyProvisionedSPKISHA256=nil`. Nada de appinst, IPA, DEB, Release, nova Build71 ou teste físico é necessário nesta fase.

**CI DC:** preencher resultado somente após a execução final dos jobs. Não presumir autorização nem isolamento iOS12 com base em compilação.

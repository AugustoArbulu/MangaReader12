# WebReader Build70 — Fase DQ: inspeção opcional SOMENTE LEITURA do app instalado no iPad

**11/11/2026.** Branch `feat/chimera-updater-phase1-protocol-audit`, PR #90 Draft, `main` intacta. Build70 do iPad iOS12.5.8 e suas bibliotecas, favoritos, histórico e downloads offline **não foram acessados nem modificados por estes testes**. Sem IPA/DEB nova, Release ou instalação.

## Por que existe DQ

A Fase DP confirmou uma limitação concreta: o SDK iPhoneOS/Xcode16.4 usado pelo WebReader **não exporta** `SecTaskCreateFromSelf`, `SecTaskCopySigningIdentifier` ou `SecTaskCopyValueForEntitlement` ao Swift. A primeira tentativa falhou na compilação; foi removida por completo para manter a compatibilidade com iOS12, sem usar símbolos privados, hacks de `dlsym` nem publicar uma IPA. O app futuro só poderá informar Bundle ID/UID/GID; **não conseguirá atestar o `application-identifier` já assinado na Build70 do iPad**.

Uma nova instalação poderia ter Bundle ID idêntico e ainda diferir em entitlement ou code signature, correndo risco de não reaproveitar o contêiner. DQ prepara uma rota externa para coletar informações de **arquivos do aplicativo já instalado**, sem atualizar primeiro.

## O que foi implementado

`ci/build70_dq_installed_bundle_readonly.sh` é um script shell POSIX opcional e somente leitura para eventual execução humana via NewTerm/Filza no iPad com Chimera. **Não é implantado nem executado automaticamente.**

- O único argumento é o caminho **explícito** da pasta `MangaReader12.app` instalado, selecionado pelo proprietário no Filza. O script **não executa `find` nem varre** a lista de aplicativos. Aceita somente localização padrão de bundle iOS em `/var/containers/Bundle/Application/UUID/MangaReader12.app` ou suas variantes `/private`/`/var/mobile`, exigindo um componente UUID válido no formato.
- Não aceita paths relativos, intermediários `..`, executáveis ou plists ausentes, nem symlinks para o bundle, `Info.plist` ou `MangaReader12`. Não requer root, sudo, AppSync, appinst, modificação de entitlements, rede ou instalação de ferramenta.
- Detecta **somente se já existem** `plutil`, `ldid` e `awk` em caminhos de ferramentas explícitos; **não tenta instalá-los**. Usa `plutil -p` para ler do `Info.plist` apenas `CFBundleIdentifier` e `CFBundleVersion`; se `ldid` estiver disponível, `ldid -e` extrai **somente o texto do entitlement `application-identifier`** do Mach-O já instalado. Se a ferramenta ou o formato de saída for incompatível, responde `UNAVAILABLE` em vez de supor o valor histórico.
- Limita os valores expostos a caracteres ASCII permitidos e 256 bytes, não imprime caminhos do contêiner, não enumera documentos ou dados da biblioteca e não lê imagens offline. Os três campos são `BUNDLE_IDENTIFIER_TEXT`, `BUNDLE_VERSION_TEXT` e `APPLICATION_IDENTIFIER_ENTITLEMENT_TEXT`.
- `ldid -e` lê um blob de entitlement mas **não valida criptograficamente a assinatura do código**, nem autentica o publicador. Um relatório de shell pode ser forjado ou capturado de outro bundle. Por isso saem obrigatoriamente `CODE_SIGNATURE_CRYPTOGRAPHIC_VALIDITY_PROVEN=NO`, `PUBLISHER_IDENTITY_AUTHENTICATED=NO`, `CURRENT_DEVICE_PROVEN_BY_SHELL_TEXT=NO`, `DATA_CONTAINER_RETENTION_PROVEN=NO` e `INSTALLATION_AUTHORIZED=NO`.

**O script ainda NÃO foi executado no iPad.** Ele é opcional e pode encontrar `UNAVAILABLE` em qualquer uma das ferramentas. O caminho real do bundle não é conhecido pelo assistente nem deve ser inventado. Não é necessário transferir o script ou executar comandos durante esta fase.

## Testes de host e CI

`ci/test_build70_dq_installed_bundle_readonly.py` contém 12 casos de segurança e compatibilidade:
- `/bin/sh -n` para validar a sintaxe POSIX;
- tentativas com caminho ausente, relativo, bundles falsos e UUID inválido, que têm de recusar a execução;
- inspeção da obrigatoriedade de `Info.plist`/Mach-O regulares sem symlinks;
- conferência de caminhos de ferramentas fixos e fallback `UNAVAILABLE`;
- ausência de chamadas a sudo, root, instalação, exclusão, rede, backup, leitura de dados privados ou comandos de alteração;
- permanência das três travas de produção no Swift.

Workflow `.github/workflows/chimera-build70-phase-dq-installed-bundle-readonly.yml`: Linux e macOS, somente leitura, sem pacotes de teste distribuíveis e sem dispositivo físico. **O CI não certifica a disponibilidade de `plutil` ou `ldid` dentro do Chimera**; essas dependências permanecem condicionais.

## Interpretador local do relatório (não autentica sua origem)

Adicionados `ci/build70_dq_installed_bundle_report.py` e `ci/test_build70_dq_installed_bundle_report.py`, com **10 testes adversariais**. O parser consome exclusivamente o texto da ferramenta shell, em arquivo regular de até 2 KiB, e exige todos os cabeçalhos e negativas de privilégio.

O status `DQ_REPORTED_MATCH_HISTORICAL_METADATA_NOT_ATTESTED` significa **somente** que as strings digitadas/lidas coincidem com Bundle ID `com.example.MangaReader12`, Build `70` e application-identifier histórico `AR5SFJC432.com.example.MangaReader12.AR5SFJC432`. O conteúdo não tem assinatura autenticadora; `ldid -e` também não verifica a integridade da assinatura Mach-O. O parser mantém `inputProvenToComeFromCurrentPhysicalIPad=false`, `nativeCodeSignatureCryptographicallyValidated=false`, `installedBuild70IndependentEntitlementAttested=false` e `installationAuthorized=false`.

Se qualquer um dos três campos estiver `UNAVAILABLE`, retorna `DQ_REPORTED_INSTALLED_IDENTITY_FIELDS_UNAVAILABLE`, sem inventar metadados. Se algum valor informado **divergir**, retorna `DQ_REPORTED_BUNDLE_VERSION_OR_ENTITLEMENT_MISMATCH_STOP_QA`, exigindo revisão. Relatórios truncados, adulterados, com caracteres de shell, campos extras ou uma permissão que não seja negativa são recusados. A ferramenta host também não escreve nem instala nada.

A CI DQ agora executa em Linux/macOS os **12 testes do script shell + 10 testes do parser**, além da checagem `/bin/sh -n` e das três travas editoriais/instalação. Os resultados físicos no iPad continuam pendentes.

## Relação com as fases já aprovadas

- **DO**: confronta os nove indicadores SQLite e lotes de presença offline já gerados na Build70.
- **DL**: compilou e assinou ad-hoc uma cópia efêmera do WebReader 71 inteiro **apenas no CI**, sem distribuir IPA.
- **DM**: reabriu biblioteca SQLite e páginas binárias fictícias usando Swift real no macOS, sem exercício do instalador iOS.
- **DN**: mantém backup/restauração e exclusão de downloads fora dos fluxos diretos de inicialização e da tela de atualizações.
- **DP**: relata apenas UID/GID e Bundle ID do próprio app por APIs públicas, sem tentar ler entitlements assinados em Swift.

DQ prepara uma observação da **Build70 já instalada**, mas não completa o protocolo de autorização, não prova identidade de editor e não confirma que o mesmo IPA final será consumido pelo instalador.

## Procedimento humano futuro (não executado)

Quando o proprietário quiser testar a Build71, ele poderá abrir Filza, identificar **a pasta do bundle do WebReader**, não a pasta `Containers/Data/Application` da biblioteca, e só então avaliar o script somente leitura em NewTerm. Caso `ldid` esteja ausente, não é necessário instalar nenhuma dependência automaticamente: revisar método alternativo. Não copiar a pasta de dados privada nem arquivos de capítulos para o GitHub. Compartilhar apenas os campos não privados, se desejar.

Antes de criar e entregar uma IPA 71 para teste ainda faltam consentimento explícito do proprietário, backup externo cuidadoso (sem restaurar por cima dos downloads), comparação SHA/CDHash/entitlement da IPA final com a identidade da Build70 e verificação física antes/depois da instalação **por cima** com Wi-Fi desligado.

**Gates inalterados:** `productionPublicKeyX963=nil`; `independentlyProvisionedSPKISHA256=nil`; `liveInstallationEnabled=false`. Nenhuma autorização de instalação ou publicação é inferida de uma coleta de metadados.

**CI DQ:** verificar os jobs e logs finais antes de declarar aprovação. Nunca confundir testes macOS/Linux de sintaxe com validação física no iPad.

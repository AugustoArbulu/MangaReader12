# WebReader Build70 — Fase CV: ABI iOS 12 do LSApplicationWorkspace e decisão de entrega da IPA

**Data:** 10/11/2026. **Branch experimental:** `feat/chimera-updater-phase1-protocol-audit`. **PR #90:** Draft. `main`, GitHub Releases, helper existente, Build70 física, biblioteca e offline **não foram alterados**.

## 1. Por que esta fase muda a investigação

A Fase CS identificou na fonte pública **de referência** do appinst um padrão de duas aberturas por pathname: `zip_open(argv[1])` e depois `copyItemAtPath:filePath toPath:installPath`, seguido de `LSApplicationWorkspace.installApplication` com a cópia temporária. A CT testou duas cópias controladas e mostrou que o mesmo UID ainda pode mudar os bytes *após* o último SHA-256. A CU validou caminhos ancorados em FDs, mas sem isolar um helper real do processo cliente.

Portanto, mais testes de hash do arquivo fechado **não provam** que o serviço de instalação recebe os mesmos bytes. A próxima hipótese útil é uma **interface de instalação direta a partir de um pathname sob custódia de helper independente**, sem a segunda cópia implementada pelo appinst upstream. Isso seria uma alternativa arquitetural, NÃO uma decisão de ativar instalação.

## 2. Fontes que sustentam a hipótese — e seus limites

- Fonte fixada do appinst público (commit `235aca6cddfbdc9fa87fcb5b2aec2df37ed6d65a`): https://github.com/akemin-dayo/AppSync/blob/235aca6cddfbdc9fa87fcb5b2aec2df37ed6d65a/appinst/appinst.m
- Interface privada LSApplicationWorkspace em dump de headers **iOS 10** (não iOS 12):
  https://github.com/JaviSoto/iOS10-Runtime-Headers/blob/1501f5e689fda4644df0adbffc50c0f737c4ab96/Frameworks/MobileCoreServices.framework/LSApplicationWorkspace.h
- Header comunitário **iOS 13** mostra um método compatível, mas não prova disponibilidade exata no iOS 12:
  https://github.com/xybp888/iOS-Header/blob/master/13.0/Frameworks/CoreServices.framework/LSApplicationWorkspace.h

O método documentado nessas referências é `installApplication:withOptions:error:`, que recebe um objeto URL/caminho — **não um file descriptor**. Isto não é API pública/documentada de instalação, e uma assinatura de método inferida de headers externos não fornece garantia de entitlements ou sucesso no iOS12/Chimera.

**Não sabemos** qual binário do appinst está instalado no iPad, se LSApplicationWorkspace permite uso por um helper independente, se a API repassa/copia o arquivo internamente, se o serviço Apple elimina o IPA após consumir ou se a vida útil do arquivo sob custódia é suficiente. Nem existência do selector nem `BOOL` de retorno de uma chamada futura substituem validação de instalação/persistência.

## 3. Entrega CV: diagnóstico de ABI sem instalação

`ci/build70_cv_lsworkspace_readonly_probe.c` foi escrito para compilar como CLI ARM64 com target mínimo iOS 12.0, **somente no GitHub Actions**, sem empacotar IPA ou DEB e sem distribuir o binário.

Quando executado em um ambiente autorizado, faz APENAS:

1. `objc_lookUpClass("LSApplicationWorkspace")`;
2. se necessário, `dlopen` do framework de sistema MobileCoreServices somente para descobrir o registro da classe;
3. `sel_registerName("installApplication:withOptions:error:")` e `class_getInstanceMethod`;
4. `method_getNumberOfArguments` e inspeção grosseira do primeiro caractere do encoding do tipo de retorno;
5. imprime sete linhas fixas: presença de classe, selector, aridade, compatibilidade de retorno, `CV_CALL=NOT_ATTEMPTED`, `CV_AUTHORIZATION=DENIED`, `CV_INSTALLATION=NOT_ATTEMPTED`.

**Não cria instância de workspace, não invoca o selector, não chama objc_msgSend, appinst, posix_spawn, subprocess, Foundation instalação, rede, IPA ou arquivos do usuário.** Uma observação com classe presente, método presente, aridade 5 e retorno BOOL compatível é rotulada **apenas como plausibilidade de ABI**. Se o método não existir, tampouco é prova total de inviabilidade: pode depender de framework/caminho/versão, mas não há autorização implícita para tentar instalar.

`ci/build70_cv_lsworkspace_probe_report.py` analisa somente um relatório textual ASCII de exatamente sete linhas, com delimitadores fixos. Rejeita campos adicionais, permissões falsas, terminal malformado, valores não canônicos e contradições. O objeto `CVMethodObservation` mantém `process_entitled_to_use_selector=false`, `appinst_secondary_copy_avoided=false`, `exact_verified_ipa_consumed_by_installer=false`, `installation_authorized=false` e `installation_performed=false`, mesmo que a assinatura pareça compatível.

`ci/test_build70_cv_lsworkspace_probe_report.py` valida entradas adversariais e inspeciona o fonte C para vedar invocação de instalação. Workflow `.github/workflows/chimera-build70-phase-cv-readonly-abi.yml`: Ubuntu testa parser, macOS testa parser e **compila** o CLI nativo para ARM64/iOS12 usando Xcode16.4 e verifica Mach-O e símbolos não instaladores. A execução real em um iPad **NÃO acontece** nesta fase.

## 4. Comparação de opções

| Caminho | Benefício | Impedimento atual | Decisão |
| --- | --- | --- | --- |
| appinst público de referência | Procedimento manual já conhecido; AppSync instalado | Releitura/cópia por pathname para temporário interno e binário real ainda não identificado | **Manter apenas como fallback manual** |
| appinst recebendo `/dev/fd/N` | CR mostrou leitura original por FD em filho Python | Não prova compatibilidade com appinst; appinst de referência faz segunda cópia | **Não selecionar** para produção |
| helper próprio chamando LSApplicationWorkspace com IPA sob staging independente | Poderia eliminar a cópia extra do appinst e limitar o acesso ao arquivo | API privada; permissões iOS12 não comprovadas; serviço Apple pode reabrir/copiar; não há raiz editorial nem consentimento confiável | **Candidato para investigação, sem ativação** |
| fluxo manual Filza/NewTerm já validado | Protege a rotina atual e dados da Build70 | Não é totalmente automático | **Fallback estável enquanto faltam provas** |

## 5. Requisitos bloqueantes antes de qualquer tentativa de instalação

1. Um editor real cria a chave privada de produção localmente, fora do GitHub/chat/CI, e confere o fingerprint público por canal independente. Uma nova IPA de confiança, aprovada pelo proprietário, provisiona esse pin.
2. Uma Release imutável possui manifesto production v2 editorialmente assinado e o SHA-256 exato da IPA revisada, com auditoria nativa macOS e verificação Swift; origem fixa, antireplay e política de downgrade.
3. O helper precisa ser independente do app: raiz de staging cuja **permissão de escrita** seja realmente negada aos clientes, ancestral confiável e identidade de serviço comprovada no iOS12. Não depender de `LOCAL_PEERTOKEN` que voltou TOKEN_UNAVAILABLE no dispositivo.
4. O arquivo entregue ao serviço Apple precisa ser o mesmo objeto auditado e protegido até o consumidor abrir/concluir. Se API privada fizer outra cópia internamente, garantir que essa transição não introduza uma janela não auditada; sem demonstrar isso, manter o modo manual.
5. Consentimento local explícito e proteção durável contra replay/rollback, registro de tentativa/conclusão, preservação da biblioteca e recuperação em caso de falha; um trigger `WRCHK2\n` não autenticado só pode solicitar checagem e **jamais autorizar instalação**.
6. Teste físico somente leitura do CLI nativo iOS12 seria um gate FUTURO opcional; não há motivo para exigir nova IPA ou .deb do usuário agora. Mesmo se a assinatura de selector aparecer, não autoriza instalar.

## 6. Estado operacional

**Hard stops:** `WebReaderAppinstSocket.liveInstallationEnabled=false`, `WebReaderUpdateChannel.productionPublicKeyX963=nil`, `WebReaderProductionPublisherTrust.independentlyProvisionedSPKISHA256=nil`. Build70 estável. PR #90 Draft, `main` intocada. Nenhuma Release, build de produção, IPA/DEB ou execução de instalação na Fase CV.

**Resultado da CI:** a preencher somente após verificação dos jobs Linux/macOS. Não interpretar compilação cruzada como teste real de entitlement ou autorização do iPad.

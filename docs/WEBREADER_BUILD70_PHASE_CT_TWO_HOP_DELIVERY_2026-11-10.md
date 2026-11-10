# WebReader — Build70 / Fase CT: duas cópias verificadas não significam instalação imutável

Data: 10/11/2026. Trabalho somente em `feat/chimera-updater-phase1-protocol-audit`, PR #90 Draft. `main`, Releases, Build70 instalada e conteúdo do iPad permanecem intactos.

## Origem técnica

A Fase CR aprovou o ensaio de passagem de FD ao filho Python host-only; a Fase CS confirmou no **appinst upstream público de referência** que existe uma segunda abertura por pathname: `zip_open(argv[1])` e depois `copyItemAtPath:filePath toPath:installPath`, seguida por `LSApplicationWorkspace.installApplication` com o caminho copiado. Fonte: https://github.com/akemin-dayo/AppSync/blob/235aca6cddfbdc9fa87fcb5b2aec2df37ed6d65a/appinst/appinst.m

Não sabemos se o appinst efetivamente instalado no iPad usa a mesma implementação. Não confundir versão do `ldid` com versão do `appinst`. Isso NÃO constitui demonstração de exploração do iOS12.

## Hipótese CT e implementação

O experimento CI testa **duas cópias em sequência** sobre diretórios preexistentes `0700`, usando dados ZIP-falsos claramente identificados como `NOT_AN_IPA`:

1. `candidate.fake` no diretório de entrada -> `review-<digest>.fake` no diretório de revisão.
2. `review-<digest>.fake` -> `handoff-<digest>.fake` no diretório de segunda cópia.
3. A cada estágio: abertura por FD com `O_NOFOLLOW`, origem regular com um único hardlink e UID do usuário do job, nome canônico, diretórios separados `0700`, criação `O_EXCL`, SHA-256 durante transferência e novo SHA-256 do arquivo copiado; verifica identidade do nome e do FD, `fsync` e recusa sobrescrita.
4. Injeções entre etapas: troca do pathname, adulteração in-place, cópia final alterada, symlinks/hardlinks e diretório permissivo devem **rejeitar**.
5. Contraexemplo obrigatório: mesmo com arquivo modo `0400` e pasta `0700`, o mesmo usuário pode reabilitar escrita e mudar os bytes **depois** da última auditoria. Não existe garantida imutabilidade até o instalador.

Artefatos:
- `ci/build70_ct_two_hop_delivery_lab.py` — laboratório de duas cópias e contraexemplo de mutação tardia, **sem** `appinst`, `subprocess`, rede, IPA real, privilégios ou installer.
- `ci/test_build70_ct_two_hop_delivery_lab.py` — testes adversariais (Linux/macOS).
- `.github/workflows/chimera-build70-phase-ct-two-hop-review.yml` — matriz host e verificações dos travamentos de produção.

O resultado `CTTwoHopObservation` tem ambos os hashes revisados, mas mantém explicitamente `protection_from_later_same_uid_mutation=false`, `true_privilege_separation_proven=false`, `exact_iOS_installer_consumption_proven=false`, `owner_consent_verified=false`, `installation_authorized=false` e `installation_performed=false`.

## Conclusão para arquitetura

Um processo com o **mesmo UID** pode alterar seus próprios arquivos 0400, e um caminho auditado não é uma capacidade de acesso imutável. Diretórios 0700 reduzem interferência de **outros usuários**, mas não provam integridade contra código de mesmo UID ou root. O protótipo também não verifica permissões de cada ancestral, isolamento real de conta/entitlement, política do kernel Chimera, assinatura Apple de IPA real ou o ciclo de vida no serviço de instalação Apple.

**Não usar automaticamente o appinst upstream no novo fluxo de atualização apenas porque os hashes de duas cópias conferiram.** A direção segura para o projeto permanece: helper independente com raiz editorial fixa e aprovada, verificação de manifesto v2, objeto de arquivo sob custódia exclusiva e integridade durante a leitura efetiva do instalador, proteção anti-replay/downgrade, consentimento local independente e testes físicos isolados. Se for preciso substituir o caminho do appinst, isso exigirá revisão técnica/assinatura/entitlements e validação física separada — sem trocar o binário do appinst existente sem autorização.

## Próximos testes de decisão

- Identificar **somente por leitura** o pacote/binário `appinst` efetivamente instalado no iPad, quando houver uma razão concreta para o teste físico. Não instalar IPA ou DEB diagnóstico agora.
- Pesquisar se existe mecanismo de instalação com arquivo sob custódia do helper que não devolva confiança ao pathname mutável; separar demonstração macOS de viabilidade iOS12.
- Provisionamento editorial continua bloqueado até uma chave real criada exclusivamente pelo usuário em seu computador e pin público confirmado independentemente.

**Hard stops:** `WebReaderAppinstSocket.liveInstallationEnabled=false`, `WebReaderUpdateChannel.productionPublicKeyX963=nil`, `WebReaderProductionPublisherTrust.independentlyProvisionedSPKISHA256=nil`. PR #90 continua Draft, nenhuma Release ou Build71.
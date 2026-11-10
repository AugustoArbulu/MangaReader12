# WebReader Build70 — Fase CU: limite de custódia do helper e auditoria por diretórios abertos

**Data:** 10/11/2026. **Branch:** `feat/chimera-updater-phase1-protocol-audit`. **PR #90:** Draft. **Estado físico:** Build70 instalada e aprovada no iPad iOS 12.5.8, sem mudanças nesta fase. `main`, Releases, biblioteca, backups e downloads intactos.

## Por que a CT não é suficiente

A Fase CT aprovou duas cópias com SHA-256 e controles de links, mas comprovou em Linux/macOS que uma entidade que **continua sendo dona do inode** pode alterar seu próprio arquivo depois do último hash, mesmo que os bits de permissão sejam 0400 e o diretório esteja em 0700. O fechamento do FD de revisão e a reabertura posterior pelo instalador tornam essa diferença relevante.

A Fase CS encontrou ainda uma segunda cópia por pathname no código público de referência do appinst:
https://github.com/akemin-dayo/AppSync/blob/235aca6cddfbdc9fa87fcb5b2aec2df37ed6d65a/appinst/appinst.m
Isso não comprova que o binário do appinst efetivamente instalado no iPad tenha essa mesma revisão.

## Implementação CU — fatos verificáveis, sem autoridade

O novo `ci/build70_cu_helper_custody_audit.py` é um auditor **somente leitura e somente host**, em arquivos de teste `.fake` de até 1 MiB. Recebe um diretório inicial *supostamente confiável* apenas como fixture de laboratório, abre o diretório e seus descendentes relativos via `dir_fd`, exige modo exato `0700` e UID do próprio usuário do job, bloqueia symlinks na etapa final de cada `open`, e impõe profundidade e componentes canônicos.

Para o arquivo, exige regular, mesmo UID, um único hardlink, ausência de escrita para grupo/outros, tamanho esperado, SHA-256 lido por FD, além da concordância entre `fstat` antes/depois e `stat` por nome ao final. A revisão pode detectar algumas trocas por nome e mutações in-place **ocorridas durante o teste**. Entretanto `mtime`/`ctime`, o SHA e o FD não protegem contra mudanças futuras, nem são uma prova absoluta contra adversários privilegiados com poder de editar e restaurar metadados.

O recibo `CustodyHostObservation` registra o digest e a quantidade de diretórios vistos, mas mantém explicitamente **false** para:

- `chain_root_from_trusted_device_policy`, pois a raiz foi passada ao laboratório e seus **ancestrais** não foram auditados independentemente;
- `separate_helper_uid_verified_on_device` e `client_write_access_excluded`, pois os jobs Linux/macOS executam no mesmo UID e não reproduzem o isolamento de um helper iOS;
- `future_inode_mutation_excluded`, `appinst_secondary_copy_protected`, `final_installer_bytes_bound_to_verified_fd`, pois o verificador não controla o consumidor nem o tempo após a leitura;
- `production_editor_identity_authenticated`, `consent_from_trusted_owner_ui`, `durable_antireplay_completed`, `ios12_runtime_verified`, `installation_authorized`, `installation_performed`.

Arquivos novos:
- `ci/build70_cu_helper_custody_audit.py` — validação de evidência host via FDs sem instalar.
- `ci/test_build70_cu_helper_custody_audit.py` — 15 testes adversariais de permissão, caminho, troca, links, digest e recusa de autoridade.
- `.github/workflows/chimera-build70-phase-cu-helper-custody.yml` — matriz Linux/macOS com teste e as travas de produção.

## Arquitetura de isolamento recomendada — ainda não implementada

| Fronteira | Princípio | Estado |
| --- | --- | --- |
| WebReader no iPad | Pode emitir no máximo `WRCHK2\n` fixo, sem URL, IPA, caminho, hash, chave, versão ou sinal de instalação | Modelo CN, não ligado ao app |
| Helper | Seleciona origem de atualização fixa e verificada, sem confiar na chamada do app. Deve possuir sua própria raiz, protegida contra escritos do cliente, e material editorial público independente | Pendente; **nenhum helper instalador** |
| Conteúdo de release | Manifesto v2 ECDSA-P256/SHA256 assinado pela chave privada sob guarda do proprietário, IPA de mesmo digest e code seal nativo verificado | CQ sintético aprovado; produção sem chave provisionada |
| Entrega ao serviço de instalação | O objeto consumido deve ser exatamente o aprovado, inclusive após cópias e reabertura pelo serviço. Analisar permissões/ACLs, UID real do serviço, NSFileManager e transições de pathname | **Não comprovado** |
| Confirmação | Consentimento real do proprietário via superfície confiável, de uso único, com registro durável antirreplay/rollback e recuperação | Pendente |

Não basta executar o helper como root, porque um processo de privilégio elevado pode também comprometer arquivos, temporários ou o armazenamento de estado; isolamento por UID, sandbox/entitlements, ACLs, controle do objeto e protocolo são requisitos independentes. Também não presumir que a pasta `0700` protege contra processos do mesmo UID ou root.

## Evidência e próximos gates

A CI deve primeiro demonstrar Linux/macOS com os testes adversariais acima. Um resultado verde valida **somente** a implementação de laboratório.

Para avançar rumo à instalação direta, a próxima decisão deve comparar alternativas concretas de entrega da IPA a `LSApplicationWorkspace`/MobileInstallation, incluindo a segunda cópia do appinst de referência, sem alterar appinst ou executar instalação no iPad agora. A identidade e a versão do binário do appinst instalado ainda são uma incógnita; qualquer inspeção física futura será apenas de leitura e deve ter motivação concreta.

A criação da chave editorial real continua uma ação futura, local e exclusivamente do proprietário, sem importar segredo ao GitHub, CI, chat ou ao WebReader. O pin público permanece `nil`, o instalador do app `liveInstallationEnabled=false`, e a PR segue em rascunho, sem merge.

**Nenhuma nova Build71, IPA, DEB, GitHub Release, instalação ou mudança de arquivos do usuário nesta fase.**
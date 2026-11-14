# WebReader — Build 69 futura, fases AV–AY: validação completa e diagnóstico sem rede

**Data:** 09/11/2026 UTC (trabalho experimental).  
**Branch:** `feat/chimera-updater-phase1-protocol-audit`, [PR #90 Draft](https://github.com/AugustoArbulu/MangaReader12/pull/90). **Não alterar `main`.**  
**Referência física:** Build68 aprovada no iPad iOS 12.5.8, biblioteca e capítulos offline preservados. IPA de QA aceita SHA-256 `fb8263573a5b46a94bab74f91c2a25b08de6aa9ac327f078339f1ff77ae5d841`, commit candidato `605f607b08d714d8eabfd3270516b77dfaf673e0`.

Este lote avança a descoberta de releases, mas **não** gera uma nova IPA, não cria Release, não inscreve chave editorial, não toca na `main` e não instala nada pelo Chimera. Complementa [AS/AT/AU](WEBREADER_BUILD69_PHASES_AS_AT_AU_OWNER_TRUST_BOOTSTRAP_2026-11-09.md).

## Problema encontrado: falso “já atualizado” com metadados antigos inválidos

Antes da Fase AV, `WebReaderUpdateManifestVerifier.verify` conferia a assinatura ECDSA, a versão e a identidade da aplicação, mas lançava `notNewer` **antes** de validar todos os campos do payload: URL de IPA, tamanho, digest, compatibilidade mínima de iOS e `publishedAt`. O checker tratava `notNewer` como `upToDate`. Assim, um manifesto *efetivamente assinado*, porém estruturalmente inadequado, com Build igual/antiga, podia ser apresentado como uma verificação válida de versão instalada.

A mesma ordem existia no parser de GitHub Releases públicos: o retorno `upToDate` acontecia antes da validação do asset/URL/digest da release consultada.

Não se trata de execução remota de código, instalação ou quebra da ECDSA. É uma **falha de integridade do status exibido**, relevante para a confiança da interface de atualizações.

## AV — manifesto assinado: validar tudo antes de status positivo

`MangaReader12/Core/WebReaderUpdateManifestVerifier.swift`

- `build` continua exigindo inteiro positivo e limite estrito.
- O verificador valida todos os campos assinados, incluindo schema v2, `applicationIdentifier`, canal, `minimumIOS`, `ipaSize`, SHA-256, `publishedAt`, release notes, HTTPS e caminho exato do asset, **antes** de comparar Build instalada.
- Somente um payload integralmente válido e já autenticado pode gerar `notNewer`. O checker continua apresentando `upToDate` apenas nesse caso.
- Não altera chaves, transporte, URL de produção ou regras de instalação.

Regressão **Swift real** adicionada a `ci/test_native_webreader_update_verifier.py`: Build66 assinada e válida versus instalada 66 retorna current; Build66 assinada com URL não permitida, SHA inválido, iOS13 obrigatório, canal trocado e claim extra **rejeita com erro específico**, não retorna current.

## AW — GitHub Releases público: asset válido antes de “atualizado”

`MangaReader12/Core/WebReaderGitHubReleaseParser.swift`

- Continua consulta pública de metadados via HTTPS, sem autenticação editorial independente.
- Analisa URL canônica, estado `uploaded`, contagem e nome exclusivo do asset, tamanho positivo e `digest=sha256:...` antes da comparação com a Build instalada.
- Release antiga ou atual sem IPA, com SHA malformado ou URL externa deve retornar `invalidGitHubRelease`, **não** `upToDate`.
- Mantida a separação entre GitHub Release não assinado editorialmente e manifesto ECDSA autenticado.

Regressão em `ci/test_public_github_release_parser.py`: release atual/antiga válida é `upToDate`; versões antigas com asset ausente, digest inválido ou URL externa são rejeitadas.

## AX — diagnóstico offline na tela de atualizações

`WebReaderAppUpdatesViewController.swift` + `WebReaderUpdaterSecuritySnapshot.swift`

- **Quinta linha da seção CANAL DO APLICATIVO:** `Copiar diagnóstico do canal assinado`.
- Relatório copiável com Build/iOS, presença de chave pública, presença de pin SPKI independente, geração e resultado booleano da avaliação já compilada `isProvisioned`.
- Explicita que GitHub Releases públicos não equivalem à assinatura editorial e que a recuperação de Builds privadas depende de Android/PC + Filza.
- **Nenhuma rede iniciada, segredo emitido ou diretório da biblioteca acessado** pelo relatório. Não inclui chave privada, PIN hexadecimal completo, PEM, caminhos locais, cookie ou token.
- Um resultado de prontidão **não** garante que exista release publicado e jamais autoriza instalação. Chimera continua bloqueado.
- UI IPC de teste permanece com somente 2 seções e não expõe essa nova ação.

Testes Swift reais de relatório em `ci/test_native_webreader_update_security_snapshot.py`, incluindo privacidade, concatenação de linhas, trust root ausente e prontidão contraditória. Política estática adicional em `ci/test_build69_phase_av_aw_ax_ay_update_policy.py`.

## AY — proveniência e nome de asset na camada de download

`MangaReader12/Core/WebReaderIPAStager.swift`

- **Caminho real de `.signedManifest`:** aceita somente `/releases/download/buildN/WebReader-BuildN-iOS12-adhoc.ipa`. A forma `WebReader-iOS12-unsigned.ipa` não é aceitável por esse canal em produção.
- **`.publicGitHubRelease`:** preserva as duas convenções históricas (asset legado e ad hoc de Build nomeada), ambas explicitamente sem autenticação editorial independente.
- **`.manualLocalFile`:** não pode ser confundido com um download de release; importação Filza/Arquivos continua sendo caminho separado.
- Testes de transporte sintético com `URLProtocol` continuam aceitando o legado exclusivamente na **fixture de laboratório**, sem relaxar o caminho real de produção.
- O download continua dependente de escolha do usuário, versão estritamente crescente, orçamento de disco, GET permitido, SHA/ZIP validado e exportação manual. Nenhuma autorização do helper Chimera.

Regressão no `ci/test_native_webreader_ipa_stager.py` impede que proveniência `.manualLocalFile` efetue GET de release mesmo com transporte injetado. Política de admissibilidade estática reforçada.

## Validação integrada e limites

Workflow: `.github/workflows/chimera-build69-phase-ac-af-integrated-qa.yml`, renomeado para **AC–AY**.

- Linux: suítes AV–AY, AS–AU, controles de atualização, biblioteca/offline, preservação do bloqueio Chimera e ausência de trigger de IPA.
- macOS: testes Swift reais de assinatura, versão antiga inválida, parser GitHub público, URLSession nativo com respostas sintéticas, staging, recibo de segurança, bootstrap editorial e assinatura ad hoc de fixtures; compilação integral Debug e Release ARM64/iOS12 com signing desabilitado.
- [Execução iniciada #42550113510](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42550113510). **Registrar resultado real após conclusão, não presumir SUCCESS.** Nenhum IPA é produzida pelo workflow.

## Estado do projeto

`productionPublicKeyX963=nil`  
`independentlyProvisionedSPKISHA256=nil`  
`productionTrustGeneration=0`  
`liveInstallationEnabled=false`

Build68 permanece instalada/aprovada. Build69 é código experimental **sem nova IPA**; PR #90 Draft; `main` não modificada. Chave privada real, pin independente, provisionamento do trust root no aplicativo, GitHub Release público e feed assinado ainda dependem de decisão e autorização do proprietário. O login do GitHub, PAT ou chaves privadas nunca devem ser embutidos no WebReader.

## Próxima etapa proposta

Concluir CI AC–AY e, depois, iniciar **AZ: estabilização/QA de Build69 sem publicação automática**, conferindo invariantes de versão, integridade do backup/biblioteca e checklist físico de atualização manual. Um candidato instalável da Build69 requer autorização para empacotamento/distribuição privada e posterior QA no iPad, sem tocar `main` ou ativar Chimera.

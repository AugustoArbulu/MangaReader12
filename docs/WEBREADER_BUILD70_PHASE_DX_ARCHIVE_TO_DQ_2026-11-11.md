# WebReader — Fase DX: comparar IPA real Build70 arquivada com o relatório DQ do iPad

**Data:** 11/11/2026. **Branch:** `feat/chimera-updater-phase1-protocol-audit`; PR #90 Draft. Sem merge em `main`, nenhuma ação automática de rede no dispositivo, pacote novo instalável ou alteração de dados do iPad.

## Objetivo

A DV validou a Build71 **completa** no macOS somente como IPA temporária e descartável. A DW recuperou e verificou via Apple `codesign` o artefato de QA **real** da Build70 de 09/11/2026. O ponto sem evidência física é o bundle que está efetivamente instalado no iPad hoje. A DQ já dispõe de um script estritamente somente leitura que poderá ser executado manualmente, com um caminho para o bundle selecionado no Filza.

A DX cria a comparação **offline de host** entre dois insumos: (1) arquivo ZIP original da Build70 arquivada no GitHub Actions, contendo IPA + recibos, e (2) texto DQ eventualmente obtido no iPad. Um pacote histórico íntegro **não garante** que seu código ou assinatura seja o que está atualmente instalado. O texto DQ pode ser forjado, vir de outro aparelho ou não validar o selo criptográfico.

## Implementação

Arquivo `ci/build70_dx_archived_vs_installed_identity.py`, modo CLI:

```sh
python3 ci/build70_dx_archived_vs_installed_identity.py \
  --archive "/caminho/para/WebReader-Build70-OwnerApproved-QA-archive.zip" \
  --dq "/caminho/para/relatorio-DQ.txt"
```

Este é um comando **para computador/host**, não uma linha de comando de instalação no iPad. Ele exige os dois insumos em arquivos regulares de tamanho limitado, recusa links simbólicos e inconsistências no conteúdo. Nunca modifica dados do usuário, publica Release, altera entitlements, invoca appinst ou escreve dados privados. O relatório de saída é JSON somente com metadados.

O ZIP original é fixado por hash SHA256 dos **bytes integrais do arquivo de archive**:

- ZIP externo SHA256: `026c4097af0b24b38ec573cbef9093ff1082496e1e905ce427d42f06f09b3d70`
- IPA interna: `WebReader-Build70-iOS12-adhoc.ipa`
- IPA interna SHA256: `526291cc77203c3881e5f3f1c75904e8863dbde3b3bd9df7e1185c3229fb4fc1`
- IPA interna tamanho: **17.845.463 bytes**
- Identidade esperada: `com.example.MangaReader12`, Build70, mínimo iOS12.0
- Entitlement de assinatura histórico: `AR5SFJC432.com.example.MangaReader12.AR5SFJC432`
- CDHash de CodeDirectory registrado e revalidado pela fase DW macOS: `e0de7f55a2684da7507c3a862247480bd05c39bd`
- GitHub Actions original: run `42705903886`; commit de código fonte registrado `ae931abb725977a417a1fcb20b79c82af825dd55`

A DX confere exatamente os seis membros esperados do ZIP, recusa membros extras, duplicatas, criptografados ou symlinks; confirma o hash da IPA real, checksum, os dois relatórios originais e sua proveniência, além do `Info.plist` embarcado. Em seguida usa o parser DQ rígido já existente, **sem pedir privilégios adicionais no iPad**.

## Estados de saída

| Status | Leitura operacional |
| --- | --- |
| `DX_ARCHIVED_PACKAGE_MATCHES_DQ_TEXT_ONLY_NOT_DEVICE_ATTESTED` | Todos os metadados enviados coincidem **textualmente**, mas não há atestado de procedência física, integridade do bundle atual ou autorização para instalar |
| `DX_WAIT_REPORTED_INSTALLED_IDENTITY_INCOMPLETE` | Algum campo está `UNAVAILABLE`; não inventar valores nem prosseguir para teste de IPA71 |
| `DX_STOP_REPORTED_INSTALLED_IDENTITY_DIFFERS_FROM_ARCHIVE` | Um campo reportado diverge; interromper QA e investigar por método somente leitura |
| `BLOCKED` / erro | Arquivo histórico, relatório, assinatura textual, formato ZIP, SHA256 ou integridade dos recibos inválidos ou indisponíveis |

Os três resultados positivos/negativos de texto mantêm explicitamente como `false`: `currentlyInstalledBuild70CryptographicallyAttested`, `deviceAndArchiveSameCodeDirectoryProven`, `physicalBundleDataContainerPreservationProven`, `physicalOfflineChapterPagesVerified`, `ownerPrivateQADistributionConsentRecorded`, `readyToDistributeIPA`, `readyToInstallIPA`, `automaticUpdaterEnabled`, `installationAuthorized` e `installationPerformed`.

A DX **não repete o Apple codesign**; esse teste ocorreu independentemente no workflow DW. Nesta ferramenta, os bytes originais são cotejados com o hash, o CDHash é confrontado com recibos históricos e a assinatura atual do iPad permanece **não verificada**.

## Roteiro físico mínimo futuro (não executado)

Quando chegar o momento do teste no iPad:

1. Abrir Filza e selecionar **o bundle do WebReader instalado** (`MangaReader12.app` na árvore `.../Containers/Bundle/Application/<UUID>/`). Não usar a pasta `Containers/Data/Application` que contém biblioteca/arquivos do usuário. Não inventar o UUID.
2. Se for necessário, copiar somente o shell `ci/build70_dq_installed_bundle_readonly.sh` e executá-lo com o **caminho exato selecionado no Filza**; ele não faz scans, instalação ou escrita. As ferramentas `plutil`, `ldid` e `awk` precisam já existir. Caso contrário, os campos retornam `UNAVAILABLE`. Não instalar pacotes automaticamente nem forçar privilégios.
3. Repassar **somente as 3 strings de identidade e as negativas** do texto DQ para o PC/diagnóstico; **não compartilhar UUID/caminhos de contêiner, títulos, URLs privadas, documentos ou páginas offline**.

O usuário **não precisa fazer isso agora** enquanto o próximo pacote Build71 real não tiver sido especificamente aprovado e preparado. A investigação não deve afirmar que a DQ foi executada antes do usuário fornecer o relatório.

## Regressões e CI

`ci/test_build70_dx_archived_vs_installed_identity.py` verifica texto compatível/indisponível/divergente, recusa de alterações no archive e recibos, cabeçalho do `Info.plist`, ausência de autoridade em qualquer resultado, resistência a entradas adversariais e preservação da natureza somente leitura. As IPAs criadas nas fixtures de teste são **fictícias e não assinadas**: sua SHA é alterada no âmbito do teste para cobrir o contrato. Elas não são pacote do usuário e não demonstram integridade de assinatura Apple.

`.github/workflows/chimera-build70-phase-dx-original-archive-dq-compare.yml` executa a suíte em Linux/macOS e preserva as três travas Swift. Só registrar DX aprovada depois de conferir os dois jobs, e nunca promover o resultado a teste físico. Evitar duplicar workflows por `push` e `pull_request` na mesma PR.

## Limites de segurança e próximo marco

- O backup `.mr12backup` **não guarda os bytes das imagens**; restaurá-lo por cima pode perder downloads. Não iniciar restauração automática.
- O usuário ainda não confirmou um backup externo completo dos arquivos de leitura; nunca eliminar cache/documentos baseado em teste textual.
- É necessário consentimento específico antes de distribuir uma nova IPA71 para QA manual, mesmo com a Build71 sombra validada pelo CI.
- Não existe autenticação criptográfica do editor nem da ponte de instalação Chimera em produção; nenhum sucesso de CI autoriza a atualização automática.

As travas permanecem `productionPublicKeyX963=nil`, `independentlyProvisionedSPKISHA256=nil` e `liveInstallationEnabled=false`. A `main` e o iPad permanecem intocados.

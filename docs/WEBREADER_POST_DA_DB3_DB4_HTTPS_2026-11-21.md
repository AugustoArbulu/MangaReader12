# WebReader iOS 12 — pós-DA DB3/DB4: HTTPS real, status 403 e laboratório físico separado

Data: 21/11/2026 UTC. Branch exclusiva de trabalho feat/chimera-updater-phase1-protocol-audit, PR #90 Draft. Nunca alterar main, Build70 física, biblioteca, banco offline, serviço CX ou aplicativo DA já instalados.

## Antecedentes imutáveis

- iPad iOS12.5.8, Chimera, serviço CX checkonlylab e app DA com Bundle ID separado: relatório físico do proprietário apresentou WR_DA=NOTICE_ACCEPTED após chamada de 7 bytes para 127.0.0.1:38973, UID/EUID 501/501.
- A fase DB2 criou observador Swift que reutiliza WebReaderUpdateChecker e WebReaderGitHubReleaseParser para consultar, SOMENTE quando explicitamente executado, o endpoint fixo https://api.github.com/repos/AugustoArbulu/MangaReader12/releases/latest. A chave editorial e seu pin ainda são nil; metadados não autorizam instalação.
- Releases listadas pelo conector GitHub: []; /releases/latest pelo conector retornou HTTP 404 no momento da consulta, antes da DB3. Este conector não usa a mesma rota IP que o runner macOS.

## DB3 — observação macOS real

Em https://github.com/AugustoArbulu/MangaReader12/actions/runs/44860381932 (SUCCESS), no commit ac08fb4f0463afa459ecef780769bc10a4abf7cf, um novo workflow de disparo único compilou o MESMO observador Swift, executou --selftest e --live no macOS usando URLSession, sem autenticação nem token, sem download de asset e sem instalar nada.

Resultado real do binário na CI:

```text
WR_DB2_SOURCE=FIXED_PUBLIC_GITHUB_HTTPS_METADATA_ONLY
WR_DB2_OBSERVATION=UNEXPECTED_HTTP_403
WR_DB2_PUBLIC_RELEASE_IS_SIGNED_PUBLISHER=NO
WR_DB2_OWNER_TRUST_PROVISIONED=NO
WR_DB2_PEER_AUTHENTICATED=NO
WR_DB2_IPA_DOWNLOADED=NO
WR_DB2_INSTALL_AUTHORIZED=NO
WR_DB2_INSTALL_PERFORMED=NO
```

O HTTP 403 demonstra uma resposta HTTP real na máquina de CI. A causa da recusa NÃO foi determinada: não confundir rate limit, restrição de acesso, egress do runner, origem da API nem política de proteção sem inspecionar cabeçalhos. A resposta 404 do conector é uma observação diferente, e não deve substituir ou corrigir artificialmente o 403 do cliente Swift.

## DB4 — QA iOS12 de HTTPS separada do WebReader

Proposta: reproduzir apenas o status HTTP e poucos cabeçalhos de diagnóstico no dispositivo físico, a partir de um aplicativo sandboxed único e independente, para comparar a execução macOS e iOS12. Sem tocar em nenhuma versão do WebReader.

- ci/chimera_db4_https_app_probe/main.m: app UIKit com botão Testar HTTPS GitHub, origin fixo no código, NSURLSessionConfiguration.ephemeralSessionConfiguration, apenas um GET explícito. O delegate rejeita redirecionamentos, cancela a resposta no recebimento dos cabeçalhos com NSURLSessionResponseCancel e não imprime nem persiste corpo.
- O relatório copia exclusivamente status, content-type, x-ratelimit-remaining, x-ratelimit-limit, x-ratelimit-resource, retry-after e server (valores truncados e sem quebra de linha), além de versão iOS, UID/EUID, Bundle ID e estados negativos de instalação/identidade editorial.
- ci/chimera_db4_https_app_probe/qa.entitlements: somente application-identifier WRTEST0001.com.example.WebReaderDB4HTTPSProbe, sem no-container, sem root, sem entitlements do serviço CX.
- ci/build_chimera_db4_https_qa_ipa.sh: compilação Objective-C ARM64 com mínimo iOS 12.0, assinatura ad hoc, Bundle ID com.example.WebReaderDB4HTTPSProbe, display WebReader HTTPS Teste; nenhuma instalação automática.
- ci/test_chimera_db4_https_qa_ipa.py: auditoria de Info.plist, mach-o, assinatura, entitlements, hash e ausência de AppInst/código de atualização.
- .github/workflows/chimera-db4-ios12-https-qa.yml: verifica escopo no Linux e gera artefato QA opcional no macOS; não publica Release nem instala no dispositivo.

### Gate físico opcional depois de CI verde

1. O proprietário transfere somente a IPA DB4 para o iPad via Filza/AppSync (Bundle ID distinto da Build70, do app DA e dos serviços).
2. Abre WebReader HTTPS Teste e toca UMA vez em Testar HTTPS GitHub.
3. Copia o relatório e envia o resultado. Se HTTP 403, os cabeçalhos rate-limit/retry-after podem ajudar; se HTTP 404, o iPad obteve resposta diferente da CI; se NSURLSession falhar, informar domínio e código sem inferir que a rede esteja bloqueada por jailbreak. Nenhum desses casos é uma atualização encontrada.
4. A DB4 não modifica o serviço CX, não faz WRCHK2, não baixa IPA, não acessa biblioteca, não cria chave de produção e não usa AppInst. O pacote é descartável.

## Limites da aprovação

Mesmo se a DB4 comunicar com api.github.com, o GitHub HTTPS e seu SHA não autenticam independentemente o publisher. Permanecem pendentes: pin P-256/SPKI independente, consentimento de instalação fora do cliente não confiável, custódia do mesmo arquivo instalado, anti-replay/downgrade, separação efetiva de armazenamento entre UIDs, backup/recovery e prova de instalação descartável. Manter WebReaderAppinstSocket.liveInstallationEnabled=false, productionPublicKeyX963=nil e independentlyProvisionedSPKISHA256=nil, sem Build71 e sem alteração da main.


## CI e artifact final (21/11/2026 UTC)

- GitHub Actions DB4: https://github.com/AugustoArbulu/MangaReader12/actions/runs/44860617523 — **SUCCESS 2/2** (escopo estático no Ubuntu e build/auditoria ARM64 iOS12 no macOS), no commit `fc128c216af05d88bb0727bd9e05b093cacf3c78`.
- Artifact: `WebReader-DB4-HTTPS-Only-iOS12-QA`, ID **14689757266**; ZIP contém uma IPA e seu `.sha256`, sem DEB, biblioteca ou recursos do WebReader. Disponibilidade de artifact GitHub Actions até 05/12/2026 UTC.
- Nome da IPA: `WebReader-DB4-HTTPS-Only-iOS12-adhoc.ipa`; **18.193 bytes**.
- SHA-256 recalculado depois de baixar e extrair ZIP na sessão: `602b03dfe1c9638eaa683bdeb366e8f7e2bd815fd07b9580d966e9ec4e5584f8`, igual ao manifesto publicado pela CI.
- Info.plist extraído e verificado: `CFBundleIdentifier=com.example.WebReaderDB4HTTPSProbe`, `MinimumOSVersion=12.0`; conteúdo inclui só executável, Info.plist e CodeResources/assinatura.
- A auditoria macOS `test_chimera_db4_https_qa_ipa.py` comprovou assinatura ad hoc e único entitlement `application-identifier`, cabeçalhos lidos por `NSURLSession` sem corpo, e ausência de comandos/símbolos de instalador. Nenhuma rede externa foi acionada pelo aplicativo em CI; sua requisição real ocorrerá somente após toque do proprietário no iPad.
- Nenhuma Build70, serviço CX, app DA ou branch `main` foi alterado; nenhuma Release ou atualização publicada.

**Estado físico:** DB4 pronta para ensaio manual opcional. A autorização explícita do proprietário para instalar o aplicativo descartável NÃO pode ser inferida da CI verde. Resultado de HTTP/TLS no iPad ainda não existe nesta data.

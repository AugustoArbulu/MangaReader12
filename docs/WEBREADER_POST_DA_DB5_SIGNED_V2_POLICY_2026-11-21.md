# WebReader iOS 12 — pós-DA DB5: fechamento do contrato assinado v2

Data: 21/11/2026 UTC. Trabalho exclusivamente em feat/chimera-updater-phase1-protocol-audit / PR #90 Draft. Sem alterações em main, Build70 instalada, biblioteca, banco, downloads, serviços CX/DA/DB4 ou Releases.

## Contexto preservado

- Evidência física CX: serviço Mobile launchd em localhost 38973 responde ao probe mesmo após fechar/reabrir NewTerm. Evidência DA: aplicativo iOS12 sandboxed com UID/EUID 501/501 recebeu WR_DA=NOTICE_ACCEPTED da mesma porta.
- Evidência DB4: app iOS12 recebeu HTTP 404 do endereço HTTPS de Releases com X-RateLimit-Remaining=58/60. Não há Releases publicadas conforme GitHub connector, portanto não existe Build71 real para baixar.
- Já existe validador ECDSA P-256 v2 implementado para iOS12: WebReaderUpdateManifestVerifier, WebReaderSignedReleaseTrustGate, WebReaderProductionPublisherTrust e checker de produção. O valor compilado productionPublicKeyX963 continua nil e independentlyProvisionedSPKISHA256 continua nil. Qualquer produção real permanece desativada.

## Divergências concretas identificadas na auditoria de código

1. **Produção com v1 no verificador de baixo nível:** o validador Python ci/webreader_update_manifest.py impedia expected_channel=production com schema v1, mas WebReaderUpdateManifestVerifier.swift antes admitia v1 assinado com channel=production quando invocado diretamente (a camada superior v2 já o barrava). DB5 incorpora essa invariância no próprio verificador de baixo nível. Isso evita que um novo caminho do código use o verificador sem o gate superior e reintroduza legado.
2. **Timestamp semanticamente inválido:** Python valida publishedAt com datetime.strptime, enquanto Swift aceitava uma string que atendesse apenas o padrão YYYY-MM-DDTHH:MM:SSZ, incluindo datas impossíveis. DB5 acrescenta validação Gregorian UTC com round-trip exato (anos bissextos válidos; fevereiro 30, hora 24, minuto 60, segundo 60 e ano 0000 rejeitados). Nenhuma hora do dispositivo, validade temporal, expiração ou antirreplay foi inferida.
3. **Base64 não canônico:** ambos os validadores decodificavam payload/signature Base64, mas não checavam se os bytes re-encodados preservavam exatamente a mesma string. DB5 compara a representação canônica original, bloqueando aliases que alteram bits de padding sem alterar os bytes assinados. Isso remove ambiguidade de representação; a ECDSA continua cobrindo o payload binário exato.

## Mudanças de escopo controlado

- MangaReader12/Core/WebReaderUpdateManifestVerifier.swift: três endurecimentos acima, sem alterar campos assinados, nomes de asset, endpoint, chave pública, aplicação de pacotes ou APIs públicas.
- ci/webreader_update_manifest.py: exige Base64 canônico para paridade com Swift. A regra production requires signed v2 e o calendário UTC já existiam em Python.
- ci/test_native_webreader_update_verifier.py e ci/test_webreader_update_manifest.py: conjuntos independentes de casos negativos usando assinaturas de chaves efêmeras, mais exemplos positivos de produção v2 e 29/02/2024 válido. Incluem Base64 com padding deliberadamente alterado que decodifica para os mesmos bytes do payload realmente assinado.
- .github/workflows/chimera-db5-signed-v2-policy-parity.yml: testes Python Linux/macOS, testes Swift Security.framework macOS, gates nativos de confiança e descoberta com production root ausente, compilação iOS12 ARM64 apenas para checar compatibilidade. Não gera IPA/DEB, não instala e não publica Releases.

## Riscos que permanecem NÃO resolvidos

- Uma chave gerada temporariamente em CI não atesta o publicador real. Para habilitar produção, o proprietário precisará gerar e custodiar uma chave editorial privada fora do repositório, verificar por canal independente a pública e o pin SPKI SHA-256 e provisionar a raiz em build revisada. DB5 não faz nenhuma dessas operações.
- Um manifesto assinado e compatível ainda não basta para instalar IPA: faltam vinculação imutável dos bytes ao instalador, assinatura nativa Apple do arquivo exato, diretório privado de UID efetivamente distinto no iOS, resistência a replay/rollback, consentimento confiável do proprietário e plano de backup/recuperação da biblioteca.
- NÃO reutilizar um sucesso WRNOTE2 de CX, o HTTP 404 da DB4 ou digest de GitHub Release como autorização. O serviço CX instalado continuará sem rede externa e sem código de instalação.
- Travas: WebReaderAppinstSocket.liveInstallationEnabled=false, WebReaderUpdateChannel.productionPublicKeyX963=nil, WebReaderProductionPublisherTrust.independentlyProvisionedSPKISHA256=nil, productionTrustGeneration=0, PR #90 Draft.

## Gate de validação

GitHub Actions dedicado: https://github.com/AugustoArbulu/MangaReader12/actions/workflows/chimera-db5-signed-v2-policy-parity.yml. Registrar o RUN ID e resultado após CI. Não substituir referência por 'verde' antes de obter conclusão dos jobs.


## CI definitiva aprovada em 21/11/2026 UTC

**GitHub Actions #44861557092 — SUCCESS, 3/3 jobs**, commit de código `68ef3cdb5014185e1c00fdcdb3de6545fed3c6fb`:
https://github.com/AugustoArbulu/MangaReader12/actions/runs/44861557092

- Ubuntu: todos os testes Python com chaves temporárias e regressões de manifestos P-256 **PASS**.
- macOS: todos os testes Python equivalentes **PASS**.
- macOS Swift: verificador Security.framework real, trust gate v2 independente de SPKI, produção sem chave e vínculo do envelope ao metadata de IPA **PASS**. Logs incluem `PASS DB5 Swift native: production v2, Gregorian UTC, canonical Base64`.
- Compilação do conjunto de verificadores Swift como módulo **ARM64 target iOS 12.0** **PASS**.
- Validações constantes: `liveInstallationEnabled=false`, chave pública de produção e pin independentes `nil`, geração de confiança 0.
- Nenhuma IPA, DEB, Release ou operação AppInst produzida/executada.

O workflow anterior #44861439733 falhou **somente no crosscompile auxiliar**: o arquivo WebReaderAppinstSocket.swift fora incluído isoladamente, mas dependia de WebReaderHelperPingProbe.swift, que não integrava esse teste. Todos os testes Swift/assinatura/Python anteriores a esse passo passaram. O commit `68ef3cdb5014185e1c00fdcdb3de6545fed3c6fb` removeu a dependência não relacionada da compilação isolada; as travas de AppInst permanecem verificadas em análise estática. A CI final confirmou novamente todo o conjunto.

**Gate DB5 aprovado:** os validadores Python e Swift ficam alinhados em produção v2, data UTC real e Base64 canônico, sem enrolar qualquer chave editorial verdadeira. Próximo trabalho distinto deve avaliar autorização do proprietário e custódia real dos bytes, ou a gestão independente da chave editorial, sem habilitar instalação com os testes DB5.

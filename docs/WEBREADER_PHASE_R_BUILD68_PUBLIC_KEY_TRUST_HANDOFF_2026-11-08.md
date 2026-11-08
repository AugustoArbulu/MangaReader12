# WebReader — Build68 experimental / Fase R: ponte de chave pública editorial SPKI → X9.63

**Data:** 2026-11-08
**Repositório:** AugustoArbulu/MangaReader12
**Branch:** feat/chimera-updater-phase1-protocol-audit
**PR:** #90 Draft, sem alteração na main.
**Última versão aprovada no iPad:** Build66. Build67 permanece pendente de aprovação física. Build68 sem IPA distribuída.

## Por que esta fase existe

A auditoria de release assinada no host já exige uma chave EC P-256
e um fingerprint SHA-256 **independente** do DER SubjectPublicKeyInfo (SPKI).
O verificador nativo iOS12 \`SecKeyCreateWithData\`, em contraste, recebe
a representação pública ANSI X9.63 **não compactada**, 65 bytes com
primeiro byte \`0x04\`.

Copiar bytes arbitrários do repositório, do manifesto recebido ou de
um link de Release para o campo \`productionPublicKeyX963\` seria uma falha
de confiança. A Fase R não configura esse campo: acrescenta uma prova
**offline, auditável e sem instalação** de que uma chave pública
previamente autenticada pelo proprietário produz as duas representações
compatíveis.

## Código

\`ci/build68_release_public_key_handoff.py\`

A função \`prepare_public_key_handoff(public_pem, independent_spki_sha256)\`:

1. Exige \`independent_spki_sha256\` com exatamente 64 caracteres hex minúsculos.
   Esse dado deve vir de um canal confiável **separado do release**.
2. Só aceita **um bloco PEM público**, sem chave privada, material extra,
   cadeia de blocos ou entradas não limitadas.
3. Confirma curva P-256 com OpenSSL, serializa SPKI DER canônico, confronta
   o fingerprint resultante ao informado **externamente** com comparação
   de tempo constante e exige ASN.1 exato para P-256 / ponto X9.63
   não comprimido.
4. Retorna somente \`canonical_spki_sha256\`, \`x963_public_key_hex\` e
   flags de negação explícita: chave de produção NÃO configurada,
   editor NÃO autenticado no dispositivo, release NÃO verificado,
   peer NÃO autenticado e instalação NÃO autorizada/executada.

Não há download, escrita de arquivos, importação em Swift ou chave privada
gerada pelo módulo. A geração de chaves ocorre apenas em fixtures efêmeras
das suítes de teste.

## Testes

- \`ci/test_build68_release_public_key_handoff.py\`: fingerprint correto,
  SPKI canônico, X9.63 65 bytes, chave e pin divergentes, pin ausente,
  curva errada, chave privada em lugar de pública, PEM duplicado, entradas
  malformadas, imutabilidade do recibo e ausência de permissão de instalar.
- \`ci/test_native_build68_release_public_key_handoff.py\`: cria uma chave
  descartável em diretório temporário; OpenSSL assina um payload sintético;
  a conversão SPKI → X9.63 é confrontada com o Security.framework real
  do macOS (\`SecKeyCreateWithData\`, \`SecKeyVerifySignature\`), incluindo
  recusa de mensagem adulterada e chave incorreta.
- \`.github/workflows/chimera-phase-r-public-key-handoff.yml\`: Linux para
  regressões do trust gate e macOS para interoperabilidade, sem IPA,
  appinst, jailbreak ou Release. O workflow não altera \`main\`.

**Aprovação da Fase R depende de CI do HEAD exato; nenhuma aprovação
de dispositivo iOS12 decorre do Security.framework em macOS.**

## Limites de confiança

- Um fingerprint é confiável **somente** se sua origem for previamente
  estabelecida fora do mesmo canal que entrega a chave. Fazer download
  de chave e fingerprint juntos não garante autoria.
- Uma chave pública compatível com Security.framework **não comprova**
  que ela pertence ao editor do WebReader. Essa associação precisa ser
  estabelecida por quem administra o projeto.
- A assinatura ad hoc de uma IPA comprova integridade de seu próprio código
  perante as regras de assinatura aplicáveis, **não** identidade editorial.
- Mesmo um manifesto v2 com assinatura válida não concede
  \`install_authorized\`. O helper Chimera precisa verificar os bytes
  reais e a autorização do solicitante em um mecanismo independente.
- O app conserva \`productionPublicKeyX963: Data? = nil\` e
  \`WebReaderAppinstSocket.liveInstallationEnabled = false\`.

## Próximo gate técnico

Antes de configurar uma chave editorial de produção:

1. O proprietário deve selecionar e proteger **a chave privada**
   fora do repositório e CI. Nenhum segredo de produção deve ir ao GitHub,
   IPA, logs, chat ou backup de biblioteca.
2. A **chave pública** e seu fingerprint devem ser conferidos por canal
   independente e imutável de provisionamento. Registrar versão e plano
   de rotação/revogação; os laboratórios de rotação da Build66 continuam
   restritos à análise.
3. Um build de avaliação separado pode futuramente consumir a chave
   pública confiável em Swift e validar um manifesto v2 real em
   modo exclusivamente read-only. É necessário CI, inspeção do binário
   e, por fim, QA em iOS12 antes de qualquer ativação operacional.
4. O instalador rootless/rootful via Chimera permanece bloqueado até
   atestar com segurança o processo requisitante e vincular autorização,
   consentimento, anti-replay e os bytes imutáveis da IPA ao helper.

Nenhum dos testes altera bibliotecas, downloads ou arquivos do iPad;
nenhuma IPA Build68 é distribuída nesta fase.


## Resultado final de CI (08/11/2026)

**GitHub Actions:** https://github.com/AugustoArbulu/MangaReader12/actions/runs/42450242694
**Commit de código testado:** \`72b98a0def04eedc75b5efe4ac72bf3a0ffa3c64\`
**Status:** **SUCCESS**, ambos os jobs concluídos.

- Linux / \`pure-host-trust-regression\`: passou a suíte nova de pin/SPKI e
  a regressão do verificador de release da Build66; o gate de produção
  continua com chave \`nil\` e instalação desabilitada.
- macOS / \`security-framework-interop\`: executou com sucesso a
  interoperabilidade real entre OpenSSL P-256/SPKI e Swift
  Security.framework/X9.63, inclusive testes negativos de assinatura.

A primeira execução identificou um erro apenas no helper de testes:
\`None\` explícito era confundido com o argumento opcional omitido. A suíte
foi corrigida para usar um sentinela distinto; os testes de rejeição de
entradas ausentes passaram na nova execução.

**Escopo da aprovação:** compilação/executabilidade de testes host-only.
Não é aprovação física do iPad, não valida identidade do solicitante do
Chimera e não cria/instala/atualiza IPA.

# WebReader iOS 12 — contrato de atualização assinado v2 (Build 66)

Data: 2026-11-07 UTC. Trabalho experimental na PR #90 Draft, branch
\`feat/chimera-updater-phase1-protocol-audit\`; \`main\` preservada.

## Motivo

O contrato v1 aceita exatamente
\`/releases/download/build{N}/WebReader-iOS12-unsigned.ipa\`,
enquanto a versão aprovada e instalada, Build65, foi empacotada como
\`WebReader-Build65-iOS12-adhoc.ipa\`. Aceitar qualquer arquivo com a extensão
\`.ipa\` ou substituir silenciosamente o nome de um asset afrouxaria a política.
Por isso, o v1 foi mantido sem modificação semântica e introduzimos v2 separado.

## v1 — legado (preservado)

- \`envelope.schemaVersion = 1\` e \`payload.schemaVersion = 1\`.
- Envelope: exatamente \`schemaVersion\`, \`algorithm\`, \`payload\`, \`signature\`.
- Assinatura sobre os bytes exatos do payload, \`ecdsa-p256-sha256\`.
- Campos de payload: \`schemaVersion\`, \`application\`, \`bundleId\`, \`channel\`,
  \`build\`, \`minimumIOS\`, \`ipaUrl\`, \`ipaSize\`, \`sha256\`,
  \`releaseNotes\`, \`publishedAt\`.
- Asset: \`https://github.com/AugustoArbulu/MangaReader12/releases/download/build{N}/WebReader-iOS12-unsigned.ipa\`.

## v2 — candidato ad hoc, não instalável nesta etapa

- \`envelope.schemaVersion = 2\` e \`payload.schemaVersion = 2\`, ambos iguais.
- Todos os campos da v1 **mais exatamente um campo assinado**:
  \`applicationIdentifier: "AR5SFJC432.com.example.MangaReader12.AR5SFJC432"\`.
- Asset nomeado por build, sem redirects/URLs alternativas:
  \`https://github.com/AugustoArbulu/MangaReader12/releases/download/build{N}/WebReader-Build{N}-iOS12-adhoc.ipa\`.
- \`application = WebReader\`, \`bundleId = com.example.MangaReader12\`,
  \`channel = development\`.
- SHA-256/bytes exatos, build monotonicamente crescente, iOS mínimo compatível
  com 12.5.8, limite de IPA 512 MiB, sem campos extras ou faltantes.
- O preparador \`ci/prepare_signed_webreader_update.py --schema-version 2\`
  **não aceita** IPA com outro nome, sem integridade \`codesign\` ou entitlement
  assinado diferente do instalado. Ele só gera manifesto **local**, 0600,
  com chaves provisionadas pelo proprietário **fora do repositório**.
- Ambos os verificadores, Python e Swift Security.framework, exigem a versão
  correta e a URL exata. A análise completa \`codesign\` é host-only/macOS.
- Nenhuma chave de release de produção está pinada no app
  (\`productionPublicKeyX963: Data? = nil\`); portanto, a checagem de manifesto
  pela aplicação real continua desabilitada por padrão.

## Matriz de segurança e testes

1. Aceitar v1 validamente assinado com asset v1 e campos v1.
2. Aceitar v2 validamente assinado com asset v2 e identidade instalada exata.
3. Rejeitar chave errada, assinatura adulterada, URL externa, asset errado.
4. Rejeitar campo v2 em v1, ausência de identidade v2, versões v1/v2 conflitantes,
   downgrade, SHA-256 e tamanho errados, campos extras, JSON duplicado.
5. Rejeitar IPA v2 sem assinatura ad hoc nativa macOS válida, entitlement
   incompatível/extra ou executável que não seja thin ARM64.
6. Confrontar a IPA Build65 aprovada com SHA-256, \`codesign\` e entitlement
   sem modificar o iPad; esse controle já obteve sucesso antes da v2.

Rotas: \`ci/test_webreader_update_manifest.py\`,
\`ci/test_native_webreader_update_verifier.py\`,
\`ci/test_build66_signed_release_preflight.py\`,
\`ci/test_build66_code_signature_gate.py\`,
\`.github/workflows/chimera-build66-preflight.yml\`.

## Bloqueadores NÃO resolvidos

- **Origem do publicador**: \`codesign -\` é ad hoc, autentica a integridade e
  entitlements mas **não a identidade do autor**. A confiança de origem requer
  chave de release genuína, gerenciada pelo proprietário e fixada previamente no app.
- **Distribuição real**: GitHub Releases de repositório privado pode exigir
  autenticação e pode não ser acessível pelo iOS12 como Release pública. Não
  publicar automaticamente nem presumir que a URL exista.
- **Instalador**: PING/PONG/HMAC não atestam o processo solicitante. O helper
  ainda precisa autenticação independente, decisão de consentimento de uma
  operação por vez, proteção contra replay/downgrade e verificação do objeto
  imutável efetivamente usado pelo instalador. Até lá,
  \`liveInstallationEnabled = false\`.
- **Aplicativo físico**: nenhum novo teste de IPA no iPad foi feito após a
  aprovação manual da Build65. Nem o manifesto v2 nem a auditoria de host
  autorizam substituí-lo.
- **Privacidade**: não coletar, enviar, publicar chaves privadas, entitlements
  de outros aplicativos, diretórios pessoais ou arquivos da biblioteca.

## Critérios para a próxima fase

Manter a PR #90 Draft e \`main\` intocada. Exigir CI Linux/macOS aprovadas,
documentar a autoridade pública e gestão da chave de release, e projetar
autenticação do helper em um canal distinto do serviço diagnóstico. Não
implementar instalação real antes de validação independente e um plano de QA
que preserve biblioteca e downloads offline do WebReader instalado.

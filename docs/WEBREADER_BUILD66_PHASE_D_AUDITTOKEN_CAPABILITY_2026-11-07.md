# WebReader Build66 — Fase D: audit token e viabilidade de identidade de peer no iOS12

**Data:** 2026-11-07 (UTC)  
**Repo/branch:** \`AugustoArbulu/MangaReader12\` / \`feat/chimera-updater-phase1-protocol-audit\`  
**PR:** #90, **Draft**, com base \`main\`, sem merge  
**Dispositivo:** iPad Chimera, iOS 12.5.8; Build65 instalada e aprovada fisicamente

## Hipótese e evidência

A Build63 já mediu PID do peer em conexões locais TCP/AF_UNIX no macOS, mas **PID não é identidade de código do WebReader**. Testar \`LOCAL_PEERTOKEN\` é um próximo passo observacional defensável. O cabeçalho Darwin \`sys/un.h\` define \`LOCAL_PEERTOKEN = 0x006\`, mas o código do iOS12/Chimera ainda NÃO foi exercitado no dispositivo.

Fontes externas para a investigação, NÃO provas de compatibilidade iOS12:
- XNU \`sys/un.h\`: https://www.newosxbook.com/src.php?file=%2Fbsd%2Fsys%2Fun.h&tree=xnu
- Apple Security \`SecCode.cpp\`: https://github.com/apple-oss-distributions/Security/blob/main/OSX/libsecurity_codesigning/lib/SecCode.cpp
- Documentação Apple SecCodeCopyGuestWithAttributes: https://developer.apple.com/documentation/security/seccodecopyguestwithattributes

O código Apple consultado traz \`SecCodeCreateWithAuditToken\`, \`SecCodeCopyGuestWithAttributes\` e \`SecCodeCreateWithPID\` sob \`#if TARGET_OS_OSX\`. Portanto, não pressupor que esses símbolos possam ser usados no iOS12. O diagnóstico inspeciona **somente presença de símbolo**, sem chamar qualquer função de validação de código nem extrair informações de terceiros.

## Pacote isolado criado na branch

| Caminho | Objetivo |
|---|---|
| \`ci/webreader_chimera_audit_token_probe66.c\` | CLI de autoensaio que cria um socket UNIX efêmero entre processos controlados, usa \`getsockopt(LOCAL_PEERTOKEN)\` e observa presença de símbolos com \`dlsym\` |
| \`ci/test_chimera_audit_token_probe66.py\` | Compila/executa quatro vezes no macOS, rejeita execução com argumentos de instalação |
| \`ci/build66_audit_token_capability_report.py\` | Parser rígido: somente disponibilidade e status de símbolos, sempre sem autenticação |
| \`ci/test_build66_audit_token_capability_report.py\` | 26 cenários de relatórios falsificados, saída inesperada, token/identidade vazados e tentações de elevar autorização |
| \`ci/package_chimera_audit_token_probe66.py\` | Empacota um único CLI \`/usr/local/bin/webreader-auditprobe66\` como .deb **sem hooks e sem daemon** |
| \`ci/test_chimera_audit_token_probe66_deb.py\` | Audita DEB, SHA256, ARM64 Mach-O, iOS mínimo 12.0, assinatura ad hoc e ausência de processos executores |
| \`.github/workflows/chimera-build66-audittoken-probe.yml\` | Runners macOS + Linux, executável iOS12 assinado e artifact opcional. Não gera IPA nem instala o app |

**Output do CLI:** exatamente seis linhas. Uma linha \`UNIX_PEERTOKEN=NONZERO|ZERO|UNAVAILABLE|TRANSPORT_FAILED\`, três linhas de presença de símbolos Security (\`PRESENT|MISSING|FRAMEWORK_UNAVAILABLE\`) e a última \`FINAL_INSTALL_AUTHORIZATION=DENIED\`. Nenhum byte do token, PID, UID, caminho pessoal ou segredo é exibido.

**Superfície de privilégio:** CLI recusa UID 0, não possui comando de instalação, serviço persistente, shell, launchd, \`appinst\`, IPA ou conexões de rede externas. O símbolo \`dlsym\` é utilizado apenas para saber se um símbolo existe; sua presença **não** prova que a API funciona ou autentica um app.

## Matriz de interpretação obrigatória

| Resultado | Interpretação permitida | Interpretação proibida |
|---|---|---|
| \`UNIX_PEERTOKEN=NONZERO\` | Kernel devolveu um campo token não vazio na conexão de ensaio | Processo identificado como WebReader |
| \`UNIX_PEERTOKEN=UNAVAILABLE\` | Opção indisponível/negada para aquele processo e ambiente | Exigir root, elevar entitlements, contornar sandbox |
| \`UNIX_PEERTOKEN=TRANSPORT_FAILED\` | Falhou transporte/fork/permissão; investigar sem tocar app | Reclassificar como sucesso |
| \`Security_* = PRESENT\` | \`dlsym\` achou um símbolo naquele binário/runtime | API usável, política de confiança aprovada |
| \`Security_* = MISSING\` | Símbolo não foi encontrado na biblioteca carregada | Diagnóstico prova impossibilidade absoluta de qualquer autenticação |
| \`FINAL_INSTALL_AUTHORIZATION=DENIED\` | Nenhuma operação foi autorizada | Pode iniciar \`appinst\` |

## QA e proteção da instalação existente

**Não há QA física da Fase D até o proprietário optar por executar o CLI no iPad.** Uma compilação no SDK 18.5 com deployment target iOS 12.0 valida formato/ligação de código, não confirma suporte de runtime no iOS 12.5.8.

Se o artifact da CI for aprovado, o pacote opcional se chamará:
\`WebReader-Chimera-AuditTokenProbe66-iOS12.deb\`. O artifact contém também os checksums e precisa ser transferido pelo usuário. Em teste opcional futuro, o pacote seria instalado com gerenciador \`dpkg\`, e o CLI executado **como mobile não-root** com:
\`/usr/local/bin/webreader-auditprobe66 selftest\`.

Não pedir ao usuário para desinstalar, atualizar ou reinstalar o WebReader principal. Nenhuma Build66 IPA foi produzida. Nenhum serviço PING existente é alterado. Em caso de falha, preservar fluxo manual Filza; não habilitar instalador automático.

## Condições de bloqueio para autenticação real

1. Confirmar **em iOS12/Chimera** se uma API consegue entregar token verdadeiro vinculado ao descritor de conexão, não uma string fornecida pelo cliente.
2. Confirmar se existe uma verificação de identidade de código da parte do helper que vincula token, processo em execução e assinatura/CodeDirectory confiáveis, sem race.
3. Distinguir assinatura de código ad hoc (integridade) de chave editorial de release pinada (origem).
4. Persistência/replay em armazenamento exclusivo do helper e verificação de bytes imutáveis usados pelo instalador, com consentimento inequívoco do usuário.
5. Se qualquer requisito não puder ser comprovado, manter o fluxo de IPA baixada/verificada e instalada manualmente pelo Filza.

**Garantias inalteradas:** \`WebReaderAppinstSocket.liveInstallationEnabled = false\`; \`productionPublicKeyX963 = nil\`; PR #90 Draft; \`main\` e Build65 preservadas.


## CI FINAL — compilação e pacote aprovados (07/11/2026)

- **WebReader Build66 iOS12 Peer Audit Token Capability (CLI-only)**:
  run **#13**, ID **42341357737**, **SUCCESS** nos jobs Linux e macOS.
  https://github.com/AugustoArbulu/MangaReader12/actions/runs/42341357737
- O job Linux aprovou **26 testes** de parser, inclusive reports falsificados,
  duplicações, flags de autorização não permitidas e tentativa de revelar tokens.
- No macOS, quatro autoensaios não-root devolveram
  \`UNIX_PEERTOKEN=NONZERO\` e presença dos três símbolos Security examinados.
  Todos terminaram com \`AUTHORIZATION=DENIED\`.
- Compile e assinatura ad hoc de binário **ARM64/Mach-O** com deployment target
  **iOS 12.0** passaram. A auditoria validou estrutura DEB, assinatura,
  entitlements mínimos e ausência de hooks/serviço instalador.
- **Artifact:** \`WebReader-Build66-AuditTokenProbe-CLI-only-iOS12\`,
  ID **13561995053**; contém
  \`WebReader-Chimera-AuditTokenProbe66-iOS12.deb\` e checksums.
- **SHA-256 do DEB:**
  \`e31f978f0f1b9136fb50c01358797a456f244c78c8f1642790745d6b9abe67cf\`.

O artefato é **opcional** e não foi executado no iPad. Uma correspondência de
símbolos macOS não prova a disponibilidade do iOS12 nem autoriza \`appinst\`.

## Fluxo alternativo — consulta independente do solicitante

Também foram implementados os arquivos:
\`ci/build66_requester_blind_check_policy.py\` e
\`ci/test_build66_requester_blind_check_policy.py\`.

- O cliente não pode fornecer **URL, IPA, comando, build, hash, manifesto,
  chave pública ou caminho**. A única mensagem admitida pelo laboratório
  é \`WR-CHECK-APPROVED-RELEASE-ONLY-V1\`.
- O host recebe manifesto v2, chave pública, SPKI pinado e arquivo
  diretamente de configuração de teste independente do cliente.
- \`verify_independently_pinned_v2\` valida assinatura e SHA256.
  O resultado só comunica candidato de release aprovado, com
  \`installation_authorized=False\`, \`requester_authenticated=False\` e
  \`user_install_consent_verified=False\`.
- São **16 testes negativos/positivos**, incluindo injeções de caminho,
  comando de instalação, chave falsa, build arbitrário, concorrência,
  downgrade e adulteração de IPA.
- **WebReader Build66 IPA Preflight Security QA run #105**, ID
  **42341357735**: **SUCCESS** nos dois jobs, Linux e macOS.
  https://github.com/AugustoArbulu/MangaReader12/actions/runs/42341357735

Esse desenho pode reduzir a necessidade de confiar no **solicitante da
consulta** (a simples solicitação não escolhe bytes, nem executa nada).
**Ele não resolve o consentimento confiável nem torna seguro que qualquer
processo dispare uma instalação.** Um cliente falso ainda poderia causar
negação de serviço ou iniciar verificações repetidas. Uma eventual operação
de instalação exigirá canal/autorização adicional e revalidação independente
do arquivo pelo helper.

## Pista para fase E (ainda não testada)

XNU expõe \`csops_audittoken\` e a operação
\`CS_OPS_CDHASH\` em documentação/código de kernel. Em implementações
documentadas, o kernel confere PID e versão do processo presentes no token
antes de consultar metadados de assinatura. Isso **sugere** um ensaio futuro
de relação \`LOCAL_PEERTOKEN\` -> \`csops_audittoken\` -> CodeDirectory hash
de **processo filho controlado**, sem divulgar hashes reais de terceiros.
Fontes de pesquisa:
- https://github.com/apple-oss-distributions/xnu/blob/main/bsd/kern/kern_proc.c
- https://github.com/apple/darwin-xnu/blob/main/bsd/sys/codesign.h

A presença em fontes modernas **não prova** disponibilidade/semântica no
iOS 12.5.8, e o jailbreak/ad hoc exigem análise separada da confiabilidade
da assinatura em runtime. Não implementar nem habilitar autenticação real
sem evidência na versão-alvo e modelo de ameaças validado.

# WebReader Build60 — Chimera iOS12, pacote único de QA

## Escopo e limite de segurança

A Build58 confirmou TCP PING/PONG no iPad. A Build59 confirmou HMAC com código temporário nos dois lados. O usuário solicitou uma única Build60 mais completa, sem microbuilds.

A prova HMAC não autentica a assinatura nem o Bundle ID da aplicação. É INSEGURO transformar o listener localhost em instalador sem resolver essa limitação. Portanto, a Build60 reúne o laboratório de atualização de um aplicativo DESCARTÁVEL, separado do leitor principal. Nenhuma IPA WebReader pode ser instalada pelo gate de laboratório.

## Conteúdo de UM artifact de GitHub Actions

Artifact: WebReader-Chimera-Build60-SignedQA-iOS12

- WebReader-IPC-Probe-iOS12-unsigned.ipa — Build60 diagnóstica independente, HMAC e PING.
- WebReader-Chimera-Ping-DIAG-iOS12 — apenas PING/HMAC, sem símbolos de instalação.
- WebReader-Chimera-Disposable-Gate-iOS12 — helper específico do teste de atualização descartável; não possui listener de rede.
- WebReader-Appinst-Disposable-v1-iOS12-adhoc.ipa e v2 — mesmo Bundle ID descartável, diferentes versões.
- Hashes SHA-256 de cada artefato.

O gate incorpora por compilação os dois hashes SHA-256 calculados após a construção das IPAs auditadas. Não aceita caminho, hash ou Bundle ID recebidos por TCP, Swift ou linha de comando. Os únicos comandos permitidos são selftest, inspect-v1, inspect-v2, install-v1, install-v2 e run-disposable-qa (orquestra v1→v2 em um comando, exigindo NEXT no meio). Instalação requer a frase literal I-CONFIRM-DISPOSABLE-ONLY.

A validação recusa arquivo symlink, hardlink, proprietário diferente do usuário mobile, permissão de escrita para grupo/outros, caminho diferente de /var/mobile/Documents, arquivo muito grande, magic bytes errados ou SHA-256 errado. É feita nova validação antes de chamar /usr/bin/appinst. Existe risco residual de alteração entre validação e leitura pelo instalador, por isso o gate NÃO deve ser reaproveitado para atualização do WebReader principal.

O app descartável tem Bundle ID com.example.WebReaderAppinstDisposableTest e grava uma chave NSUserDefaults na v1 para a v2 verificar se foi preservada. Não acessa Biblioteca, fontes, capítulos nem configurações do WebReader.

## CI da Build60

A workflow .github/workflows/chimera-mobile-ping.yml executa: regressão Swift/C do IPC e HMAC, testes C com appinst FALSO e conteúdo NÃO instalável, criação e auditoria das IPAs descartáveis arm64/iOS12, compilação da gate com hashes pinados, assinatura mínima com entitlement no-container, compilação da IPA de diagnóstico CFBundleVersion 60 e auditoria dos checksums.

Nenhum appinst verdadeiro é invocado pela CI. O helper HMAC continua separado e sem instalação.

## Única sessão de QA no iPad, após CI verde

1. Baixar o ZIP único. Pelo Filza, transferir somente o gate e as duas IPAs descartáveis para /var/mobile/Documents. Se desejar testar o botão de roteiro, instalar a IPA de diagnóstico Build60 sobre o IPC Test; ela não substitui o WebReader Build56.
2. No NewTerm 2 como mobile UID501, executar **um único comando**:

    /var/mobile/Documents/WebReader-Chimera-Disposable-Gate-iOS12 run-disposable-qa I-CONFIRM-DISPOSABLE-ONLY

3. Esse comando primeiro inspeciona e verifica SHA de AMBAS as IPAs antes de instalar a v1. Após a confirmação de que a v1 foi instalada, abrir WR Appinst Test v1 para criar o registro local.
4. Voltar ao terminal, digitar NEXT e Enter. O gate revalida o hash da v2 e instala apenas a atualização descartável.
5. Abrir WR Appinst Test v2 e confirmar Persistência dos dados: SIM. Copiar as linhas de resultado do NewTerm, sem compartilhar segredos. Se digitar qualquer coisa diferente de NEXT, a segunda instalação não é executada.

Se aparecer zsh: killed, assinatura inválida, SHA diferente ou appinst falhar: PARAR. Não fazer ldid -S manual no gate assinado pela CI e não executar como root.

## O que ainda impede atualizar o próprio leitor automaticamente

- Autorização e autenticação efetiva do aplicativo solicitante, incluindo proteção contra processos locais no jailbreak (não resolvida por código HMAC).
- Serviço persistente com bootstrap de uma vez e modelo de privilégios revisado.
- Validação de publisher/IPA independente do cliente e proteção ponta a ponta contra troca de arquivos.
- Teste físico de instalação e persistência do app descartável.
- Backup e confirmação específica do usuário para atualizar o WebReader.

Estado preservado: PR #90 Draft na branch feat/chimera-updater-phase1-protocol-audit, main intocada, Build56 principal preservada, nenhum release publicado e nenhuma instalação real executada até teste físico autorizado.

## Correção de assinatura após QA física inicial (06/11/2026)

Usuário tentou instalar v1 com o gate Build60 aprovado e obteve `MIInstallerErrorDomain Code=3: Application is missing the application-identifier entitlement`. A conferência de ambas as IPAs pelo gate SHA-256 foi bem-sucedida, mas `appinst` falhou na validação do iOS. Nenhuma v1 foi instalada e nenhuma v2 executada.

Correção na branch experimental: gerar **duas IPAs ad-hoc assinadas**, cada uma com entitlement `application-identifier` igual a `WRQA000001.com.example.WebReaderAppinstDisposableTest`, via `codesign` no pacote `.app` depois do Info.plist. O prefixo é um identificador sintético exclusivo do laboratório, **não** Team ID de assinatura Apple e **não** autentica autor no iOS sem jailbreak. Ambas as versões compartilham o mesmo App ID, necessário para testar atualização. CI agora audita assinatura de ambos os `.app`, suas entitlements exatas, `CodeResources` e igualdade dos bytes do segmento Mach-O __TEXT,__text. Gate e nomes de IPAs foram atualizados para sufixo `-adhoc.ipa` e hashes recompilados, para que o pacote antigo `-unsigned.ipa` não seja aceito por engano.

**Não reutilizar o ZIP anterior** `WebReader-Chimera-Build60-OneBatch-iOS12`; aguardar CI verde do novo `WebReader-Chimera-Build60-SignedQA-iOS12`. Ainda não há prova física de instalação da versão ad-hoc.

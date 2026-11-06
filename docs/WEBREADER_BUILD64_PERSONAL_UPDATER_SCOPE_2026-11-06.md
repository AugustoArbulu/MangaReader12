# Build 64 — escopo proporcional de atualizações para uso pessoal

Data: 2026-11-06. Projeto privado de uso individual no iPad iOS 12.5.8 com Chimera. Decisão solicitada pelo usuário: priorizar simplicidade e praticidade em vez de um mecanismo corporativo de autenticação/assinatura.

## Estado confirmado

- Build 56 WebReader: versão estável; preservar dados e downloads.
- Build 60: o usuário confirmou atualização v1→v2 via `appinst` num aplicativo descartável, sem demonstrar migração do WebReader real.
- Build 61 FIX1: helper TCP PING/PONG persistiu após fechar NewTerm e reabrir o cliente; teste após reinício completo ainda pendente.
- Build 62: a instalação pelo cliente WebReader está desabilitada por padrão; consulta/download/exportação continuam.
- Build 63: QA físico no iPad retornou `PEER_PID=MATCH AUTHORIZATION=DENIED` para `TCP_LOOPBACK` e `UNIX_LOCAL`. Isso não autentica o aplicativo.

## Revisão da prioridade

Não bloquear a entrega do atualizador pessoal apenas para alcançar um sistema de identidade corporativo ou uma cadeia independente de assinaturas P-256. Manter, porém, limites mínimos: um helper com privilégios pode ser acionado por outro processo local se aceitar comandos sem restrições; `localhost` e PID `MATCH` não são autenticação.

### Fase A — usável já, zero risco novo do helper

O app consulta GitHub Releases, baixa IPA por HTTPS, compara SHA-256 divulgado, inspeciona ZIP e `Info.plist` (bundle ID e versão), apresenta versão e mudança ao usuário e permite **Compartilhar/Exportar para Filza**. O usuário aprova manualmente no Filza; não é instalação automática. Hash publicado junto à IPA serve para consistência, não comprova identidade independente do editor.

### Fase B — atualização em um toque, apenas após laboratório isolado

Implementar um helper de produção **separado do serviço PING** e incapaz de receber URLs, caminhos arbitrários ou Bundle IDs escolhidos pelo cliente. Aceitar somente IPA previamente verificada em local controlado; comparar Bundle ID exato do WebReader, versão superior e hash do arquivo imediatamente antes da chamada de instalação. Exigir confirmação explícita dentro do app e credencial/pareamento local por instalação, não embutida estaticamente no IPA, com validade curta e negação de replay. Validar operações negativas: cliente não pareado, arquivo trocado, bundle diferente, hash errado, versão antiga e consentimento ausente. Não alegar defesa completa contra atacante com root/jailbreak, pois este já tem acesso amplo ao dispositivo.

Nenhum daemon que instala IPAs deve ficar acessível a qualquer processo só porque conecta em `127.0.0.1`. Antes de habilitar o `appinst` via helper, documentar explicitamente limitações da credencial e revalidar no iOS 12 físico com app descartável. Investigações de audit token tornam-se **opcionais** e não bloqueiam o MVP manual.

## Decisão de integração

Preservar `main`, Build 56 e helper PING da Build 61; PR #90 continua experimental. Evitar migração destrutiva de dados, desinstalação e atualização silenciosa. A prioridade é funcionalidade pessoal com controles simples e confiáveis, não certificação de segurança de nível empresarial.

## Critérios de conclusão

1. MVP manual: teste iOS 12 de download, validação da IPA e exportação para Filza; preservação de biblioteca após atualização somente com backup.
2. Helper eventual: testes de rejeição explícita de pedidos inválidos, teste em app descartável e consentimento, sem abrir caminho de instalação arbitrária.
3. Somente após QA e backup, experimento opcional no WebReader real.

## Decisão do usuário — distribuição das IPAs (06/11/2026)

- **Temporariamente, durante o desenvolvimento:** entregar as IPAs de QA do WebReader por e-mail para `gutoarbulu@icloud.com`, quando uma build instalável estiver disponível e o usuário pedir o envio. A instalação continuará manual no Filza. Para anexos além do limite do provedor, enviar link direto do artefato/release do GitHub, sem afirmar que o arquivo foi anexado.
- **Objetivo final obrigatório:** o próprio WebReader deverá consultar o GitHub, detectar a nova versão, obter a IPA do Release, verificar integridade e identidade do pacote, solicitar confirmação explícita e instalar a atualização no dispositivo com o helper compatível com Chimera/`appinst`, sem e-mail, computador nem Filza.
- **Após validação do atualizador integrado:** parar de usar o e-mail como mecanismo rotineiro de distribuição; e-mail somente como alternativa excepcional se o usuário solicitar ou houver falha de atualização. Não interpretar a preferência como autorização para envios automáticos em background.
- **Preservação:** atualizar o mesmo app sem desinstalar, com backup e validação de manutenção da biblioteca, configurações e downloads. Nenhuma instalação silenciosa ou disparada por outros processos locais.

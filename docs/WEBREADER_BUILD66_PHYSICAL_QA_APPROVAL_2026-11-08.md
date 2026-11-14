# WebReader Build 66 — relato de QA físico no iPad (2026-11-08)

**Origem:** confirmação direta do proprietário em conversa de teste.
**Dispositivo informado:** iPad, iOS 12.5.8, Chimera.
**Versão testada:** Build 66, disponibilizada como IPA manual de QA na Fase L.
**Versão anterior:** Build 65.
**Branch:** `feat/chimera-updater-phase1-protocol-audit` · PR #90 Draft.
**Não realizar merge na `main`, instalação ou publicação automática por causa deste registro.**

## Resultados relatados pelo usuário

- Depois da explicação da nova tela de atualizações, o usuário declarou: **“tudo parece está funcionando”**.
- À pergunta direta sobre **biblioteca permanecer intacta** e sobre **capítulos baixados anteriormente ainda abrirem normalmente sem Wi-Fi**, respondeu afirmativamente (**“s”**).
- Portanto, os testes físicos reportados permitem marcar **biblioteca preservada** e **leitura offline funcional** no upgrade para a Build 66.
- A experiência geral foi relatada como positiva, mas **não há checklist individual detalhado** para todas as fontes, casos de erro e métodos de download.

## Alcance desta aprovação

**Aprovada apenas no escopo relatado pelo usuário:**
preservação de biblioteca e capítulos offline, com funcionamento geral aparentemente normal no dispositivo.

**Não afirmar que já foram validados especificamente:**
atualização automática via appinst, identidade criptográfica do cliente iOS12, manifesto editorial de produção, instalação não supervisionada, atualização a partir de GitHub Releases privado, reversão de banco Build66 → Build65, nem testes individuais exaustivos de cada fonte.

O canal de instalação automática do WebReader continua **desabilitado**:
`WebReaderAppinstSocket.liveInstallationEnabled = false`;
a chave editorial de produção segue ausente:
`WebReaderUpdateChannel.productionPublicKeyX963 = nil`.

## Orientação do próximo marco

Manter a Build66 como referência **estável no escopo testado** para desenvolver o próximo incremento do atualizador. Evitar alterações destrutivas, downgrade automático ou operações no banco de dados. Preferir planejamento de autorização independente do helper e de distribuição de releases assinados, sem depender de `LOCAL_PEERTOKEN`, que se mostrou indisponível no ensaio físico do Chimera.

**Nenhuma IPA nova foi publicada/instalada por este registro.** A `main` permanece inalterada.

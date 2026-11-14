# WebReader Build70 — Fase CN: trigger não confiável e validação independente

**Data:** 10/11/2026. **Branch:** `feat/chimera-updater-phase1-protocol-audit`. **PR #90 Draft**, `main` intacta. **Objetivo:** tomar uma decisão de arquitetura informada pelos testes físicos CL/CM, sem exigir novos testes do usuário.

## Evidência física real que motivou a mudança

No iPad iOS 12.5.8 com Chimera, o teste CL produziu três `INCONCLUSIVE` (o terceiro foi transcrito como `MINCONCLUSIVE`). O pacote corrigido CM v0.2.0 produziu **três `TOKEN_UNAVAILABLE AUTHORIZATION=DENIED`** em A, B e C. Isso mostra que o servidor local recebeu as mensagens dos clientes, mas não obteve os dados necessários para comparar as identidades.

No código `ci/build66_separate_signed_peer_lab.c`, `TOKEN_UNAVAILABLE` engloba **quatro possíveis problemas**: `getsockopt(SOL_LOCAL, LOCAL_PEERTOKEN)` falhou; comprimento do token inesperado; PID zero; ou pidversion zero. Sem diferenciar `errno`, nenhuma dessas causas pode ser atribuída definitivamente. A família Darwin de opções `LOCAL_PEERTOKEN` usa o código `0x006`, mas sua existência nos headers não prova disponibilidade no runtime Chimera iOS12.

### Decisão técnica

**Não tratar LOCAL_PEERTOKEN, PID, UID, bundle ID, assinatura ad hoc do aplicativo ou HMAC de pareamento como autorização do instalador.** Não há identidade de processo confiável comprovada no dispositivo. Continuar repetindo diagnósticos sem uma hipótese específica validável criaria trabalho sem aproximar uma atualização segura.

Em vez disso, separar o sistema em duas superfícies:

1. **Trigger não confiável (possivelmente qualquer cliente local):** permite, no máximo, pedir uma *verificação de atualização somente leitura*. O protocolo não recebe **URL, caminho da IPA, hash, versão, chave, assinatura, desafio, consentimento nem código de instalação**. Deve ser limitado por tempo/volume e não pode executar `appinst`. O cliente pode estar comprometido: mesmo assim, não é autoridade para escolher conteúdo.
2. **Fluxo independente de confiança** (ainda **não implementado**): um serviço minimalista, cujo material de verificação pertence ao proprietário e não pode ser alterado pelo app, busca **origem fixa configurada e controlada**, valida manifesto assinado v2 e identidade da release, verifica versão superior e antirreplay/rollback, obtém por conta própria bytes da IPA vinculados à assinatura, confere assinatura nativa e SHA-256 no mesmo objeto de arquivo que será consumido no instalador e exige consentimento proprietário originado de contexto confiável. Só então pode iniciar instalação. Nenhum campo recebido do trigger influencia escolha de artefato ou permissão.

A separação evita tornar a indisponibilidade do token do peer um bloqueio arquitetural absoluto. **Ainda não prova que o fluxo de instalação será possível**, nem evita que clientes não confiáveis tentem provocar verificações ou spam: limites globais e controle de recursos são obrigatórios.

## Protótipo CI — apenas modelo em memória

`ci/build70_cn_untrusted_check_only_gate.py`: aceita somente os **sete bytes** `WRCHK2\n` (nada após a quebra de linha) e produz apenas uma observação de pedido de checagem, com intervalo mínimo de 60 segundos em uma instância. **Não abre socket, não busca versão, não toca arquivos, não instala, não chama subprocess/appinst.**

O resultado é tipado `CheckOnlyDecision`, tem `source_caller_untrusted=True` e **todos os campos de autorização false**: nenhuma URL/caminho/hash/chave externa é aceita, nem há assinatura/publisher/consentimento validado.

Testes `ci/test_build70_cn_untrusted_check_only_gate.py` cobrem bytes alterados, injeção de URL/caminho/consentimento, frame `WRINST1`, spam, clock inválido/recuado, falsa identidade de processo, negação de instalação e ausência de APIs privilegiadas. CI: [Phase CN untrusted trigger host safety](https://github.com/AugustoArbulu/MangaReader12/actions/workflows/chimera-build70-phase-cn-untrusted-trigger.yml).

O protótipo **não é chamado pelo aplicativo**; não tem root, rede, loopback, sincronização nem persistência. A aprovação de CI valida somente a política de formato. Uma fila real precisa ter limite global entre processos, proteção contra flood e uma única fonte fixa para checagem.

## Bloqueios para automatização real

- O proprietário precisa provisionar de forma independente a **chave pública editorial** e seu pin em app/helper; não criar chave privada de produção no GitHub/CI/chat, não habilitar publisher trust a partir de um simples relatório do aplicativo.
- Definir origem fixa para manifest/IPA, política de TLS e readback, verificar envelope assinado com **número de build e digest do mesmo objeto** e identidade nativa da IPA.
- Provar um caminho de **mesmos bytes verificados até `appinst`**, eliminando TOCTOU na passagem por pathname; staging modo 0400 não é imutável.
- Implementar autorização local separada e inequívoca do proprietário e replay journal de propriedade adequada, persistente/atômico.
- Conter e auditar helper privilegiado (se necessário) e restaurar/recuperar dados; realizar QA física iOS 12 antes de ativação.

**Hard stops:** `WebReaderAppinstSocket.liveInstallationEnabled = false`; `productionPublicKeyX963 = nil`; `independentlyProvisionedSPKISHA256 = nil`; `main`, Releases e Build70 do iPad intocados. Sem IPA nova, DEB novo, serviço instalado ou alteração da biblioteca nesta fase.

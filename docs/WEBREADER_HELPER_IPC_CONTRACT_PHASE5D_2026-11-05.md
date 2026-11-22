# WebReader — Fase 5D: contrato do futuro helper Chimera (somente especificação)

**Data:** 2026-11-05  
**Projeto:** iOS 12.5.8 / Chimera rootful / WebReader Build 56 aprovada  
**Branch:** `feat/chimera-updater-phase1-protocol-audit` / PR #90 Draft

## 1. Estado: NÃO É INSTALADOR

Esta fase implementa **somente** o parser de referência, offline, para uma
mensagem mínima de solicitação de revisão, em
`ci/webreader_helper_request_contract.py`. O módulo é executado no host CI,
não faz parte do target do aplicativo e **não é um daemon, serviço IPC, helper
privilegiado nem executor**. Não contém execução de comandos, download,
descompactação, instalação ou escrita em arquivos.

A chave de produção do WebReader continua `nil` no iOS. A Build 56 instalada
e a `main` não são alteradas. O iPhone do usuário não participou destes testes.

## 2. Ameaças e fronteiras de confiança

Um aplicativo UIKit **não pode atribuir a si mesmo** a autorização de um daemon
rootful. O futuro helper deve considerar todo IPC, manifesto, arquivo de IPA,
hash relatado, caminho, nome de pacote e parâmetro fornecido pelo app como
**não confiável**.

Principais ameaças:

- Instalação solicitada por outro app, cliente forjado ou serviço aberto em rede.
- Comandos/argumentos livres (`sh`, `appinst`, URL arbitrária, caminhos
  personalizados), redirecionamento de alvo e instalação de outros Bundle IDs.
- Replay de solicitação ou autorização após timeout/cancelamento.
- Troca do arquivo IPA entre validação e execução (TOCTOU), symlink e hardlink,
  substituição de arquivo via diretório gravável e descritor com acesso indevido.
- Manifesto falso, assinatura inválida, downgrade, IPA corrompida e
  incompatibilidade de iOS.
- Origem do `appinst` não comprovada, AppSync incompatível e perda do sandbox.
- Vazamento de log contendo tokens, paths privados ou query temporária do CDN.

## 3. Envelope proposto, sem autoridade de instalação

Mensagem JSON UTF-8 de até **2048 bytes**, com seis chaves exatas. Exemplo
fictício — não usar em produção:

```json
{
  "schemaVersion": 1,
  "operation": "request-install-review",
  "bundleId": "com.example.MangaReader12",
  "build": 57,
  "manifestSHA256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "nonce": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
}
```

Restrições: JSON objeto, chaves duplicadas proibidas (também via escapes
Unicode), sem campos adicionais; versão de protocolo exatamente 1, operação
**somente revisão**, bundle fixo, build inteiro positivo de 32 bits, digest e
nonce em hex minúsculo com 64 caracteres, distintos. Strings JSON não podem
fornecer **path, URL, shell, comando, argv, assinatura, chave ou autorização**.

O `nonce` da mensagem serve apenas como correlação. O futuro helper deverá
impor **unicidade e expiração por estado de servidor**, vinculados à sessão
autenticada; validar sintaxe de 64 dígitos não prova imprevisibilidade.
O hash `manifestSHA256` serve apenas para localizar candidatos; o helper
não deve confiar no hash apresentado, mas obter/verificar os bytes novamente.

O protótipo retorna apenas um objeto de dados de revisão e logs redigidos.
Qualquer consumo futuro que trate o resultado do parser como aprovação de
instalação será uma vulnerabilidade.

## 4. Gates antes de qualquer helper real (todos obrigatórios)

1. **Procedência:** origem oficial do `appinst` comprovada independentemente,
   hash do executável comparado ao binário instalado. Hash de um espelho não
   autentica o publicador. AppSync compatível e Chimera ativo verificados.
2. **Transporte:** escolher IPC local capaz de autenticar a identidade do
   processo/credenciais do cliente pelo sistema e de verificar a assinatura de
   código quando disponível; permissões mínimas. Não assumir que
   `CFMessagePort` por si só identifica um cliente. Sem socket aberto à rede.
3. **Chave/manifesto:** chave pública real fixada **independentemente no
   helper** e no app, com rotação/revogação definida; assinatura ECDSA-P256
   sobre os bytes canônicos e JSON estrito.
4. **Arquivo:** helper deve adquirir um descritor para arquivo **regular**
   permitido, sem seguir symlink; validar `fstat`, identidade, tamanho,
   SHA-256, estrutura ZIP, `Info.plist`, Bundle ID, build superior e
   `MinimumOSVersion`. Revalidar sobre **os mesmos bytes/descritor** que
   serão usados na instalação; não confiar na pré-auditoria do app.
5. **Operação:** consentimento explícito na superfície de confiança
   apropriada, um pedido por vez, timeout, cancelamento, anti-replay e
   confirmação de backup antes de qualquer tentativa.
6. **Execução restrita:** somente `/usr/bin/appinst` autenticado, somente
   IPA do WebReader e somente após todos os gates, **sem shell** ou argv
   determinado pelo cliente. Falha deve encerrar a transação sem retry
   infinito. Nada disso foi implementado nesta fase.
7. **Recuperação:** testar instalação isolada no aparelho descartável, depois
   cópia separada de dados de teste, e conferir identidades de app, SQLite,
   biblioteca, filtros e capítulos offline. Exportar `.mr12backup` e copiar
   arquivos offline em backup separado antes de atualizar o app real.

## 5. Testes offline

`ci/test_webreader_helper_request_contract.py` valida envelope aceito,
operação inválida, Bundle ID indevido, build malformada, chaves desconhecidas,
payload com shell/path/URL/argv, digests/correlators errados, JSON duplicado,
UTF-8 inválido, tokens não finitos e tamanho maior que o permitido.

**Limite de validação:** testes do parser NÃO provam credenciais de IPC,
execução real de `appinst`, compatibilidade Chimera, instalação por
`LSApplicationWorkspace`, proteção de diretórios ou preservação de dados.
A aprovação da CI autoriza apenas continuar a pesquisa do protocolo.

## 6. Próximo gate

- Encerrar CI do HEAD exato do PR #90 e corrigir eventuais falhas.
- Se desejado, coletar **somente** SHA-256 local de `/usr/bin/appinst` no
  iPhone (sem executar o binário), comparando ao hash do executável no DEB.
- Obter fonte oficial verificável, manter helper inteiramente fora do bundle
  normal e desenvolver testes de identidade/arquivo/replay separados antes
  de considerar qualquer execução privilegiada.
- Continuar com PR **Draft**, sem merge nem Release/Build 57.

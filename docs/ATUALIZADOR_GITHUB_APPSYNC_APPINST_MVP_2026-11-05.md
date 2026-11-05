# WebReader iOS 12 — atualizador pessoal GitHub + AppSync + appinst

**Direção decidida em 05/11/2026:** parar de criar camadas de auditoria
antes de um fluxo funcional. Objetivo: verificar a versão publicada no
GitHub, baixar a IPA no app, confirmar e instalar por meio do appinst
que já está no iPhone com Chimera + AppSync Unified.

## Implementado na branch experimental

1. A tela Atualizações do WebReader consulta manualmente a API
   pública fixa `api.github.com/repos/AugustoArbulu/MangaReader12/releases/latest`.
   Não requer token do GitHub nem chave adicional de assinatura de release.
   Um HTTP 404 é interpretado como ausência de release publicado.
2. O release precisa ter tag canônica `build57`, `build58` etc.,
   ser publicado (não draft/prerelease), e conter exatamente um asset
   `WebReader-iOS12-unsigned.ipa` com tamanho válido, estado `uploaded`,
   URL HTTPS exata deste repositório e digest GitHub `sha256:<64 hex>`.
   JSON inválido, asset ambíguo e caminhos de outro repositório são rejeitados.
3. O botão **Baixar IPA verificada** solicita confirmação explícita.
   `WebReaderIPAStager` transfere apenas via GitHub HTTPS/CDN
   permitido, confere o SHA-256 e audita ZIP/Info.plist, bundle ID,
   build e mínimo iOS com o auditor nativo. Download só armazena a IPA.
4. Após sucesso, a interface oferece **Compartilhar IPA verificada**,
   permitindo exportar o arquivo para um mecanismo manual já instalado
   no aparelho. Não existe instalação silenciosa.
5. **Abrir GitHub Releases** permite ver lançamentos no navegador.
   O app de diagnóstico IPC separado continua isolado e sem tela
   de download.
6. O canal anterior baseado em manifesto assinado fica no repositório
   e mantém seus testes; não é requisito para o modo pessoal via
   GitHub Releases. A origem do hash neste modo é o próprio GitHub,
   não uma assinatura editorial P-256 independente.

## O que falta para a função totalmente automática

**Uma ponte local mínima para chamar `appinst <caminho-IPA>` após
confirmação, e somente com uma IPA já verificada.** O app iOS pode
ser impedido pelo sandbox de executar ferramentas do jailbreak;
ainda não foi comprovado no dispositivo. Precisamos primeiro testar
o socket já compilado, com processo separado **sem root**, no
aplicativo IPC Test. Se possível, reutilizar essa comunicação para
enviar um pedido de instalação controlado. Se não funcionar, ajustar
o transporte com o mínimo necessário.

O appinst oficial aceita exatamente um argumento IPA. Atenção:
a execução da própria ferramenta cria outra cópia temporária
e pode fazer limpeza de diretórios de sessões anteriores até
quando chamada para exibir ajuda. Por isso, **não** executar
appinst automaticamente nem como teste de interface por enquanto.

## Critérios práticos de conclusão

- GitHub Release real, público, contendo a IPA pretendida e digest
  SHA-256; nenhum arquivo de Actions deve ser tratado como release.
- Download no iOS12 via HTTPS com IPA válida, sem falhas de TLS/CDN.
- Comunicação local testada no Chimera, depois teste isolado de
  appinst com um **app descartável** e confirmação do usuário.
- Backup portátil, Biblioteca e downloads offline verificados antes
  da primeira atualização real do WebReader.
- Instalação do mesmo Bundle ID e versão maior preservando
  sandbox/dados; nunca remover e reinstalar o app principal.
- Manter Build56 instalada e `main` intocadas até validação final.

**Estado:** PR #90 Draft na branch
`feat/chimera-updater-phase1-protocol-audit`, sem merge, sem execução
de appinst, sem nova IPA instalada no iPhone. A UI e o parser de
GitHub precisam de CI verde no commit exato antes de uso físico.


## Ponte CLI para appinst (05/11/2026)

Foi adicionado ci/webreader_appinst_bridge.c. Este executável C
SEPARADO DO APLICATIVO contém uma chamada real a appinst, portanto
não deve ser executado no iPhone para instalar o WebReader agora.

Operações:
- selftest: comprova execução como usuário mobile; recusa root.
  Não usa appinst.
- inspect IPA SHA256: checa nome, caminho do container WebReader,
  arquivo regular sem symlink/hardlink, ownership/permissões,
  limite de tamanho, prefixo PK e SHA-256. Não instala.
- install-confirmed IPA SHA256 I-CONFIRM-INSTALL: somente para
  testes futuros em aplicativo descartável após consentimento.
  Revalida o arquivo e chama o binário fixo /usr/bin/appinst por
  posix_spawn, sem shell nem path de executável fornecido por IPC.

O caminho da IPA no iOS deve ser o staging conhecido:
  /private/var/mobile/Containers/Data/Application/<UUID>/
  Library/Application Support/WebReaderUpdates/
  WebReader-build<build>-<UUID>.ipa
O alias padrão /var/mobile/... também é aceito.

A suíte ci/test_webreader_appinst_bridge.py usa um executável
FAKE no macOS, enraizamento de teste compilado especificamente
para a CI, e conteúdo sintético que NÃO é IPA instalável.
Ela testa confirmação, SHA, prefixos, versões de filename,
symlinks/hardlinks, comportamento em falha e argumentos
transmitidos exclusivamente ao executável fixo.

CI compila um Mach-O ARM64 iOS12 assinado ad hoc e publica somente
artefato de Actions denominado
WebReader-Appinst-Bridge-iOS12-MOBILE-PREVIEW. Não é Release,
não é .deb e não é automaticamente instalado no telefone.

### Limitações explícitas

- Este SHA é fornecido pelo chamador: não substitui a validação
  GitHub HTTPS, nem prova assinatura independente de editor.
- O programa C não implementa auditoria completa ZIP/Info.plist;
  o WebReaderIPAStager deve tê-la realizado antes.
- O descritor de IPA é fechado antes de appinst abrir o caminho
  e appinst ainda recopia a IPA: não há garantia de identidade
  fim-a-fim do arquivo; teste com app descartável é indispensável.
- Esta primeira ponte é uma FERRAMENTA CLI. A integração com o
  botão Atualizar dentro do app ainda depende do IPC físico Chimera.
- Não executar install-confirmed no WebReader principal sem
  comprovar a preservação de dados e um backup separado.

Status: commit experimental PR #90, aguardando CI no HEAD, sem
execução real, sem merge e sem tocar na Build56/main.

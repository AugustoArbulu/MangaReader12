# WebReader iOS 12 — fase DA: aplicativo independente para testar CX dentro da sandbox

Data: 21/11/2026 UTC. Branch: feat/chimera-updater-phase1-protocol-audit. PR #90 Draft.

## Estado herdado, sem reinício

O usuário confirmou no chat que o serviço CZ/CX com.example.webreader.checkonlylab foi instalado e respondeu aos testes de CLI no iPad iOS 12.5.8/Chimera, inclusive após fechar completamente e reabrir NewTerm. Registro por relato, sem logs reais anexados. Isso ainda não comprova a comunicação de um aplicativo sandboxed nem persistência após reboot/rejailbreak.

A Build 70 estável e o serviço PING Build61 não foram modificados. AppInst 2.1.1 responde no terminal, mas o self-spawn pelo app sandboxed falhou com EPERM. A fase DA não tenta spawn nem instala IPA.

## Entrega DA

- ci/chimera_cx_app_probe/cx_client.c e cx_client.h — implementação C que envia exclusivamente WRCHK2 seguido de LF para 127.0.0.1:38973, encerra o lado de escrita e espera resposta exata WRNOTE2/WRRATE2/WRDENY2 com EOF. Nenhuma URL, versão, IPA, caminho, SHA, autorização ou instalação pode ser transmitida.
- ci/chimera_cx_app_probe/main.m — interface UIKit mínima com botão Testar comunicacao CX e Copiar relatorio, sem chamadas automáticas, rede em background e reporte de UID, EUID, versão iOS e resultado. Não acessa arquivos do WebReader.
- ci/chimera_cx_app_probe/qa.entitlements — somente application-identifier WRTEST0001.com.example.WebReaderCXSandboxProbe, não pede no-container nem qualquer permissão de instalador.
- ci/chimera_cx_app_probe/host_main.c e ci/test_chimera_cx_sandbox_client.py — executam e testam no host o mesmo cliente C embarcado na IPA contra serviço CX real e respostas maliciosas simuladas; a porta variável está disponível somente em WR_DA_HOST_TEST, explicitamente proibida para TARGET_OS_IPHONE.
- ci/build_chimera_cx_sandbox_qa_ipa.sh — compila iOS12 ARM64, assina ad hoc um aplicativo separado, empacota WebReader-CX-Sandbox-DA-iOS12-adhoc.ipa e produz SHA-256.
- ci/test_chimera_cx_sandbox_ipa.py — inspeção de assinatura, Bundle ID, compatibilidade iOS 12, ZIP, Mach-O, entitlements e ausência de appinst/IPA/WebReader.
- .github/workflows/chimera-da-cx-sandbox-qa.yml — Ubuntu/macOS para o cliente e build do aplicativo assinado no macOS. Upload somente de artifact QA, nenhuma Release nem instalação física.

Identidade física da IPA: com.example.WebReaderCXSandboxProbe, versão 1, display WebReader CX Teste. Não possui LaunchDaemon nem helper. É independente de com.example.MangaReader12 e não substitui a Build70.

## Resultado do ensaio físico esperado e interpretação

Instalar somente a IPA DA depois da CI verde, usando Filza e AppSync no iPad, sem tocar na Build70. Abrir WebReader CX Teste e pressionar Testar comunicacao CX; depois Copiar relatorio. WR_DA=NOTICE_ACCEPTED indica que o aviso chegou ao serviço local, sem consulta GitHub nem instalação. WR_DA=RATE_LIMITED também indica conexão, sujeita ao limitador de 60 segundos. WR_DA=UNAVAILABLE ou outra falha exigem investigação da sandbox ou do listener, sem atualizar WebReader ou reconfigurar AppInst.

O app deve continuar sem acesso a dados de leitura, sem background fetch, sem permissão de root e sem instalação. Não solicitar restart/rejailbreak para este ensaio inicial.

## Hard stops

main intocada, PR #90 Draft, Build70 e downloads intocados; WebReaderAppinstSocket.liveInstallationEnabled=false; productionPublicKeyX963=nil; independentlyProvisionedSPKISHA256=nil; nenhuma Build71/Release/IPA do WebReader ou instalação via appinst. A QA física da DA ainda depende de ação explícita do usuário; compilar no GitHub Actions não prova que a sandbox do iOS físico permitirá conexão ao CX.


## Resultado CI final e artifact de QA

GitHub Actions #44859172297: SUCCESS nos três jobs (host Ubuntu, host macOS e build assinado no macOS), código commit a3d211cca0cef00dd5d8b3d8a07e2443217ac118.
https://github.com/AugustoArbulu/MangaReader12/actions/runs/44859172297

A primeira tentativa de build encontrou UIFont.monospacedSystemFontOfSize disponível somente em iOS13; foi substituído por Menlo-Regular com fallback. Uma segunda revelou ausência de link explícito ao CoreGraphics (CGRectZero), corrigido na terceira execução. Testes de host passaram em todas as rodadas; somente a terceira gerou artifact aprovado.

Artifact GitHub Actions: WebReader-DA-CX-Sandbox-iOS12-QA, ID 14688662029, ZIP com IPA e SHA256; expira em 05/12/2026 UTC.
IPA: WebReader-CX-Sandbox-DA-iOS12-adhoc.ipa; tamanho 13.687 bytes; SHA256 8fba25d3176b3d617c04f10470b5698b32de6bbd47f6929d5f2ba181dd138a1a.
Inspeção adicional dos bytes extraídos do artifact: Info.plist com CFBundleIdentifier com.example.WebReaderCXSandboxProbe, CFBundleDisplayName WebReader CX Teste, CFBundleVersion 1, MinimumOSVersion 12.0; executável thin Mach-O ARM64; não contém strings de AppInst, WRINST1 ou LSApplicationWorkspace. O SHA-256 coincidiu com o manifesto do artifact.

**Estado após CI:** IPA descartável pronta para instalação manual opcional. Nenhum teste de app sandboxed foi executado no iPad até esta data; nenhuma atualização de WebReader, modificação de Build70 ou instalação de app foi realizada em CI. A CI aprova compilação e integração host, não a comunicação física de sandbox.


## Resultado físico real DA — CONFIRMADO (21/11/2026 UTC)

O proprietário instalou e executou o aplicativo de QA no iPad e forneceu **o relatório textual real**, reproduzido abaixo exatamente no conteúdo relevante:

```text
WebReader CX Sandbox QA
Bundle: com.example.WebReaderCXSandboxProbe
iOS: 12.5.8
UID: 501 | EUID: 501
Destino: 127.0.0.1:38973
Comando: WRCHK2 (7 bytes, LF)
WR_DA=NOTICE_ACCEPTED
Servico CX respondeu. Nenhuma Release consultada; nenhuma IPA instalada.
WR_DA_INSTALL=NEVER
WR_DA_PUBLISHER_AUTHENTICATED=NO
```

**Interpretação auditável:** o aplicativo DA com Bundle ID exclusivo executou como mobile (UID/EUID 501) e recebeu uma resposta válida e completa do listener CX em loopback, após enviar `WRCHK2\n`. O caminho aplicativo iOS12 de QA → serviço CX fora do processo do app foi observado fisicamente. Como a IPA foi auditada sem o entitlement no-container e sem instalador, esta é a evidência necessária para a comunicação entre os componentes separados no contexto sandbox do teste.

**Limites:** `NOTICE_ACCEPTED` é somente sinal de transporte, não download ou consulta de Releases; não autentica identidade de peer ou do servidor, nem publisher. Não demonstra instalação, persistência após reboot/rejailbreak, acesso seguro ao AppInst pelo helper nem preservação de dados após atualização. `WR_DA_INSTALL=NEVER` e `WR_DA_PUBLISHER_AUTHENTICATED=NO` são afirmações do cliente de teste sobre ausência dessas funções, não provas de uma arquitetura de instalação real.

**Decisão:** fase DA física de transporte considerada APROVADA. Prosseguir sem reinstalar CX, sem repetir testes de spawn do app. Próximo gate de projeto deve tratar consulta genuína de Release com origem fixa, versionamento e publisher trust como questões distintas de IPC, com qualquer fluxo de instalação ainda fechado; o app principal Build70 não foi tocado.

# WebReader Build66 — Protocolo de QA físico manual (iOS 12.5.8 + Chimera)

**Objetivo:** testar uma IPA de QA entregue como artefato privado do GitHub Actions, não como release de produção. Nenhuma instalação automática; o proprietário decide quando e se instalar pelo Filza.

## Contrato do pacote

- IPA: WebReader-Build66-iOS12-adhoc.ipa
- Bundle ID preservado: com.example.MangaReader12
- Entitlement que deve coincidir com o app instalado: AR5SFJC432.com.example.MangaReader12.AR5SFJC432
- iOS mínimo: 12.0; CPU: ARM64.
- Necessário conferir o SHA-256 da IPA com o arquivo .sha256 e com os dois recibos JSON gerados pelo workflow. Os valores podem variar entre execuções de assinatura/compactação. Não usar um hash anterior.
- Assinatura ad hoc garante a integridade dos bytes e entitlement no macOS, não autentica o editor de releases nem permite autoinstalação.

## Antes de instalar

1. **Não desinstalar a Build65 existente.** Produzir um backup da biblioteca usando o recurso do próprio WebReader e copiar o arquivo para fora do iPad (Android/PC). Conferir que o arquivo foi transferido corretamente. Garantir que os capítulos offline necessários estão disponíveis, e registrar a quantidade de obras na biblioteca.
2. Referência validada para recuperação: [Build65 aprovada — workflow #42263333598](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42263333598). Artifact: WebReader-Build65-OfflineRepair-ManualQA-iOS12, ID 13526372276. SHA-256 previamente aprovado da IPA Build65: 798d2bc9472e626eea9dd9c794fb7d6053b4eac01d288e86d0f04a3c092af10a. O artefato estava não expirado quando foi verificado. Uma reinstalação da Build65 sobre banco já migrado na Build66 não é necessariamente um rollback seguro.
3. Baixar o pacote **privado** de QA da Build66 que contém IPA, .sha256, auditoria nativa e recibo de transferência. Confirmar hash após download e, preferencialmente, após a transferência ao iPad. Se diferir, não instalar.
4. Verificar que é realmente uma IPA do aplicativo com bundle com.example.MangaReader12, e não um app descartável IPC Probe ou outro Bundle ID.
5. A instalação só ocorre pela escolha explícita do proprietário usando Filza. O WebReader não deve oferecer, executar ou encaminhar comandos appinst de instalação.

## Matriz de teste após eventual instalação

- Ajustes: versão exibida deve ser **Build 66**, obtida dinamicamente do Info.plist.
- Biblioteca: contagem, obras, progresso e favoritos preservados.
- Leitor: abrir capítulos e rolar por várias páginas, sem imagens em branco.
- Offline: desligar Wi-Fi ou ativar modo avião e abrir dois capítulos baixados anteriormente. Não deve aparecer falha de rede -1009.
- Rede: verificar fontes antes aprovadas (WeebCentral e Webtoons EN, além de Asura EN conforme disponibilidade externa).
- Atualizações do WebReader: a consulta HTTPS não deve apresentar HTTP 404 de repositório privado como "já atualizado". Não há chave editorial de produção disponível.
- Confirmar que nenhum instalador privilegiado ou instalação automática foi acionado.
- Reiniciar o aplicativo e verificar persistência de biblioteca e downloads.

## Relatório curto após testes físicos

- Dispositivo: iOS 12.5.8, Chimera, usuário mobile.
- Instalação Filza sobre Build65: sucesso / erro exato.
- WebReader abre e mostra Build 66: sim/não.
- Biblioteca, favoritos e progresso: OK / alterações.
- Leitura offline (duas obras): OK / erro.
- Leitura online (WeebCentral/Webtoons/Asura): OK / erro.
- Tela de atualizações / GitHub Releases privado: resultado.
- Erros e observações.

## Recuperação / proteção de dados

Nunca selecionar apagar/remover aplicativo como resposta inicial a um erro. Não limpar pasta Documents ou banco de dados. Em caso de falha, interromper novas tentativas, registrar a mensagem exata e conservar o backup externo.

Embora a IPA antiga da Build65 esteja arquivada, um downgrade de versão do aplicativo **não garante compatibilidade inversa de banco de dados**. O procedimento de retorno só deve ser decidido depois de inspecionar o estado real e preservar a cópia externa anterior ao teste.

## Garantias que ainda NÃO existem

- Nenhuma chave pública editorial de produção está instalada.
- O iOS12/Chimera não forneceu um LOCAL_PEERTOKEN utilizável no diagnóstico como mobile.
- Autorizar a instalação com audit token de um socket é insuficiente, inclusive devido ao caso de mensagens acumuladas visto no macOS.
- Não existe consentimento independente de helper, replay/rollback seguro ou instalador automático aprovado.
- O arquivo em Actions é QA manual, não GitHub Release nem prova criptográfica do editor.

**Resultado desta fase:** entregar uma IPA experimental verificável por hash e mantê-la separada do instalador automático, deixando a Build65 intacta até a decisão do proprietário.

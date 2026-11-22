# WebReader Chimera Test — um único aplicativo

**Objetivo:** confirmar se um app separado no iOS 12.5.8 consegue iniciar um executável local e comunicar-se com ele, sem terminal, Filza após a instalação ou comandos adicionais.

## Qual arquivo baixar

Em GitHub Actions do commit aprovado, abra o artefato **WebReader-Chimera-OneApp-iOS12-TEST**. Extraia somente a IPA **WebReader-Chimera-Test-iOS12-unsigned.ipa**.

**Não instale** `WebReader-iOS12-Build56` nem nenhuma atualização do leitor principal neste teste.

## Passos no iPhone

1. Instale a IPA separada com o procedimento que já funciona no Chimera/AppSync (por exemplo Filza).
2. Abra **WebReader Chimera Test**.
3. Toque em **Testar Chimera**. O aplicativo tenta iniciar sozinho um helper **PING/PONG somente**, sem instalar IPA, executar `appinst` ou exigir terminal.
4. Toque em **Copiar resultado** e cole o texto no chat.

Só isso. O aplicativo diagnóstico tem identificador `com.example.MangaReader12.chimeraoneapp`, separado do WebReader original `com.example.MangaReader12`. Não acessa Biblioteca, fontes, dados offline nem executa atualização em segundo plano.

## Interpretação

- **PING/PONG aprovado:** o iOS permitiu iniciar um processo local e conectar dois processos com o mesmo UID. Não garante que ele poderá executar `/usr/bin/appinst` ou instalar IPAs.
- **Execução bloqueada:** a chamada `posix_spawn` não conseguiu iniciar o helper. O relatório inclui o código de erro para diagnóstico.
- **Helper não respondeu:** o processo iniciou, mas socket/permissões/sandbox não permitiram concluir a troca.
- **Helper ausente:** problema com empacotamento, assinatura ou permissão da IPA.

O resultado também informa se o app consegue detectar `/usr/bin/appinst` **sem executá-lo**. A disponibilidade por leitura não prova permissão para instalá-lo.

## O que falta para o atualizador final

Depois desse teste no iPhone, escolher o modo simples de iniciar a ponte real `appinst` — de preferência incorporada ao próprio WebReader, se o Chimera permitir. Testar instalação em app descartável, confirmar persistência dos dados e só então liberar atualização do leitor.

**Não existe instalação automática ativa na IPA de teste.** Build 56, Biblioteca e main permanecem intocadas. PR #90 é Draft e não será mesclado automaticamente.

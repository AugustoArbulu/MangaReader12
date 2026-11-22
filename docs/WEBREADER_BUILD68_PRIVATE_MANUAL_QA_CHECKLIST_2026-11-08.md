# WebReader Build 68 — Checklist de QA física no iPad iOS 12.5.8

**Canal:** artefato PRIVADO do GitHub Actions, sem GitHub Release público.  
**Branch:** `feat/chimera-updater-phase1-protocol-audit`, PR #90 Draft; `main` permanece intocada.  
**Referência:** Build 66, última aprovada fisicamente; a Build 67 tem IPA de QA anterior, mas sua validação no iPad não foi confirmada.  
**Objetivo:** avaliar manualmente a Build 68 que reúne as Fases N–AB. Não habilitar o atualizador automático Chimera.

## Antes de instalar: preservação dos dados

1. Dentro da Build 66 instalada, gere um **backup novo da biblioteca**.
2. Copie o backup para FORA do iPad (por exemplo, computador ou armazenamento pessoal separado) e confira que o arquivo foi transferido.
3. Confirme a quantidade de obras na biblioteca, favoritos, progresso e alguns capítulos offline disponíveis **sem Wi‑Fi**; anote esses valores para comparação.
4. **Não apague ou desinstale o WebReader** e não limpe seus Documents, Application Support, Downloads ou bibliotecas. Uma substituição ad hoc no iOS12 com AppSync/Filza pode ser feita sobre o app existente, mas só continue se a interface do Filza indicar claramente que o aplicativo será atualizado com a identidade existente.
5. Guarde a Build 66 aprovada como referência de emergência. Não faça um downgrade se houver migração de banco ou incompatibilidade; preserve os dados e peça uma análise primeiro.

## Arquivo esperado da Build 68

No GitHub, abra o workflow **WebReader Build68 PRIVATE Manual IPA for Filza — Audited, Never Installed** e baixe o artefato `WebReader-Build68-PRIVATE-ManualQA-Filza-iOS12` da execução **SUCCESS**.

O ZIP do artefato conterá:

- `WebReader-Build68-iOS12-adhoc.ipa`
- `WebReader-Build68-iOS12-adhoc.ipa.sha256`
- `WebReader-Build68-private-rehearsal-audit.json`
- `WebReader-Build68-private-manual-qa-delivery.json`
- `WebReader-Build68-source-provenance.json`
- Este checklist.

Depois de extrair o ZIP, confira que o SHA-256 da IPA corresponde à linha do arquivo `.sha256` e aos campos correspondentes do JSON **da mesma execução de GitHub Actions**. Esse hash deve ser verificado **novamente após a transferência para o iPad**, quando possível.

A identidade esperada é:

| Campo | Esperado |
|---|---|
| Nome do app | WebReader |
| Bundle ID | `com.example.MangaReader12` |
| CFBundleVersion | `68` |
| iOS mínimo | `12.0` |
| Arquitetura | ARM64 |
| application-identifier | `AR5SFJC432.com.example.MangaReader12.AR5SFJC432` |
| Assinatura | ad hoc (integridade, **não** identidade editorial) |
| Instalação | **manual pelo Filza**, nunca automática |

**Importante:** GitHub Actions e assinatura ad hoc não provam a identidade de um publicador externo. O pacote só é candidato de **teste pessoal**; a prova de atualização sem perda de dados exige testes no aparelho.

## Instalar manualmente apenas após o backup

1. Transfira a IPA para uma pasta do Filza usando o método que já funciona no seu ambiente Chimera (por exemplo, WebDAV ou importação pelo próprio Filza).
2. Abra a IPA no Filza e selecione **Install** somente se mantiver o app/Bundle ID existente. Não execute a ação de desinstalar nem remova dados locais.
3. Abra o WebReader e confira a versão **Build 68**.
4. Se falhar, **não tente reinstalar repetidamente** ou apagar o app. Registre o erro exato, preserve o backup e peça diagnóstico.

## Roteiro de testes da Build 68

- **Biblioteca:** mesmo número de títulos e progresso da Build 66, favoritos preservados, detalhes e filtro intactos.
- **Offline:** desligue o Wi‑Fi e abra dois capítulos que já estavam armazenados antes da atualização; percorra várias páginas sem receber o erro `-1009`.
- **Leitor:** role páginas e teste largura/altura, navegação, capítulos, histórico e escala.
- **Fontes:** WeebCentral, Asura Scans EN e Webtoons.com EN; verifique capas, detalhes, capítulos e downloads sem alteração de fontes.
- **Atualizações / Segurança:** verifique informações corretas sobre o GitHub Release público, chave editorial ausente e **Instalação pelo Chimera bloqueada**.
- **IPA manual local:** importe somente outro arquivo de teste de Build MAIOR que a instalada, se existir, com checksum independente; copie hash, compartilhe e descarte apenas a cópia QA escolhida. **Não é necessário criar uma IPA nova para esse teste**.
- **Espaço:** sem consumir todo armazenamento, simule baixa capacidade somente se o dispositivo já estiver naturalmente com pouco espaço; o app deve mostrar mensagem de insuficiência sem apagar capítulos.
- **Download:** para um Release futuro que realmente esteja acessível e tenha digest, confira percentuais em intervalos de 5% e o comando **Cancelar download em andamento**. Não force downloads de teste volumosos.
- **Recibo:** quando uma IPA tiver sido baixada e revalidada, confira **Copiar recibo de integridade da IPA**, com Build, SHA-256 e aviso de que hash não autentica editor.
- **Limpeza segura:** inventários do cache e importações locais não devem mostrar Biblioteca nem remover dados sem confirmação.
- **Chimera:** o diagnóstico PING/PONG continua possível, mas **não pode instalar** nenhuma IPA automaticamente.

**Não é falha da Build 68** caso o GitHub Releases público de um repositório privado retorne 404; o pacote de QA deste roteiro é um artefato privado no GitHub Actions e pode exigir abrir o GitHub em dispositivo moderno.

## Modelo de retorno após testar

Copie e preencha:

```text
WebReader Build 68 • iOS 12.5.8
Instalação sobre Build 66 pelo Filza: OK / ERRO:
Build mostrada no aplicativo:
Biblioteca, favoritos e progresso: OK / PROBLEMA:
Capítulos offline sem Wi‑Fi: OK / PROBLEMA:
Leitor e fontes: OK / PROBLEMA:
Atualizações (progresso/cancelamento/recibo): OK / NÃO TESTADO / PROBLEMA:
Backup externo preservado: SIM / NÃO:
Instalação automática ainda bloqueada: SIM / NÃO:
Erros adicionais:
```

**Nenhum teste do GitHub Actions toca ou instala aplicativos no iPad.** Não considerar a Build 68 aprovada até o usuário confirmar a QA física.

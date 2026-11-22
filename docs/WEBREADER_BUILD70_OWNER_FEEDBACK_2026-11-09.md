# WebReader Build70 — retorno do teste no iPad

**Data:** 09/11/2026. **Ambiente-alvo:** iPad iOS 12.5.8. **Origem:** relato direto do proprietário nesta conversa, depois de receber a IPA real Build70.

## Resultado comunicado

> "está funcionando"

**Classificação:** retorno positivo geral do proprietário para a Build70; nenhuma falha específica relatada neste retorno. Isso **não equivale** à confirmação individual de todos os testes do roteiro nem a um relatório técnico gerado automaticamente pelo iPad.

## O que já foi validado no projeto

- CI AC–CD de código, políticas e compilação ARM64/iOS12: **SUCCESS** [#42705574337](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42705574337).
- Entrega da IPA Build70 ad hoc em Actions com auditoria local e hash: **SUCCESS** [#42705903886](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42705903886).
- SHA-256 do arquivo Build70: `526291cc77203c3881e5f3f1c75904e8863dbde3b3bd9df7e1185c3229fb4fc1`.
- Na Build69, usuário havia reportado 9/10 checks OK, incluindo biblioteca e capítulos antigos offline. O item de importar IPA futura estava pendente.

## Cobertura física ainda não discriminada neste retorno

O comentário "está funcionando" não especificou separadamente o resultado de: importação SHA da IPA70 pela Build69 antes da instalação; largura adaptável 100% em retrato/75% em paisagem; controles de 60/75/85/100%; rotação preservando posição no capítulo; persistência da preferência após reinício; leitura de capítulo antigo com Wi-Fi desligado **na Build70**. Não declarar esses casos individualmente aprovados até confirmação explícita.

## Próximo objetivo

Manter Build70 como candidata funcional relatada pelo proprietário e avançar no desenho da atualização interna com confiança editorial e autenticação da ponte Chimera antes de qualquer instalação automática. Não alterar `main`, não publicar release de produção, não apagar biblioteca ou downloads, e não ligar `WebReaderAppinstSocket.liveInstallationEnabled` sem validação separada.

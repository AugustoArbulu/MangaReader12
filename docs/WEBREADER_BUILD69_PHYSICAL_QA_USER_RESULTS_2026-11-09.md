# WebReader Build 69 — resultados da QA física relatados pelo proprietário

**Data do relato:** 2026-11-09, iPad iOS 12.5.8. **Origem:** relato explícito do proprietário após instalar a IPA Build 69 entregue no artifact do GitHub Actions [#42699330354](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42699330354). Não são testes executados remotamente e não foram extraídos dados privados do dispositivo.

## Verificações relatadas

| Teste | Resultado do proprietário |
| --- | --- |
| Build 69 exibida na área de atualizações | OK |
| Biblioteca, favoritos e progresso preservados | OK |
| Capítulo baixado antes do upgrade abre sem Wi-Fi | OK |
| Capítulo offline completo, sem páginas ausentes | OK |
| Capítulo offline persiste após fechar/reabrir sem Wi-Fi | OK |
| Escala largura/altura e navegação no leitor | OK |
| Pesquisa, capas, capítulos e leitura em Asura, WeebCentral e Webtoons | OK |
| Área de Atualizações e suas opções abrem | OK |
| Importar IPA local, validar SHA-256 e copiar recibo, sem instalar | PENDENTE |
| Instalação automática Chimera continua desativada | OK |

**Resultado desta amostra:** 9 OK, 1 PENDENTE, 0 falhas relatadas.

## Por que o teste de importação fica pendente

O código de `MangaReader12/UI/WebReaderAppUpdatesViewController.swift`, em `promptLocalIPAImport`, exige `build > self.installedBuild`. Uma IPA real da Build 69 não pode ser importada pelo verificador da própria Build 69: essa rejeição é intencional e não é defeito de armazenamento. Não devemos renomear ou alterar `Info.plist` da IPA 69 para contornar o controle.

**Próximo teste apropriado:** uma IPA futura de QA com versão superior (por exemplo Build 70), assinada e auditada, sem instalação automática. Só depois conferir o fluxo de importação/revalidação SHA-256 e o recibo, sem instalar a candidata pelo botão de QA.

## Ressalvas

Este relatório cobre a lista de **10 testes reportada pelo proprietário**, não equivale a todos os **16 pontos do roteiro físico completo** em `WebReaderPhysicalQAChecklist.swift`. A evidência da preservação offline se refere à amostra testada pelo proprietário; não é prova de cada arquivo existente no iPad. Não declara canal de atualização de produção ativo, assinatura editorial autenticada, testagem de importação da IPA superior nem instalação automática.

**Segurança:** nenhuma instrução de apagar app, restaurar `.mr12backup`, reindexar ou limpar downloads foi dada. Manter `main` intacta e PR #90 Draft enquanto o projeto de atualização automática continua sob revisão.

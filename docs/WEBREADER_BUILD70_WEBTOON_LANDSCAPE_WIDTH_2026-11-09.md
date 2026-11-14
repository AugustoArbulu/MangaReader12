# WebReader — desenvolvimento posterior à Build69: escala Webtoon no iPad deitado

**Data:** 09/11/2026. **Branch:** `feat/chimera-updater-phase1-protocol-audit`; PR #90 Draft. A IPA da **Build69 já instalada permanece imutável**: estes commits não a modificam nem geram automaticamente nova IPA. A numeração da próxima candidata ainda depende de empacotamento e revisão próprios.

## Solicitação e causa

O proprietário testou a Build69 no iPad iOS12.5.8, relatou **9/10 testes OK** e pediu uma alternativa de escala para o leitor **Webtoon** em paisagem. Na fonte anterior, o modo Webtoon força sempre `ReaderScaleMode.fitWidth`, e cada `UICollectionViewCell` vertical usa a largura inteira da viewport. Ao girar o iPad para paisagem, as tiras ficam grandes demais.

## Implementação em código-fonte

- `ReaderPreferences.swift`: novo enum `ReaderWebtoonWidth` e chave de preferência independente `reader.webtoon.widthMode`. Modo padrão **Adaptável** (100% em retrato, 75% em paisagem); opções manuais 100%, 85%, 75% e 60%. Configurações antigas de escala de **Páginas** não são alteradas.
- `ReaderViewController.swift`: o menu **Opções → Largura Webtoon** permite mudar a largura durante a leitura, sem fechar o capítulo, refazer download, decodificar outra imagem ou gravar novo progresso. As tiras são horizontalmente centralizadas. A altura de cada item usa exatamente a mesma fração de largura da imagem para preservar a continuidade vertical sem gaps artificiais. O scroll interno das células Webtoon fica desabilitado, deixando a rolagem vertical com a coleção.
- Quando o iPad gira, a largura adaptável usa as dimensões atuais da viewport. A posição no capítulo é capturada em índice de tira + fração vertical e restaurada após a transição; troca manual de escala usa o mesmo mecanismo.
- `ReaderSettingsViewController.swift`: seção **Webtoon → Largura do Webtoon**, com as mesmas opções e persistência. A opção **Espaço entre páginas** existente continua disponível separadamente.
- Os arquivos de imagens, biblioteca, leitura offline, entitlements, instalador, segurança de atualizações e `main` não são editados nesta mudança.

## Testes

`ci/test_reader_webtoon_landscape_width.py` cobre de modo estático:
- nenhuma alteração à escala do modo Páginas;
- mesma fração para largura da UIImage e altura da célula;
- centralização horizontal;
- nenhuma chamada de recarregar coleção, baixar página, persistir progresso ou apagar dados no manipulador de largura;
- opções nos dois menus e preservação da posição ao girar.

Se `swiftc` está disponível, o teste também compila `ReaderPreferences.swift` com stub mínimo de `ReaderDisplayMode`, exercita os cálculos reais da porcentagem e `UserDefaults` (default, persistência, orientação e independência da escala de Páginas).

Workflow integrado atualizado para **AC–CC**, com verificações Linux e macOS/iOS12 Debug/Release sem gerar IPA, instalar no dispositivo ou publicar Release. [CI AC–CC](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42703266813) — confirmar conclusão.

## Como testar na próxima candidata

1. Em pé: abrir capítulo Webtoon antigo e confirmar que o padrão Adaptável mantém a largura já conhecida da Build69.
2. Virar iPad deitado: a tira deve ficar com **75% da largura**, centralizada, sem cortar balões nem abrir espaços estranhos entre imagens; scroll permanece contínuo.
3. Abrir **Opções → Largura Webtoon** e testar 60%, 85%, 100% e Adaptável, sem saltar para outra página.
4. Verificar persistência em **Configurações → Leitor → Webtoon** e após fechar/reabrir app.
5. Testar leitor de Páginas (fit tela/largura/altura/original) e capítulos offline preexistentes, confirmando ausência de regressão.

**Importante:** não declarar QA física concluída com base apenas em CI. A IPA69 aprovada pelo proprietário não inclui esta nova opção; o recurso chegará somente numa candidata **posterior** quando compilada, auditada e explicitamente entregue para teste.

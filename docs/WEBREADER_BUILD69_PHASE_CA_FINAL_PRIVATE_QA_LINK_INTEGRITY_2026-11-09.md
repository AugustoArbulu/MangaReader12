# WebReader Build69 — Fase CA: integridade da IPA após publicação local

**Data:** 09/11/2026. **Branch:** `feat/chimera-updater-phase1-protocol-audit`. PR #90 continua Draft. `main` permanece intocada. Build68 no iPad e sua biblioteca não foram acessadas/modificadas. **Nenhuma IPA real Build69 foi gerada ou instalada por esta fase.**

## Base confirmada

CI AC–BZ [#42692085242](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42692085242): SUCCESS 2/2 jobs (Linux + macOS/iOS12). A CI valida o aplicativo, mas não publica artefatos instaláveis.

O empacotador privado BK/BL havia sido reforçado para recusar dados inválidos mesmo sob Python otimizado (BZ), verificar a assinatura ad hoc e calcular o checksum da IPA **temporária**, criando em seguida o nome final por links exclusivos. Uma revisão identificou uma lacuna residual: **não havia leitura do nome final publicado**, para confirmar que seus bytes permaneciam os mesmos depois dos links.

## CA — auditoria do caminho final e rollback

O bloco de publicação atômica em `ci/package_webreader_build69_private_qa_ipa.sh` agora:

1. Exige a linha SHA-256 local com **64 hexadecimais**, dois espaços, nome exato `WebReader-Build69-iOS12-adhoc.ipa` e LF final.
2. Abre a IPA temporária com `O_NOFOLLOW | O_NONBLOCK`, verifica tipo regular, tamanho positivo até **512 MiB** (mesmo limite do auditor de IPA) e estabilidade de inode, tamanho e timestamps durante o hash.
3. Recusa divergência entre bytes temporários e checksum **antes** de criar qualquer nome final.
4. Publica primeiro o checksum e **por último** a IPA, usando `os.link` exclusivo, sem sobrescrita.
5. Abre novamente **o caminho final** com as mesmas restrições, compara inode/dispositivo/tamanho/SHA-256 e revalida os bytes do checksum publicado.
6. Se qualquer checagem falhar, desfaz apenas os links criados nesta tentativa; não remove arquivos preexistentes. O diretório temporário é destruído pelo trap existente.

Os testes `ci/test_build69_bl_atomic_private_delivery.py` agora produzem checksum sintético **válido**; recusam SHA divergente e simulam alteração dos bytes imediatamente após o segundo hard link, exigindo rollback da IPA e do checksum. Mantêm os cenários prévios de colisões, symlink e falha do segundo link. Os testes de Python -O (BZ) também proíbem `assert` em todo o bloco final.

## Limites

A conferência CA garante consistência local do nome final no instante da verificação: **não comprova autenticidade editorial**, não protege contra alterações posteriores em diretórios controlados por terceiros e não substitui a revisão independente do SHA após transferência ao Filza. Os scripts continuam proibidos em GitHub Actions, não criam Release, não instalam, não ativam Chimera e não são autorização para executar o empacotador.

## Próximo marco

Verificar a nova CI integrada AC–CA; após aprovação específica do proprietário e execução em macOS apropriado, criar a primeira IPA privada Build69 e seu SHA-256, aplicar BB/BC e preparar o teste físico manual in-place, preservando biblioteca e capítulos offline. Nenhum desses passos finais foi realizado aqui.

# WebReader Build70 — laboratório descartável EV–FD

Este pacote contém **somente protótipos de QA**. Não há IPA, instalador, chamada ao app ou acesso à biblioteca real do iPad. Os testes geram diretórios temporários com marcador `EV_SYNTHETIC_ONLY`, arquivos fictícios e bancos SQLite sintéticos.

## Testes locais (Linux + Swift)

```sh
python3 -m unittest discover -s ci -p 'test_build70_*.py' -q
```

| Fase | Testes locais | Escopo |
|---|---:|---|
| EV | 13 | Quarentena sintética Python e falhas injetadas |
| EW | 15 | Primitivas Swift por descritores de arquivo |
| EX | 22 | Journal de operações SQLite e recuperação |
| EY | 26 | Migração SQLite shadow + corrida de inode |
| EZ | 33 | Snapshot copy-only e journal |
| FA | 42 | Schema v1 integral em fixture, três rotas não destrutivas |
| FB | 52 | Plano/recibo no Swift + journal copy-only no shadow v2 integral |
| FC | 20 | Compatibilidade Codable do modelo, bloqueio de cabeçalhos privados e pré-flight nativo |
| FD | 27 | Snapshot estrito completed-only, sem duplicar planos que podem conter segredos |\n| **Total** | **250** | **Revalidados em Linux a partir da extração limpa; CI completo Linux/macOS configurado** |

Leia `docs/WEBREADER_BUILD70_PHASE_FD_SEALED_COMPLETED_SNAPSHOT_2026-11-13.md` e o relatório FC. Os 41 arquivos deste laboratório estão versionados em `ci/labs/webreader-ev-fd/` na branch Draft do PR #90. O workflow raiz `.github/workflows/chimera-build70-phase-fe-evfd-full-lab.yml` testa os mesmos arquivos em Ubuntu/macOS, sem gerar IPA nem instalar nada.

## Limites

- Não integra `ChapterDownloadManager.remove`, `removeAllConfirmed`, `DownloadRepository.removeMissingFiles` nem altera `SQLiteDatabase.swift` do aplicativo.
- `snapshotmeta` preserva o capítulo original; **não implementa delete** nem restauração automática.
- Testes de Linux não substituem execução macOS/APFS/iOS 12, backup real verificado ou testes físicos.
- O antigo experimento `stage` por rename de origem continua conhecido como **inseguro** para produção diante de troca do basename. Use **somente** os novos modos copy-only para experimentos de preservação; nenhum modo do laboratório deve ser usado com arquivos do usuário.

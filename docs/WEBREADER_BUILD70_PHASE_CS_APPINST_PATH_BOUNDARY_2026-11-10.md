# WebReader Build70 — Fase CS: appinst e segunda leitura por pathname

**Data:** 10/11/2026. **Branch:** feat/chimera-updater-phase1-protocol-audit. **PR:** #90 Draft. Nenhuma alteração em main, Releases, helper, Build70 física, biblioteca, backups ou downloads.

## Evidência na fonte upstream de referência

Origem: https://github.com/akemin-dayo/AppSync/blob/235aca6cddfbdc9fa87fcb5b2aec2df37ed6d65a/appinst/appinst.m

Commit fixo: 235aca6cddfbdc9fa87fcb5b2aec2df37ed6d65a. SHA1 git blob: be0350e637c85da70b5cb1a573780bcb0d46d534.

Sequência: (1) fileExistsAtPath; (2) zip_open(argv[1]) para inspecionar ZIP; (3) solicitação de modo temporário 0777; (4) copyItemAtPath:filePath toPath:installPath, com nova abertura pelo caminho; (5) chamada a LSApplicationWorkspace.installApplication com NSURL do arquivo copiado. Este último passo é relevante no iOS >=8.

**A fonte upstream não identifica o binário instalado no iPad.** O arquivo control daquele repositório declara appinst 2.1.1. O número 2.1.5-procursus6 pertence ao projeto de assinatura ldid; não é evidência da versão local de appinst.

## Consequência arquitetural

Mesmo que o helper passe /dev/fd/N ao processo appinst, o código de referência fecha o ZIP e **copia novamente por pathname** a partir de um novo instante. Em seguida entrega um segundo pathname ao serviço Apple, não o descritor inicial. A Fase CR só demonstrou passagem de FD para um filho Python controlado, não consumo imutável pelo instalador.

Solicitar permissão 0777 num diretório temporário também merece auditoria. Isso **não prova** exploração, ausência de proteções do runtime ou modo efetivo no iOS12. O laboratório CS apenas demonstra a possibilidade de diferença entre bytes já revisados e uma cópia posterior por pathname **num modelo de host controlado**.

## Implementação e validação

- ci/build70_cs_appinst_path_boundary_audit.py: compara uma fonte upstream obtida externamente com um git blob SHA1 **exato**, verifica cinco operações ordenadas, gera recibo não-autorizativo. Fonte desconhecida falha fechada.
- No mesmo script: laboratório com bytes sintéticos. Abre por FD, revisa e fecha, troca pathname por conteúdo diferente e copia pelo nome alterado. Hash do revisado e copiado devem divergir. Nunca roda appinst ou IPA.
- ci/test_build70_cs_appinst_path_boundary_audit.py: nove testes de regressão offline cobrindo formato de fonte, mutação, ordem, integridade do hash, troca de caminho e impossibilidade de autorizar instalação.
- .github/workflows/chimera-build70-phase-cs-appinst-source-audit.yml: Linux/macOS, obtém somente o código-fonte público pelo commit fixo e testa o limite. Sem chave privada, binário appinst, IPA, serviço privilegiado, DEB ou acesso ao dispositivo.

## Próximas hipóteses

1. Manter instalação manual atual como fallback aceito; não substituir appinst instalado com binário não revisado.
2. Estudar serviço mínimo que guarde os bytes aprovados em diretório privado e prove que terceiros não podem mudar entrada ou inode; confirmar consumo exato pelo instalador Apple.
3. Alternativamente avaliar um mecanismo próprio rigorosamente auditado, sem depender da cópia mutável feita pelo appinst de referência, com testes macOS e iOS12 antes de permitir qualquer instalação.
4. Criar chave editorial real apenas sob custódia do proprietário; provisionar pin público de forma independente; exigir manifesto v2, verificação nativa do code seal, anti-replay, consentimento local e recuperação.

As constantes de produção permanecem nil e liveInstallationEnabled=false. O trigger local não autenticado continua CHECK_ONLY e não escolhe IPA/URL/versão. **Nenhuma Build71, IPA, .deb, release ou instalação nesta fase.**

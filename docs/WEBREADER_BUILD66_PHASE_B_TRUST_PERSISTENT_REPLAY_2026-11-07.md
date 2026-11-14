# WebReader / MangaReader12 — Build 66, entrega ampliada: confiança de release + replay persistente

Data: **2026-11-07 UTC**.
Branch: **feat/chimera-updater-phase1-protocol-audit**.
PR **#90 Draft**, base **main**; nenhum merge e nenhuma alteração na Build65 instalada.

## Resumo da entrega

A fase de segurança B combina, em ambiente **host-only e sem privilégios**:

1. Manifesto v2 assinado com ECDSA P-256/SHA-256, asset ad hoc nomeado por build e application-identifier do WebReader instalado;
2. IPA sintética com SHA-256 verificado e metadados vinculados aos bytes corretos;
3. Fingerprint SHA-256 do SubjectPublicKeyInfo DER da chave pública ECDSA P-256, fornecido **independentemente** de qualquer manifesto/download;
4. Sessão CHECK_ONLY de uso único com desafio e validade temporal;
5. Registro persistente do desafio usado, com abertura de diretório protegido, criação exclusiva O_EXCL, O_NOFOLLOW e fsync do arquivo e do diretório;
6. Testes de reinicialização de processo, replay, concorrência e negação de instalação;
7. Compilação de Swift e teste nativo de que WebReaderAppinstSocket.install() sempre recusa em builds não instrumentadas.

**Importante:** nenhuma destas verificações autoriza instalação. São evidências de integridade e pesquisa de protocolos. Continua desabilitado: liveInstallationEnabled = false. A chave pública de atualização em produção continua nil.

## Arquivos de implementação

| Caminho | Responsabilidade |
| --- | --- |
| ci/build66_durable_replay_journal.py | Registra a tentativa em arquivos .spent, com O_EXCL, diretório 0700 e fsync |
| ci/test_build66_durable_replay_journal.py | Testa replay entre processos, concorrência, root symlink, permissões e marker parcial |
| ci/build66_release_key_pinning_gate.py | Valida EC P-256, fingerprint do SPKI DER independente, exige manifesto v2 |
| ci/test_build66_release_key_pinning_gate.py | Verifica chaves divergentes, RSA/P-384, hash, assinatura e IPA adulterados |
| ci/build66_durable_one_shot_lab.py | Une release verificado, fingerprint pinado, CHECK_ONLY e registro persistente |
| ci/test_build66_durable_signed_release_chain.py | Exercita fluxo fim a fim em laboratório, inclusive reinicialização e concorrência |
| .github/workflows/chimera-build66-preflight.yml | Amplia suíte Linux e adiciona execução nativa Swift de negação do install no macOS |

O ledger não cria o diretório por conta própria; o harness escolhe uma raiz preexistente, privada (0700) e do UID do processo. Para cada par domínio/nonce/hash do manifesto/hash da IPA/build, cria o marker SPENT de forma exclusiva. **Qualquer tentativa, inclusive malformada, é reservada ANTES de analisar os bytes do pedido.** Uma queda entre reservar e responder não reabilita a mesma tentativa em outro processo que use o mesmo diretório. Marker vazio/parcial também é considerado usado.

Esta regra é propositalmente conservadora e pode negar atualizações após falhas. Ela evita repetir uma tentativa já iniciada, mas não recupera/retoma instalação; não há rotina de instalação neste protótipo.

## CI e evidência

- **Workflow #73**: https://github.com/AugustoArbulu/MangaReader12/actions/runs/42339159926 — **SUCCESS** nos jobs Linux e macOS.
- **165 testes de Python aprovados** no job Linux (somatório das suítes executadas).
- macOS compilou e executou o verificador real Swift Security.framework, validou assinatura ad hoc de fixtures e compilou/executou o ensaio nativo Swift que nega instalação em modo de produção.
- Auditoria anterior do **artefato real Build65**: run https://github.com/AugustoArbulu/MangaReader12/actions/runs/42332475367 — **SUCCESS**. Build65 permanece versão física estável.
- Os testes usam chaves efêmeras P-256, IPAs sintéticas, e scripts locais; não fazem chamadas ao site Comix nem distribuição de IPA.

## O que os testes NÃO provam

**Identidade do solicitante:** um cliente com mesmo UID pode falsificar a origem de um socket se não houver autenticação independente e um processo privilegiado isolado. PID, UID, PONG, challenge e HMAC por si só não provam identidade de código. O protótipo não abre sockets.

**Rollback por quem controla a pasta:** o journal rejeita replay sob a suposição de que a área de estado é confiável. Um adversário capaz de apagar/retroceder diretórios, snapshots de filesystem, ou modificar a pasta do helper consegue reabrir estados antigos. A solução instalada precisaria área protegida pelo helper, autenticação do peer e política de rollback.

**Segredo editorial:** não existe chave de release em produção provisionada ou distribuída no app. A impressão digital SPKI tem de ser estabelecida fora do canal não confiável, por uma etapa confiável de publicação do proprietário. Obter a chave e a fingerprint da MESMA resposta de GitHub não estabelece confiança.

**Assinatura ad hoc:** codesign - demonstra integridade e entitlements, não autenticidade do publicador. Um manifesto assinado com chave confiável poderia estabelecer procedência dos bytes depois de configurar a raiz de confiança, mas isso não torna qualquer solicitação de instalação autorizada.

**Consentimento do usuário:** não existe autorização da UI vinculada ao objeto exato. CHECK_ONLY nunca representa permissão; DiagnosticResult devolve installation_authorized=False e installation_performed=False.

**Imutabilidade na instalação:** a verificação do cliente/host não garante que um helper instalará os mesmos bytes. Antes de permitir appinst seria preciso validação independente no helper e uso de um arquivo immutable/privado do helper, sem caminhos fornecidos livremente pelo cliente.

**Distribuição GitHub:** Releases de repositório privado ainda podem exigir autenticação e não devem ser tratadas como endereços públicos seguros sem validação real no iOS 12.

## Próximo lote de trabalho permitido

1. Elaborar matriz de capacidades e autenticação do peer real em Chimera/iOS12, considerando tokens/identidade de processo e uma identidade de app verificável **independentemente** do próprio cliente. Não ativar helper até esse critério ser atingido.
2. Projetar journal de replay ancorado em armazenamento protegido pelo helper, com política de recuperação de crash/power-loss e rollback; o journal de host não deve ser instalado no iPad nem reutilizado como autorização de instalação.
3. Formalizar procedimento da chave de release (custódia off-repo, rotação e revogação, inicialização confiável da chave pública no cliente e no helper), sem inserir segredos no Git.
4. Fazer revisão de ameaça do fluxo ponta a ponta, testes negativos e gate para preservar biblioteca/downloads offline sem desinstalar o aplicativo.
5. Se a autenticação independente for inviável no Chimera, manter o fluxo manual Filza — baixar/validar/compartilhar IPA pode permanecer, sem servidor de instalação.

**Nenhuma Build66 IPA instalável foi produzida. Nenhuma instalação foi realizada. PR segue Draft.**

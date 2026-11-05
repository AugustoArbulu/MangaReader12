# WebReader — Fase 5G: cópia privada verificada e auditoria do appinst

Data: 2026-11-05
Branch: feat/chimera-updater-phase1-protocol-audit
PR: #90 — DRAFT, sem merge.
Base estável: Build 56 (iOS 12.5.8) na main, intocada.

## Escopo e resultado

Implementação de laboratório Python, HOST-ONLY, em:
- ci/webreader_private_snapshot.py
- ci/test_webreader_private_snapshot.py
- .github/workflows/build.yml — teste novo integrado.

O código tem apenas operações de arquivos temporários **no host** e não
faz parte do target iOS. Não usa IPC, root, Chimera, AppSync ou appinst.
Nenhuma IPA foi instalada e nenhum Release foi publicado.

Foram executados localmente **16 testes offline em Linux — sucesso**.
A CI do GitHub/macOS precisa confirmar este HEAD separadamente.

## Modelo de cópia verificada

1. Entrada: pasta de origem e nome específico
   WebReader-build<N>-<UUID>.ipa. Os paths de diretório são assumidos
   confiáveis pelo teste; no futuro helper não poderão vir do cliente.
2. Abre diretórios via descritores, usando O_DIRECTORY e O_NOFOLLOW,
   exige que a pasta privada seja 0700-equivalente, pertencente ao
   EUID do processo. Recusa usar origem e destino que sejam a mesma
   pasta, symlinks finais, arquivos especiais, hardlinks e permissões
   excessivamente abertas.
3. Abre a IPA de origem uma única vez via dir_fd, valida tipo, inode,
   proprietário, tamanho esperado e metadados. O tamanho/hash esperado
   são injetados para o TESTE; em produção precisarão vir da verificação
   independente de manifesto assinado no helper, com chave real pinada.
4. Cria arquivo de saída exclusivo com O_EXCL em diretório privado,
   faz cópia streaming em blocos limitados e mede SHA-256 ao longo da
   transferência. Confere prefixo ZIP (sem pretender auditar o ZIP).
5. Confere identidade/tempo do arquivo de entrada antes/depois,
   detectando swap de nome/inode e mutações observáveis.
6. Fecha a cópia com permissões 0400, fsync, publica nome aleatório
   exclusivo sem sobrescrever arquivos existentes, reabre a cópia
   por O_NOFOLLOW e verifica seu hash pela SEGUNDA VEZ.
7. Retorna um objeto que mantém aberto um descritor somente leitura
   da cópia. Ler/inspecionar novamente esse descritor reconfirma o
   digest. A API expõe installer_authorized=False de modo permanente.
8. O teste pode descartar explicitamente a cópia via unlink relativo
   ao próprio descritor do diretório, sem solicitar caminhos novos.

São testes unitários de integridade e manejo de descritores, não provas
de segurança rootful, separação entre usuários ou instalação.

### Testes negativos

- IPA de origem é substituída depois da cópia: o descritor mantido
  ainda aponta para a cópia validada.
- Arquivo de origem trocado ou modificado durante leitura: rejeição.
- Hash/tamanho/build divergentes ou metadata malformada: rejeição.
- Symlink em pasta final ou arquivo, hardlink, permissões 0777, mesmo
  diretório para origem e destino e caminho malicioso: rejeição.
- Cópia privada alterada por processo do mesmo UID durante o teste:
  uma nova leitura detecta o hash divergente. NÃO prova imutabilidade.
- Colisão de nome do destino: saída existente permanece intacta.
- Sem criar arquivos de produção, e sem chamada de instalador.

## Novo bloqueador encontrado na revisão oficial do appinst

Origem: código oficial do projeto AppSync/appinst:
https://github.com/akemin-dayo/AppSync/blob/master/appinst/appinst.m

Pontos verificados na implementação pública atual:
- Obtém workPath a partir de NSTemporaryDirectory() + /appinst.
- Cria o diretório de trabalho solicitando permissão **0777**.
- Copia a IPA original com copyItemAtPath para um nome de sessão
  aleatório no diretório temporário e então passa ESSA NOVA CÓPIA a
  LSApplicationWorkspace no iOS 8+ (inclui iOS 12).
- A implementação tenta limpar arquivos temporários após instalar.

Trechos: aproximadamente appinst.m linhas 1041, 1221–1224,
1257–1285, 1294–1326 (numeração exibida no GitHub).
O diretório 0777 é uma consideração relevante de segurança e merece
avaliação: o código não mantém, por si, o descritor validado pelo
futuro helper até o consumo pelo instalador. A acessibilidade real
do diretório depende de seus pais, ambiente, UID e contexto do
jailbreak. Isto **não constitui prova de exploração**, mas impede
a declaração de que o caminho de instalação seja fim-a-fim imutável.

**Gate bloqueado:** não basta validar nossa cópia privada se a ferramenta
de instalação fizer outra cópia em local não auditado. A eventual
execução automática via appinst 2.1.1 não está autorizada.

## Possíveis soluções a investigar, não implementadas

A. Primeiro validar procedência oficial do appinst e comparar o hash do
   binário instalado com o pacote de origem confiável.
B. Estudar se o workPath efetivo no Chimera está dentro de uma raiz
   inacessível aos demais usuários/processos; medir ownership e
   permissões no dispositivo apenas por observação, sem instalar IPA.
C. Estudar adaptação revisada/compilada de fonte oficial que opere em
   diretório privado 0700 e preserve a identidade dos bytes até
   instalar. É uma PROPOSTA, não existente nem aprovada.
D. Investigar IPC local autenticado e uma API nativa de instalação
   capaz de consumir arquivo protegido sem nova cópia exposta, apenas
   após testes com app de descarte. Não ativar APIs privadas agora.
E. Backups: MR12Backup e cópia independente de capítulos offline;
   verificar SQLite, progressos, fontes, filtros e espaço disponível
   antes de atualização real, nunca confiar somente no exit code.

## Critérios de promoção

- CI do HEAD exato aprovada (inclusive teste novo em macOS e builds
  Debug/Release iOS12); testes locais não substituem esta validação.
- Prova da identidade do appinst instalado e de sua origem oficial.
- Teste físico do isolamento do diretório interno do appinst no
  iOS 12.5.8 e mitigação demonstrada do risco de troca de arquivos.
- Helper real separado com credenciais IPC verificadas, assinatura
  independente, auditoria completa de ZIP/Info.plist/versão e
  confirmação explícita do usuário.
- Teste em app descartável, depois dados fictícios, e backups,
  antes de qualquer atualização do WebReader principal.

**NÃO usar o protótipo como instalador ou como autorização.**
Nenhum merge, Build 57, chave de produção, nova release, alteração
da Biblioteca nem execução privilegiada foi realizada nesta fase.

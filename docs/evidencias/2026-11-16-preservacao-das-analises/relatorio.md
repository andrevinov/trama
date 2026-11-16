# Preservação das análises — 16/11/2026

[Evidências](../README.md) · [Cobertura atual](../../sistema/qualidade/cobertura-atual.md)

Este registro documenta a preservação offline das evidências durante a
consolidação do simulador. **Nenhuma nova chamada de IA foi executada.**
O [inventário](manifesto.json) foi produzido depois das análises: sua data de
registro não substitui a data das medições e não é um plano prévio de experimento.

## Material preservado

| Registro | Documentos versionados | Arquivos locais | Alcance e ressalvas |
| --- | ---: | ---: | --- |
| [Ordem de esquema, 15/11](../2026-11-15-ordem-esquema/relatorio.md) | 1 | 4 | Três pedidos em duas variantes; contrato antigo. A variante `legacy` errou um dos pedidos. |
| Exploração contextual `20261116T115849-43931618` | 0 | 16 | Lote anterior à bateria revisada, inventariado separadamente. Sem nova revisão de narração ou manifesto prévio de fontes. |
| [Bateria contextual, 16/11](../2026-11-16-movimento-contextual/relatorio.md) | 2 | 20 | Oito casos, uma execução de cada; aprovação mecânica com ressalvas narrativas já registradas. |

Os três documentos originais — dois relatórios e o manifesto contextual — foram
mantidos sem alterações. Os 40 arquivos locais também foram mantidos em seus
caminhos originais. O inventário registra caminho, tamanho e SHA-256 de cada um.
Não há seleção de apenas respostas favoráveis: os arquivos de comparação
conservam o pedido incorreto e o relatório contextual conserva suas ressalvas.

Os 16 arquivos de resultado/log da bateria revisada foram comparados com os
hashes **já registrados no manifesto original**, e todos conferiram. Os hashes
dos demais materiais foram registrados agora; não demonstram sua integridade
desde a data da análise. `hash_origin` explicita essa diferença.

Para a comparação de esquema, `recorded_results` conserva também os metadados
e o resumo numérico extraídos dos arquivos locais identificados. O resumo
preserva os três resultados por variante, chamadas e tokens informados. Dados
de configuração ausentes no registro antigo não foram completados com padrões
atuais. Os conteúdos brutos dos pedidos e respostas continuam nos logs locais.

## Relação com a reorganização

`source_relocations` identifica quatro mudanças com bytes preservados na data
deste inventário: grade simples, mapa Cela/Guardas, dungeon e casos de interpretação.
Também identifica refatorações e incorporações, como a análise importável e o
catálogo de situações, **sem declará-las equivalentes byte a byte**.

Os caminhos literais e hashes dos manifestos históricos continuam descrevendo
a execução original. Não foram substituídos pelos caminhos novos. A tabela de
relocações é uma referência para investigação, não um redirecionamento usado
pelo jogo ou pelos testes. A verificação de evidências não compara o código
atual com hashes antigos; a aplicação pode continuar evoluindo.

O HEAD original da bateria contextual tinha alterações locais. Seus hashes não
reconstroem os conteúdos dos fontes daquela árvore. A preservação não cria um
snapshot recuperável que não existia, nem converte a amostra antiga em aprovação
do catálogo, dos prompts ou da aplicação atual.

## Conferir a integridade

A [ferramenta de verificação](../../../tools/check_evidence.py) é somente leitura:
não importa a engine ou o SDK, não abre o simulador e não atualiza hashes.

```bash
# Confere os documentos e os logs presentes; informa ausências locais.
poetry run python tools/check_evidence.py

# Exige também todos os logs inventariados nesta máquina.
poetry run python tools/check_evidence.py --require-local
```

O resultado JSON discrimina cada análise e informa:

- `verified`: todos os documentos e arquivos locais conferiram.
- `local_artifacts_missing`: faltam arquivos locais; não afirma verificação completa.
  Isso permite conferir os documentos num clone. Com `--require-local`, retorna erro.
- `integrity_failed`: arquivo versionado ausente ou conteúdo alterado, inclusive
  log local presente e divergente. Retorna erro nos dois modos.
- `invalid_inventory`: declaração inválida ou arquivo inacessível. Retorna erro.

`verified_versioned` e `verified_local` contam arquivos conferidos; `missing_local`
e `errors` aparecem por análise. Código de saída zero significa integridade dos
arquivos exigidos pelo modo escolhido, não aprovação do comportamento do jogo.

Os logs seguem ignorados pelo Git e não acompanham um clone. O inventário não
é uma cópia desses arquivos. Nesta máquina, a conferência estrita verificou
**3 documentos e 40 arquivos locais**, sem divergências. Os testes offline
também verificam alteração, ausência, inventário inválido e independência dos
fontes atuais, sem novas chamadas pagas.

## Acrescentar novas observações

Uma nova execução ou nova conclusão recebe registro datado próprio, com suas
condições e limitações. Não se regrava este inventário para fazer conteúdo
alterado passar. Correções posteriores devem ser identificadas em novo registro,
preservando a informação anterior e apontando o motivo da correção.

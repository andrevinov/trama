# Consolidação do simulador — conclusão em 16/11/2026

[Roadmaps implementados](../README.md) · [Simulador atual](../../../sistema/simulador/README.md)

Registro de conclusão dos sete passos executados incrementalmente a pedido do
usuário. Este documento arquiva o trabalho entregue; a referência do funcionamento
atual permanece em `docs/sistema/`. Não é um plano de experimento com IA.

## Objetivo e resultado

Manter um único simulador jogável, evoluído dentro da aplicação. Situações
reproduzíveis e análises compartilham as implementações pertinentes, com critérios
de avaliação independentes. As medições anteriores conservam suas datas e limites.

## Passos concluídos

| Passo | Entrega |
| --- | --- |
| 1 — Entrada oficial | `poetry run trama-simulator`, registrado no pacote, com dungeon padrão acessível por `importlib.resources`. |
| 2 — Dados da aplicação | Dungeon em `src/trama/scenarios/`; mapas anteriores em `tests/fixtures/scenarios/`, sem alteração de bytes. |
| 3 — Execução compartilhada | CLI usa composição oficial e entrega o fluxo pré-composto à janela; avaliações completas usam o mesmo coordenador pelo runner. Runner independente de movimento removido. |
| 4 — Situações reproduzíveis | Oito situações no catálogo da aplicação, selecionáveis com `--situation`; preparação, rolagens, pré-condições, histórico e reinício compartilhados. |
| 5 — Análises importáveis | Testes importam `trama.analysis.interpretation`; quinze casos preservados nas fixtures e ferramenta auxiliar em `tools/`. Escopo parcial identificado nos resultados. |
| 6 — Evidências datadas | Inventário de três análises, com hashes de três documentos e quarenta artefatos locais, distinção de proveniência e verificador somente leitura. |
| 7 — Limpeza e documentação | Pasta de POCs, encaminhador e cache órfão removidos; reexports e argumento de compatibilidade da CLI retirados; instruções e referências atuais consolidadas. |

As informações úteis dos READMEs antigos foram incorporadas à
[execução do simulador](../../../sistema/simulador/execucao.md),
[dungeon](../../../sistema/simulador/fuga-da-dungeon.md),
[mapas de regressão](../../../../tests/fixtures/scenarios/README.md) e
[análise de interpretação](../../../sistema/qualidade/analise-de-interpretacao.md).
O [AGENTS.md](../../../../AGENTS.md) orienta novos incrementos pelo simulador,
catálogo e fluxo compartilhados, sem novas entradas independentes.

O carregamento reutilizável permanece em `application.scenarios`; a CLI não
reexporta atalhos para runners removidos. `main()` usa as opções da CLI para
selecionar recursos, cenários explícitos ou situações.

## Verificação final

- `poetry run pytest -q`: **867 testes passaram**; suíte local sem rede.
- A entrada oficial abriu, desenhou e encerrou o loop real do Pygame com driver
  SDL sem tela e somente o evento de saída simulado, sem cliente de IA.
- Os testes do wheel mantiveram abertura e recursos fora do checkout, inclusive
  situação reproduzível; cenários explícitos e reinício também foram verificados.
- `poetry run pytest tests/live --collect-only -q`: **38 casos coletados**, sem
  execução de chamadas reais.
- `poetry check` aprovado e contratos conferidos sem atualizar a referência.
- Conferência estrita de evidências: **3 documentos e 40 artefatos locais** íntegros.
- Links e âncoras revisados, `git diff --check` sem erros e pasta antiga ausente.

Nenhuma chamada paga foi executada nos sete passos de consolidação. Os resultados
live anteriores continuam datados e não certificam automaticamente as mudanças
posteriores. Veja a [preservação das análises](../../../evidencias/2026-11-16-preservacao-das-analises/relatorio.md).

## Limites mantidos

A consolidação não alterou regras, prompts, esquemas ou contratos de contexto.
As oito situações contextuais usam o fluxo completo da interação preparada;
as outras cinco suítes live mantêm os escopos parciais/experimentais da
[matriz de cobertura](../../../sistema/qualidade/cobertura-atual.md).
As sequências de dados das situações são finitas e os modelos podem variar.

Os caminhos antigos nos registros históricos são preservados como proveniência.
Relocações e refatorações estão identificadas separadamente, sem reescrever
resultados anteriores ou apresentar uma análise parcial como partida completa.

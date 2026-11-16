# Casos de contrato do interpretador

`cases.json` preserva os 15 casos da antiga análise de interpretação: frases,
planos de referência e expectativas independentes. Os bytes do JSON foram
mantidos na migração. O mapa base é o
[cenário legado](../scenarios/legacy_cell_and_guards.json), carregado pela aplicação.

O módulo `trama.analysis.interpretation` e a ferramenta
`tools/analyze_interpretation.py` usam estes dados. Testes locais e duas suítes
live importam o módulo diretamente; não dependem de scripts ou dados de POCs.

Os planos de referência servem às regressões locais e as expectativas servem à
avaliação. Não são instruções para o modelo nem substitutos de um plano rejeitado.
As variantes de contexto/esquema são experimentos explícitos. Esses casos
verificam o contrato parcial do interpretador, sem executar efeitos do jogo.

Leia a [política live](../../../docs/sistema/qualidade/politica-live-tests.md) e a
[referência da análise](../../../docs/sistema/qualidade/analise-de-interpretacao.md)
antes de alterar os casos ou autorizar chamadas reais.

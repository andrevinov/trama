# Testes locais e fronteiras

Tier 3 · [Qualidade](README.md) · [Visão geral](../../../README.md)

## Organização e comandos

O pytest padrão descobre `tests/unit/` e `tests/integration/`, conforme
[pyproject.toml](../../../pyproject.toml). Não usa rede, credenciais ou modelos reais.
Na raiz:

```bash
poetry install
poetry run pytest
poetry run pytest tests/unit -q
poetry run pytest tests/integration/test_contextual_movement.py -q
poetry check
```

`tests/unit` verifica regras isoladas; `tests/integration` liga componentes reais.
Transporte de IA pode ser simulado, mantendo adaptadores, instruções, esquemas,
contextos e execução reais. O Pygame também pode ser exercitado com driver SDL
sem tela; isso é diferente de testar somente o runner sem interface.

## Critérios e controle da aleatoriedade

Resultados esperados são escritos a partir do comportamento desejado.
Não devem ser calculados chamando a mesma função que produziu o resultado.
Verifique posição, percurso, custo, alvo, portas, inventário, iniciativa,
recursos e causas de parada pertinentes ao caso.

Use o contrato `Roller` para controlar as rolagens. A preparação de um estado
intermediário usa operações públicas e valida seus resultados; atribuir estado
privado para contornar regras pode esconder a regressão que se pretendia medir.
A [preparação reproduzível](preparacao-de-cenarios.md) detalha essa estratégia.

## Fronteiras e contratos

[test_module_boundaries.py](../../../tests/unit/test_module_boundaries.py) protege
imports e delegação entre regras, aplicação, provedor e UI. A
[verificação de contextos](../ia/contextos-e-contratos.md) compara
a referência revisada sem usá-la para gerar pedidos da aplicação.

A [demonstração de regressões](deteccao-de-regressoes.md) combina controles
positivos e negativos: igualdade entre janela e runner não basta se ambos
omitirem o mesmo efeito. Logs e relatórios locais distinguem observações reais
de cópias entregues apenas à avaliação.

## Limites

Respostas simuladas verificam integração e efeitos das propostas declaradas;
não medem a frequência com que o modelo real propõe cada plano. A
[cobertura](cobertura-atual.md) e a [política live](politica-live-tests.md)
distinguem essas evidências. Não acrescente testes que apenas repitam a
implementação ou chamadas pagas para validar uma edição local.

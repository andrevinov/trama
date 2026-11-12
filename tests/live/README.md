# Testes live

Esta pasta contém testes com serviços externos, credenciais ou chamadas reais de IA.

O cenário atual é `test_openai_movement.py`: oito chamadas à OpenAI (cinco de
interpretação básica, uma de narração inicial e duas para a troca mista on/off), usando
`OPENAI_API_KEY` e o modelo `gpt-5.6-luna` (ou `TRAMA_OPENAI_MODEL`). Só executa
quando `RUN_OPENAI_LIVE_TESTS=1`; sem essa autorização, fica ignorado.
Veja [a POC de movimento](../../pocs/movimento/README.md) para critérios e comando.

Cada módulo de testes deve usar `@pytest.mark.live` nos testes ou `pytestmark = pytest.mark.live` no módulo. Documente as variáveis de ambiente exigidas, os serviços utilizados e os critérios de avaliação. As credenciais ficam no ambiente local e nunca devem ser versionadas.

Execute explicitamente, após configurar os requisitos do cenário:

```bash
poetry run pytest tests/live -m live
```

O comando padrão `poetry run pytest` descobre apenas `tests/unit/` e `tests/integration/`.

Ao transformar uma prova de conceito em teste live, reutilize o código do sistema e os cenários pertinentes. Verifique resultados estruturados e invariantes do jogo; avalie a narração com critérios definidos pelo experimento, sem exigir frases idênticas do modelo.

# Testes live

Esta pasta receberá testes que usam serviços externos, credenciais ou chamadas reais de IA. Nenhuma integração está implementada nesta etapa.

Cada módulo de testes deve usar `@pytest.mark.live` nos testes ou `pytestmark = pytest.mark.live` no módulo. Documente as variáveis de ambiente exigidas, os serviços utilizados e os critérios de avaliação. As credenciais ficam no ambiente local e nunca devem ser versionadas.

Execute explicitamente, após configurar os requisitos do cenário:

```bash
poetry run pytest tests/live -m live
```

O comando padrão `poetry run pytest` descobre apenas `tests/unit/` e `tests/integration/`.

Ao transformar uma prova de conceito em teste live, reutilize o código do sistema e os cenários pertinentes. Verifique resultados estruturados e invariantes do jogo; avalie a narração com critérios definidos pelo experimento, sem exigir frases idênticas do modelo.

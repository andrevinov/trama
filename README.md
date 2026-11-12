# Trama

Sistema para jogar **D&D 5.5e com IA**, desenvolvido em Python e gerenciado com Poetry.

O objetivo final é ter uma IA narrando e conduzindo a experiência do jogador como em uma mesa de RPG. Vamos chegar lá aos poucos: primeiro, ferramentas e regras determinísticas; depois, interpretação de pedidos e narração com IA, apoiadas nesse funcionamento já validado.

## Como vamos construir

- Trabalhar em incrementos pequenos, definidos e orientados pelo responsável pelo projeto.
- Começar pelas partes determinísticas que ajudam a jogar. O primeiro tema previsto é movimento; suas regras e implementação serão definidos na próxima etapa.
- Explorar cada avanço com provas de conceito, incluindo pequenos cenários jogáveis quando fizer sentido.
- Transformar os comportamentos validados nessas experiências em testes reproduzíveis. Interações com serviços reais de IA também terão testes live, executados explicitamente.
- Manter as decisões de regras no código Python. A IA poderá interpretar intenções e narrar resultados, apoiando-se nas ações permitidas pelo sistema.

## Preparação

Requisitos: Python 3.14 e Poetry 2.3 ou superior.

```bash
poetry install
```

As dependências ficam em `pyproject.toml`, com versões resolvidas em `poetry.lock`. Não há dependências de execução nesta etapa; o pytest faz parte do grupo de desenvolvimento.

## Estrutura

```text
src/trama/          Código reutilizável do sistema.
tests/unit/         Testes isolados das regras e componentes.
tests/integration/  Testes de componentes trabalhando juntos, sem serviços externos.
tests/live/         Testes com serviços externos e chamadas reais de IA.
tests/fixtures/     Dados e cenários compartilhados entre testes.
pocs/               Provas de conceito organizadas por experimento.
```

Cada prova de conceito terá sua própria pasta, instruções de execução, dados de cenário e critérios de sucesso. Consulte [pocs/README.md](pocs/README.md).

## Testes

```bash
# Testes locais, sem chamadas externas.
poetry run pytest

# Testes live, quando houver cenários implementados e credenciais configuradas.
poetry run pytest tests/live -m live
```

Os testes live usam o marcador `live` e ficam fora da descoberta padrão. Consulte [tests/live/README.md](tests/live/README.md) para as convenções. As pastas estão preparadas; os primeiros testes serão escritos junto com as primeiras funcionalidades.

## Estado atual

Estrutura inicial do projeto. Ainda não há regras de jogo, integração com IA ou prova de conceito implementadas.

As orientações para agentes e contribuições estão em [AGENTS.md](AGENTS.md).

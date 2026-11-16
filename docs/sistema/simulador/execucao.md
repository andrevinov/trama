# Executar e diagnosticar o simulador

Tier 3 · [Simulador](README.md) · [Visão geral](../../../README.md)

## Objetivo e execução

Este é o cenário jogável atual do Trama. O antigo experimento de movimento
cresceu para um simulador de conversa, percepção, interação e combate. O jogador
continua enviando mensagens livres; os adaptadores reais interpretam e narram,
e o Python valida e altera o estado antes da resposta.

Na raiz, com Python 3.14, Poetry e `OPENAI_API_KEY` exportada:

```bash
poetry install
poetry run python pocs/simulador/run.py --debug
```

`TRAMA_OPENAI_MODEL` escolhe o modelo; o padrão continua `gpt-5.6-terra`.
`--log-file logs/fuga.jsonl` escolhe o arquivo. Sem chave, a janela abre para
visualização, mas não interpreta mensagens. Abertura/reinício e mensagens usam
chamadas potencialmente pagas à Responses API. O runner anterior também abre
esta dungeon por padrão; o cenário antigo pode ser escolhido explicitamente.

## Opções e cenários

O comando usa [simulator.py](../../../src/trama/simulator.py) pela entrada local da POC.
`--scenario CAMINHO` seleciona outro JSON; `--debug` amplia diagnóstico;
`--log-file CAMINHO` muda o destino dos logs. Os comandos partem da raiz:

```bash
poetry run python pocs/simulador/run.py --help
poetry run python pocs/simulador/run.py --debug --log-file logs/fuga.jsonl
poetry run python pocs/simulador/run.py --scenario pocs/movimento/cela_guardas.json
```

Python e dependências são instalados com Poetry. O Pygame precisa de ambiente
gráfico para interação. Os [serviços de IA](../ia/integracao-openai.md)
resolvem autenticação e modelo. Não há leitura automática de `.env`, login do
ChatGPT ou MCP para essa integração.

## Uso e critérios observáveis

A partida começa com a [abertura da dungeon](fuga-da-dungeon.md). Envie uma
mensagem on para agir ou escreva dúvidas entre colchetes. O mapa acompanha os
efeitos executados. Ficha e Inimigos permitem consultar estado; Reiniciar restaura
a partida e solicita uma nova abertura. Veja [controles](../interfaces/pygame.md#controles).

Abertura, mensagens, turnos de NPCs e reinício podem fazer chamadas pagas.
Sem chave, a janela abre para visualização e apresenta a configuração necessária.
Uma mensagem deve produzir efeito, interação ou explicação de impedimento; se
narração falhar, efeitos anteriores continuam no estado.

## Diagnóstico e regressões

Veja [logs](../observabilidade/logs.md) e
[lnav](../observabilidade/investigacao-com-lnav.md) para acompanhar
pedido, proposta, execução e resposta final. A suíte local usa `poetry run pytest`;
chamadas live seguem a [política própria](../qualidade/politica-live-tests.md).

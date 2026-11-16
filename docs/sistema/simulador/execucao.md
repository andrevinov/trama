# Executar e diagnosticar o simulador

Tier 3 · [Simulador](README.md) · [Visão geral](../../../README.md)

## Objetivo e execução

Este é o cenário jogável atual do Trama. O antigo experimento de movimento
cresceu para um simulador de conversa, percepção, interação e combate. O jogador
continua enviando mensagens livres; os adaptadores reais interpretam e narram,
e o Python valida e altera o estado antes da resposta.

Na raiz, com Python 3.14, Poetry e `OPENAI_API_KEY` exportada, instale o projeto
para disponibilizar o comando oficial:

```bash
poetry install
poetry run trama-simulator --debug
```

`TRAMA_OPENAI_MODEL` escolhe o modelo; o padrão continua `gpt-5.6-terra`.
`--log-file logs/fuga.jsonl` escolhe o arquivo. Sem chave, a janela abre para
visualização, mas não interpreta mensagens. Abertura/reinício e mensagens usam
chamadas potencialmente pagas à Responses API. Os cenários anteriores são
fixtures que podem ser escolhidas explicitamente pelo mesmo comando.

## Opções e cenários

O comando `trama-simulator` usa [simulator.py](../../../src/trama/simulator.py),
registrado nos metadados do projeto. Também é possível usar
`poetry run python -m trama.simulator`. As duas formas chamam o mesmo `main()`.

O antigo runner de movimento foi removido. A criação de cliente/adaptadores
fica em `open_services`, ligada à sessão e ao `GameFlow` por `open_game`.
A janela recebe o fluxo já composto; avaliações de fluxo completo usam
`game.runner`, a agenda sem janela desse mesmo coordenador. As avaliações
parciais de contratos continuam identificadas na
[cobertura](../qualidade/cobertura-atual.md).

O padrão é [dungeon_escape.json](../../../src/trama/scenarios/dungeon_escape.json),
distribuído com o pacote. `importlib.resources` localiza esse recurso; quando
necessário, ele é materializado como arquivo temporário durante a partida.
O carregamento continua usando `open_game` e os validadores compartilhados.

`--scenario CAMINHO` seleciona outro JSON; `--debug` amplia diagnóstico;
`--log-file CAMINHO` muda o destino dos logs. Com o ambiente Poetry instalado:

```bash
poetry run trama-simulator --help
poetry run trama-simulator --debug --log-file logs/fuga.jsonl
poetry run trama-simulator --scenario tests/fixtures/scenarios/legacy_cell_and_guards.json
poetry run trama-simulator --situation investigar-cela-do-log --debug
```

O executável instalado não depende da raiz do repositório para abrir a dungeon.
`poetry run` precisa localizar o projeto Poetry; fora da árvore, pode-se indicar
o projeto com `poetry --project /caminho/para/Trama run trama-simulator` ou chamar
diretamente o executável do ambiente. Caminhos de cenário explícito e logs são
resolvidos a partir do diretório atual. Um cenário explícito ausente ou inválido
gera erro, sem substituição silenciosa pela dungeon.

`--situation ID` seleciona uma [situação reproduzível](carregamento-de-cenarios.md#situações-reproduzíveis),
alternativa a `--scenario`. Janela e testes usam `open_situation`, com a mesma
preparação e validação. Reiniciar refaz a situação escolhida, inclusive os dados
fixados. A sequência de rolagens é limitada ao recorte declarado; novas ações
podem exigir dados que esse recorte não prevê.

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

As regressões de [test_simulator_entry.py](../../../tests/integration/test_simulator_entry.py)
verificam diretório externo, cenário explícito, erro de arquivo ausente e a
entrada do wheel com recurso carregado diretamente do ZIP. A janela e a criação
do cliente de IA são bloqueadas nessas verificações; o fluxo e o cenário são reais.

Um smoke adicional abre a janela, desenha o mapa e encerra o loop real com o
driver SDL sem tela, sem provedor configurado. Apenas o evento de saída é
simulado. Esse teste verifica que a entrada oficial mantém a interface jogável
após a limpeza das entradas antigas; não avalia respostas de um modelo real.

Também há uma regressão com cliente simulado para falha da janela: ela confere
que o fluxo entregue é o pré-composto, a configuração chega à UI e o cliente é
fechado uma única vez. O teste de falha de inicialização em
[test_logging.py](../../../tests/integration/test_logging.py) usa a CLI oficial
e verifica eventos de configuração, erro e encerramento na mesma sessão.

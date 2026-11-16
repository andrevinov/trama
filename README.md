# Trama

Sistema para jogar **D&D 5.5e com IA**, desenvolvido em Python e gerenciado com Poetry.

O objetivo final é ter uma IA narrando e conduzindo a experiência do jogador como em uma mesa de RPG. Vamos chegar lá aos poucos: primeiro, ferramentas e regras determinísticas; depois, interpretação de pedidos e narração com IA, apoiadas nesse funcionamento já validado.

## Como vamos construir

- Trabalhar em incrementos pequenos, definidos e orientados pelo responsável pelo projeto.
- Começar pelas partes determinísticas que ajudam a jogar. O primeiro módulo é movimento terrestre em grade, com regras da edição 2024.
- Explorar cada avanço com provas de conceito, incluindo pequenos cenários jogáveis quando fizer sentido.
- Transformar os comportamentos validados nessas experiências em testes reproduzíveis. Interações com serviços reais de IA também terão testes live, executados explicitamente.
- Manter as decisões de regras no código Python. A IA poderá interpretar intenções e narrar resultados, apoiando-se nas ações permitidas pelo sistema.

## Preparação

Requisitos: Python 3.14 e Poetry 2.3 ou superior.

```bash
poetry install
```

As dependências ficam em `pyproject.toml`, com versões resolvidas em `poetry.lock`.
Usamos Pygame Community Edition (`pygame-ce`) para a janela e o SDK oficial
`openai` para interpretação dos prompts. O pytest faz parte do grupo de desenvolvimento.

## Executar o simulador

```bash
poetry run python pocs/simulador/run.py --debug
```

O cenário atual é uma **fuga de dungeon**: quatro celas, corredor iluminado por
tochas com duas casas de largura, um guarda, banheiro e saída. O jogador é um
**Guerreiro Humano 3, Campeão, Defesa**, em trapos, sem equipamento, com 28 PV e
CA 11. A cela abre magicamente no início. Há caminhos de combate, disfarce,
furtividade e resgate de outro prisioneiro.

Objetos do mapa têm posição, fixação (`floor` ou `wall` com lado cardinal) e
efeitos independentes sobre passagem e visão. As quatro tochas ficam na parede
leste do corredor, desenhadas na borda das casas, sem bloquear movimento ou visão.
Consulte o [formato dos objetos](pocs/simulador/README.md#objetos-do-mapa).

A janela mantém mapa, conversa, Ficha e Inimigos. **Metros são a unidade padrão**;
cada casa mede 1,5 m. Com `OPENAI_API_KEY` exportada, a IA descreve a abertura,
interpreta mensagens e narra os resultados calculados. O modelo padrão é
`gpt-5.6-terra`, configurável por `TRAMA_OPENAI_MODEL`. Sem chave, a janela abre
para visualização e informa a configuração necessária.

**Enter** envia e **Shift+Enter** insere uma nova linha. Falas entre colchetes
são off, usadas para dúvidas, e não executam ações:

```text
Vou até a grade da Cela 4 e tento abri-la.
[Como funciona investigar um cômodo?]
```

Os testes, a descoberta/coleta de itens, a roupa vestida, as chaves e as respostas
do roteiro alteram o estado antes da narração. A ficha mostra o inventário em
**Dados → Equipamento e treinamento**. A espada precisa ser encontrada e pega;
o uniforme não concede armadura. O contexto do interpretador contém operações
e objetos conhecidos. O Mundo conhece os segredos, que a narração deve preservar.

O **modo narrado** não limita movimento por turno. O **modo por turnos** começa
quando há conflito, usa iniciativa, ações, bônus e reações, e avança pela conversa.
`Fico parado` ou `não faço mais nada`, como decisão de passar a vez, encerram o
turno. Ataques de oportunidade continuam disponíveis. A execução para no primeiro
impedimento e preserva o que já ocorreu; o off explica a causa.

O **movimento contextual** prepara a aproximação necessária para investigar um
cômodo, pegar um objeto, atacar em corpo a corpo, abrir/fechar, destrancar,
escutar ou acordar o prisioneiro. Cada ação declara um requisito espacial; a
aplicação calcula o percurso e revalida antes de executar. Alvo/arma inválidos ou
falta de ação conhecida barram a tentativa antes de caminhar. A aproximação de
um ataque que inicia combate vem depois da iniciativa, com movimento por turno.

Uma operação já satisfeita retorna `already_satisfied`, sem deslocamento ou
gasto. Dizer “sem sair do lugar” proíbe a aproximação contextual. Barreiras,
oportunidades e respostas do Mundo podem interromper o trajeto. O motor preserva
o progresso e não usa Dash, poderes ou abertura de outras portas automaticamente.

A rotina do banheiro e o auxílio do prisioneiro são específicos deste cenário.
Consulte o [README do simulador](pocs/simulador/README.md) para mapa, exemplos,
CDs, referências de D&D 2024, simplificações e critérios de sucesso. A IA escolhe
as ações do guarda em combate; o código adjudica as interações de exploração.
Abertura/reinício, mensagens e turnos de NPCs podem fazer chamadas pagas à API.

O runner anterior também abre a dungeon por padrão. Os mapas anteriores foram
preservados para regressões e podem ser abertos explicitamente:

```bash
poetry run python pocs/simulador/run.py --scenario pocs/movimento/cela_guardas.json
```

Os detalhes históricos estão na [POC de movimento](pocs/movimento/README.md).
O [experimento de interpretação](pocs/interpretacao/README.md) continua separado.

## Logs

Os logs do simulador ficam em **`logs/trama.jsonl`**, com o mesmo formato
JSON para todos os módulos e rotação automática. Para acompanhar prompts,
respostas da IA, validações, rolagens e mudanças no jogo:

```bash
poetry run python pocs/simulador/run.py --debug
```

O modo normal registra mensagens completas da conversa, operações, resultados,
erros e consumo de tokens. O
debug acrescenta o conteúdo completo das chamadas e os detalhes das regras.
Identificadores relacionam mensagem, chamadas à IA e operações, inclusive entre
threads. Consulte [o contrato e os exemplos de logs](docs/logging.md).
Para visualizar colunas e consultar tabelas de eventos, IA e erros, use o
[add-on do lnav](tools/lnav/README.md), independente da engine.
Ele mostra prévias específicas por evento; `|trama-detail` abre o texto completo
ou JSON do evento selecionado na visão LOG (`q` retorna).

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

As responsabilidades do código estão separadas:

| Componente | Responsabilidade |
| --- | --- |
| `spatial.py` | Posições e grade compartilhadas |
| `distances.py` | Metros, conversão de unidades na entrada e formatação |
| `movement.py` | Regras e custos de movimento |
| `scene.py` | Lugares, passagens, estados e opacidade do mapa |
| `actions.py` | Abrir/fechar e orçamento de ação, ação bônus, reação e interação |
| `dice.py` | Rolagens locais com aleatoriedade injetável |
| `characters.py` | Fichas e recursos de Humano/Guerreiro 1–3/Campeão |
| `combat.py` | Iniciativa, ordem de turnos e resolução de ataques básicos |
| `reactions.py` / `application/travel.py` | Gatilho geométrico de oportunidade e coordenação de movimento, decisão e reação |
| `vision.py` | Campo de visão normal e obscurecimento |
| `creatures.py` | Criaturas posicionadas, sem comportamento |
| `application/` | Intenções, caminhos, sessão e contexto para interpretação |
| `application/preparation.py` | Contrato de requisitos espaciais e cálculo da aproximação, sem executar efeitos |
| `application/dungeon.py` | Estado e adjudicação do cenário de fuga, sem SDK ou Pygame |
| `simulator.py` | Composição do cenário, adaptadores e janela |
| `application/encounter.py` / `sheets.py` | Recursos do encontro e projeções das fichas para UI/IA |
| `application/sheet_options.py` | Consulta de disponibilidade, custos e recuperação para a ficha, sem executar ações |
| `application/dialogue.py` / `conversation.py` | Canais on/off, histórico, execução ordenada e fatos para narração |
| `application/modes.py` | Modos narrado/por turnos e contrato fixo compartilhado |
| `application/world.py` / `world_resolution.py` | Respostas do Mundo e validação das ações de NPCs |
| `application/failures.py` | Dados estruturados dos impedimentos, sem dependência de IA ou visualização |
| `infrastructure/` | Adaptadores separados para ação do Jogador, decisão do Mundo e narração |
| `ui/` | Entrada e visualização Pygame, sem dependência do provedor de IA |
| `observability.py` | Configuração de logs JSON, correlação e rotação; produtores de regras usam apenas `logging` padrão |

Mapa e movimento não dependem das fichas; combate usa fichas e dados, sem conhecer
Pygame ou OpenAI. A aplicação coordena os resultados e filtra o que é visível.
Testes de fronteira protegem essa separação. O narrador já descreve a cena e os
resultados implementados; a aventura completa ainda depende de outros incrementos.

## Testes

```bash
# Testes locais, sem chamadas externas.
poetry run pytest

# Testes live, quando houver cenários implementados e credenciais configuradas.
poetry run pytest tests/live -m live
```

Os testes live usam o marcador `live` e ficam fora da descoberta padrão. Consulte
[tests/live/README.md](tests/live/README.md) para as convenções. Os testes de
movimento cobrem regras, integração com respostas simuladas e desenho da janela
com driver SDL sem interface gráfica. A suíte padrão não faz chamadas de IA.
Há uma [suíte live focada de movimento contextual](tests/live/README.md), com oito
situações da dungeon. Para executar apenas ela, com chamadas pagas autorizadas:

```bash
RUN_OPENAI_LIVE_TESTS=1 poetry run pytest tests/live/test_contextual_movement.py -m live -v
```

Os resultados e logs completos ficam em `logs/live/contextual_movement/`.


## Estado atual

Simulador narrado com mapa, visão, itens do cenário, testes de atributo, disfarce,
furtividade, chaves, NPCs e uma base de combate por turnos com oportunidades.
As regras reutilizáveis permanecem separadas da adjudicação específica da dungeon,
da entrada/saída, da interpretação por IA e da visualização. O escopo e as
limitações do encontro estão registrados no README do simulador.

As orientações para agentes e contribuições estão em [AGENTS.md](AGENTS.md).

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

## Experimentar movimento

```bash
poetry run python pocs/movimento/run.py
```

A janela mostra a **Cela**, o **Corredor** e a **Sala dos Guardas**, com o
personagem na Cela. A grade começa aberta; a porta dos guardas, fechada e
destrancada. O corredor ocupa 7 casas (10,5 m), aproximando os 10 m solicitados
para preservar as casas de 1,5 m da demonstração.

**Metros são a unidade padrão** das regras, dos arquivos de cenário, do contexto
da IA e da tela. A velocidade inicial é 9 m por turno; cada casa custa 1,5 m,
ou 3 m em terreno difícil. Entradas explícitas em pés são convertidas pelo
código na convenção de D&D: 5 pés equivalem a 1,5 m.

Com `OPENAI_API_KEY` exportada, a IA começa descrevendo a cena. O painel de
conversa recebe a resposta do narrador e mantém o histórico com rolagem.
Digite uma ação e, se quiser, uma pergunta em off entre colchetes:

```text
Ando 5 m para a direita.
[Como funciona Dash?]
```

**Enter** envia; **Shift+Enter** insere uma nova linha. Textos entre colchetes
não executam ações. A IA narra o resultado em on e responde regras/dúvidas em
off, também entre colchetes. Se não puder realizar nada, responde só em off.

O jogo executa o possível **até o primeiro impedimento**, preservando o progresso.
Pedidos podem encadear movimento, abrir e fechar. Uma parede, porta fechada,
guarda, limite do mapa ou saldo insuficiente interrompe a execução e as etapas
seguintes. O off informa onde parou e por quê. Na grade atual, 5 m permitem andar
4,5 m; o meio metro restante é explicado, sem arredondar para cima.

Cada abertura/reinício faz uma chamada para a descrição inicial; uma mensagem
com ações usa normalmente duas (interpretação e narração), e uma mensagem só off
usa uma. As chamadas à Responses API são potencialmente pagas. O modelo padrão
é `gpt-5.6-luna`, configurável por `TRAMA_OPENAI_MODEL`. Sem a chave, a janela
informa a configuração necessária. Falhas de narração não desfazem nem repetem
ações já executadas.

O Python valida o percurso e calcula seu custo antes de atualizar a posição.
O saldo de movimento persiste entre pedidos; o botão **Novo turno** o renova.
O código resolve destinos nomeados pelo menor caminho livre, respeitando paredes
e passagens. “Até a porta” para numa casa adjacente; não abre a porta.
Depois de se aproximar, envie **“abra a porta”** ou **“feche a porta”**.
A primeira interação do turno é gratuita; a seguinte usa Utilize, que compartilha
a ação com Dash. **Novo turno** também renova esses recursos.

O personagem usa visão normal humana. O cenário está iluminado, e a região clara
do mapa indica o campo de visão atual, limitado por paredes e portas fechadas.
Há **três guardas parados** na sala. Eles aparecem somente quando visíveis e
suas casas não podem ser atravessadas. Abrir a porta revela os guardas; fechá-la
volta a ocultá-los. A IA recebe somente as criaturas atualmente visíveis.
O cenário original 10×10 continua disponível com
`poetry run python pocs/movimento/run.py --scenario pocs/movimento/scenario.json`.
Consulte [a prova de conceito](pocs/movimento/README.md) para preparação, referências
de regras, exemplos, limitações e testes live opcionais.

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
| `actions.py` | Abrir/fechar e orçamento de interações/ação |
| `vision.py` | Campo de visão normal e obscurecimento |
| `creatures.py` | Criaturas posicionadas, sem comportamento |
| `application/` | Intenções, caminhos, sessão e contexto para interpretação |
| `application/dialogue.py` / `conversation.py` | Canais on/off, histórico, execução ordenada e fatos para narração |
| `infrastructure/` | Adaptadores separados para interpretar ações e narrar resultados |
| `ui/` | Entrada e visualização Pygame, sem dependência do provedor de IA |

As regras não importam umas às outras: a aplicação coordena seus resultados.
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

## Estado atual

Primeiro módulo implementado: movimento terrestre em grade, terreno difícil,
bloqueios, diagonais e Dash, com interface Pygame e interpretação pela OpenAI.
O mapa inclui lugares e passagens nomeados, seus estados e cálculo de percurso.
Há interações de abrir/fechar, visão humana básica e três guardas estáticos.
O fluxo de jogo inclui descrição inicial, mensagens on/off e narração após a
execução completa ou parcial das ações.
O escopo ainda é uma prova de conceito, sem motor completo de combate.

As orientações para agentes e contribuições estão em [AGENTS.md](AGENTS.md).

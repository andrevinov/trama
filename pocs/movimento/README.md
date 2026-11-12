# Movimento, ações e conversa

## Objetivo

Experimentar uma mesa de D&D 5.5e por mensagens: o narrador descreve a cena
inicial, o jogador propõe ações e/ou pergunta em off, o Python executa o possível
e a IA narra o resultado validado. O mapa Pygame acompanha posição, passagens,
visão e guardas. Não há motor completo de combate ou comportamento de inimigos.

## Preparação e execução

Com Python 3.14 e Poetry, na raiz do repositório:

```bash
poetry install
poetry run python pocs/movimento/run.py
```

O SDK oficial usa `OPENAI_API_KEY` exportada no ambiente do terminal. Não há
leitura automática de `.env`, login do ChatGPT ou MCP. A janela usa Pygame
Community Edition (`pygame-ce`, importado como `pygame`) e precisa de ambiente
gráfico para uso interativo. Sem a chave, exibe uma orientação em off.

| Variável | Uso | Padrão |
| --- | --- | --- |
| `OPENAI_API_KEY` | Autenticação na API | Necessária para conversar |
| `TRAMA_OPENAI_MODEL` | Modelo dos dois adaptadores | `gpt-5.6-luna` |
| `RUN_OPENAI_LIVE_TESTS` | Autorizar testes pagos explicitamente | Desabilitado |

Abrir/reiniciar a demonstração faz **uma chamada real** para a descrição inicial.
Uma mensagem com ação faz normalmente **duas chamadas**: interpretação e narração.
Uma mensagem apenas em off faz **uma chamada**, diretamente ao narrador.
Todas são potencialmente pagas. Os adaptadores usam Responses API, JSON Schema
estrito, raciocínio `low` e até 1000 tokens de saída por chamada. O cliente tem
prazo de 30 segundos e nenhuma repetição automática. A disponibilidade do modelo
depende da conta.

## Conversa on/off

O painel à direita mantém as mensagens do jogador e do narrador. Fala em jogo
(on) aparece sem delimitadores. Regras, dúvidas e explicações (off) aparecem
entre **colchetes**, em outra cor. É possível misturar os dois canais:

```text
Ando 5 metros para a direita.
[Pode me explicar como funciona Dash?]
```

Apenas o texto fora dos colchetes é enviado ao interpretador de ações. Texto em
off, inclusive no histórico, nunca propõe ações na engine. Perguntas em off são
respondidas pelo narrador, junto à narração do resultado quando houver ação.
Colchetes desbalanceados pedem correção antes de qualquer execução.

O narrador recebe fatos verificados: percurso realizado, custo, posição final,
portas alteradas e percepção atual. Não pode alterar o mundo, inventar reações
dos guardas ou declarar concluída uma parte impedida. Para dúvidas, recebe as
regras implementadas e suas referências; deve pedir referência quando não houver
base, por exemplo para uma mecânica de “Dados Místicos” não definida no projeto.
Não há busca automática em livros ou na internet durante o jogo.

O código controla os canais: se nada foi realizado, a resposta é **somente off**.
Se houve progresso parcial, o on descreve o realizado e o off informa onde parou,
o motivo e que etapas seguintes ficaram sem execução. O motivo e a localização
são acrescentados deterministicamente, mesmo que a IA os omita.

## Execução até o primeiro impedimento

A política anterior de rejeitar o pedido inteiro foi substituída por decisão do
usuário. O código executa o maior prefixo legal do pedido, preservando o progresso:

- Para antes de paredes, portas/grades fechadas, guardas, limites do mapa ou
  da próxima casa que o saldo não permita pagar.
- Um pedido pode ter até 10 operações em ordem, combinando movimento, abrir e
  fechar. “Corra até a porta, abra e entre” é processado nessa ordem.
- A primeira operação impedida encerra o processamento. Não pula o obstáculo
  para executar partes posteriores. Operações já realizadas não são desfeitas.
- Se não existe caminho livre a um lugar, o planejamento pode usar o percurso
  arquitetônico; a execução real para na passagem fechada, sem abri-la.
- Distâncias fracionárias executam as casas inteiras possíveis. **5 m** em espaço
  livre produzem **4,5 m**, com explicação off sobre os **0,5 m** restantes.
- Uma distância menor que uma casa não move o personagem nem consome Dash.
- Dash indisponível permite usar apenas o saldo normal restante, explicando em off.
- Pedidos ambíguos ainda pedem esclarecimento. O personagem não tem orientação
  própria: “para frente” sem direção definida não autoriza escolher um rumo.

Respostas inválidas ou incompletas da interpretação não executam ações. Se a
narração falhar **depois** da execução, os efeitos permanecem; a janela registra
um resumo local em off e não repete as ações. Não há repetição automática de rede.

## Controles

- **Enter** ou **Enviar**: enviar a mensagem; **Shift+Enter**: nova linha.
- **Roda do mouse / PgUp / PgDn**: percorrer a conversa, sem truncar mensagens.
- Setas, Home, End, Backspace e Delete editam o texto. Ctrl+A seleciona tudo;
  Ctrl+V cola, preservando novas linhas. Limite: **2000 caracteres**.
- **Novo turno** renova movimento, ação e interação gratuita; a conversa continua.
- **Reiniciar cenário** restaura posição, passagens e conversa, e solicita outra
  descrição inicial ao narrador. **Esc** fecha a janela.
- Durante uma chamada, envio, edição e mudanças de turno aguardam a resposta;
  desenho, fechamento e rolagem da conversa continuam funcionando.

## Cenário e unidades

`cela_guardas.json` contém Cela, Corredor e Sala dos Guardas numa grade 19×11.
O personagem começa na Cela, na coluna 4, linha 6. A grade começa aberta; a porta
começa fechada e destrancada. O corredor ocupa 7 casas: **10,5 m**, aproximação
registrada dos 10 m pedidos para manter casas inteiras.

**Metros** são a unidade padrão dos cenários (`speed_meters`), estado, custos,
contexto da IA e visualização. Velocidade inicial: **9 m**; com Dash: **18 m**.
Cada casa custa **1,5 m**, ou **3 m** em terreno difícil. Os cálculos usam Decimal.
Entradas explícitas em pés são convertidas no código: **5 pés = 1,5 m**, na
convenção de D&D. Entradas sem unidade são metros. A IA preserva o valor recebido;
a conversão e a separação da fração restante cabem ao Python.

Colunas crescem para a direita, linhas para baixo e norte fica para cima.
Coordenadas visíveis começam em 1; os arquivos JSON e o domínio começam em 0.
A linha dourada mostra o último percurso e o círculo verde, a posição atual.

O tabuleiro original 10×10 continua disponível, com a mesma política de execução:

```bash
poetry run python pocs/movimento/run.py --scenario pocs/movimento/scenario.json
```

## Portas, visão e guardas

As passagens da POC são mecanismos simples de operação manual. Abrir/fechar
requer estar na mesma casa ou numa casa adjacente de 1,5 m, sem alcançar através
de paredes. Porta trancada não abre; não se fecha uma passagem com alguém em seu
espaço. Esses critérios operacionais de alcance e ocupação são decisões da POC.
Repetir o estado atual não consome recursos. Trancar, destrancar, forçar portas
e combater ainda pedem esclarecimento em off.

A primeira interação do turno é gratuita; a seguinte usa **Utilize**, compartilhando
a ação com Dash. Após correr até a porta, ainda é possível abri-la pela interação
gratuita. Fechá-la em seguida exigirá um novo turno se a ação já foi usada.

O observador é um Humano Médio com visão normal, sem visão no escuro. Todo o
cenário está em luz plena. Listas opcionais `dim` e `dark` no JSON permitem marcar
casas em luz fraca ou escuridão. Luz fraca permanece visível com obscurecimento
leve; escuridão é obscurecimento pesado para esse observador. Não há testes de
Percepção, furtividade, sentidos especiais ou propagação de fontes de luz.

A visão é de 360°, sem cone ou limite artificial de distância. Paredes e portas
fechadas são opacas; grades permitem ver pelas barras mesmo fechadas. Criaturas
não são paredes opacas. O cálculo amostra cantos do observador e nove pontos
do destino, uma aproximação discreta da geometria do DMG. A face de um obstáculo
pode ser vista sem revelar o que está atrás dele.

O mapa arquitetônico e seus nomes são conhecidos para navegação; regiões fora
da visão atual ficam escuras. O narrador descreve somente a percepção atual.
Os três guardas Médios, hostis e conscientes, permanecem parados nas posições
internas (15, 4), (15, 5) e (15, 6). Não se atravessam suas casas. São desenhados
e enviados à IA somente quando visíveis; não há ficha de combate, ataques,
iniciativa ou comportamento de IA para eles.

## Referências e limites

Foram consultados os PDFs locais em `books/rules/5.5e/`: **PHB 2024**, Vision and
Light, Human Traits, pp. 23–25 (turno, movimento, grade, interação com objetos),
e glossário Dash/Utilize; **DMG 2024**, p. 45, Diagonals e Line of Sight.
Os livros não são versionados. Fontes oficiais abertas equivalentes:
[Playing the Game](https://www.dndbeyond.com/sources/dnd/br-2024/playing-the-game),
[Rules Glossary](https://www.dndbeyond.com/sources/dnd/br-2024/rules-glossary) e
[Human](https://www.dndbeyond.com/sources/dnd/br-2024/character-origins#Human).

Usamos diagonais de 1,5 m do PHB, sem ativar a alternativa 1,5/3 m do DMG.
Saltos, escalada, voo, natação, rastejar, condições, montarias, habilidades de
classe e ataques de oportunidade ainda não estão implementados. Cada operação
de movimento aceita até 10 segmentos de até 10000 m; valores são limitados antes
da execução. O planejamento de destino nomeado encontra o menor custo, enquanto
segmentos direcionais preservam o percurso solicitado.

## Critérios observáveis de sucesso

Reinicie antes dos exemplos independentes:

| Entrada/ação | Resultado esperado |
| --- | --- |
| Abrir a demonstração com chave | Primeira mensagem do narrador descreve a Cela e o visível; guardas ocultos |
| `Ando 5 m para a direita. [Como funciona Dash?]` | Avança 4,5 m até coluna 7, linha 6; on narra isso; off responde e explica 0,5 m restantes |
| `[Quanto movimento me resta?]` | Só resposta off, sem alterar estado ou executar interpretação |
| `Caminhe até a porta e abra.` | Avança 9 m até coluna 10, linha 6; para por saldo, não abre; explica em off |
| `Corra até a porta, abra e entre na Sala dos Guardas.` | Coluna 15, linha 6; custo total 16,5 m; porta aberta; guardas visíveis e parados |
| `Corra para dentro da Sala dos Guardas.` com porta fechada | Para na coluna 13, linha 6, diante da porta; explica o bloqueio |
| `Abra a porta.` da posição inicial | Só off explicando alcance; posição e porta preservadas |
| `Ande dez casas para cima.` no tabuleiro original | Anda até o limite e explica onde parou, sem sair do mapa |

Verifique a rolagem com uma conversa longa e o envio multilinha. Abrir a porta
revela os guardas; após **Novo turno**, fechá-la pelo corredor os oculta. Simular
uma falha na narração deve preservar os efeitos já executados e registrar um
resumo off sem repetir o movimento.

## Testes

```bash
# Regras, diálogo, adaptadores simulados e Pygame sem janela real/rede:
poetry run pytest
poetry check

# Testes reais opcionais e pagos (chave + autorização explícita):
RUN_OPENAI_LIVE_TESTS=1 poetry run pytest tests/live/test_openai_movement.py -m live -v
```

O módulo live inteiro faz **oito chamadas**: cinco testes básicos de interpretação,
uma descrição inicial e uma troca mista que usa interpretação e narração.
É possível selecionar `-k initial_narration` (uma chamada) ou
`-k mixed_message` (duas chamadas). A avaliação verifica estrutura, fatos do
estado e invariantes, sem exigir frases idênticas. Uma execução real aprovada
não garante que o modelo entenderá ou narrará corretamente qualquer outra frase.

## Separação dos componentes

- `spatial.py` / `distances.py`: grade, posições e metros.
- `movement.py`: movimento e interrupções; sem IA, diálogo ou Pygame.
- `scene.py`, `actions.py`, `vision.py`, `creatures.py`: mapa, interações, visão e entidades.
- `application/intents.py`: operações e planos estruturados.
- `application/routing.py` / `session.py`: planejamento e execução do estado.
- `application/dialogue.py`: canais on/off e contrato do narrador.
- `application/conversation.py`: sequência de ações, histórico e relatório para narração.
- `application/context.py`: contexto com criaturas visíveis.
- `infrastructure/openai_intent_interpreter.py`: interpretação de ações.
- `infrastructure/openai_narrator.py`: descrição inicial, narração e respostas off.
- `infrastructure/openai_json.py`: transporte JSON compartilhado, sem regras de jogo.
- `ui/movement_window.py`: painel de conversa, entrada e mapa, sem importar OpenAI.

Caminhos relativos a `src/trama/`. O `run.py` monta as dependências. A IA propõe
intenções e narra fatos; somente a engine determinística altera o mundo.

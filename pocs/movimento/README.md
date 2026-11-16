# Mapas anteriores — movimento, fichas, turnos e conversa

O cenário jogável atual está em [Simulador](../simulador/README.md). Este
documento descreve os mapas anteriores, preservados para regressão. O runner
antecessor agora abre a dungeon por padrão; especifique o JSON abaixo para
reproduzir o cenário antigo.


## Objetivo

Experimentar uma mesa de D&D 5.5e por mensagens: o narrador descreve a cena
inicial, o jogador propõe ações e/ou pergunta em off, o Python executa o possível
e a IA narra o resultado validado. O mapa Pygame acompanha posição, passagens,
visão, fichas e guardas. Há uma base de combate por turnos, com ataques corpo a
corpo simples; a IA decide respostas dos NPCs, executadas e validadas pelo Python.

## Preparação e execução

Com Python 3.14 e Poetry, na raiz do repositório:

```bash
poetry install
poetry run python pocs/movimento/run.py --scenario pocs/movimento/cela_guardas.json
```

Para acompanhar o diagnóstico completo:

```bash
poetry run python pocs/movimento/run.py --scenario pocs/movimento/cela_guardas.json --debug
tail -F logs/trama.jsonl
```

`--log-file logs/caso-porta.jsonl` escolhe outro arquivo. Os logs usam um envelope
JSON comum, com módulo, evento e identificadores de execução, mensagem, operação
e chamada de IA. DEBUG inclui instruções e contexto enviados, resposta original,
decisão validada, erro concreto, rolagens, recursos e alterações do jogo. INFO
mantém resultados e tokens informados pela API. O arquivo tem rotação de 5 MB
com três cópias; não há chamadas adicionais de IA para gerar logs.
Veja [o contrato e o roteiro para investigar planos inválidos](../../docs/logging.md).

O SDK oficial usa `OPENAI_API_KEY` exportada no ambiente do terminal. Não há
leitura automática de `.env`, login do ChatGPT ou MCP. A janela usa Pygame
Community Edition (`pygame-ce`, importado como `pygame`) e precisa de ambiente
gráfico para uso interativo. Sem a chave, exibe uma orientação em off.

| Variável | Uso | Padrão |
| --- | --- | --- |
| `OPENAI_API_KEY` | Autenticação na API | Necessária para conversar |
| `TRAMA_OPENAI_MODEL` | Modelo dos três adaptadores | `gpt-5.6-terra` |
| `RUN_OPENAI_LIVE_TESTS` | Autorizar testes pagos explicitamente | Desabilitado |

Abrir/reiniciar a demonstração faz **uma chamada real** para a descrição inicial.
Uma mensagem com ação faz normalmente **três chamadas**: ação do Jogador, decisão do Mundo e narração.
Cada turno de NPC em conflito acrescenta uma decisão do Mundo.
Inconsistência entre origens declaradas e plano permite uma tentativa de correção antes
de qualquer efeito; ela acrescenta no máximo uma chamada.
Uma mensagem apenas em off faz **uma chamada**, diretamente ao narrador.
Todas são potencialmente pagas. Os adaptadores usam Responses API, JSON Schema
estrito e raciocínio `low`: até 1000 tokens para interpretação/narração e
até 2000 para decisões do Mundo. O cliente tem
prazo de 30 segundos e nenhuma repetição automática de falhas de rede. A disponibilidade do modelo
depende da conta.

O interpretador recebe contexto mínimo, separado do cenário completo enviado ao
Mundo. A IA interpreta o pedido e fornece trechos de origem classificados; o
código verifica os dados e as regras de cada etapa, sem lista de verbos. O
contexto inclui último alvo/arma efetivamente usados e recursos de turno. Veja
[o contrato e seus limites](../../docs/action-authorization.md) e
[o experimento](../interpretacao/README.md).

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
dos guardas sem uma decisão do Mundo validada, ou declarar concluída uma parte impedida. Para dúvidas, recebe as
regras implementadas e suas referências; deve pedir referência quando não houver
base, por exemplo para uma mecânica de “Dados Místicos” não definida no projeto.
Não há busca automática em livros ou na internet durante o jogo.

O código controla os canais: se nada foi realizado, a resposta é **somente off**.
Se houve progresso parcial, o on descreve o realizado e o off informa onde parou,
o motivo e que etapas seguintes ficaram sem execução. O motivo e a localização
são acrescentados deterministicamente, mesmo que a IA os omita.

## Execução até o primeiro impedimento

Depois de uma execução, `[Por que o guarda não atacou?]` consulta o resultado
mais recente do motor, com motivo, posições e ações puladas, separado do relatório
vazio da pergunta. Perguntas sucessivas não apagam esse registro. Uma nova
tentativa o substitui e **Reiniciar** o limpa. Consultar não gasta recursos, não
executa ataques e não avança turnos. O registro descreve o que aconteceu, sem
corrigir automaticamente um destino inválido escolhido pelo Mundo.

A política anterior de rejeitar o pedido inteiro foi substituída por decisão do
usuário. O código executa o maior prefixo legal do pedido, preservando o progresso:

- Para antes de paredes, portas/grades fechadas, guardas, limites do mapa ou
  de uma resposta impeditiva do Mundo; em conflito, também da próxima casa
  que o saldo não permita pagar.
- Um pedido pode ter até 10 operações em ordem, combinando movimento, abrir e
  fechar, ataques e recursos da classe. “Corra até a porta, abra e entre” é
  processado nessa ordem.
- A primeira operação impedida encerra o processamento. Não pula o obstáculo
  para executar partes posteriores. Operações já realizadas não são desfeitas.
- Se não existe caminho livre a um lugar, o planejamento pode usar o percurso
  arquitetônico; a execução real para na passagem fechada, sem abri-la.
- Distâncias fracionárias executam as casas inteiras possíveis. **5 m** em espaço
  livre produzem **4,5 m**, com explicação off sobre os **0,5 m** restantes.
- Uma distância menor que uma casa não move o personagem nem consome Dash.
- Em conflito, Dash indisponível permite usar apenas o saldo normal restante, explicando em off.
- Pedidos ambíguos ainda pedem esclarecimento. O personagem não tem orientação
  própria: “para frente” sem direção definida não autoriza escolher um rumo.

Respostas inválidas ou incompletas da interpretação não executam ações. Se a
narração falhar **depois** da execução, os efeitos permanecem; a janela registra
um resumo local em off e não repete as ações. Não há repetição automática de rede.

## Controles

- **Enter** ou **Enviar**: enviar a mensagem; **Shift+Enter**: nova linha.
- **Roda do mouse / PgUp / PgDn**: percorrer a conversa, sem truncar mensagens.
  Sobre a ficha, a roda percorre o conteúdo da ficha.
- **Jogo / Ficha / Inimigos**: alternar o painel esquerdo. A conversa permanece
  visível; é possível consultar as guias enquanto uma resposta está pendente.
- Na **Ficha**, **Agora / Recursos / Dados** selecionam a seção; clique no
  cabeçalho de um cartão para abrir ou fechar os detalhes. Esses cliques só consultam.
- Ao surgir uma oportunidade do personagem, **Atacar (reação)** ou **Deixar
  passar** decide a resposta e retoma o movimento do NPC. Os botões aparecem no
  painel de turno; não é necessário enviar outro pedido à IA para essa escolha.
- Setas, Home, End, Backspace e Delete editam o texto. Ctrl+A seleciona tudo;
  Ctrl+V cola, preservando novas linhas. Limite: **2000 caracteres**.
- A exploração começa no **modo narrado**, sem limite por turno. Não há botões
  de iniciar combate ou novo turno. Um confronto entra naturalmente no **modo
  por turnos**; `Encerro meu turno` passa a vez e a IA resolve os guardas.
- Em combate, `fico parado`, `não faço nada` ou `aguardo`, como declaração de
  passar a vez sem outra ação, também encerram o turno. Na exploração são espera
  narrativa. Permanecer parado durante outra ação não a encerra antecipadamente.
- **Reiniciar** restaura posição, passagens, fichas, recursos e conversa, e solicita outra
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
Repetir o estado atual não consome recursos. Trancar, destrancar e forçar portas
ainda pedem esclarecimento em off.

No modo por turnos, a primeira interação do turno é gratuita; a seguinte usa **Utilize**, compartilhando
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
Os três guardas Médios, hostis e conscientes, começam nas posições do cenário.
O Mundo pode fazê-los falar, caminhar, abrir/fechar passagens, observar, iniciar
ou encerrar conflito e atacar em seu turno. Percursos, alcance, iniciativa,
recursos e dano são validados pelo código. As casas ocupadas continuam bloqueadas.
O Python calcula o caminho dos NPCs contornando paredes e criaturas, sem cortar
quinas. Portas abertas permitem passagem e ocupação. Se uma porta fechada ou o
saldo de movimento impedir alcançar o destino, preserva-se o trecho realizado e
a resposta para antes das ações seguintes, incluindo ataques.
A IA recebe todos no contexto `world`; o campo `perception` e a interface exibem
somente o que é percebido. Fatos ocultos não devem aparecer na narração sem causa.

## Fichas e escolhas do cenário

A guia **Ficha** mostra um resumo de PV, CA, velocidade e classe, com três seções:

- **Agora — O que posso fazer:** cartões de movimento, ataque, Retomar o Fôlego,
  Surto de Ação, portas, Dash, interação e encerramento de turno. Cada um indica
  disponibilidade, condição ou impedimento atual. Preparar aparece sem execução.
- **Recursos — Fora do turno e recuperação:** reação, Inspiração Heroica, Mente
  Tática, usos com recuperação por descanso e itens mágicos. Oportunidades usam
  a reação e pedem confirmação quando surgem. Mente Tática e descansos ainda não têm comandos; o cenário não registra efeitos
  de itens mágicos. A ficha distingue essas limitações de um recurso gasto.
- **Dados:** atributos, salvaguardas, perícias, equipamento, maestrias e traços.

Clique no cabeçalho de um cartão para expandir/recolher detalhes de uso, custo,
momento, recuperação e exemplos. Role sobre o painel para continuar a leitura.
A consulta não altera o jogo e pode ser feita enquanto uma resposta está em
andamento. As ações são solicitadas pela conversa. A projeção é calculada pela
aplicação, sem SDK ou Pygame; a interface apenas apresenta o resultado. Esta
mudança não adiciona novas ações de combate, itens ou regras de descanso.

O jogador usa **Humano Médio, Guerreiro 3, Campeão e Defesa**, conforme a escolha
do usuário. Os guardas usam Humano Médio, Guerreiro 1 e Defesa, sem subclasse.
Para as escolhas restantes, esta POC adota:

- Atributos pela matriz padrão: FOR 15, DES 12, CON 14, INT 10, SAB 13, CAR 8;
  Soldado concede +2 FOR e +1 CON. Resultado: **17, 12, 15, 10, 13, 8**.
- Soldado: Atletismo, Intimidação, proficiência em jogos de dados e o talento
  **Savage Attacker**. O Humano escolhe Sobrevivência por Skillful e **Skilled**
  por Versatile: Acrobacia, História e Investigação. A classe escolhe Percepção
  e Intuição. São oito perícias distintas.
- Cota de malha, espada grande, mangual e oito azagaias, da opção A da classe.
  Soldado usa a opção monetária de equipamento. Mochila, moedas e inventário
  geral ainda não são simulados; o recorte atual registra armadura e armas.
- Maestrias: espada grande (**Graze**), mangual (**Sap**) e azagaia (**Slow**).
- PV fixos após o primeiro nível: **28 PV** para o jogador e **12 PV** para cada
  guarda. Cota de malha 16 + Defesa 1 = **CA 17**. Velocidade **9 m**.

As escolhas de ficha ficam em `player` e em `creatures[].sheet` no JSON. O motor
suporta esse conjunto de origem/estilo/subclasse; ainda não é um criador geral de
personagens. Começa após um descanso longo válido, com recursos cheios e
Inspiração Heroica. Idiomas, biografia, carga e inventário completo não são
modelados neste incremento.

| Traço/recurso | Regra implementada |
| --- | --- |
| Humano: Resourceful | Recebe Inspiração Heroica após descanso longo; não acumula duas |
| Humano: Skillful / Versatile | Uma perícia adicional e o talento de origem escolhido |
| Defesa | +1 CA com armadura; não se aplica sem armadura |
| Retomar o Fôlego | Ação bônus, cura 1d10 + nível; 2 usos; descanso curto recupera 1 e longo recupera todos |
| Maestria em Armas | Três escolhas; pode trocar uma após descanso longo |
| Surto de Ação (2) | Uma ação adicional, exceto Magia; um uso por descanso curto/longo |
| Mente Tática (2) | +1d10 a teste de atributo falho; consome Retomar o Fôlego só se converter em sucesso |
| Crítico Aprimorado (3) | Armas e ataques desarmados têm crítico com 19–20 natural |
| Atleta Notável (3) | Vantagem em iniciativa e Força (Atletismo); movimento imediato de até metade da velocidade após crítico, sem ataques de oportunidade |
| Savage Attacker | Uma vez por turno, duas rolagens dos dados de dano da arma; a POC escolhe automaticamente a maior |

A guia **Ficha** mostra atributos e modificadores, salvaguardas, perícias,
proficiências, CA, PV, Dados de Vida, armas, maestrias e recursos em cartões
expansíveis, além das possibilidades atuais em **Agora**. **Inimigos**
mostra nome, espécie, classe/nível, PV, CA e arma dos guardas visíveis. Fechar a
porta os retira desse painel e do contexto atual da IA.

Nas projeções de ficha enviadas à IA, `at_zero_hp` indica exclusivamente se os
PV estão zerados. O campo `combat` informa o combate atual (`null` em exploração).

## Combate por turnos: alcance deste incremento

Ver guardas não inicia combate automaticamente. A intenção de ataque ou uma
resposta justificada do Mundo inicia conflito e rola iniciativa antes dos golpes.
Se o jogador ganha, o ataque pedido é resolvido; se um guarda ganha, o jogador
aguarda os turnos dos NPCs antes de escolher sua ação. Não há ataque gratuito
antes da iniciativa. Campeão tem vantagem; guardas idênticos rolam em grupo.
Desempates são uma decisão do cenário: jogador primeiro, guardas na ordem do JSON.

`Encerro meu turno` avança a vez do jogador. Cada turno de NPC é consultado à IA,
executado e encerrado automaticamente. Recursos de turno retornam no início do
turno correspondente; usos da classe e Inspiração não são recuperados por isso.
Uma decisão de trégua/fim do conflito retorna ao narrado, preservando PV e usos.
Não há relógio contínuo de exploração nem turnos artificiais fora de conflito.
Veja [o contrato de modos, respostas e pontos de interrupção](../../docs/game-flow.md).

Para exercitar os recursos, o recorte inclui **um ataque corpo a corpo por ação**
contra um participante visível e adjacente (1,5 m), sem obstáculo no alcance.
A IA envia somente intenção, alvo e arma. O Python usa FOR + proficiência,
rola o d20, compara com CA, resolve 1/20 naturais, crítico e dano. Críticos dobram
os dados, sem dobrar o modificador. O jogador ainda não tem Ataque Extra, que
chega no nível 5; Surto de Ação permite uma segunda ação de Ataque ou Dash.

Graze causa apenas o modificador de atributo quando o ataque erra. Sap impõe
desvantagem no próximo ataque do alvo até o início do próximo turno da fonte.
Slow reduz velocidade em 3 m sem acumular, até o início do próximo turno da
fonte. O movimento de Atleta Notável tem saldo separado, consumido primeiro;
termina ao realizar outra operação ou encerrar o turno. O relatório identifica
quanto movimento ficou protegido. Esse trecho protegido não provoca ataques
de oportunidade. O movimento normal pode provocá-los ao sair do alcance de um
adversário que vê a criatura; entrar ou circular dentro do alcance não provoca.
Um ataque de oportunidade usa reação, sem consumir a ação normal. O Jogador
confirma ou recusa no painel de turno; os guardas reagem automaticamente neste
cenário. A reação volta no início do turno do seu dono. Veja
[detalhes e simplificações](../../docs/opportunity-attacks.md).

Exemplos após abrir a porta e se aproximar de um guarda:

```text
Ataque o Guarda 1 com o mangual.
Use Surto de Ação e ataque o Guarda 1 com a espada grande.
Use Retomar o Fôlego.
Encerre o turno.
```

Inspiração Heroica tem API para rerrolar **qualquer dado**, mantendo o novo
resultado mesmo pior. No prompt de ataque, `use_inspiration` autoriza rerrolar
obrigatoriamente o d20 imediatamente após a rolagem original, antes do dano.
Escolhas interativas após ver os dados, condições como “só se errar” e rerrolagens
de outros dados por prompt ainda pedem esclarecimento.

Descansos, Dados de Vida, testes de atributo, Mente Tática e troca de maestria
têm funções puras em `characters.py`, testadas sem IA. Ainda não há comandos
para eles na janela. A aplicação que chamar os efeitos de descanso deve antes
validar duração, interrupções e elegibilidade; não há avanço instantâneo de tempo
por prompt. Um descanso longo válido recupera todos os Dados de Vida na edição
2024; não cria novas azagaias.

A 0 PV, a criatura fica **fora de combate** e não age. Seu turno é pulado.
No mapa, seu marcador fica escuro, com um pequeno **X** no canto e o número
preservado para identificação. Continua sujeito ao campo de visão.
Quando o ataque deixa todos os inimigos com 0 PV, o combate termina automaticamente.
A IA não declara morte: testes de morte, inconsciência e a opção de deixar uma
criatura inconsciente ainda não têm resolução completa. A ocupação das casas
continua conservadora mesmo a 0 PV. Ataques à distância, cobertura completa,
ações de combate adicionais e condições ficam para os próximos incrementos.

## Referências e limites

Foram consultados os PDFs locais em `books/rules/5.5e/`: **PHB 2024**, Vision and
Light, Human Traits, pp. 23–25 (turno, movimento, grade, interação com objetos),
e glossário Dash/Utilize; **DMG 2024**, p. 45, Diagonals e Line of Sight.
Os livros não são versionados. Fontes oficiais abertas equivalentes:
[Playing the Game](https://www.dndbeyond.com/sources/dnd/br-2024/playing-the-game),
[Rules Glossary](https://www.dndbeyond.com/sources/dnd/br-2024/rules-glossary) e
[Human](https://www.dndbeyond.com/sources/dnd/br-2024/character-origins#Human).

Para fichas e combate: **PHB 2024**, Core Fighter Traits e Fighter Features
(pp. 91–92), Champion (p. 96), Soldier (p. 185), Human (p. 194), talentos
Skilled/Savage Attacker/Defense e as propriedades de maestria do capítulo
Equipment. Consulte também as fontes oficiais abertas
[Character Classes](https://www.dndbeyond.com/sources/dnd/br-2024/character-classes),
[Character Origins](https://www.dndbeyond.com/sources/dnd/br-2024/character-origins),
[Feats](https://www.dndbeyond.com/sources/dnd/br-2024/feats) e
[Equipment](https://www.dndbeyond.com/sources/dnd/br-2024/equipment).

Usamos diagonais de 1,5 m do PHB, sem ativar a alternativa 1,5/3 m do DMG.
Saltos, escalada, voo, natação, rastejar, condições, montarias, outras habilidades
de classe, Desengajar e Preparar ainda não estão implementados. Cada operação
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
| `Caminhe até a porta e abra.` | No modo narrado sem resposta impeditiva, percorre 13,5 m até coluna 13, linha 6 e abre a porta |
| `Eu caminho até a direção da porta da sala dos guardas.` | Sem impedimento do Mundo, executa movimento até coluna 13, linha 6; posição e desenho mudam antes da narração |
| `Observo o corredor.` | Resposta a partir da posição atual; não registra deslocamento nem altera o personagem no mapa |
| `Corra até a porta, abra e entre na Sala dos Guardas.` | Coluna 15, linha 6; custo total 16,5 m; porta aberta e guardas visíveis, se o Mundo não interromper |
| `Corra para dentro da Sala dos Guardas.` com porta fechada | Para na coluna 13, linha 6, diante da porta; explica o bloqueio |
| `Abra a porta.` da posição inicial | Só off explicando alcance; posição e porta preservadas |
| `Ande dez casas para cima.` no tabuleiro original | Anda até o limite e explica onde parou, sem sair do mapa |
| Guia **Ficha** | Guerreiro Humano 3/Campeão/Defesa, 28 PV, CA 17, atributos e recursos; roda mostra o restante |
| Guia **Inimigos** antes/depois de abrir a porta | Nenhum antes; depois três Guerreiros Humanos 1, 12 PV e CA 17 |
| `Ataque o Guarda 1`, visível e adjacente | Iniciativa antes do golpe; turnos de NPCs resolvidos pela IA |
| `Use Retomar o Fôlego` duas vezes no turno | Primeiro cura até o máximo e gasta uso/ação bônus; segundo para por ação bônus usada |
| `Use Surto de Ação` | Concede outra ação; novo turno não recupera o uso |

Verifique a rolagem com uma conversa longa e o envio multilinha. Abrir a porta
revela os guardas; fechá-la pelo corredor os oculta. Simular
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
- `dice.py`: rolagens locais, com fonte de aleatoriedade injetável nos testes.
- `characters.py`: fichas, recursos, descansos e testes de atributo, sem mapa ou IA.
- `combat.py`: iniciativa, turnos e ataques, usando fichas e dados, sem geometria.
- `application/encounter.py`: coordena recursos, orçamento e efeitos do encontro.
- `application/sheets.py`: projeções das fichas para interface e contexto da IA.
- `application/sheet_options.py`: disponibilidade atual e detalhes de uso/recuperação para consulta, sem executar ações.
- `reactions.py` / `application/travel.py`: gatilho de oportunidade e coordenação de movimento/reações, sem UI ou SDK.
- `application/modes.py`: contrato fixo dos modos narrado e por turnos.
- `application/world.py` / `world_resolution.py`: contratos e efeitos das respostas do Mundo.
- `infrastructure/openai_world_director.py`: decisão do Mundo, separada da intenção do Jogador.
- `application/intents.py`: operações e planos estruturados.
- `application/routing.py` / `session.py`: planejamento e execução do estado.
- `application/dialogue.py`: canais on/off e contrato do narrador.
- `application/conversation.py`: sequência de ações, histórico e relatório para narração.
- `application/context.py`: geometria e percepção visível; a sessão acrescenta contexto completo do Mundo.
- `infrastructure/openai_intent_interpreter.py`: interpretação de ações.
- `infrastructure/openai_narrator.py`: descrição inicial, narração e respostas off.
- `infrastructure/openai_json.py`: transporte JSON compartilhado, sem regras de jogo.
- `ui/movement_window.py` / `character_panel.py`: conversa, entrada, mapa e guias das fichas, sem importar OpenAI.

Caminhos relativos a `src/trama/`. O `run.py` monta as dependências. A IA propõe
intenções e narra fatos; somente a engine determinística altera o mundo.

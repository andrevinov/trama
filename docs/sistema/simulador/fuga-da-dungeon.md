# Fuga da dungeon: cenário e adjudicação

Tier 3 · [Simulador](README.md) · [Visão geral](../../../README.md)

## Cenário e estado inicial

Os dados estão em [dungeon_escape.json](../../../src/trama/scenarios/dungeon_escape.json), com posições internas em base 0.
Na tela e nos contextos da IA, colunas/linhas começam em 1. Cada casa mede 1,5 m.

- Quatro celas ao longo de um corredor de duas casas (3 m), iluminado por tochas.
- Cela 1, a mais distante dos guardas: o jogador ouve sua grade abrir magicamente,
  sem ninguém próximo. A causa permanece desconhecida.
- Cela 2: prisioneiro adormecido, grade fechada e trancada.
- Cela 3: vazia, fechada e trancada.
- Cela 4, a mais próxima dos guardas: fechada, **destrancada**. Espada longa sob
  panos; uniforme da limpeza bem escondido sob a cama.
- Sala dos Guardas: um único Guerreiro Humano 1, uma mesa com a chave das celas,
  uma porta para o banheiro e uma porta de saída. Ambas fechadas e destrancadas.
- Jogador: Guerreiro Humano 3, Campeão, Defesa, 28 PV, **CA 11**, velocidade 9 m,
  somente trapos e **nenhum item**. Defesa não concede CA sem armadura. Mantém
  conhecimentos, perícias, recursos da classe e Inspiração Heroica.
- Prisioneiro: trapos de lã, sem inventário. A identidade de mago ilusionista só
  é revelada após a libertação. Não recebe uma ficha fictícia de Guerreiro.

A espada encontrada passa a ser uma arma real da ficha, com ataque, dano e
maestria Sap. É usada com uma mão, 1d8 + Força. Largá-la remove a arma da ficha.
Vestir o uniforme não cria armadura, armas, ferramentas ou poderes adicionais.
Movimento contextual também vale para investigar, pegar, atacar, destrancar,
escutar e acordar: a ação publica a posição necessária, e a aplicação calcula e
executa a caminhada antes dela. “Checo a cela” pode entrar pela grade aberta e
investigar; “pego a espada” aproxima do objeto já descoberto; “ataco o Guarda 1”
pode aproximar ao alcance, resolvendo iniciativa antes desse movimento tático.
A falta de movimento ou uma resposta impeditiva preserva o percurso sem realizar
a ação. Recursos/alvos/arma conhecidos são validados antes de começar.

Uma operação já satisfeita não exige caminhada, custo ou avanço da rotina.
“Sem sair do lugar” proíbe a aproximação contextual. Outras barreiras no caminho
não se abrem sozinhas, e a preparação não usa Dash/poderes ou destranca sem pedido.
A chave abre as celas 2 e 3; destrancar e abrir são operações distintas.

## Interações

Exemplos de mensagens, conforme a situação percebida:

```text
Caminho até a grade da Cela 4 e tento abri-la.
Entro na cela e investigo a cama e os panos.
Vou até a espada longa e a pego.
Pego o uniforme e o visto.
Largo a espada antes de falar com o guarda.
Oculto a espada sob o uniforme.
Escuto junto à porta da Sala dos Guardas.
Espero um pouco.
Vou furtivamente até a porta de saída.
Acordo o prisioneiro.
Uso a chave para destrancar e abrir a cela do prisioneiro.
Vou até o Guarda 1 e o ataco com a espada longa.
```

Encontrar um item não o coloca automaticamente no inventário. É preciso estar
a até uma casa, com caminho visual livre, para pegá-lo. Investigar exige entrar
no cômodo. Pedidos com várias etapas executam na ordem e param no impedimento;
portas não se abrem automaticamente. Para atravessar a saída, abra-a e caminhe
até a área Saída, ou peça para escapar. A chegada conclui o simulador.

Jogo/Ficha/Inimigos permanecem disponíveis. A ficha registra roupa e inventário
em **Dados → Equipamento e treinamento**. O mapa mostra tochas, itens conhecidos
e visíveis e o prisioneiro (`P`). O estado da fechadura não é revelado só por
olhar a grade. O guarda caído tem marcador diferente; pode ser atravessado como
terreno difícil, mas sua casa não é um destino para terminar o movimento.

## Testes e decisões de mestre

Referências da edição 2024: [testes e exploração](https://www.dndbeyond.com/sources/dnd/br-2024/playing-the-game),
[Study, Search, Influence, Unconscious e Utilize](https://www.dndbeyond.com/sources/dnd/br-2024/rules-glossary),
[Ilusão Menor](https://www.dndbeyond.com/spells/2619039-minor-illusion).
As CDs abaixo e as reações são **decisões deste cenário**, não regras gerais de
audição, disfarce ou rotina de NPCs impostas a todo o motor.

| Situação | Resolução implementada |
| --- | --- |
| Investigar a Cela 4 | A espada é encontrada sem teste. Inteligência (Investigação), CD 15, encontra o uniforme. |
| Passar perto do prisioneiro | Destreza (Furtividade), CD 10, representa o ruído produzido; falha acorda-o. Não se rola Percepção de uma criatura inconsciente. |
| Acordar/falar junto à cela | O prisioneiro acorda, pede ajuda e informa onde está a chave. |
| Vozes nas celas | Guarda testa Sabedoria (Percepção), CD 15. Sucesso faz com que abra a porta e investigue o corredor. |
| Escutar junto à porta dos guardas | Sabedoria (Percepção), CD 10, revela sinais do guarda e sua intenção de ir ao banheiro; não revela o futuro. |
| Passar-se por empregado | Carisma (Enganação), CD 15, conforme Influence. Falha inicia conflito; não há novas tentativas idênticas para apagar a falha. |
| Espada com o uniforme | Guarda testa Percepção, CD 10; CD 15 se a espada foi ocultada sob a roupa. Sucesso desfaz o disfarce e inicia iniciativa. |
| Pegar a chave à vista do guarda | Destreza (Prestidigitação), CD 13. Falha mantém a chave na mesa e inicia conflito. Não se exige esse teste sem observador. |
| Mover-se furtivamente | Furtividade CD 15, com resultado também usado para o ruído junto à cela. Não concede invisibilidade em plena luz diante do guarda. Aproveite ausência ou distração. |
| Ilusão Menor do prisioneiro | Som de fuga no corredor, a 7,5 m da cama, duração de 1 minuto. O guarda escolhe examinar o som (Study): Investigação contra CD de magia 13 (INT 16, proficiência +2). Falha leva-o a investigar o ruído; sucesso reconhece a ilusão. |

O NPC usa um fiapo dos próprios trapos de lã como componente material de Ilusão
Menor, além do componente somático. Não aparece um foco ou bolsa de componentes.
A ilusão não enfeitiça, controla a mente nem garante sucesso contra o guarda.

## Simplificações deliberadas

- As tochas são objetos fixados à parede e justificam iluminação normal; não há simulação de
  combustível, propagação dinâmica de luz ou coleta das tochas neste incremento.
- A rotina do banheiro é um pequeno roteiro determinístico: após **dois pedidos
  de espera** em exploração, o guarda vai ao banheiro e fecha a porta. Há uma
  janela de **quatro ações completas do jogador**, depois ele tenta voltar.
  São intervalos abstratos de tempo do cenário, sem orçamento de turnos ou
  relógio geral. Perguntas off e tentativas inválidas não avançam essa rotina.
- Ouvir o pedido de ajuda pode trazer o guarda às celas. O roteiro do banheiro
  fica suspenso quando ele está alertado ou em combate.
- No combate, a IA continua escolhendo deslocamento/ataque/espera do guarda,
  e as regras já existentes aplicam iniciativa, alcance, ações e oportunidades.
  A espada precisa ser obtida antes; o jogador começa com ataques desarmados.
- O mago é um acompanhante de cenário, sem ficha completa ou turno próprio.
  O auxílio por Ilusão Menor ocorre na libertação **fora de combate**. Ele
  acompanha por caminhos livres na exploração; não ganha ações gratuitas
  durante o combate. Este incremento não implementa um motor geral de magias.
- Após a libertação e a distração, há quatro ações de exploração para fugir; o guarda então
  retoma sua posição. Paredes, ocupantes e portas continuam validados.
- A origem da abertura mágica inicial é um fato da história; não implementamos
  uma magia do jogador que possa ser usada para destrancar outras celas.
- Chegar à área Saída encerra este encontro e registra se o acompanhante está
  próximo o bastante para fugir junto. Não cria regras gerais de perseguição.
- Não há arrombamento, ferramentas de ladrão, descanso, Esconder-se em combate, combate com o mago,
  diálogos sociais gerais ou sistema de equipamento completo. Há os três itens
  necessários ao cenário e as operações registradas no contexto.

## Separação e observabilidade

`DungeonSession`, em `src/trama/application/dungeon.py`, coordena somente este
cenário sobre a sessão existente. Movimento, fichas, dados, iniciativa, geometria
e visão reutilizam seus módulos. O Pygame recebe `map_view()` e as projeções da
ficha; não consulta o estado privado da dungeon. Os adaptadores recebem as
operações suportadas e contexto construído da mesma sessão que será executada.

A janela usa `GameFlow` para abertura, mensagens, turnos dos NPCs, oportunidades,
narração e reinício. Mantém somente entrada, desenho e a agenda de chamadas em
workers; os resultados são identificados e aplicados pelo fluxo na thread
principal. Não há mais uma coordenação de jogo paralela no código do Pygame.

No momento, a decisão em exploração desse roteiro é adjudicada pelo código.
O diretor de Mundo recebe a orientação de não duplicar testes, rotina ou
iniciativa; a IA narra os fatos produzidos e resolve o turno do guarda em combate.
Descobertas e respostas são fatos estruturados em `execution.reactions`.
O contexto `scenario` declara as operações adicionais ao interpretador;
`world.scenario` contém estado completo, segredos e decisões de mestre.
O interpretador recebe o conhecimento do jogador; o Mundo conhece os segredos.

Logs `dungeon.*` registram testes, descobertas, inventário, disfarce, ruídos,
rotina, magia, acompanhamento e conclusão, no mesmo envelope do restante do jogo.
DEBUG continua incluindo prompts, contextos, saída estruturada e rolagens.

## Critérios de sucesso e regressões

- Grade inicial abre sem NPC próximo; jogador e prisioneiro não possuem itens.
- Grade 4 pode abrir; objetos só aparecem após descoberta e só entram na ficha
  após coleta. Roupa não aumenta CA. A chave realmente altera a fechadura.
- Disfarce, espada, passos e vozes têm consequências calculadas e registradas.
- É possível fugir por disfarce, pela ausência do guarda, vencendo o combate ou
  libertando o prisioneiro e aproveitando sua distração, conforme os testes.
- Movimento e respostas do Mundo alteram posições/portas antes de serem narrados.
- Perguntas off não executam interações. Reiniciar restaura itens e personagens.

```bash
poetry run pytest tests/integration/test_dungeon_simulator.py tests/integration/test_interaction_preparation.py tests/integration/test_contextual_movement.py
poetry run pytest
poetry check
```

Os testes usam este JSON e a mesma sessão/contextos/adaptadores da aplicação,
com dados controlados e o transporte de rede substituído quando necessário.
Há regressões live opcionais da abertura/saída da cela e da investigação com
entrada contextual, descritas em
[tests/live/README.md](../../../tests/live/README.md); outros cenários live serão
derivados depois da validação do encontro. Nenhuma
chamada paga é necessária para executar as regressões locais.

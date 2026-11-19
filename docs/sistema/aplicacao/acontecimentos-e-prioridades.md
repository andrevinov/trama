# Acontecimentos percebidos e prioridade do NPC

Tier 3 · [Aplicação](README.md) · [Intenções dos NPCs](intencoes-dos-npcs.md)

O passo 7 permite reconsiderar uma conversa quando o NPC recebe informação
pertinente ou percebe um incidente, inclusive depois de já ter respondido ao
jogador. `AgencySystem` registra notificações individuais; o mesmo `GameFlow`
agenda a revisão, aplica os cálculos e pede a decisão. Não há polling,
temporizador, chamada por frame ou coordenador alternativo.

## Origem e pertinência das notificações

`KnowledgeSystem._learn` notifica somente aquisições novas. As âncoras de
`Persona.interests` identificam pertinência por tópico ou predicado, como
`supply_outlook` no conselho. `observed_injury` também é incidente pertinente.
Resumos derivados de episódio, compromisso ou pendência não provocam novas
revisões. Não há equivalência linguística automática entre predicados, assuntos
ou paráfrases: uma informação sem âncora pertinente não dispara esse caminho.

`PerceptionSystem.evaluate` notifica ruídos não verbais de volume `loud`
efetivamente ouvidos. Esse recorte de perturbação forte é política do Trama para
seleção de eventos, usando a audição existente; não acrescenta regra de D&D
para transformar todo ataque em ruído forte. Passos e observações passivas
comuns não viram chamadas por quadro. Um ruído precisa ter sido emitido por
operação existente ou preparação autoral explícita.

Falas, inclusive as respostas roteirizadas do prisioneiro na dungeon, conservam
o marcador de comunicação verbal. Não são duplicadas como incidentes não verbais;
seu conteúdo depende dos ouvintes e das memórias efetivamente transmitidas.

O NPC deve estar acompanhando uma intenção ou participando de conversa conhecida,
ativa ou suspensa. Ouvir de passagem não cria automaticamente agência para todos
os habitantes. NPC morto ou adormecido não ganha uma decisão consciente.

Cada notificação guarda `event_id`, tipo e, quando existe, `memory_id`, interesses
pertinentes e posição percebida. Relatos/inferências iguais do mesmo emissor não
reabrem a revisão só por recontagem ou novo id de memória. Observações distinguem
ocorrências reais pelo evento; a aquisição passiva já evita duplicações por frame.
Reiniciar limpa notificações e identidades processadas.

Uma avaliação social já calculada sobre a base atual consome as notificações de
conhecimento daquele dono. Não há revisão extra para refazer o cálculo que acabou
de considerar aquela informação. Ruídos ainda não considerados seguem pendentes.
Novas informações adquiridas depois desse cálculo podem disparar reconsideração.

## Revisão antes da decisão

O fluxo após uma operação executada é:

1. Percepção e conhecimento registram os acontecimentos que cada dono recebeu.
2. `npc_review` recebe a perspectiva privada de um NPC notificado.
3. O diretor propõe apenas opiniões afetadas e/ou episódios desse dono. Pode
   retornar plano vazio se nada merece alteração.
4. `Conversation.execute_review` valida referências e calcula com o estado real.
5. `npc_agency` recebe a base atual e escolhe a iniciativa. Só a execução
   posterior produz falas ou efeitos físicos para a narração.

`npc_review` reutiliza `WorldPlan`, com `intent=null`, `adjudications=[]`,
ações vazias e reações em `step_index=0`, `after_squares=null`, sem teste ou
interrupção de percurso. Não exige fala atual do jogador. Rejeita avaliação de
outro dono e qualquer ação antecipada. Episódios continuam sujeitos à
[política de evidência](evolucao-das-relacoes.md), antes das opiniões.
O contexto de revisão não prepara solicitações de dificuldade física: as
adjudicações ficam vazias até a etapa de agência que poderá executar uma operação.

O contexto contém somente persona, relações, memórias e conversas do NPC,
além das comunicações percebidas. `observations.events` inclui até quatro eventos
recentes da oportunidade; eventos de conhecimento trazem a memória original e
`current`, indicando se ela continua ativa. Isso permite interpretar a ocasião
sem tratar lembrança histórica como prova atual. Esses campos privados não
entram na interpretação do jogador nem na narração.

Cada interação admite no máximo uma reconsideração por NPC, além do acompanhamento
comum. Novos eventos podem recolocar na fila quem já agiu, mas não geram uma
cascata ilimitada de falas. Eventos posteriores ao orçamento daquele NPC ficam
pendentes para a próxima ação em jogo ou continuação explícita por evento. Cada
lote é consumido uma vez, com os quatro eventos mais recentes no contexto;
os ids recebidos permanecem nos logs. Essa seleção não garante que toda informação
recebida em uma sequência longa entre no mesmo prompt.

`GameFlow.receive` continua rejeitando resultados antigos/duplicados. Não há
retry automático após falha de revisão, agência ou narração. Efeitos anteriores
válidos permanecem registrados; repetir a narração não reexecuta acontecimentos.

## Incidente ouvido, condição vista e autoria

| Percepção efetiva | Informação disponível |
| --- | --- |
| Relato de outro personagem | Claim com `source.kind=report`, emissor e origem; não prova autenticidade ou execução. |
| Ruído forte sem fonte vista | Notificação genérica, sem identidade do causador nem coordenadas ocultas. |
| Fonte real vista no local do ruído | Pode conservar a posição percebida; isso não comprova agressão ou ferimento. |
| Ferido visto, autor fora da visão | `observed_injury` sem `source.actor_id` do agressor, sem atribuição de culpa. |
| Autor e resultado da ação vistos | Observação com autoria, sujeita aos demais critérios do episódio. |
| Acontecimento não percebido | Sem notificação ou revisão daquele NPC. |

Portas e ataques diretos com dano usam as operações reais existentes. Ver apenas
o ferido não permite `betrayal_discovered` com autor inventado. Um ruído não
produz soldado ferido, tiro, socorro ou identificação do agressor. Mostrar um
documento ainda não tem operação de autenticação; uma alegação sobre ele continua
relato. Não foram implementados ataques à distância gerais ou incidentes físicos
por texto narrativo.

## Suspensão, investigação e retomada

Em oportunidade por evento, `IntentDecision` também pode escolher:

- `suspend`: exige fala efetiva com `conversation.status=suspended` e motivo
  literal, conservando os assuntos e as propostas percebidos.
- `resume`: exige conversa suspensa e retomada efetivamente comunicada com
  `status=active`.
- `investigate` ou `protect`: pode perguntar, falar e executar no máximo uma
  operação física suportada: `move` ou `search`.

Deslocamento exige localização percebida do incidente e destino ali ou em casa
adjacente. Geometria, ocupação e execução continuam sendo as existentes; texto
não desloca ninguém. `search` mantém seu recorte atual de Percepção para localizar
o jogador, inclusive oculto; não é investigação genérica de qualquer objeto ou
autenticação de documentos. Um observador sem ficha não ganha movimento de
Guerreiro. Proteger pode significar aproximar-se ou advertir; não cria cura,
interceptação de golpe ou bônus defensivo sem regra implementada.

O passo 8 também permite a despedida com saída `leave` sem incidente, conforme
o [contrato de intenções](intencoes-dos-npcs.md). Durante combate
não há revisão ou movimento gratuito de agência. `start_conflict` rola iniciativa
nas posições atuais; ataques dependem de turno, alcance, ação e recursos. O
conflito atual organiza jogador contra NPCs hostis/instigador. Não sustenta um
combate arbitrário entre terceiros, nem transforma todo participante da audiência
em aliado ou inimigo.

A entrada efetiva em combate suspende as perspectivas de conversa dos
participantes da iniciativa. A interrupção tem evento próprio; não fabrica fala
ou novo locutor. Pontos, termos e último falante real permanecem. Quando houver
retomada, uma pendência só é resolvida ou abandonada por contribuição explícita;
a mudança de prioridade não apaga a pergunta anterior.

## Uso no fluxo e verificação

Eventos produzidos durante a interação são recolhidos nas transições reais do
`GameFlow`, inclusive após ação de NPC e ao sair do combate. Off só consulta o
estado, sem consumir notificações ou avançar prioridade.

Para um produtor de acontecimento já executado fora de uma interação pendente,
`game.runner.react_to_events()` conduz revisão, agência e narração sem criar
mensagem do jogador. A operação pertence ao mesmo `GameFlow` usado pela janela. Não é
comando de chat, gerador de incidentes ou método a chamar por frame. Sem evento
elegível, sem diretor ou durante combate, não despacha chamadas. A CLI continua
usando o mesmo simulador e a mesma composição.

Nas situações reproduzíveis, os estímulos da preparação integram a base inicial.
Ao concluir `Situation.initialize`, suas notificações são reconhecidas sem
reapresentação durante o jogo. Memórias, percepções e logs permanecem. Reiniciar
repete essa preparação e começa com a mesma base, sem ruídos antigos pendentes.

As regressões em `tests/integration/test_npc_agency.py` usam a composição/runner
para notícia de outro NPC, pertinência, fala inaudível, revisão depois de já agir,
duplicação, suspensão, retomada, off, reinício e investigação com deslocamento
real. Controles parciais executam ataque real e comparam percepções individuais,
além de interrupção por combate e rejeição de ação fora do turno. As amostras
de `tools/context_contracts.py --check` incluem relato, ruído e conversa
interrompida. São verificações offline; a adequação semântica dos motivos e da
prioridade de um modelo real continua exigindo avaliação no simulador.

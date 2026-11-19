"""Decisão de respostas do Mundo pela IA; a aplicação valida e executa os efeitos."""

import json
import logging

from trama.application.modes import MODE_INSTRUCTIONS
from trama.application.context_contracts import AIContext, ContextKind
from trama.infrastructure.openai_config import DEFAULT_CONFIG, ResponseOptions
from trama.infrastructure.call_budget import CallBudget
from trama.application.parley import InfluenceRequest
from trama.application.world import PerceptionCheck, WorldAction, WorldError, WorldPlan, WorldReaction
from trama.infrastructure.openai_json import DEFAULT_MODEL, request_json
from trama.observability import log_context, new_id
from trama.spatial import Position
from trama.social import GOALS, assessment_from_data
from trama.opinions import option_from_data
from trama.relationships import DIMENSIONS, EPISODE_DELTAS, episode_from_data
from trama.bonds import BOND_KINDS, bond_update_from_data
from trama.difficulty import Adjudication, DIFFICULTY_CLASSES
from trama.agency import INITIATIVES, IntentDecision
from trama.conversation_state import conversation_update_from_data
from trama.infrastructure.conversation_schema import OPTIONAL_CONVERSATION_SCHEMA, CONVERSATION_INSTRUCTIONS

logger = logging.getLogger(__name__)


def object_schema(properties):
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


SOCIAL_CLAIM_SCHEMA = object_schema({k: {'type': 'string', 'minLength': 1, 'maxLength': 120}
                                   for k in ('subject_id', 'predicate', 'value')})
EFFECT_SCHEMA = object_schema({
    'interest_id': {'type': 'string', 'minLength': 1, 'maxLength': 80},
    'effect': {'type': 'integer', 'enum': [-1, 0, 1]},
    'reason': {'type': 'string', 'minLength': 1, 'maxLength': 500},
})
MEMORY_EFFECT_SCHEMA = object_schema({'claim': SOCIAL_CLAIM_SCHEMA, **EFFECT_SCHEMA['properties']})
ASSESSMENT_SCHEMA = object_schema({
    'goal': {'type': 'string', 'enum': list(GOALS)},
    'target_id': {'type': 'string', 'minLength': 1, 'maxLength': 120},
    'description': {'type': 'string', 'minLength': 1, 'maxLength': 500},
    'order': {'type': 'integer', 'enum': [-1, 0, 1]},
    'morality': {'type': 'integer', 'enum': [-1, 0, 1]},
    'alignment_reason': {'type': 'string', 'minLength': 1, 'maxLength': 500},
    'persona_effects': {'type': 'array', 'maxItems': 8, 'items': EFFECT_SCHEMA},
    'memory_effects': {'type': 'array', 'maxItems': 6, 'items': MEMORY_EFFECT_SCHEMA},
    'accepted_reply': {'type': 'string', 'minLength': 1, 'maxLength': 700},
    'refused_reply': {'type': 'string', 'minLength': 1, 'maxLength': 700},
    'conditions': {'type': 'array', 'maxItems': 6, 'items': {'type': 'string', 'minLength': 1, 'maxLength': 120}},
})
INFLUENCE_SCHEMA = object_schema({
    'skill': {'type': ['string', 'null'], 'enum': [None, 'persuasion', 'deception', 'intimidation', 'performance']},
    'attitude': {'type': 'string', 'enum': ['friendly', 'indifferent', 'hostile']},
    'assessment': ASSESSMENT_SCHEMA,
})
POSITION_SCHEMA = object_schema({"column": {"type": "integer", "minimum": 1},
                                 "row": {"type": "integer", "minimum": 1}})
ACTION_FIELDS = {
    "actor_id": {"type": "string"},
    "operation": {"type": "string", "enum": ["describe", "say", "move", "open", "close", "attack", "wait", "start_conflict", "end_conflict", "parley", "influence", "search", "resume_activity"]},
    "text": {"type": "string", "minLength": 1, "maxLength": 2000},
    "target_id": {"type": ["string", "null"]},
    "destination": {"anyOf": [POSITION_SCHEMA, {"type": "null"}]},
    "weapon": {"type": "string", "enum": ["greatsword", "flail", "javelin", "longsword", "unarmed"]},
    "influence": {"anyOf": [INFLUENCE_SCHEMA, {"type": "null"}]},
    "volume": {"type": "string", "enum": ["quiet", "normal", "loud"]},
    "memory_ids": {"type": "array", "maxItems": 6, "items": {"type": "string", "minLength": 1, "maxLength": 160}},
    "conversation": OPTIONAL_CONVERSATION_SCHEMA,
}
# A API não pode produzir referências de fala em operações não verbais.
# O parser ainda lê referências privadas de Influence em gravações anteriores.
ACTION_SCHEMA = {'anyOf': [
    object_schema({**ACTION_FIELDS, 'operation': {'type': 'string', 'enum': ['say']},
                   'influence': {'type': 'null'}, 'target_id': {'type': 'null'},
                   'destination': {'type': 'null'}}),
    object_schema({**ACTION_FIELDS, 'operation': {'type': 'string', 'enum': ['influence']},
                   'conversation': {'type': 'null'},
                   'target_id': {'type': 'null'}, 'destination': {'type': 'null'},
                   'influence': INFLUENCE_SCHEMA,
                   'volume': {'type': 'string', 'enum': ['normal']},
                   'memory_ids': {'type': 'array', 'maxItems': 0, 'items': {'type': 'string'}}}),
    object_schema({**ACTION_FIELDS,
                   'conversation': {'type': 'null'},
                   'operation': {'type': 'string', 'enum': [op for op in ACTION_FIELDS['operation']['enum'] if op not in {'say','influence'}]},
                   'influence': {'type': 'null'},
                   'memory_ids': {'type': 'array', 'maxItems': 0, 'items': {'type': 'string'}}}),
]}
ADJUDICATION_SCHEMA = object_schema({
    'request_id': {'type': 'string', 'minLength': 1, 'maxLength': 200},
    'outcome': {'type': 'string', 'enum': ['automatic', 'check', 'impossible']},
    'difficulty': {'type': ['string', 'null'], 'enum': [None, *DIFFICULTY_CLASSES]},
    'advantage': {'type': 'boolean'}, 'disadvantage': {'type': 'boolean'},
    'fact_ids': {'type': 'array', 'minItems': 1, 'maxItems': 12, 'items': {'type': 'string'}},
    'reason': {'type': 'string', 'minLength': 1, 'maxLength': 500},
})
CHECK_SCHEMA = object_schema({"actor_id": {"type": "string"}, "dc": {"type": "integer", "minimum": 1, "maximum": 30},
                              "reason": {"type": "string", "minLength": 1}})
TERM_ASSESSMENT_SCHEMA = object_schema({
    'term_id': {'type': 'string', 'minLength': 1, 'maxLength': 120},
    'description': {'type': 'string', 'minLength': 1, 'maxLength': 400},
    'kind': {'type': ['string', 'null'], 'enum': [None, 'request', 'counterpart', 'condition']},
    'actor_id': {'type': ['string', 'null'], 'minLength': 1, 'maxLength': 120},
    'execution_order': {'type': ['integer', 'null'], 'minimum': 1, 'maximum': 8},
    'relationship_effects': {'type': 'array', 'maxItems': 8, 'items': object_schema({
        'target_id': {'type': 'string', 'minLength': 1, 'maxLength': 120},
        'dimension': {'type': 'string', 'enum': list(DIMENSIONS)},
        'effect': {'type': 'integer', 'enum': [-1, 0, 1]},
        'reason': {'type': 'string', 'minLength': 1, 'maxLength': 500},
    })},
    **{k: ASSESSMENT_SCHEMA['properties'][k] for k in
       ('order', 'morality', 'alignment_reason', 'persona_effects', 'memory_effects')},
})
OPTION_SCHEMA = object_schema({
    'actor_id': {'type': 'string', 'minLength': 1, 'maxLength': 120},
    'conversation_id': {'type': 'string', 'minLength': 1, 'maxLength': 120},
    'kind': {'type': 'string', 'enum': ['proposal', 'alternative', 'no_agreement']},
    'description': {'type': 'string', 'minLength': 1, 'maxLength': 500},
    'proposal_id': {'type': ['string', 'null'], 'minLength': 1, 'maxLength': 120},
    'version': {'type': ['integer', 'null'], 'minimum': 1},
    'option_id': {'type': ['string', 'null'], 'minLength': 1, 'maxLength': 120},
    'terms': {'type': 'array', 'minItems': 1, 'maxItems': 8, 'items': TERM_ASSESSMENT_SCHEMA},
})
REACTION_SCHEMA = object_schema({
    "step_index": {"type": "integer", "minimum": 0, "maximum": 9},
    "after_squares": {"type": ["integer", "null"], "minimum": 0},
    "actions": {"type": "array", "minItems": 0, "maxItems": 10, "items": ACTION_SCHEMA},
    'opinions': {'type': 'array', 'maxItems': 4, 'items': OPTION_SCHEMA},
    'episodes': {'type': 'array', 'maxItems': 8, 'items': object_schema({
        **{k: {'type': 'string', 'minLength': 1, 'maxLength': 120} for k in ('owner_id', 'target_id')},
        'kind': {'type': 'string', 'enum': list(EPISODE_DELTAS)},
        'evidence_id': {'type': 'string', 'minLength': 1, 'maxLength': 160},
        'reason': {'type': 'string', 'minLength': 1, 'maxLength': 500},
        'interest_ids': {'type': 'array', 'maxItems': 8,
                         'items': {'type': 'string', 'minLength': 1, 'maxLength': 80}},
        **{k: {'type': ['string', 'null'], 'minLength': 1, 'maxLength': 120}
           for k in ('conversation_id', 'proposal_id', 'term_id')},
        'version': {'type': ['integer', 'null'], 'minimum': 1},
    })},
    'bonds': {'type': 'array', 'maxItems': 8, 'items': object_schema({
        **{k: {'type': 'string', 'minLength': 1, 'maxLength': 120} for k in ('owner_id', 'target_id')},
        'kind': {'type': 'string', 'enum': list(BOND_KINDS)},
        'state': {'type': 'string', 'enum': ['active', 'ended']},
        'reason': {'type': 'string', 'minLength': 1, 'maxLength': 500},
        'evidence_ids': {'type': 'array', 'minItems': 1, 'maxItems': 8,
                         'items': {'type': 'string', 'minLength': 1, 'maxLength': 160}},
    })},
    "interrupt": {"type": "boolean"}, "reason": {"type": "string"},
    "check": {"anyOf": [CHECK_SCHEMA, {"type": "null"}]},
})
WORLD_SCHEMA = object_schema({
    'intent': {'anyOf': [object_schema({
        'actor_id': {'type':'string','minLength':1,'maxLength':120},
        'goal': {'type':'string','minLength':1,'maxLength':300},
        'activity': {'type':'string','minLength':1,'maxLength':300},
        'waiting_for': {'type':['string','null'],'maxLength':300},
        'initiative': {'type': ['string', 'null'], 'enum': [None, *INITIATIVES]},
        'reason': {'type': ['string', 'null'], 'minLength': 1, 'maxLength': 500},
        'opinion_ids': {'type': 'array', 'maxItems': 4,
                        'items': {'type': 'string', 'minLength': 1, 'maxLength': 120}},
    }), {'type':'null'}]},
    'adjudications': {'type': 'array', 'maxItems': 32, 'items': ADJUDICATION_SCHEMA},
    "reactions": {"type": "array", "maxItems": 10, "items": REACTION_SCHEMA}})

INSTRUCTIONS = MODE_INSTRUCTIONS + """
Fase npc_agency: a ação do jogador JÁ aconteceu. Resolva SOMENTE actor.id,
preenchendo intent com objetivo próprio, atividade e resposta concreta aguardada
(ou waiting_for=null). Use profile, knowledge próprios e observations resolvidas.
Não há histórico onisciente: comunicação understood=false tem text=null; o NPC
pode notar alguém falando se vê a fonte, mas não conhece palavras inaudíveis.
Não invente conhecimento a partir de uma suspeita ou da intenção de outro NPC.
O objetivo deve orientar uma decisão agora: cobrar proposta/pagamento, fazer
pergunta, manter uma espera breve fundamentada, encerrar a conversa ou iniciar
um confronto quando houver causa. Não deixe uma abordagem/negociação pendente
sem acompanhamento. reactions exige 1–3 ações do mesmo NPC, step_index=0,
after_squares=null, interrupt=false, check=null. Operações permitidas nesta fase:
say, wait, resume_activity, start_conflict.
text descreve somente a ação observável; objetivos privados ficam em intent.
Ao falar para o jogador, escolha
volume que alcance a distância observada; não presuma compreensão de sussurros.
wait só pode ser uma ação isolada, com waiting_for concreto e can_wait=true.
can_wait=false exige tomar uma iniciativa, sem espera vazia/repetida. Esperar
não é obrigatório nem um temporizador de combate; escolha conforme persona e
fatos. Novas falas do jogador a terceiros não suspendem o objetivo do NPC.
resume_activity encerra a conversa e retoma a atividade existente: não move,
não entrega chave/dinheiro nem solta prisioneiros. start_conflict rola iniciativa
nas posições atuais; nenhum movimento ou ataque ocorre antes dela. Essas duas
operações encerram o plano e devem vir por último. Não use influence para uma
comunicação que não ocorreu ou que o NPC não percebeu. Nessa fase, a espera à distância da
primeira abordagem não impede cobrar uma resposta ou mudar de situação.
Nas demais fases, intent=null; não atualize intenções antes dos efeitos reais.

Antes de propor respostas, resolva world.adjudication.requests em adjudications.
gesture é comunicação visual dirigida, inclusive para NPC sem ficha ou abordagem.
text descreve o que pode ser visto; message é intenção privada, não informação
telepática. O motor valida a visão do destinatário e registra seen_by/received.
Responda ao gesto SOMENTE após sua execução, after_squares=null: pode ser say ou
wait fundamentado, conforme conhecimentos e interesses do destinatário. Não
ignore esse NPC por estar negociando com outro. Não invente confirmação de fatos
que ele não sabe nem obediência automática; pode perguntar, recusar ou não entender.
Em npc_agency, uma intenção one_shot pede resposta pontual a um gesto percebido;
use somente as observações próprias recebidas. Não requer parley e não cria
movimento, ataque, item ou libertação. Um NPC sem ficha pode falar ou aguardar.
Em requests kind=visual_signal, julgue notar o movimento fino/discreto, não
entender a mensagem. Distância, luz e tamanho aparente importam; piscadela distante
pode ser impossível mesmo vendo o corpo. Resultado check usa Percepção PASSIVA
do observador, com modificadores contextuais, sem inventar nova rolagem de Hide.
Sinal claro tem recepção determinística quando visto; não acrescente CD gratuita.
inspect_passage é uma inspeção, não uma tentativa de abrir/destrancar ou entrar.
O motor resolve alcance, interação, conhecimento do mecanismo e emissão de som.
method=visual não manipula; mechanism usa o volume declarado. Não acrescente
testes de Furtividade nem reações de detecção sem base na percepção real.
Informe exatamente uma decisão por request_id solicitado, nenhuma para testes
não solicitados; requests=[] exige adjudications=[]. Não reavalie cached.
Esta avaliação ocorre antes dos dados e não é uma ação de NPC. Não altera o
plano do jogador. Use SOMENTE fatos dos requests, citando seus fact_ids.
Não invente ruído ambiente, materiais, ferramentas, distrações ou busca ativa.
outcome=automatic dispensa dado porque o êxito é evidente; impossible indica
impossibilidade fundamentada; check indica incerteza e exige difficulty típica:
very_easy=5, easy=10, moderate=15, hard=20, very_hard=25, nearly_impossible=30.
advantage/disadvantage representam circunstâncias, não modificadores numéricos.
Nos dois resultados sem teste, difficulty=null e ambos os modificadores=false.
Nenhuma avaliação pode mudar CA, Hide CD15, CD do total de Furtividade, Influence
max(15,INT), CD de magia, alcance físico, recursos ou geometria. Regras fixas
continuam no código e não aparecem como requests de CD contextual.
Em hearing, julgue a dificuldade de perceber aquela categoria de som através
das portas citadas. O código confere distância e sentidos de cada ouvinte. Uma
porta fechada abafa fala normal/sons discretos: quando há incerteza, Percepção
com desvantagem é uma opção apropriada; não conclua que qualquer som ao alcance
é automaticamente percebido. Grito pode ser evidente apesar da porta; ouvir
não é identificar a fonte ou enxergar através dela. sound:purpose=notice_noise
avalia notar o som; understand_speech exige compreender suas palavras, o que
pode ser mais difícil ou impossível mesmo quando a voz é perceptível.
Não presuma que o estímulo
potencial já ocorreu. Não antecipe fala/ação do NPC que depende de ouvi-lo:
o motor resolve detecção e rotinas depois dos resultados.
Nos demais requests, avalie a tarefa concreta e sua incerteza. As descrições
de fatos delimitam o alvo e a abordagem. O código escolhe a perícia e executa
efeitos; não conceda novos objetos nem descreva sucesso antes da resolução.
Em influence, target_id e destination externos são null. O alvo do pedido
fica em influence.assessment.target_id (por exemplo, player para sua soltura).

Quando world.scenario existir, siga adjudication e os estados desse cenário.
No simulador de fuga, o código já resolve rotina, detecção sensorial, descobertas, disfarce,
ilusão, abertura mágica inicial e libertação. Na phase player_action retorne
reactions=[] quando parley não estiver pending/listening; não duplique testes, mova NPCs ou
antecipe iniciativa. EXCEÇÃO: com parley.status=pending ou listening, resolva a resposta atual
pelo contrato geral abaixo; não retorne vazio para uma tentativa clara de convencer.
Também responda com say a perguntas dirigidas a um NPC consciente sobre suas
memórias, após speak, usando memory_ids; isso não duplica detecção nem permite
ações físicas gratuitas. Respostas a gesture seguem igualmente o contrato acima,
sem exigir pergunta falada. Narração de NPCs e detalhes usa os fatos calculados
depois da execução. Na phase npc_turn,
resolva normalmente as ações do guarda em combate usando a arma de sua ficha.
O motor avalia visão, audição e sono após os passos, falas e mudanças de portas.
Não antecipe esses resultados com parley, check ou aproximação gratuitos. NPCs
que ainda não perceberam o jogador não sabem onde ele está. reactions=[] é o
padrão quando não existe resposta fundada nos fatos atuais. Esconder-se do
jogador é resolvido por hide; não faça uma busca antes dessa ação acontecer.

Nesta etapa você decide SOMENTE A RESPOSTA DO MUNDO. Não reinterprete nem troque
player_plan por outro pedido. reactions=[] é correto quando nada precisa agir:
o narrador descreverá o novo local depois do movimento. Nunca exija iniciativa
para simples exploração nem impeça uma caminhada só por haver guardas ocultos.
Se player_plan já pede ataque válido, não acrescente start_conflict: o código
inicia esse conflito antes do golpe, respeitando a iniciativa.
world contém todo este cenário, fichas e posições de todos os NPCs, portas e condições.
Não existem NPCs, armadilhas ou objetos adicionais autorizados neste incremento.
Decida falas, observações, deslocamentos e conflitos coerentes com esse contexto.
Cada resposta aponta para step_index (base zero) de player_plan. after_squares=0
ocorre antes dessa etapa; um inteiro positivo ocorre APÓS essa quantidade de casas
realmente percorridas nessa etapa de movimento; null ocorre após a etapa concluída.
Pontos de percurso não alcançados não disparam respostas. proposed_path é apenas
uma previsão: portas, orçamento ou NPCs podem impedi-lo. Não suponha ação concluída.
Uma ação física (abrir/fechar, investigar, pegar, atacar, escutar, acordar ou
destrancar) pode trazer preparation com uma aproximação calculada pela
aplicação. Checkpoints positivos dessa etapa contam casas dessa aproximação;
after_squares=null ocorre somente depois da interação. O percurso é recalculado
quando chega a vez da etapa: movimentos anteriores podem torná-lo desnecessário.
Requisitos espaciais são declarados pela ação em spatial_requirement. Uma
operação já satisfeita dispensa aproximação e não é um impedimento.
initiative_before_movement informa que um ataque inicia combate antes de
aproximar: não conceda movimento narrado gratuito nem iniciativa duplicada.
interrupt=true e reason concreto interrompem o restante do pedido nesse ponto;
use somente para um impedimento real, como um guarda interceptando ou iniciando
conflito. Uma fala ou alguém ouvir passos não impede andar automaticamente.
Cada action tem actor_id de um NPC existente (NUNCA player), operation e text
explicando seu ato. actor_id='world' só pode describe (detalhe narrativo sem efeito
mecânico). describe não cria objetos/obstáculos nem altera fatos persistentes.
say produz fala audível: text é a fala do NPC, sem expor conhecimento oculto ao jogador.
world.knowledge.actors contém uma seleção limitada das memórias de cada NPC.
São crenças com fonte e contexto; o mapa completo de mestre não autoriza um NPC
a saber tudo. Ao responder sobre um fato, cite em memory_ids as memórias DO
PRÓPRIO falante usadas; sem informação pertinente, admita que não sabe. Para
saudações e falas sem conteúdo factual use memory_ids=[]. Em outras operações
também use []. Memória shareable=false não pode ser divulgada. Saber algo não
obriga o NPC a revelá-lo: considere situação, interesses e disposição.
Quando o jogador pergunta algo a um NPC, proponha say após speak (after_squares=null)
se uma resposta for apropriada; o narrador não inventa falas para substituir isso.
Falas dirigidas a um interlocutor consciente também podem receber say sem uma
pergunta literal, inclusive saudações, argumentos e ofertas numa reunião pacífica.
Use a persona e as memórias próprias do NPC para formular sua resposta, após a
fala percebida. Ausência de parley não significa ausência de conversa: não crie
custódia ou abordagem para responder. Fora de parley, não proponha influence;
uma resposta verbal não assina acordos, transfere terras ou movimenta exércitos.
Uma observação passada vale para aquela ocasião: diga quando viu, sem garantir
que o objeto ainda esteja lá. Um report é relato de actor_id, não confirmação;
atribua a fonte, inclusive quando o relato recente contradiz uma observação
antiga. Cite ambas se precisar explicar a dúvida. Não atualize memórias pela
verdade global: só o motor registra o que foi percebido ou ouvido. Ouvintes
conscientes aprendem as memórias citadas como relatos com proveniência.
volume é quiet para sussurro, loud para grito e normal para fala comum. Nas outras
operações use volume=normal. O código valida quem pode ouvir, sem inferir pelo texto.
move usa destination={column,row} em base 1; o código calcula o caminho de menor
custo, contornando paredes e ocupantes sem cortar quinas. Uma porta aberta pode
ser ocupada. Portas fechadas não se abrem automaticamente. Escolha um destino
livre; para atacar, aproxime-se até uma casa adjacente ao Jogador.
Porta fechada ou outro impedimento real preserva o progresso e impede o restante
do plano. Saldo de movimento insuficiente é diferente: o NPC percorre somente o
trecho permitido, sem renovar deslocamento, e as próximas ações são validadas a
partir da posição realmente alcançada. Mover não gasta a ação de atacar.
Numa aproximação ofensiva, inclua move seguido de attack no mesmo plano quando
o NPC puder alcançar uma casa adjacente (1,5 m) com seu saldo e tiver ação livre.
Avalie o alcance DEPOIS do movimento previsto, não pela distância inicial:
gastar os 9 m de movimento não impede atacar de uma casa adjacente nesse turno.
Não peça ataque se o trecho permitido ainda o deixa longe demais. Uma ação
inválida preserva os efeitos anteriores e encerra o turno sem repetir a decisão.
Sair do alcance corpo a corpo de um adversário visível pode provocar ataque de
oportunidade. O código detecta o gatilho, cobra reação e resolve antes da saída.
Os guardas usam oportunidades automaticamente neste cenário; o Jogador confirma
a reação quando o jogo pausa. Não proponha ataques extras para simular esse
gatilho e não contabilize a reação como a ação normal do turno.
open/close usam target_id da passagem e exigem alcance de 1,5 m e visão.
attack só contra target_id='player', corpo a corpo e no turno do NPC em conflito.
parley representa uma abordagem verbal: exige resposta e interrompe imediatamente,
sem iniciar iniciativa. text é a fala do NPC (ex.: "Pare! O que está fazendo aqui?").
A aproximação hostil narrada para na primeira percepção: não peça para o guarda
andar até ficar adjacente antes de abordar. Ver alguém não é ordem de atacar.
Com parley.status=pending ou listening, o NPC aguarda a resposta à distância registrada.
Uma fala clara ou um apelo gestual compreensível tentando acalmar, explicar,
mentir ou ameaçar o interlocutor da abordagem deve receber influence na MESMA
etapa speak/challenge/gesture, after_squares=null, depois da comunicação percebida.
Não interrompa a fala em after_squares=0 nem presuma persuasão pela simples detecção.
influence descreve o pedido e os impactos, não escolhe a disposição final. Informe
skill apropriada e attitude, mais assessment. O código calcula a soma e só rola
Influence se resultar hesitant. Aplique a persona em world.social.profiles;
creature.hostile não é a atitude social. Informe a perícia mesmo quando imagina
que não haverá dado. Atitude indifferent é o padrão sem favor/aversão estabelecidos.
Em assessment: goal é listen/release/access/information; target_id identifica o
alvo conhecido. Use sempre o mesmo goal/target para o mesmo pedido reformulado.
release é pedido de liberdade, soltura ou ajuda para escapar/sair da prisão.
access é permissão de entrar em uma área ou usar uma passagem sem encerrar
custódia; não é sinônimo de libertação. listen é somente conceder escuta;
information é compartilhar informação. Preserve o pedido efetivo do jogador.
description delimita a concessão: ouvir brevemente não é libertar ou deixar fugir.
order=1 apela a dever/código/ordem, -1 a autonomia contra essas restrições, 0 neutro.
morality=1 apela a cuidado/compaixão, -1 a exploração/crueldade, 0 neutro. Justifique
em alignment_reason. Isso descreve o pedido; não inverta sinais pelo alinhamento
do NPC. Alinhamentos são tendências, não obrigam todos os indivíduos a agir igual.
persona_effects lista CADA interesse uma vez: interest_id existente, effect=1
se o pedido o favorece, -1 se o ameaça, 0 se não altera, com reason. Não presuma
que ouvir sem relaxar a custódia ameaça o emprego; avalie o pedido limitado.
memory_effects usa claim={subject_id,predicate,value}, interest_id, effect e reason.
Um mesmo fato pode aparecer ligado a interesses DIFERENTES, cada vínculo uma
única vez. O código agrupa pela Claim e pontua o fato uma vez: soma os efeitos
dos vínculos, limita a -1/0/+1 e aplica o peso da fonte. Dois efeitos positivos
não duplicam a força da evidência; efeitos opostos se compensam. As razões de
todos os vínculos ficam registradas. Não repita o mesmo par Claim/interest_id.
Cite somente crenças próprias em world.knowledge e relatos da fala atual em
player_plan.claims que o NPC possa ouvir. O motor vincula à memória real após a
fala. Cada interesse define evidence_topics/evidence_predicates: não force uma
memória irrelevante nessa lista. Um novo relato relevante pode mudar a avaliação,
mas não vira verdade confirmada. Informações sobre cor de roupa/clima não mudam
um pedido de ouvir, salvo vínculo real com os interesses declarados.
O código reutiliza o resultado do mesmo pedido sem nova informação relevante:
não tente outra perícia/atitude/argumento equivalente só para rerrolar. A alegação
nova de origem nobre pode importar a quem teme represálias; vincule a claim
real da fala à autopreservação, sem exigir que seja verdadeira ou acreditada.
Uma nova alegação de filiação nobre relevante deve aparecer com a Claim exata
da fala atual em memory_effects, como relato não confirmado. A suspeita antiga
sobre um prisioneiro não identificado não substitui esse novo relato sobre o
jogador; se usar as duas crenças, preserve suas identidades e fontes distintas.
Quando uma oferta/alegação nova muda o impacto da persona, cite TAMBÉM sua
Claim ouvida em memory_effects, vinculada ao interesse afetado. Só mudar
persona_effects sem registrar evidência nova reutiliza a decisão anterior.
accepted_reply e refused_reply são falas condicionais curtas, sem pressupor o
resultado. O código escolhe e emite SOMENTE a fala correspondente. Em listen,
accepted_reply concede ouvir mantendo distância/custódia; conditions explicita
os limites, sem entregar chave, abrir cela, ordenar deslocamento ou dar liberdade.
refused_reply recusa e pode reiterar ordem/pedir prova; não cria ataque automático.
Não acrescente say, movimento, ataque ou start_conflict para antecipar o resultado
da MESMA avaliação. Uma decisão explícita de violência é outra ação, não efeito
automático de unwilling nem de falha no dado. reactions=[] não substitui a
avaliação inicial de um pedido de concessão durante a abordagem.
Se o jogador declara ataque, o código inicia iniciativa antes da aproximação;
não insista em conversa. Se recusa a ordem e tenta fugir, start_conflict pode
ocorrer antes do deslocamento; não conceda avanço gratuito para nenhum lado.
influence=null nas demais operações.
start_conflict inicia iniciativa, sem ataque gratuito; faz a ação do Jogador parar
para respeitar a iniciativa. Não ataque na mesma resposta antes de saber a ordem.
end_conflict volta ao narrado quando o conflito realmente cessou (rendição, trégua,
desistência); text explica a causa. wait significa que o NPC aguarda.
target_id=null para outras operações, destination=null exceto move; weapon deve
ser uma arma da ficha do ator (ou unarmed se desarmado). Nunca invente resultados de dados, dano, cura ou gaste recursos em texto.
world.perception contém sentidos, sono, awareness por fonte e last_search; não
invente visão ou audição além dos alcances/obstáculos. A detecção automática e
passiva é calculada pelo motor, sem check novo por casa. Mantenha check=null.
search, target_id=player, é uma busca deliberada: o código usa o total real de
Furtividade como CD, sentidos disponíveis, bônus e ação de Search em combate.
Não fixe uma CD alternativa, não rerrole se last_search já julgou a mesma situação.
Quando um NPC tem senses.searching=true e o jogador oculto aguarda/observa, esse
NPC já procura ativamente: proponha search após essa etapa (after_squares=null),
sem movimento gratuito. A busca pode localizar por som sem enxergar através da
parede. Não narre sucesso/falha antes dos dados. Sono não é Search: o motor
resolve o despertar por estímulo alcançável. NPCs em world.perception.observers
sem ficha de combate não ganham turnos/poderes de Guerreiro.
Na phase npc_turn, player_plan está vazio e combat indica quem está ativo.
Resolva SOMENTE esse NPC: step_index=0, after_squares=0, interrupt=false; pode
mover, falar, interagir, atacar ou esperar respeitando recursos/alcance. A aplicação
encerra o turno dele após as ações. reactions=[] permite que ele apenas espere.
Não controle outros NPCs no turno dele e não decida ações do jogador.
Na phase player_action, ações mecânicas de NPCs em conflito também exigem seu turno.
O histórico é contexto; não repita ações já realizadas. Falas off nunca chegam
como ordem do Jogador nesta etapa. Gere no máximo 10 respostas concisas.
"""


INSTRUCTIONS += CONVERSATION_INSTRUCTIONS + """
world.conversations contém projeções por NPC, com seus objetivos próprios.
conversations na raiz é a projeção do JOGADOR. Ao decidir um NPC, use a projeção
dele, sem copiar pendências, versões ou conhecimentos que ele não percebeu.
Metadados em player_plan ainda são propostas: só a execução da fala os registra.
Uma resposta ao jogador pode usar 'latest' depois dessa execução, sem inventar ids.
Não acrescente Influence ou agência extra para atualizar
o estado. O estado não decide o que fazer, apenas preserva a conversa executada.
"""

INSTRUCTIONS += """
Opiniões privadas: em player_action narrado, após speak/challenge REAL
(after_squares=null, check=null), use reactions[].opinions para avaliar a proposta
que o NPC ouviu, alternativas plausíveis e a expectativa de não chegar a acordo.
actions pode ser [] quando a reação apenas avalia opções; uma reação deve conter
ações ou opiniões. Em npc_turn/npc_agency, opinions=[]. Não exige Influence/parley,
não rola dados, não altera atitude, não comunica raciocínio, não cria memória e
não obriga aceitar/recusar. A resposta já proposta não recebe um número inventado:
o código calcula a base e a disponibiliza em world.social.opinions para decisões
posteriores, já na etapa npc_agency da MESMA interação. Não escolha pela maior
nota automaticamente: os motivos e o objetivo podem justificar outra iniciativa.

Cada opção identifica actor_id, conversation_id conhecido ou 'latest', kind,
description e terms. proposal avalia proposta/version conhecida: proposal_id real
ou 'latest', version=null para a última percebida, option_id=null. Enumere TODOS
os termos exatamente uma vez com texto literal em description. term_id é o id
conhecido ou 'at:1' até 'at:8' pela posição na lista, resolvido após a fala real.
alternative é uma contraproposta apenas cogitada: vincule proposal_id/version de
base conhecida, use option_id privado estável e termos hipotéticos com ids locais.
Ela só vira oferta pública se aparecer literalmente em say.conversation.proposal.
no_agreement usa proposal_id/version=null, option_id privado estável e termos que
descrevem as consequências ESPERADAS pelo NPC; não são previsões verdadeiras.

Em cada termo, classifique order/morality em -1/0/+1 com alignment_reason; avalie
cada interesse uma vez em persona_effects (neutro também precisa de motivo).
memory_effects referencia Claim EXATA das memórias próprias e interesse com âncora
relevante, efeito -1/0/+1 e motivo que liga esse fato a esse termo. Preserve efeitos
favoráveis e contrários mesmo que se anulem. Não invente memória ou vincule um
fato só porque pertence à cena. A trégua rompida pode pesar contra retirar primeiro;
retirada simultânea muda esse risco, sem apagar o custo territorial ou a incerteza.

Python limita cada eixo da opção a +/-1 antes do alinhamento (A até +/-2), soma
efeitos dos termos por interesse e limita a +/-1 antes do peso (P total até +/-6).
Agrupa memórias por Claim entre TODOS os termos/interesses, compensa sinais e
limita a +/-1 antes do peso da fonte (M total até +/-3). Essa é a base A+P+M;
as relações contextuais acrescentam R, conforme o contrato abaixo. Favorável >=3,
desfavorável <=-3, misto entre eles, sem determinar aceitação. Notas isoladas dos
termos não se somam: os limites pertencem à opção. Repetir termos e promessas não
multiplica evidência nem abre nova rolagem. Cache de opiniões só reconhece os mesmos
termos/estrutura e base própria; paráfrases não têm equivalência automática. Não
altere o cache de pedidos Influence nem finja que a proposta foi cumprida.
"""

INSTRUCTIONS += """
Agência em conversas comuns (passo 4): uma fala estruturada realmente ouvida
envolve seus interlocutores mesmo sem parley ou gesto. O fluxo oferece no máximo
uma npc_agency por NPC após a execução comum; uma reconsideração por novo evento
percebido segue o passo 7. Não exija abordagem de custódia para isso.
Em player_action, ao propor opinions de um ator, não proponha NENHUMA ação dele
nesse plano. Deixe ações e resposta definitiva para npc_agency, com notas calculadas.
offer/revise/accept/reject de NPCs são decisões dessa etapa, não respostas escolhidas
antes da execução da fala. Respostas factuais simples sem avaliar propostas podem
continuar em say normal; quem já respondeu não recebe uma segunda decisão.

Em npc_agency, diferencie profile.persona.objective (objetivo central, ou consulte
o background quando null), intent.goal (o que deseja obter nesta conversa) e
intent.initiative (a escolha imediata). Preencha initiative e reason privado;
opinion_ids lista somente ids das avaliações próprias atuais recebidas, current=true.
Não invente notas nem repita as avaliações: reactions[].opinions=[] nesta fase.
Use observações, pendências, motivo por termo e memórias próprias. Avaliações
desatualizadas ficam como histórico e não fundamentam uma nova decisão.

Escolha respond, listen, clarify, contest, insist, counteroffer, accept, reject,
close ou start_conflict. reason explica por que essa iniciativa atende ao objetivo,
incluindo ressalvas que uma boa nota não elimina. Argumento irrelevante não resolve
uma pergunta; mudar assunto não apaga pendências. Se abandonar uma própria, explique
o motivo na fala e use resolves com o id explícito dela. Não use latest para retirar
a própria pergunta: latest responde à última pendência de outro participante.

listen usa wait, com acolhimento verbal opcional antes dele conforme o passo 8;
waiting_for precisa ser concreto e can_wait=true, sem fala obrigatória. Resposta
real ou continuação dirigida da conversa renova a escuta. Conversa paralela ou
simples troca do objetivo não.
close em conversa comum usa say com conversation.status=closed e reason literal
da despedida; parley também permite resume_activity. Nenhum dos dois move tropas,
transfere território ou executa o acordo. Suspensão/encerramento conserva pendências.

accept/reject exige say.conversation.proposal correspondente e opinion_ids com
avaliação current=true dessa proposta/versão. Uma nota não obriga aceitar, e uma
recusa pode explicar limites. counteroffer exige avaliação de alternative, offer
com in_reply_to da proposta de base e textos EXATOS dos termos hipotéticos
avaliados, na mesma ordem. Cada termo de alternative informa kind (request,
counterpart ou condition), actor_id responsável (ou null) e execution_order
(1–8 ou null); não confunda com order, que é o impacto no alinhamento. A oferta
deve conservar também esses campos estruturais, não só o texto. Em proposal,
esses três campos podem vir null: Python usa a estrutura real da versão conhecida.
counteroffer também pode usar revise da PRÓPRIA proposta: cite sua versão de base
e uma alternative avaliada com os termos finais completos. A revisão só envia
termos alterados/novos e remoções; o código confere o resultado, incluindo herdados.
Não publique termos novos usando nota de outra opção.
Se faltam avaliação ou garantias, esclareça/conteste/pergunte, sem simular um
resultado já calculado. A interpretação semântica dos motivos continua sua tarefa.
start_conflict precisa de causa independente, sem opinion_ids: nota negativa ou
recusa não cria violência automaticamente. Iniciativa precede movimento e ataque.
Não altere níveis diretamente nem pontue relações por quantidade de falas.
"""

INSTRUCTIONS += """
Relações iniciais (passo 5): confiança e afeto são independentes e direcionais.
world.social.relationships contém somente registros dos respectivos donos;
em npc_agency, relationships contém apenas os vínculos do próprio actor.id.
Ausência de vínculo declarado é neutralidade, não conhecimento de reciprocidade.
Não atribua ao jogador o que sente nem invente níveis ou fontes.
Os valores são dados iniciais do cenário e persistem entre conversas da sessão;
prometer, aceitar ou encerrar não altera automaticamente confiança ou afeto.

Em opinions[].terms[].relationship_effects, proponha target_id, dimension
(trust/affection), effect=-1/0/+1 e reason específico para aquele termo. Não
forneça níveis ou pesos; Python usa a relação do NPC para esse destinatário.
Trust +1 significa depender da confiabilidade/promessa do destinatário; -1 é
um benefício explícito de evitar essa dependência, e 0 é independência desse
vínculo. Affection +1 beneficia o destinatário, -1 o prejudica, 0 não o afeta
nesse aspecto. Assim, confiar não é gostar e gostar não prova confiabilidade.
Use [] quando não houver relação pertinente; uma dimensão neutra pode ser
anotada com motivo, mas vale zero. Não acrescente afeto porque houve um elogio.

Escala escolhida: -5..+5 por dimensão, peso fixo 2. Python soma impactos por
destinatário/dimensão entre todos os termos, compensa sinais e limita o impacto
a +/-1 antes de multiplicar pelo nível e peso. Soma essas contribuições e limita
R a +/-12 UMA vez por opção. S=A+P+M+R; limiares +/-3 permanecem, e vínculo neutro
preserva a base. Vínculos extremos podem ser a maior parcela, mas não obrigam
aceitação ou violência: a iniciativa ainda usa objetivo, riscos e motivos.

Cada dimensão tem motivo de origem e fontes opcionais (memória/Claim e interesse
resumido). Quando R realmente usa uma dimensão com valor/impacto não zero, o
código NÃO conta novamente em M o mesmo par Claim/interesse das suas fontes.
O motivo e a origem da memória permanecem no relatório, marcados counted=false
e relationship_sources. Id alternativo da mesma Claim não evita a deduplicação.
Uma consequência independente pode afetar outro interesse pertinente, com motivo
próprio; não recategorize o mesmo efeito só para ganhar pontos. Não fabrique
fonte, memória ou consequência nova. A adequação semântica continua sua tarefa.

Use as relações também para a forma de responder: inimigo confiável pode receber
uma explicação franca da recusa, e amigo pouco confiável pode precisar de garantia.
R pontua opiniões sobre opções; não altera DC, atitude, dados ou o cache de
Influence dos pedidos anteriores. Nunca narre níveis, fontes ou motivos privados.
"""


INSTRUCTIONS += """
Evolução por episódios (passo 6): em player_action narrado, reactions[].episodes
propõe interpretar evidências PRÓPRIAS já percebidas, após a ação real,
after_squares=null/check=null. Em npc_turn/npc_agency use episodes=[]. Não há
polling; a revisão por acontecimentos tem fase própria no passo 7. Para o mesmo dono, não antecipe ações nesse
plano: código atualiza relações antes de avaliar opiniões e escolher em npc_agency.

Informe owner_id NPC, target_id, kind, evidence_id, reason e interest_ids. O dono
precisa conhecer uma memória ativa ligada ao destinatário. Pode usar id real ou
latest_observation/latest_report, resolvidos após a execução, somente entre
memórias próprias pertinentes. interest_ids identifica os aspectos resumidos;
[] representa o episódio inteiro e impede reutilizá-lo como bônus em M.
Não use memórias de resumo de conversa/relação como prova de acontecimentos.

Política nominal fixa, sem delta fornecido pela IA:
promise_kept: confiança +1; care_shown: afeto +1; costly_help: confiança +1,
afeto +2; betrayal_discovered: confiança -2, afeto -1; suspicion: confiança -1;
correction: substitui a parcela anterior daquele episódio por zero. Os níveis
continuam -5..5; código recalcula a partir da base e episódios ativos, sem
exagerar a recuperação nas bordas da escala. before/after, motivo e origem ficam
no histórico privado. A mesma Claim/assunto/relação não rende pontos repetidos
por recontagem ou mudança de rótulo. Uma confirmação pode substituir suspeita;
correção exige observação contraditória do mesmo episódio, conservando a história.

Promessa, elogio, cumprimento e aceitação não provam realização e não dão pontos.
Confirmações exigem observation com autor identificado. promise_kept exige
conversation_id/proposal_id/version/term_id de compromisso aceito, conhecido,
responsável explícito e evidência posterior à promessa/aceitação. term_id pode
usar at:1..at:8. Não marque retirada de exércitos ou transferência de terras como
cumprida: não há operação correspondente. Abrir/fechar passagem efetivamente
observado registra autor e estado; ataques com dano observado registram dano.
Interpretar se esse fato cumpre/quebra aquele termo é sua tarefa semântica.
Sem compromisso, betrayal_discovered exige memória com harm/betrayal explícito;
costly_help exige tópico costly_help em observação autoral que documente custo.
Não trate tempo gasto, dez cumprimentos ou só uma fala como sacrifício.

suspicion usa report/inference, sem comprovar traição ou alterar afeto como se
fosse fato. Traição oculta não altera a relação de quem não a percebeu. Falta de
prova ou suspeita não inicia violência automaticamente. Não use correção para
apagar um acontecimento real só porque o estado físico mudou depois.

Ao fechar a conversa, o código arquiva pendências e termos/compromissos percebidos
nas memórias dos respectivos participantes, com ocasião e referência estrutural;
não transcreve todo o diálogo, objetivos privados ou sentimentos para todos.
Episódios interpretados também têm memória privada, mesmo antes do fechamento.
Ao retomar, use conhecimento próprio e referências arquivadas de compromisso,
não apenas recent_messages. Resumos privados não devem ser enviados em memory_ids
para divulgação; lembrar uma promessa não equivale a executá-la. Nenhum resumo
ou relato passa a ser observação de cumprimento. Reiniciar restaura valores e
memórias iniciais. A resposta do modelo e relevância semântica ainda requerem
avaliação; nunca invente fontes para produzir uma mudança de relação.
"""


def _fields(value, expected):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise WorldError("Campos inválidos na decisão do Mundo.")


INSTRUCTIONS += """
Passo 7 — acontecimentos percebidos e mudança de prioridade:
Fase npc_review é uma reconsideração PRIVADA disparada por observations.events,
sem aguardar nova fala do jogador. Recebe somente actor.id, seus conhecimentos,
relações, opiniões e conversas percebidas. Não contém o mundo onisciente.
Nesta fase intent=null, adjudications=[], actions=[], step_index=0,
after_squares=null, check=null, interrupt=false. Pode retornar reactions=[] se
nada muda. Pode propor opinions somente desse NPC, sobre opções/versões que ele
conhece; não precisa de fala atual do jogador. Reavalie apenas as opções afetadas,
conservando objeções independentes. Pode interpretar episodes próprios com a
mesma política de evidência; nunca escolha ações antes dos novos cálculos.

Logo depois haverá npc_agency com a base atual para decidir como reagir. Uma
informação relevante pode mudar a prioridade, mesmo se o NPC já agiu nesta
interação. Há no máximo uma reconsideração por NPC por interação, agrupando os
últimos quatro eventos; novas ocorrências excedentes ficam para a próxima ação
em jogo. Não provoque troca infinita de revelações nem repita um mesmo relato.
Avaliação já calculada sobre a informação atual não dispara revisão redundante.

knowledge em um evento continua tendo dono/origem: report não prova autenticidade,
autoria ou traição. Observação de observed_injury sem source.actor_id mostra
apenas o ferido. Ruído percebido não prova tiro, ferimento, agressor ou intenção;
position=null não fornece coordenadas. Não invente documento autenticado, socorro,
moeda transferida, projétil ou ataque à distância. As evidências podem ser
históricas; confira as memórias ativas antes de propor um episódio confirmado.

Em npc_agency com observations.intent.event_opportunity=true, pode escolher
suspend, resume, investigate ou protect além das iniciativas anteriores.
suspend exige say com conversation.status=suspended e reason literal da fala.
resume exige conversa suspensa e say com status=active. Pontos e propostas
anteriores continuam no registro, sem resolução automática. Ao retomar, responda
à pendência ou registre por fala pertinente por que deixou de importar.
Investigar/proteger permite no máximo uma operação física: move para o local
percebido do incidente ou uma casa adjacente, ou search pela percepção existente.
Sem localização percebida, pode perguntar ou buscar do lugar onde está. Não há
cura, escudo automático, dano ou movimento pelo texto. Observadores sem ficha
não ganham movimento de Guerreiro. Sem evento, não se liberam essas operações.
Ataques continuam proibidos na agência; start_conflict rola iniciativa antes de
qualquer ataque ou deslocamento de combate. O conflito implementado é jogador
contra os NPCs hostis/instigador, não combate entre quaisquer terceiros ou aliados.
Não inicie violência por uma nota ou acusação sem causa própria.
Combate interrompe as conversas dos participantes sem inventar fala; pendências
permanecem. Durante iniciativa, decisões físicas continuam exclusivamente no
turno correto. Off não consome notificações nem avança prioridade. Reiniciar
limpa notificações e restaura a situação inicial.
"""


INSTRUCTIONS += """
Passo 8 — conversas casuais no mesmo motor:
Nem toda conversa é negociação, pedido Influence, problema para resolver ou
proposta com contrapartida. Uma amizade declarada no cenário pode orientar
escuta e franqueza sem gerar romance, obrigação ou sentimentos do jogador.
O objetivo privado pode surgir, mudar ou se esgotar conforme a conversa real.
Não atribua ao jogador tristeza, vontade de conselho ou desejo de companhia
que ele não declarou; use o que ouviu e deixe espaço para escolha.

Se o interlocutor só quer contar algo, listen pode usar somente wait OU say
de acolhimento seguido de wait; waiting_for descreve uma nova fala se ele quiser
continuar, sem exigir pergunta/garantia. can_wait continua sendo validado. Uma
nova fala dirigida ao NPC ou continuação percebida da conversa a dois renova
a escuta, mesmo sem haver pergunta formal. Falas a terceiros, off e só
aguardar não a renovam. Não transforme silêncio em aconselhamento obrigatório.
Se há pergunta, pedido ou objeção explícita do NPC ainda pendente, uma fala
alheia a essa pendência não renova a espera; registre a resposta real em resolves.
Para sugerir algo quando houver abertura, use respond/clarify com fala normal;
nunca exija offer/accept/reject, nota de opção ou dado para gentileza comum.

Ajudar espontaneamente pode ser oferecer um caminho conhecido após ouvir uma
necessidade, sem que o jogador peça cada iniciativa. Use knowledge próprio e
memory_ids compartilháveis para transmitir orientação. Não mova o jogador,
não o obrigue a aceitar companhia e não crie fatos conhecidos por outro NPC.
Uma moeda recebida antes da cena é episódio inicial autoral, já incorporado na
relação quando declarado; agradecer não transfere de novo, não cria dívida,
saldo ou outro bônus. Não há nova operação de dar moedas neste incremento.

Quando o assunto terminar, close pode encerrar com despedida e waiting_for=null.
Se o NPC decidir também sair fisicamente, initiative=leave exige exatamente
say com conversation.status=closed/reason literal, depois move, waiting_for=null.
Escolha apenas position de observations.departure_targets, locais livres vistos
em outra área. A geometria executa o percurso e pode impedi-lo; despedida não
equivale a deslocamento. Sem destino ofertado ou sem ficha, use close e não
invente saída, teleporte ou desaparecimento. O NPC continua no mapa ao chegar
na outra área. Não há saída de custódia/parley por essa iniciativa.
"""


INSTRUCTIONS += """
Passo 9 — vínculos qualitativos, sem pontos novos ou decaimento por tempo:
relationships[].bonds distingue friendship, attraction, infatuation e love,
cada um absent/active/ended, com dono, motivo, fontes e história. Não é estado
do jogador nem vínculo mútuo automático. Confiança e afeto continuam independentes.
Não transforme confiança alta em amizade, amizade em romance ou nota em aceitação.

Em player_action narrado ou npc_review, reactions[].bonds pode propor atualização
SOMENTE do NPC dono, com state=active/ended, reason e evidence_ids próprios reais.
Sem after_squares/check; em npc_agency/npc_turn use bonds=[]. Para o mesmo dono,
não antecipe ações no plano de cálculo. Python valida antes de opiniões/decisão.
Não altere perfil/alinhamento para justificar resultado e não atribua escolhas
ou sentimentos ao jogador. Adultos precisam ser explicitamente declarados pelo
autor; romance.eligible=false não pode ser contornado por suposição sobre idade.

Formação de friendship exige cuidado observado nas duas direções, por episódios
distintos, não reciprocidade emocional presumida. Fontes de cuidado têm tópicos
care/costly_help autorais ou episódio care_shown/costly_help já validado; promessa
e cumprimento protocolar não equivalem a cuidado. Attraction é interpretação
própria apoiada em observação do destinatário, sem exigir amizade ou confiança.
Infatuation exige atração própria ativa e outro encontro significativo observado
após essa atração; use personal_encounter autoral ou cuidado validado. Love exige
amizade e paixão próprias, história de cuidado recíproco e novo cuidado observado
após a paixão. Nunca forme etapas sucessivas pela mesma fonte numa única rodada.
Esses são critérios de implementação do Trama, não leis psicológicas ou D&D.

Manutenção usa acontecimento novo, sem precisar revalidar sentimento a cada fala.
Ruptura exige vínculo ativo, motivo e evidência própria posterior; reaproximação
também precisa de fato novo. Repetir atualização/fonte não reaplica história.
Initial bonds são antecedentes autorais. Manter amor quando a confiança diminui
ou não sentir atração por um amigo são possibilidades; nada muda automaticamente.
Recusa ou mudança de conversa não apaga sentimentos nem baixa níveis por si só.

romance.own_choice e known_target_choice são declarações percebidas, com unknown
quando não há informação. can_express=false impede expressão/investida amorosa;
sentimentos privados podem permanecer sem perseguição ou reciprocidade forçada.
Para expressar, o NPC deve ter sentimento próprio validado e usar
conversation.romantic_expression=true e um único target_id. Se só há attraction,
não invente love. Recusa franca pode usar romance_boundary=declined com trecho
literal; preserve amizade/carinho se essa for a escolha. Respeite limite conhecido
até declaração nova e efetivamente percebida de quem o estabeleceu.

Um vínculo pode mudar a prioridade e a forma de recusar sem conceder bônus novo
a S ou repetir suas fontes em M. Resumos relationship_bond são privados e não
pontuam. Só falas/efeitos executados chegam ao narrador, não estados afetivos
secretos. Não descreva romance infantil, contato íntimo, namoro ou reciprocidade
como efeito de uma atualização unilateral. Nenhuma nova operação física é criada.
"""


def parse_world_plan(text: str) -> WorldPlan:
    try:
        value = json.loads(text)
        value.setdefault('adjudications', [])  # Transporte de gravações antigas.
        value.setdefault('intent', None)
        _fields(value, WORLD_SCHEMA["properties"])
        if not isinstance(value["reactions"], list):
            raise WorldError("Respostas do Mundo devem ser uma lista.")
        reactions = []
        for item in value["reactions"]:
            item.setdefault('opinions', [])  # Gravações anteriores ao passo 3.
            item.setdefault('episodes', [])
            item.setdefault('bonds', [])
            _fields(item, REACTION_SCHEMA["properties"])
            if not isinstance(item["actions"], list):
                raise WorldError("Ações do Mundo devem ser uma lista.")
            actions = []
            for action in item["actions"]:
                # Aceita gravações antigas; o schema atual exige o campo na API.
                action.setdefault('influence', None)
                action.setdefault('volume', 'normal')
                action.setdefault('memory_ids', [])
                action.setdefault('conversation', None)
                _fields(action, ACTION_FIELDS)
                destination = action["destination"]
                if destination is not None:
                    _fields(destination, POSITION_SCHEMA["properties"])
                    if any(type(v) is not int or v < 1 for v in destination.values()):
                        raise WorldError("Coordenadas inválidas na resposta do Mundo.")
                    destination = Position(destination["column"] - 1, destination["row"] - 1)
                influence = action['influence']
                if influence is not None:
                    if set(influence) == {'willingness', 'skill', 'attitude'}:
                        influence = InfluenceRequest(**influence)  # Leitura histórica; não autoriza executar sem avaliação.
                    else:
                        _fields(influence, INFLUENCE_SCHEMA['properties'])
                        influence = InfluenceRequest(skill=influence['skill'], attitude=influence['attitude'],
                                                     assessment=assessment_from_data(influence['assessment']))
                if not isinstance(action['memory_ids'], list):
                    raise WorldError('memory_ids deve ser uma lista.')
                actions.append(WorldAction(action["actor_id"], action["operation"], action["text"],
                                           action["target_id"], destination, action["weapon"], influence, action["volume"],
                                           tuple(action['memory_ids']),
                                           conversation_update_from_data(action['conversation'])))
            check = item["check"]
            if check is not None:
                _fields(check, CHECK_SCHEMA["properties"])
                check = PerceptionCheck(**check)
            if any(not isinstance(item[k], list) for k in ('opinions', 'episodes', 'bonds')):
                raise WorldError('Opiniões, episódios e vínculos devem ser listas.')
            reactions.append(WorldReaction(item["step_index"], item["after_squares"], tuple(actions),
                                           item["interrupt"], item["reason"], check,
                                           tuple(option_from_data(o) for o in item['opinions']),
                                           tuple(episode_from_data(e) for e in item['episodes']),
                                           tuple(bond_update_from_data(b) for b in item['bonds'])))
        decisions = []
        for decision in value['adjudications']:
            _fields(decision, ADJUDICATION_SCHEMA['properties'])
            decisions.append(Adjudication(**{**decision, 'fact_ids': tuple(decision['fact_ids'])}))
        intent = value['intent']
        if intent is not None:
            intent.setdefault('initiative', None)
            intent.setdefault('reason', None)
            intent.setdefault('opinion_ids', [])
            _fields(intent, WORLD_SCHEMA['properties']['intent']['anyOf'][0]['properties'])
            if not isinstance(intent['opinion_ids'], (list, tuple)):
                raise WorldError('Referências de opiniões devem ser uma lista.')
            intent['opinion_ids'] = tuple(intent['opinion_ids'])
            intent = IntentDecision(**intent)
        return WorldPlan(tuple(reactions), tuple(decisions), intent)
    except (ValueError, TypeError, KeyError, AttributeError) as error:
        logger.error("ai.world_rejected", extra={"data": {"reason": str(error)}}, exc_info=True)
        raise WorldError(f"A IA retornou uma resposta do Mundo inválida: {error}") from error


class OpenAIWorldDirector:
    def __init__(self, client, model: str = DEFAULT_MODEL, *, response_options: ResponseOptions = DEFAULT_CONFIG.world,
                 budget: CallBudget | None = None):
        self.client, self.model = client, model
        self.response_options = response_options
        self.budget = budget

    def decide(self, context: dict) -> WorldPlan:
        if isinstance(context, AIContext):
            context.require(ContextKind.WORLD_ACTION, ContextKind.NPC_TURN, ContextKind.NPC_AGENCY, ContextKind.NPC_REVIEW)
        with log_context(ai_call_id=new_id()):
            text = request_json(self.client, model=self.model, instructions=INSTRUCTIONS,
                                payload=context, schema=WORLD_SCHEMA, name="world_response",
                                max_output_tokens=self.response_options.max_output_tokens,
                                reasoning_effort=self.response_options.reasoning_effort, budget=self.budget)
            plan = parse_world_plan(text)
            logger.info("ai.world_validated", extra={"data": {"reaction_count": len(plan.reactions)}})
            logger.debug("ai.world_decision", extra={"data": {"plan": plan}})
            return plan

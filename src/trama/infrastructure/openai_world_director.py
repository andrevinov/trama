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
from trama.difficulty import Adjudication, DIFFICULTY_CLASSES
from trama.agency import IntentDecision

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
}
# A API não pode produzir referências de fala em operações não verbais.
# O parser ainda lê referências privadas de Influence em gravações anteriores.
ACTION_SCHEMA = {'anyOf': [
    object_schema({**ACTION_FIELDS, 'operation': {'type': 'string', 'enum': ['say']},
                   'influence': {'type': 'null'}, 'target_id': {'type': 'null'},
                   'destination': {'type': 'null'}}),
    object_schema({**ACTION_FIELDS, 'operation': {'type': 'string', 'enum': ['influence']},
                   'target_id': {'type': 'null'}, 'destination': {'type': 'null'},
                   'influence': INFLUENCE_SCHEMA,
                   'volume': {'type': 'string', 'enum': ['normal']},
                   'memory_ids': {'type': 'array', 'maxItems': 0, 'items': {'type': 'string'}}}),
    object_schema({**ACTION_FIELDS,
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
REACTION_SCHEMA = object_schema({
    "step_index": {"type": "integer", "minimum": 0, "maximum": 9},
    "after_squares": {"type": ["integer", "null"], "minimum": 0},
    "actions": {"type": "array", "minItems": 1, "maxItems": 10, "items": ACTION_SCHEMA},
    "interrupt": {"type": "boolean"}, "reason": {"type": "string"},
    "check": {"anyOf": [CHECK_SCHEMA, {"type": "null"}]},
})
WORLD_SCHEMA = object_schema({
    'intent': {'anyOf': [object_schema({
        'actor_id': {'type':'string','minLength':1,'maxLength':120},
        'goal': {'type':'string','minLength':1,'maxLength':300},
        'activity': {'type':'string','minLength':1,'maxLength':300},
        'waiting_for': {'type':['string','null'],'maxLength':300},
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
fala que não ocorreu/que o NPC não ouviu. Nessa fase, a espera à distância da
primeira abordagem não impede cobrar uma resposta ou mudar de situação.
Nas demais fases, intent=null; não atualize intenções antes dos efeitos reais.

Antes de propor respostas, resolva world.adjudication.requests em adjudications.
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
ações físicas gratuitas. Narração de
NPCs e detalhes usa os fatos calculados depois da execução. Na phase npc_turn,
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
Uma fala clara tentando acalmar, explicar, mentir ou ameaçar deve receber influence,
na MESMA etapa speak/challenge, after_squares=null, depois da fala executada.
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


def _fields(value, expected):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise WorldError("Campos inválidos na decisão do Mundo.")


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
            _fields(item, REACTION_SCHEMA["properties"])
            if not isinstance(item["actions"], list):
                raise WorldError("Ações do Mundo devem ser uma lista.")
            actions = []
            for action in item["actions"]:
                # Aceita gravações antigas; o schema atual exige o campo na API.
                action.setdefault('influence', None)
                action.setdefault('volume', 'normal')
                action.setdefault('memory_ids', [])
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
                                           tuple(action['memory_ids'])))
            check = item["check"]
            if check is not None:
                _fields(check, CHECK_SCHEMA["properties"])
                check = PerceptionCheck(**check)
            reactions.append(WorldReaction(item["step_index"], item["after_squares"], tuple(actions),
                                           item["interrupt"], item["reason"], check))
        decisions = []
        for decision in value['adjudications']:
            _fields(decision, ADJUDICATION_SCHEMA['properties'])
            decisions.append(Adjudication(**{**decision, 'fact_ids': tuple(decision['fact_ids'])}))
        intent = value['intent']
        if intent is not None:
            _fields(intent, WORLD_SCHEMA['properties']['intent']['anyOf'][0]['properties'])
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
            context.require(ContextKind.WORLD_ACTION, ContextKind.NPC_TURN, ContextKind.NPC_AGENCY)
        with log_context(ai_call_id=new_id()):
            text = request_json(self.client, model=self.model, instructions=INSTRUCTIONS,
                                payload=context, schema=WORLD_SCHEMA, name="world_response",
                                max_output_tokens=self.response_options.max_output_tokens,
                                reasoning_effort=self.response_options.reasoning_effort, budget=self.budget)
            plan = parse_world_plan(text)
            logger.info("ai.world_validated", extra={"data": {"reaction_count": len(plan.reactions)}})
            logger.debug("ai.world_decision", extra={"data": {"plan": plan}})
            return plan

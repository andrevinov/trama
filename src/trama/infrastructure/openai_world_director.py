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

logger = logging.getLogger(__name__)


def object_schema(properties):
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


INFLUENCE_SCHEMA = object_schema({
    'willingness': {'type': 'string', 'enum': ['willing', 'unwilling', 'hesitant']},
    'skill': {'type': ['string', 'null'], 'enum': [None, 'persuasion', 'deception', 'intimidation', 'performance']},
    'attitude': {'type': 'string', 'enum': ['friendly', 'indifferent', 'hostile']},
})
POSITION_SCHEMA = object_schema({"column": {"type": "integer", "minimum": 1},
                                 "row": {"type": "integer", "minimum": 1}})
ACTION_SCHEMA = object_schema({
    "actor_id": {"type": "string"},
    "operation": {"type": "string", "enum": ["describe", "say", "move", "open", "close", "attack", "wait", "start_conflict", "end_conflict", "parley", "influence", "search"]},
    "text": {"type": "string", "minLength": 1, "maxLength": 2000},
    "target_id": {"type": ["string", "null"]},
    "destination": {"anyOf": [POSITION_SCHEMA, {"type": "null"}]},
    "weapon": {"type": "string", "enum": ["greatsword", "flail", "javelin", "longsword", "unarmed"]},
    "influence": {"anyOf": [INFLUENCE_SCHEMA, {"type": "null"}]},
    "volume": {"type": "string", "enum": ["quiet", "normal", "loud"]},
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
WORLD_SCHEMA = object_schema({"reactions": {"type": "array", "maxItems": 10, "items": REACTION_SCHEMA}})

INSTRUCTIONS = MODE_INSTRUCTIONS + """
Quando world.scenario existir, siga adjudication e os estados desse cenário.
No simulador de fuga, o código já resolve rotina, detecção sensorial, descobertas, disfarce,
ilusão, abertura mágica inicial e libertação. Na phase player_action retorne
reactions=[] quando parley não estiver pending; não duplique testes, mova NPCs ou
antecipe iniciativa. EXCEÇÃO: com parley.status=pending, resolva a resposta atual
pelo contrato geral abaixo; não retorne vazio para uma tentativa clara de convencer. Narração de
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
Com parley.status=pending, o NPC aguarda a resposta à distância registrada.
Uma fala clara tentando acalmar, explicar, mentir ou ameaçar deve receber influence,
na MESMA etapa speak/challenge, after_squares=null, depois da fala executada.
Não interrompa a fala em after_squares=0 nem presuma persuasão pela simples detecção.
influence é o julgamento do Mundo, não uma ação extra do jogador. Informe
influence={willingness,skill,attitude}. willing aceita sem rolar; unwilling recusa
sem rolar; hesitant usa persuasion/deception/intimidation/performance conforme a
fala, sem pedir ao jogador que nomeie perícia. skill=null fora de hesitant.
Não considere todo guarda irredutível: um pedido razoável para ouvir uma explicação
ou evitar violência normalmente é hesitant. Uma pergunta simples pode receber say
sem teste e continuar pending. A atitude é Friendly/Indifferent/Hostile, não o
booleano hostile do mapa (esse só identifica adversários de combate). Use
indifferent quando o NPC ainda está disposto a ouvir; justifique em text o pedido
avaliado e a disposição, sem inventar o resultado. O código deriva CD e rola.
Sucesso aceita o pedido de evitar combate; recusa/falha inicia iniciativa,
preservando posições. Não acrescente start_conflict, movimento, ataque ou uma
fala que pressuponha sucesso/falha na mesma resposta de influence.
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
                _fields(action, ACTION_SCHEMA["properties"])
                destination = action["destination"]
                if destination is not None:
                    _fields(destination, POSITION_SCHEMA["properties"])
                    if any(type(v) is not int or v < 1 for v in destination.values()):
                        raise WorldError("Coordenadas inválidas na resposta do Mundo.")
                    destination = Position(destination["column"] - 1, destination["row"] - 1)
                influence = action['influence']
                if influence is not None:
                    _fields(influence, INFLUENCE_SCHEMA['properties'])
                    influence = InfluenceRequest(**influence)
                actions.append(WorldAction(action["actor_id"], action["operation"], action["text"],
                                           action["target_id"], destination, action["weapon"], influence, action["volume"]))
            check = item["check"]
            if check is not None:
                _fields(check, CHECK_SCHEMA["properties"])
                check = PerceptionCheck(**check)
            reactions.append(WorldReaction(item["step_index"], item["after_squares"], tuple(actions),
                                           item["interrupt"], item["reason"], check))
        return WorldPlan(tuple(reactions))
    except (ValueError, TypeError, KeyError, AttributeError) as error:
        logger.error("ai.world_rejected", extra={"data": {"reason": str(error)}}, exc_info=True)
        raise WorldError("A IA retornou uma resposta do Mundo inválida.") from error


class OpenAIWorldDirector:
    def __init__(self, client, model: str = DEFAULT_MODEL, *, response_options: ResponseOptions = DEFAULT_CONFIG.world,
                 budget: CallBudget | None = None):
        self.client, self.model = client, model
        self.response_options = response_options
        self.budget = budget

    def decide(self, context: dict) -> WorldPlan:
        if isinstance(context, AIContext):
            context.require(ContextKind.WORLD_ACTION, ContextKind.NPC_TURN)
        with log_context(ai_call_id=new_id()):
            text = request_json(self.client, model=self.model, instructions=INSTRUCTIONS,
                                payload=context, schema=WORLD_SCHEMA, name="world_response",
                                max_output_tokens=self.response_options.max_output_tokens,
                                reasoning_effort=self.response_options.reasoning_effort, budget=self.budget)
            plan = parse_world_plan(text)
            logger.info("ai.world_validated", extra={"data": {"reaction_count": len(plan.reactions)}})
            logger.debug("ai.world_decision", extra={"data": {"plan": plan}})
            return plan

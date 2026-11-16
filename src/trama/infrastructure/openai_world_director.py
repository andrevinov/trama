"""Decisão de respostas do Mundo pela IA; a aplicação valida e executa os efeitos."""

import json
import logging

from trama.application.modes import MODE_INSTRUCTIONS
from trama.application.world import PerceptionCheck, WorldAction, WorldError, WorldPlan, WorldReaction
from trama.infrastructure.openai_json import DEFAULT_MODEL, request_json
from trama.observability import log_context, new_id
from trama.spatial import Position

logger = logging.getLogger(__name__)


def object_schema(properties):
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


POSITION_SCHEMA = object_schema({"column": {"type": "integer", "minimum": 1},
                                 "row": {"type": "integer", "minimum": 1}})
ACTION_SCHEMA = object_schema({
    "actor_id": {"type": "string"},
    "operation": {"type": "string", "enum": ["describe", "say", "move", "open", "close", "attack", "wait", "start_conflict", "end_conflict"]},
    "text": {"type": "string", "minLength": 1, "maxLength": 2000},
    "target_id": {"type": ["string", "null"]},
    "destination": {"anyOf": [POSITION_SCHEMA, {"type": "null"}]},
    "weapon": {"type": "string", "enum": ["greatsword", "flail", "javelin", "longsword", "unarmed"]},
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
No simulador de fuga, o código já resolve rotina, ruídos, descobertas, disfarce,
ilusão, abertura mágica inicial e libertação. Na phase player_action retorne
reactions=[]; não duplique testes, mova NPCs ou antecipe iniciativa. Narração de
NPCs e detalhes usa os fatos calculados depois da execução. Na phase npc_turn,
resolva normalmente as ações do guarda em combate usando a arma de sua ficha.

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
move usa destination={column,row} em base 1; o código calcula o caminho de menor
custo, contornando paredes e ocupantes sem cortar quinas. Uma porta aberta pode
ser ocupada. Portas fechadas não se abrem automaticamente. Escolha um destino
livre; para atacar, aproxime-se até uma casa adjacente ao Jogador.
Se o deslocamento não alcançar o destino (porta fechada ou saldo insuficiente),
a execução preserva o progresso e interrompe as ações seguintes dessa resposta.
Sair do alcance corpo a corpo de um adversário visível pode provocar ataque de
oportunidade. O código detecta o gatilho, cobra reação e resolve antes da saída.
Os guardas usam oportunidades automaticamente neste cenário; o Jogador confirma
a reação quando o jogo pausa. Não proponha ataques extras para simular esse
gatilho e não contabilize a reação como a ação normal do turno.
open/close usam target_id da passagem e exigem alcance de 1,5 m e visão.
attack só contra target_id='player', corpo a corpo e no turno do NPC em conflito.
start_conflict inicia iniciativa, sem ataque gratuito; faz a ação do Jogador parar
para respeitar a iniciativa. Não ataque na mesma resposta antes de saber a ordem.
end_conflict volta ao narrado quando o conflito realmente cessou (rendição, trégua,
desistência); text explica a causa. wait significa que o NPC aguarda.
target_id=null para outras operações, destination=null exceto move; weapon deve
ser uma arma da ficha do ator (ou unarmed se desarmado). Nunca invente resultados de dados, dano, cura ou gaste recursos em texto.
Se um guarda pode ouvir passos, mas há incerteza, check pode propor Percepção com
actor_id, dc (CD decidida pelo mestre, não distância de audição oficial) e reason
explicando a situação. O Python rola d20+Percepção; as actions e a interrupção só
ocorrem se passar. Falha não impede a ação. Não peça testes para tudo. Sem teste,
check=null. Não altere o estado escondido para justificar uma interrupção.
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
                _fields(action, ACTION_SCHEMA["properties"])
                destination = action["destination"]
                if destination is not None:
                    _fields(destination, POSITION_SCHEMA["properties"])
                    if any(type(v) is not int or v < 1 for v in destination.values()):
                        raise WorldError("Coordenadas inválidas na resposta do Mundo.")
                    destination = Position(destination["column"] - 1, destination["row"] - 1)
                actions.append(WorldAction(action["actor_id"], action["operation"], action["text"],
                                           action["target_id"], destination, action["weapon"]))
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
    def __init__(self, client, model: str = DEFAULT_MODEL):
        self.client, self.model = client, model

    def decide(self, context: dict) -> WorldPlan:
        with log_context(ai_call_id=new_id()):
            text = request_json(self.client, model=self.model, instructions=INSTRUCTIONS,
                                payload=context, schema=WORLD_SCHEMA, name="world_response", max_output_tokens=2000)
            plan = parse_world_plan(text)
            logger.info("ai.world_validated", extra={"data": {"reaction_count": len(plan.reactions)}})
            logger.debug("ai.world_decision", extra={"data": {"plan": plan}})
            return plan

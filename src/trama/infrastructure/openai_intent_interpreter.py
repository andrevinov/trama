"""Interpretação pela Responses API; o modelo não altera o estado do jogo."""

import json
import logging
from trama.knowledge import Claim
from copy import deepcopy

from openai import OpenAI
from trama.infrastructure.openai_json import DEFAULT_MODEL, OpenAIRequestError, request_json

from trama.application.intents import (
    DIRECTIONS, MovementIntent, MovementSegment, DoorIntent, PlayerIntent, InterpretationError, ActionPlan, RuleIntent, NarrativeIntent, NARRATIVE_OPERATIONS,
    RequestPart, REQUEST_KINDS, PLAN_OPERATIONS, ScenarioIntent, SCENARIO_OPERATIONS, InspectionIntent, GestureIntent,
)
from trama.application.modes import MODE_INSTRUCTIONS
from trama.application.authorization import PlanAuthorizationError, validate_player_plan
from trama.application.interpretation_context import compact_context
from trama.application.context_contracts import AIContext, ContextKind
from trama.infrastructure.openai_config import DEFAULT_CONFIG, ResponseOptions
from trama.infrastructure.call_budget import CallBudget
from trama.distances import CELL_METERS, to_meters
from trama.observability import log_context, new_id

logger = logging.getLogger(__name__)


# A geração estruturada segue a ordem das propriedades: o discriminador deve
# aparecer primeiro em todos os ramos do anyOf, antes dos parâmetros específicos.
INTENT_SCHEMA = {
    "type": "object",
    "properties": {
        "operation": {"type": "string", "enum": ["move"]},
        "segments": {
            "type": "array", "maxItems": 10,
            "items": {
                "type": "object",
                "properties": {
                    "direction": {"type": "string", "enum": list(DIRECTIONS)},
                    "distance": {"type": "number", "minimum": 0, "maximum": 10000},
                    "unit": {"type": "string", "enum": ["meters", "feet", "squares"]},
                },
                "required": ["direction", "distance", "unit"], "additionalProperties": False,
            },
        },
        "dash": {"type": "boolean"},
        "clarification": {"type": "string"},
        "target_id": {"type": ["string", "null"]},
    },
    "required": ["segments", "dash", "clarification", "target_id", "operation"], "additionalProperties": False,
}

DOOR_SCHEMA = {"type": "object", "properties": {
    "operation": {"type": "string", "enum": ["open", "close"]},
    "target_id": {"type": "string", "minLength": 1},
    "allow_approach": {"type": "boolean"}},
    "required": ["operation", "target_id", "allow_approach"], "additionalProperties": False}

INSPECTION_SCHEMA = {"type": "object", "properties": {
    "operation": {"type": "string", "enum": ["inspect_passage"]},
    "target_id": {"type": "string", "minLength": 1},
    "method": {"type": "string", "enum": ["visual", "mechanism"]},
    "volume": {"type": "string", "enum": ["quiet", "normal"]},
    "allow_approach": {"type": "boolean"}},
    "required": ["operation", "target_id", "method", "volume", "allow_approach"], "additionalProperties": False}

GESTURE_SCHEMA = {"type": "object", "properties": {
    'operation': {'type': 'string', 'enum': ['gesture']},
    'target_id': {'type': 'string', 'minLength': 1},
    'text': {'type': 'string', 'minLength': 1, 'maxLength': 1000},
    'message': {'type': 'string', 'maxLength': 1000},
    'subtle': {'type': 'boolean'}},
    'required': ['operation', 'target_id', 'text', 'message', 'subtle'], 'additionalProperties': False}

RULE_SCHEMA = {
    "type": "object",
    "properties": {
        "operation": {"type": "string", "enum": ["end_turn", "second_wind", "action_surge", "hide"]},
        "target_id": {"type": "null"},
        "weapon": {"type": "string", "enum": ["greatsword", "flail", "javelin", "longsword", "unarmed"]},
        "use_inspiration": {"type": "boolean"},
    },
    "required": ["operation", "target_id", "weapon", "use_inspiration"], "additionalProperties": False,
}

ATTACK_SCHEMA = {**RULE_SCHEMA, "properties": {**RULE_SCHEMA["properties"],
    "operation": {"type": "string", "enum": ["attack"]},
    "target_id": {"type": "string", "minLength": 1},
    "allow_approach": {"type": "boolean"}},
    "required": [*RULE_SCHEMA["required"], "allow_approach"]}
CLAIM_SCHEMA = {"type": "object", "properties": {
    name: {"type": "string", "minLength": 1, "maxLength": 120}
    for name in ('subject_id', 'predicate', 'value')},
    "required": ['subject_id', 'predicate', 'value'], "additionalProperties": False}
NARRATIVE_SCHEMA = {"type": "object", "properties": {
    "operation": {"type": "string", "enum": list(NARRATIVE_OPERATIONS)},
    "text": {"type": "string", "minLength": 1, "maxLength": 2000},
    "volume": {"type": "string", "enum": ["quiet", "normal", "loud"]},
    "claims": {"type": "array", "maxItems": 3, "items": CLAIM_SCHEMA}},
    "required": ["operation", "text", "volume", "claims"], "additionalProperties": False}

SCENARIO_SCHEMA = {"type": "object", "properties": {
    "operation": {"type": "string", "enum": list(SCENARIO_OPERATIONS)},
    "target_id": {"type": "string", "minLength": 1},
    "allow_approach": {"type": "boolean"}},
    "required": ["operation", "target_id", "allow_approach"], "additionalProperties": False}

PLAN_SCHEMA = {
    "type": "object",
    "properties": {"request_parts": {"type": "array", "minItems": 1, "maxItems": 20, "items": {
        "type": "object", "properties": {
            "text": {"type": "string", "minLength": 1, "maxLength": 2000},
            "kind": {"type": "string", "enum": list(REQUEST_KINDS)},
            "operations": {"type": "array", "maxItems": 30, "items": {"type": "string", "enum": list(PLAN_OPERATIONS)}},
            "step_indices": {"type": "array", "maxItems": 10, "items": {"type": "integer", "minimum": 0, "maximum": 9}},
        }, "required": ["text", "kind", "operations", "step_indices"], "additionalProperties": False}},
                   "steps": {"type": "array", "minItems": 0, "maxItems": 10,
                             "items": {"anyOf": [INTENT_SCHEMA, ATTACK_SCHEMA, RULE_SCHEMA, NARRATIVE_SCHEMA, SCENARIO_SCHEMA, DOOR_SCHEMA, INSPECTION_SCHEMA, GESTURE_SCHEMA]}}},
    "required": ["request_parts", "steps"], "additionalProperties": False,
}


def action_plan_schema(order: str = "operation-first") -> dict:
    """O jogo usa operation primeiro; legacy existe apenas para comparação controlada."""
    if order not in {"operation-first", "legacy"}:
        raise ValueError("Ordem de esquema inválida.")
    schema = deepcopy(PLAN_SCHEMA)
    if order == "legacy":
        properties = schema["properties"]["steps"]["items"]["anyOf"][0]["properties"]
        operation = properties.pop("operation")
        properties["operation"] = operation
    return schema


INSTRUCTIONS = MODE_INSTRUCTIONS + """
Interprete semanticamente a mensagem atual do Jogador em português. Você é o
único interpretador de linguagem: o Python verifica dados e regras, sem uma
lista de verbos autorizados. Retorne request_parts e steps, na ordem do pedido.

request_parts registra trechos LITERAIS de player_prompt e sua interpretação:
text, kind, operations e step_indices (índices de steps, base 0). Um trecho pode
solicitar várias operações: 'uso Surto de Ação para atacar novamente' é execute,
operations=['action_surge','attack'], step_indices=[0,1]. 'Para atacar' expressa
uma ação solicitada junto do poder, não exige outra mensagem ou conectivo 'e'.
Cada etapa aparece exatamente uma vez nas origens, na ordem. As operações de
cada origem devem corresponder às etapas vinculadas. Se move usa dash=true,
operations inclui move,dash. Se ataque usa use_inspiration=true, inclui
attack,inspiration, somente com autorização explícita do Jogador.

Pergunta explicitamente dirigida a um NPC é fala dentro do jogo: execute/speak,
inclusive quando termina com interrogação; não é uma dúvida de regras em off.
Classifique também perguntas de regras ao narrador (question), negações (negated), citações (quoted)
e detalhes narrativos (narrative_detail): operations=[] e step_indices=[].
Não use menções, perguntas, negações, discurso relatado, catálogo ou histórico
como ordens de gastar recursos. 'Não uso Retomar o Fôlego; caminho até a porta'
gera somente move, com a negação registrada separadamente. 'Digo ao guarda para
usar Retomar o Fôlego' gera speak, sem ativar o poder do Jogador. Uma pergunta
sobre uma habilidade não a ativa: steps pode ser vazio. Registre a pergunta e
ela será respondida em off. Texto em off não está autorizado nesta etapa.

Em mode=turn_based, quando combat.player_turn=true, uma declaração autônoma de
inatividade significa passar a vez: 'fico parado', 'fico parado na mesma posição',
'não faço nada', 'não faço mais nada', 'aguardo' ou 'espero' gera end_turn.
Interprete o sentido, sem exigir essas palavras exatas. Isso vale mesmo havendo
ação, bônus ou movimento disponíveis. Registre kind=execute, operations=['end_turn']
e a etapa end_turn com target_id=null; não classifique essa intenção de passar
a vez como negated, narrative_detail, wait ou plano vazio. A expressão 'não faço
nada' é uma decisão de encerrar a vez, não uma negação de end_turn.
Considere a mensagem inteira: 'fico parado e uso Retomar o Fôlego' pede o poder
sem encerrar o turno; 'ataco e depois não faço mais nada' pede attack e end_turn,
nessa ordem. Permanecer no lugar durante outra ação é apenas postura. Perguntas,
citações e uma negação real ('não quero encerrar meu turno') não passam a vez.
Em mode=narrated, permanecer/aguardar usa wait, sem criar combate, turnos ou
tempo mecânico. A aplicação valida de quem é a vez antes de executar end_turn.

Trate 'fico de frente para a sala' como narrative_detail, sem etapa mecânica,
sem custo e sem impedir a caminhada. A visão atual é de 360 graus, sem regra de
orientação ou ação de virar. 'Volto', 'retorno', 'recuo' e outras paráfrases são
movimento quando esse for o sentido contextual. Não exija uma forma de escrever.
Se houver ambiguidade que muda o resultado ou ação não implementada, use kind
unclear/unsupported/conditional, operations=['clarify'] e uma última etapa
move com segments=[], dash=false, target_id=null e clarification em português.
Preserve etapas anteriores suportadas. Não peça esclarecimento para postura
narrativa nem para uma caminhada com destino ou coordenadas definidos.

Operações básicas: move, open, close, inspect_passage, gesture, attack, end_turn, second_wind,
action_surge, look, speak, wait, challenge. available_actions descreve seu uso;
são capacidades suportadas, não ordens para usá-las. Não invente outras operações,
resultados de dados ou respostas do Mundo. Caminhar nunca autoriza atacar.
look/speak/wait/challenge não mudam posição, portas, PV ou recursos. O
movimento real é executado como move, inclusive quando preparado pela aplicação. O Mundo decide seus NPCs.

Sinais, gestos, acenos, piscadelas e mímica DIRIGIDOS a um NPC são comunicação:
execute/gesture, nunca apenas narrative_detail. target_id vem de communication_targets
ou visible_creatures, inclusive um NPC conhecido que não esteja visível agora;
o motor verifica se ELE consegue ver o jogador. Não declare sucesso nem mova o
personagem para tornar o gesto possível. Sem alvo identificável, peça esclarecimento.
text descreve SOMENTE o movimento exterior observável; message registra a intenção
do jogador, sem torná-la entendimento do NPC. Ex.: sinal para confirmar a história:
text='Faço um gesto pedindo a palavra ao prisioneiro.', message='Quero que confirme
minha história.' Não invente código previamente combinado, significado secreto,
resposta ou fala do NPC. subtle=true em piscadelas/gestos finos ou discretos;
false para acenos e sinais claros. Discreto não garante que terceiros não vejam.
Um simples assentir comunicativo também usa gesture. Postura sem destinatário ou
intenção comunicativa continua detalhe narrativo. Não transforme gesto em speak,
não acrescente fala/Hide/teste. Preserve fala e gesto como etapas distintas quando
o jogador pedir ambos, na ordem real da mensagem.

Inspecionar uma porta ou grade usa inspect_passage e target_id da PASSAGEM,
não investigate no cômodo. 'Checo se a Cela 4 está trancada' significa conferir
seu acesso: inspect_passage/gate_4, method=mechanism. É uma capacidade geral,
inclusive sem scenario, não uma operação não suportada. Conferir exige alcance;
allow_approach=true permite aproximar, false preserva 'sem sair do lugar'.
volume=quiet preserva pedidos de cuidado, silêncio ou ausência de barulho;
silêncio é uma tentativa, não sucesso garantido. Não acrescente hide nem outro
sneak para uma conferência cuidadosa. O motor mantém a furtividade existente.
Quando o jogador limita a ação a OLHAR/OBSERVAR, use method=visual,
allow_approach=false, volume=normal, sem deslocamento ou manipulação, mesmo
que queira saber se está trancada. Aparência fechada não prova trancamento:
locked=null é desconhecido; nunca invente o resultado. Inspeção não autoriza
open, unlock, entrada no cômodo, chaves, arrombamento ou desarmar armadilhas.
Sem alvo identificável e sem referência inequívoca no contexto/histórico,
peça esclarecimento; não escolha uma porta por conta própria.

move usa segmentos/destino; open/close usam operation, target_id e allow_approach.
Abrir ou fechar uma passagem autoriza a aproximação necessária: allow_approach=true
por padrão. A aplicação calcula o percurso e valida alcance, obstáculos, orçamento
e respostas do Mundo antes de interagir. Você pode retornar somente open/close
quando o pedido já implica essa aproximação; não precisa inventar microetapas.
Se o Jogador proibir deslocamento ('sem sair do lugar'), allow_approach=false;
preserve essa restrição. Não acrescente move que a contradiga. Ações já satisfeitas
(abrir uma grade já aberta, fechar uma já fechada) não exigem aproximação, recursos
ou mudança de estado; o restante do pedido continua. Isso não autoriza destrancar,
abrir obstáculos no caminho, Dash ou ataques não solicitados.
Para lugares,
passagens e criaturas VISÍVEIS, target_id é seu id existente, segments=[].
Uma criatura numerada é identificada por number em visible_creatures. 'Vou até
o guarda 1 e o ataco' gera move e attack com o mesmo id. O código calcula
aproximação até uma casa livre adjacente; não ocupe a casa da criatura.
Até a porta significa aproximar-se; para ocupar a casa da porta aberta, use
movimento por segmentos. Não abra portas sem pedido. Ir e abrir são duas etapas.

Para coordenadas (coluna,linha), calcule segmentos a partir de character.column
/row. Ex.: de (15,6) a (13,6), west,3,meters. Metros são padrão e cada casa mede
1,5 m. Não substitua coordenadas explícitas por aproximar-se de uma passagem.
Coordenadas começam em 1. Direções: north=cima, south=baixo, east=direita,
west=esquerda e diagonais. Preserve distância e frações, sem arredondar para cima
ou encurtar para caber num turno. Feet só se pedir pés: 5 pés=1,5 m. 'Todo meu
movimento' usa remaining_meters no combate, speed_meters na exploração.
Sem distância pedida, destino nomeado basta; exploração não limita à velocidade.
Dash=true só a pedido de correr/Dash/Disparada.

Movimento contextual: uma ação física pode autorizar somente a aproximação
necessária para realizá-la. attack, investigate, take, unlock, listen e wake usam
allow_approach=true por padrão, assim como open/close. A aplicação calcula onde
precisa estar: dentro da área para investigar, ao alcance para coletar/interagir
ou atacar. Você pode propor apenas investigate/cell_4 para 'checo a cela', take
para pegar objeto e attack para atacar; o Python cuida da aproximação necessária.
A execução não gasta Dash/poderes, destranca ou abre barreiras intermediárias por
conta própria. 'Sem sair do lugar' exige allow_approach=false na ação e nenhum
move contraditório. Uma caminhada explícita anterior não é duplicada. Se faltar
movimento ou houver interrupção, o percurso para e a ação fica não realizada.
O ataque que precisa aproximar e inicia combate resolve iniciativa ANTES da
caminhada tática. A aplicação verifica recursos/alvo/arma antes de aproximar e
revalida depois; não invente resultados nem iniciativa na interpretação.

Se scenario estiver presente, suas operations e guidance definem as interações
adicionais implementadas. Use o ramo operation/target_id/allow_approach correspondente, sem
inventar campos ou substituir interação mecânica por look/speak. Investigar
panos/cama usa investigate no id do cômodo referido, mesmo estando fora.
Encontrar não equivale a pegar: pegar e vestir são take e wear. sneak executa teste e movimento até target_id; não
acrescente move duplicado. Objetos em visible_objects incluem itens conhecidos
ou carregados: só esses ids podem ser usados. Prisioneiro usa id prisoner.
map.scene.objects descreve objetos estáticos visíveis: move pode aproximar-se
desses ids; não há ação para removê-los ou manipulá-los. attachment=wall indica
fixação no lado cardinal da casa, sem ocupar a casa vizinha da parede. Os campos
blocks_movement e blocks_vision são independentes; fixação não implica bloqueio.
Destrancar e abrir são unlock e open. Se pedir ambas, gere ambas em sequência.
Ir até a saída pode usar move/outside ou escape/outside; portas não abrem sozinhas.
Disfarçar-se perante o guarda usa deceive/guard_1, após vestir a roupa.
hide é uma operação geral para esconder-se: target_id=null, use_inspiration=false.
sneak é geral e usa target_id do destino, inclusive sem scenario; não acrescente
move duplicado. O código valida cobertura, rola Furtividade CD 15 se necessário
e mantém o total como CD de detecção. Não escolha CD nem sucesso.
Em speak/challenge, volume=quiet para sussurrar, loud para gritar e normal para
fala comum. Nas outras intenções narrativas, volume=normal. Não transforme uma
fala em percepção: o motor notifica os NPCs que efetivamente podem ouvi-la.
knowledge contém somente memórias do jogador, com origem e contexto, não a
verdade atual nem memórias privadas dos NPCs. Perguntar a um NPC em jogo usa
speak; uma pergunta não afirma um fato. Em claims informe apenas afirmações
concretas que o jogador está de fato comunicando, com subject_id, predicate e
value. Use ids conhecidos em knowledge/map; localização usa predicate=location,
value=position:coluna,linha, carried:id ou id de lugar referido. Esses dados são
relatos não confirmados, nunca autorização para mudar o mundo. claims=[] em
perguntas, negações, hipóteses, look e wait. Nunca invente uma afirmação para
preencher o campo. Preserve a fala do jogador em text.
Durante uma conversa, promessas e ofertas explícitas também são informação:
registre a promessa declarada em claims, sem realizá-la. Para recompensa use
subject_id=player, predicate=offer_reward e value descrevendo valor/condição;
repetições equivalentes mantêm a mesma Claim. Isso não transfere dinheiro nem
confirma que o jogador possa pagar. Uma alegação de filiação usa predicate=parentage
e value descrevendo o parentesco alegado, sem torná-lo fato confirmado.
Apenas olhar usa look, sem Search ou teste gratuito. Percepção pertence aos
sentidos dos NPCs, não a um teste inventado pelo interpretador.

attack exige alvo visível e usa weapon de equipped_weapons. Se não há arma,
use unarmed. Uma arma que o próprio plano manda pegar antes pode ser usada
no ataque subsequente. Na falta de arma explícita, use a arma padrão da ficha. last_attack informa o último ataque real
do Jogador: alvo, arma e se o alvo continua vivo/visível. 'Ataco novamente o
guarda anterior' usa essa referência, sem presumir outro alvo. Uma referência
a morto ou oculto não permite substituir por outro guarda silenciosamente.
Surto de Ação seguido de ataque deve produzir as DUAS etapas no mesmo plano,
mesmo se a ação atual já estiver gasta: o poder concede a ação para a seguinte.
Use end_turn só quando o Jogador encerrar a vez; o ataque respeita iniciativa.
Ataques de oportunidade são tratados pela aplicação, sem acrescentar ataques
extras ao plano. Preparar, Desengajar, ataques à distância, teleporte, saltos,
descansos ainda não têm comandos. Testes de cenário usam as operações de scenario. Condicionais para efeitos
futuros precisam de esclarecimento. Histórico serve para referências, não para
repetir ações antigas. correction contém inconsistências objetivas do plano:
corrija usando o MESMO pedido original, sem omitir ações solicitadas válidas.
"""



def parse_intent(text: str) -> PlayerIntent:
    """Valida novamente a saída externa, inclusive tipos e campos inesperados."""
    try:
        value = json.loads(text)
        if isinstance(value, dict) and value.get('operation') == 'gesture':
            if set(value) != {'operation', 'target_id', 'text', 'message', 'subtle'}:
                raise ValueError('Campos de comunicação gestual inválidos')
            return GestureIntent(value['target_id'], value['text'], value['message'], value['subtle'])
        if isinstance(value, dict) and value.get('operation') == 'inspect_passage':
            if set(value) != {'operation', 'target_id', 'method', 'volume', 'allow_approach'}:
                raise ValueError('Campos de inspeção inválidos')
            return InspectionIntent(value['target_id'], value['method'], value['volume'], value['allow_approach'])
        if isinstance(value, dict) and value.get("operation") in {"open", "close"} and set(value) == {"operation", "target_id", "allow_approach"}:
            return DoorIntent(value["operation"], value["target_id"], value["allow_approach"])
        if isinstance(value, dict) and value.get("operation") in SCENARIO_OPERATIONS:
            if set(value) not in ({"operation", "target_id"}, {"operation", "target_id", "allow_approach"}):
                raise ValueError("Campos de interação inválidos")
            return ScenarioIntent(value["operation"], value["target_id"], value.get("allow_approach", True))
        if isinstance(value, dict) and value.get("operation") in NARRATIVE_OPERATIONS:
            if not {'operation', 'text'} <= set(value) or set(value) - {'operation', 'text', 'volume', 'claims'}:
                raise ValueError("Campos de intenção narrativa inválidos")
            claims = value.get('claims', [])
            if not isinstance(claims, list):
                raise ValueError('claims deve ser uma lista de afirmações.')
            return NarrativeIntent(value["text"], value["operation"], volume=value.get("volume", "normal"),
                                   claims=tuple(Claim(**c) for c in claims))
        if isinstance(value, dict) and value.get("operation") in {"end_turn", "attack", "second_wind", "action_surge", "hide"}:
            if set(value) not in ({"operation", "target_id", "weapon", "use_inspiration"},
                                   {"operation", "target_id", "weapon", "use_inspiration", "allow_approach"}):
                raise ValueError("Operação de combate inválida")
            return RuleIntent(value["operation"], value["target_id"], value["weapon"], value["use_inspiration"], value.get("allow_approach", True))
        if not isinstance(value, dict) or set(value) != {"segments", "dash", "clarification", "target_id", "operation"}:
            raise ValueError("Campos inválidos")
        segments = value["segments"]
        if not isinstance(segments, list) or len(segments) > 10:
            raise ValueError("Segmentos inválidos")
        parsed = []
        for segment in segments:
            if (not isinstance(segment, dict) or set(segment) != {"direction", "distance", "unit"}
                    or not isinstance(segment["direction"], str)):
                raise ValueError("Segmento inválido")
            distance = to_meters(segment["distance"], segment["unit"])
            if distance > 10000:
                raise ValueError("Um segmento não pode exceder 10000 m.")
            squares = int(distance // CELL_METERS)
            parsed.append(MovementSegment(segment["direction"], squares, distance % CELL_METERS))
        if value["operation"] in {"open", "close"}:
            if parsed or value["dash"] is not False or value["clarification"] != "":
                raise ValueError("Uma interação não pode conter movimento ou esclarecimento")
            return DoorIntent(value["operation"], value["target_id"])
        if value["operation"] != "move":
            raise ValueError("Operação desconhecida")
        return MovementIntent(tuple(parsed), value["dash"], value["clarification"], value["target_id"])
    except (ValueError, TypeError) as error:
        logger.error("ai.intent_rejected", extra={"data": {"reason": str(error)}}, exc_info=True)
        logger.debug("ai.rejected_intent_payload", extra={"data": {"output_text": text}})
        raise InterpretationError("A OpenAI retornou uma intenção inválida. Tente reformular.") from error


def parse_plan(text: str, *, require_sources: bool = False) -> ActionPlan:
    step_index = None
    try:
        value = json.loads(text)
        if (not isinstance(value, dict) or set(value) not in ({"steps"}, {"request_parts", "steps"})
                or not isinstance(value["steps"], list) or (require_sources and "request_parts" not in value)):
            raise ValueError("Plano inválido")
        steps = []
        for step_index, step in enumerate(value["steps"]):
            steps.append(parse_intent(json.dumps(step)))
        parts = value.get("request_parts", [])
        if not isinstance(parts, list):
            raise ValueError("Origens devem ser uma lista")
        sources = []
        for part in parts:
            if (not isinstance(part, dict) or set(part) != {"text", "kind", "operations", "step_indices"}
                    or not isinstance(part["operations"], list) or not isinstance(part["step_indices"], list)):
                raise ValueError("Origem inválida")
            sources.append(RequestPart(part["text"], part["kind"], tuple(part["operations"]), tuple(part["step_indices"])))
        plan = ActionPlan(tuple(steps), tuple(sources))
        logger.info("ai.plan_validated", extra={"data": {"step_count": len(plan.steps), "validation": "structure"}})
        logger.debug("ai.decision", extra={"data": {"plan": plan}})
        return plan
    except (ValueError, TypeError) as error:
        logger.error("ai.plan_rejected", extra={"data": {"step_index": step_index, "reason": str(error)}}, exc_info=True)
        logger.debug("ai.rejected_plan_payload", extra={"data": {"output_text": text}})
        raise InterpretationError("A OpenAI retornou um plano inválido. Tente reformular.") from error


class OpenAIIntentInterpreter:
    def __init__(self, client: OpenAI, model: str = DEFAULT_MODEL, *, context_mode: str = DEFAULT_CONFIG.context_mode,
                 max_corrections: int = DEFAULT_CONFIG.max_corrections, schema_order: str = DEFAULT_CONFIG.schema_order,
                 response_options: ResponseOptions = DEFAULT_CONFIG.interpretation, budget: CallBudget | None = None) -> None:
        if context_mode not in {"minimal", "full"} or type(max_corrections) is not int or max_corrections not in (0, 1):
            raise ValueError("Use contexto minimal/full e no máximo uma correção.")
        self.client = client
        self.model = model
        self.context_mode = context_mode
        self.max_corrections = max_corrections
        self.schema_order = schema_order
        self.schema = action_plan_schema(schema_order)
        self.response_options = response_options
        self.budget = budget

    def interpret(self, prompt: str, context: dict) -> ActionPlan:
        return self._interpret(prompt, context)

    def _interpret(self, prompt: str, context: dict) -> ActionPlan:
        if not prompt.strip() or len(prompt) > 2000:
            raise InterpretationError("Digite um pedido com 1 a 2000 caracteres.")
        if isinstance(context, AIContext):
            context.require(ContextKind.INTERPRETATION)
        selected = (context if isinstance(context, AIContext) or self.context_mode == "full"
                    else compact_context(context))
        payload = {**selected, "player_prompt": prompt}
        for attempt in range(1, self.max_corrections + 2):
            with log_context(ai_call_id=new_id()):
                logger.info("ai.interpretation_attempt", extra={"data": {"attempt": attempt,
                            "context_mode": self.context_mode, "schema_order": self.schema_order}})
                try:
                    text = request_json(self.client, model=self.model, instructions=INSTRUCTIONS,
                                        payload={**payload, "interpretation_attempt": attempt}, schema=self.schema, name="action_plan",
                                        max_output_tokens=self.response_options.max_output_tokens,
                                        reasoning_effort=self.response_options.reasoning_effort, budget=self.budget)
                except OpenAIRequestError as error:
                    raise InterpretationError(str(error)) from error
                plan = parse_plan(text, require_sources=True)
                try:
                    validate_player_plan(prompt, plan, selected, stage="interpretation")
                except PlanAuthorizationError as error:
                    if attempt <= self.max_corrections:
                        logger.warning("ai.plan_correction_requested", extra={"data": {"attempt": attempt, "reason": str(error)}})
                        payload["correction"] = {"reason": str(error), "previous_plan": json.loads(text)}
                        continue
                    logger.error("ai.plan_authorization_failed", extra={"data": {"attempts": attempt, "reason": str(error)}})
                    raise PlanAuthorizationError("Não consegui interpretar seu pedido sem contradições. Nenhuma ação foi executada. " + str(error)) from error
                return plan

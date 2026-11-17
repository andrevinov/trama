"""Contratos das projeções de IA; sem mapa, regras, provedor ou arquivos de referência."""

from dataclasses import dataclass
from enum import StrEnum
import json
from math import isfinite


class ContextKind(StrEnum):
    INTERPRETATION = 'interpretation'
    WORLD_ACTION = 'world_action'
    NPC_TURN = 'npc_turn'
    NARRATION_INITIAL = 'narration_initial'
    NARRATION_RESULT = 'narration_result'
    NARRATION_OFF = 'narration_off'


class ContextError(ValueError):
    """A projeção não atende ao contrato da fase que vai consumi-la."""


@dataclass(frozen=True)
class ContextField:
    types: str
    source: str
    meaning: str
    optional: bool = False


@dataclass(frozen=True)
class ContextContract:
    fields: dict[str, ContextField]
    scope: str
    forbidden: tuple[str, ...] = ()


F = ContextField
STATE = {
    'knowledge': F('array', 'KnowledgeSystem / KnowledgeStore.select', 'Memórias selecionadas do jogador; não inclui memórias privadas de NPCs nem verdade global.'),
    'sensing': F('object', 'GameSession.perception', 'Ocultação e possibilidade atual de esconder-se; não revela observadores ocultos.'),
    'mode': F('string', 'GameSession.mode', 'Modo narrado ou por turnos.'),
    'character': F('object', 'GameSession.interpreter_context', 'Posição e recursos atuais do jogador.'),
    'parley': F('object|null', 'GameSession.parley', 'Abordagem, posições de detecção e situação da conversa antes do combate.'),
    'combat': F('object|null', 'GameSession.combat_context', 'Iniciativa/vez atual, ou null fora de combate.'),
}
KNOWN = {
    'map': F('object', 'build_context / compact_context', 'Grade em metros e arquitetura nomeada; não é somente a área vista.'),
    'visible_creatures': F('array', 'GameSession.visibility / DungeonSession', 'Criaturas vistas, com identidade e posição.'),
    'equipped_weapons': F('array', 'GameSession.encounter.player_sheet', 'Ids das armas atualmente equipadas.'),
    'last_attack': F('object|null', 'Encounter.last_attacks', 'Último ataque real, com validade atual do alvo.'),
    'recent_messages': F('array', 'Conversation._full_context', 'Histórico recente on; não inclui fala off.'),
    'scenario': F('object', 'DungeonSession.interpreter_context', 'Operações e orientação pública do cenário.', optional=True),
    'visible_objects': F('array', 'DungeonSession.known_objects', 'Itens conhecidos, inclusive carregados ou lembrados fora de visão.', optional=True),
}
WORLD = {
    **STATE, **KNOWN,
    'player_sheet': F('object', 'GameSession.character_context', 'Ficha validada do jogador.'),
    'visible_enemies': F('array', 'GameSession.visible_enemy_summaries', 'Resumo dos inimigos vistos.'),
    'world': F('object', 'GameSession / DungeonSession', 'Estado completo de mestre, inclusive NPCs ocultos e segredos.'),
    'player_plan': F('array', 'Conversation.world_context', 'Etapas propostas e preparação espacial; não são efeitos realizados.'),
    'player_request_parts': F('array', 'ActionPlan.request_parts', 'Origens declaradas das etapas.'),
    'phase': F('string', 'Conversation.world_context', 'player_action ou npc_turn.'),
    'available_actions': F('array', 'Catálogo de ações da sessão', 'Extensão opcional de capacidades.', optional=True),
    'turn_resources': F('object', 'Orçamento da sessão', 'Extensão opcional de disponibilidade.', optional=True),
}
NARRATION = {
    **STATE,
    'phase': F('string', 'Conversation.narration_context', 'initial para abertura, reply para resultado ou off.'),
    'allow_on': F('boolean', 'Conversation.narration_context', 'Autoriza descrição em jogo a partir dos efeitos/percepções.'),
    'player': F('object', 'Conversation.prepare / Speech', 'Mensagem atual separada em on/off.'),
    'execution': F('object', 'ExecutionReport / Conversation._execution_context', 'Efeitos, impedimentos, reações e movimento reais desta interação.'),
    'previous_execution': F('object|null', 'Conversation._remember', 'Último registro anterior; memória, não nova execução.'),
    'perception': F('object', 'Visão e objetos conhecidos da sessão', 'Fatos percebidos/lembrados pelo jogador.'),
    'player_sheet': F('object', 'GameSession.character_context', 'Ficha atual validada.'),
    'world': F('object', 'GameSession / DungeonSession', 'Estado de mestre para coerência; não autoriza revelar segredos.'),
    'history': F('array', 'Conversation.messages', 'Até 12 mensagens, com papéis e canais on/off.'),
    'verified_rules': F('array', 'Conversation.narration_context', 'Regras e simplificações implementadas, não poderes propostos.'),
}
CONTRACTS = {
    ContextKind.INTERPRETATION: ContextContract({
        **STATE, **KNOWN,
        'available_actions': F('array', 'compact_context', 'Operações disponíveis e uso; não gasta recursos.'),
        'turn_resources': F('object', 'Ficha/orçamento via compact_context', 'Disponibilidade da ação, bônus, reação e extras.'),
    }, 'Conhecimento para interpretar o jogador, sem world/ficha completa/off.',
        ('world', 'player_sheet', 'recent_messages[].off', 'map.blocked', 'map.difficult')),
    ContextKind.WORLD_ACTION: ContextContract(WORLD, 'Mestre completo avaliando a proposta do jogador.'),
    ContextKind.NPC_TURN: ContextContract(WORLD, 'Mestre completo para o NPC ativo; proposta do jogador vazia.'),
    ContextKind.NARRATION_INITIAL: ContextContract(NARRATION, 'Descrição inicial limitada à percepção; world só para coerência.',
        ('world.social', 'world.knowledge', 'world.adjudication', 'execution.reactions[].disposition', 'execution.reactions[].private_memory_ids', 'previous_execution.execution.reactions[].disposition', 'execution.reactions[].adjudication', 'previous_execution.execution.reactions[].adjudication', 'previous_execution.execution.reactions[].private_memory_ids')),
    ContextKind.NARRATION_RESULT: ContextContract(NARRATION, 'Narra efeitos validados e responde off; não executa intenções.',
        ('world.social', 'world.knowledge', 'world.adjudication', 'execution.reactions[].disposition', 'execution.reactions[].private_memory_ids', 'previous_execution.execution.reactions[].disposition', 'execution.reactions[].adjudication', 'previous_execution.execution.reactions[].adjudication', 'previous_execution.execution.reactions[].private_memory_ids')),
    ContextKind.NARRATION_OFF: ContextContract(NARRATION, 'Explica regras/memória sem ação nova nem fala on.',
        ('world.social', 'world.knowledge', 'world.adjudication', 'execution.reactions[].disposition', 'execution.reactions[].private_memory_ids', 'previous_execution.execution.reactions[].disposition', 'execution.reactions[].adjudication', 'previous_execution.execution.reactions[].adjudication', 'previous_execution.execution.reactions[].private_memory_ids')),
}

# Tipos críticos internos. Demais extensões internas também entram na revisão
# estrutural offline, sem transformar eventos e cenários em um esquema fechado.
INTERNAL = {
    'knowledge[]': 'object', 'knowledge[].owner_id': 'string', 'knowledge[].id': 'string',
    'knowledge[].claim': 'object', 'knowledge[].claim.subject_id': 'string',
    'knowledge[].claim.predicate': 'string', 'knowledge[].claim.value': 'string',
    'knowledge[].source': 'object', 'knowledge[].source.kind': 'string',
    'knowledge[].source.event_id': 'string', 'knowledge[].when': 'string',
    'knowledge[].context': 'string', 'knowledge[].shareable': 'boolean', 'knowledge[].acquired_at': 'integer',
    'sensing.hidden': 'boolean', 'sensing.can_hide': 'boolean',
    'world.perception': 'object', 'world.perception.hidden': 'boolean',
    'world.perception.stealth_total': 'integer|null', 'world.perception.observers': 'array',
    'world.perception.observers[]': 'object', 'world.perception.observers[].id': 'string',
    'world.perception.observers[].sleeping': 'boolean', 'world.perception.observers[].senses': 'object',
    'character.column': 'integer', 'character.row': 'integer',
    'character.current_area': 'string|null', 'character.speed_meters': 'number',
    'character.remaining_meters': 'number|null',
    'map.columns': 'integer', 'map.rows': 'integer', 'map.distance_unit': 'string', 'map.cell_size_meters': 'number',
    'map.scene': 'object', 'visible_creatures[]': 'object',
    'visible_creatures[].id': 'string', 'visible_creatures[].column': 'integer', 'visible_creatures[].row': 'integer',
    'recent_messages[]': 'object', 'recent_messages[].role': 'string', 'recent_messages[].on': 'string',
    'world.map': 'object', 'world.npcs': 'array', 'world.conditions': 'array',
    'world.npcs[]': 'object', 'visible_objects[]': 'object',
    'player.on': 'string', 'player.off': 'string',
    'execution.status': 'string', 'execution.events': 'array', 'execution.reactions': 'array',
    'execution.progress': 'boolean', 'execution.stop_reason': 'string|null', 'execution.failures': 'array',
    'execution.player_movement': 'object', 'execution.player_movement.occurred': 'boolean',
    'execution.player_movement.traveled_meters': 'number',
    'perception.current_place': 'string', 'perception.current_description': 'string',
    'perception.visible_places': 'array', 'perception.visible_passages': 'array',
    'perception.visible_creatures': 'array', 'perception.visible_enemies': 'array',
    'perception.visible_objects': 'array', 'perception.visible_scene_objects': 'array',
    'perception.visible_passages[]': 'object', 'perception.visible_scene_objects[]': 'object',
    'perception.visible_passages[].visible': 'boolean', 'perception.visible_scene_objects[].visible': 'boolean',
    'perception.visible_objects[]': 'object',
    'history[]': 'object', 'history[].role': 'string', 'history[].on': 'string', 'history[].off': 'string',
    'verified_rules[]': 'string',
}
OPTIONAL_INTERNAL = {'character.current_area', 'map.scene'}
_MISSING = object()


def _values(value, path, prefix=''):
    part, *rest = path.split('.')
    name = part.removesuffix('[]')
    if not isinstance(value, dict):
        return
    location = f'{prefix}.{name}' if prefix else name
    if name not in value:
        if not rest:
            yield location, _MISSING
        return
    items = enumerate(value[name]) if part.endswith('[]') and isinstance(value[name], list) else [(None, value[name])]
    for index, item in items:
        at = f'{location}[{index}]' if index is not None else location
        if rest:
            yield from _values(item, '.'.join(rest), at)
        else:
            yield at, item


def _matches(value, kinds):
    name = {dict: 'object', list: 'array', str: 'string', bool: 'boolean', int: 'integer',
            float: 'number', type(None): 'null'}.get(type(value), 'object' if isinstance(value, dict) else '')
    return (name in kinds.split('|') or (name == 'integer' and 'number' in kinds.split('|'))) and (
        name != 'number' or isfinite(value))


def validate_context(kind: ContextKind, context: dict) -> None:
    """Valida sem filtrar/adicionar campos nem consultar a referência aprovada."""
    kind = ContextKind(kind)
    contract = CONTRACTS[kind]
    if not isinstance(context, dict):
        raise ContextError(f'{kind}: o contexto deve ser um objeto.')
    extra = set(context) - set(contract.fields)
    if extra:
        raise ContextError(f'{kind}: campos não declarados: {sorted(extra, key=str)}.')
    for path, spec in contract.fields.items():
        value = context.get(path, _MISSING)
        if value is _MISSING and spec.optional:
            continue
        if value is _MISSING or not _matches(value, spec.types):
            raise ContextError(f'{kind}.{path}: esperado {spec.types}' + (' (campo ausente).' if value is _MISSING else '.'))
    for path, kinds in INTERNAL.items():
        if path.split('.')[0].removesuffix('[]') not in context:
            continue
        for location, value in _values(context, path):
            if value is _MISSING and path in OPTIONAL_INTERNAL:
                continue
            if value is _MISSING or not _matches(value, kinds):
                raise ContextError(f'{kind}.{location}: esperado {kinds}.')
    for path in contract.forbidden:
        if any(value is not _MISSING for _, value in _values(context, path)):
            raise ContextError(f'{kind}.{path}: informação proibida nesta projeção.')
    if context['mode'] not in {'narrated', 'turn_based'}:
        raise ContextError(f'{kind}.mode: modo desconhecido.')
    if kind in {ContextKind.WORLD_ACTION, ContextKind.NPC_TURN}:
        expected = 'player_action' if kind == ContextKind.WORLD_ACTION else 'npc_turn'
        if context['phase'] != expected or (kind == ContextKind.NPC_TURN and (context['player_plan'] or context['player_request_parts'])):
            raise ContextError(f'{kind}: fase ou proposta do jogador incompatível.')
    if kind.value.startswith('narration_'):
        if context['phase'] != ('initial' if kind == ContextKind.NARRATION_INITIAL else 'reply'):
            raise ContextError(f'{kind}.phase: fase de narração incompatível.')
        perception = context['perception']
        for key in ('visible_passages', 'visible_scene_objects'):
            if any(not o.get('visible', False) for o in perception[key]):
                raise ContextError(f'{kind}.perception.{key}: inclui elemento oculto.')
        if any(not (o.get('visible', True) or o.get('carried')) for o in perception['visible_objects']):
            raise ContextError(f'{kind}.perception.visible_objects: inclui item não percebido nem carregado.')
    if kind == ContextKind.NARRATION_OFF and (
            context['player']['on'] or not context['player']['off'] or context['allow_on']
            or context['execution']['events'] or context['execution']['reactions']):
        raise ContextError(f'{kind}: pergunta off não autoriza ação nova nem fala on.')
    try:
        json.dumps(context, allow_nan=False)
    except (ValueError, TypeError) as error:
        raise ContextError(f'{kind}: o contexto deve conter somente dados JSON finitos.') from error


class AIContext(dict):
    """Dict JSON compatível, com tipo de fase fora do payload enviado ao modelo."""
    def __init__(self, kind: ContextKind, data: dict):
        validate_context(kind, data)
        super().__init__(data)
        self.kind = ContextKind(kind)

    def require(self, *kinds: ContextKind) -> None:
        if self.kind not in kinds:
            raise ContextError(f'Contexto {self.kind} não atende às fases {kinds}.')
        validate_context(self.kind, self)

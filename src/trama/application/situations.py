"""Situações reproduzíveis do simulador, preparadas por operações públicas reais."""

from collections import deque
from copy import deepcopy
from dataclasses import asdict
from importlib.resources import files
import json
import logging
import re

from trama.application.dialogue import DialogueMessage
from trama.application.intents import (ActionPlan, DoorIntent, MovementIntent,
                                       MovementSegment, NarrativeIntent, RuleIntent, ScenarioIntent)
from trama.knowledge import Claim
from trama.observability import current_context, log_context, new_id

logger = logging.getLogger(__name__)


class SituationError(ValueError):
    """Uma declaração ou preparação não corresponde à situação esperada."""


class ScriptedRoller:
    """Sequência estrita de [faces, valor]; sem sorteio substituto ao esgotar."""

    def __init__(self, rolls, optional_tail=()):
        if (not isinstance(rolls, list) or not isinstance(optional_tail, (list, tuple)) or
                any(not isinstance(r, list) or len(r) != 2 or
               any(type(n) is not int for n in r) or r[0] < 2 or not 1 <= r[1] <= r[0]
               for r in [*rolls, *optional_tail])):
            raise SituationError('Cada rolagem deve declarar [faces, valor] válidos.')
        self._rolls = deepcopy(rolls)
        self._optional = deepcopy(optional_tail)
        self.reset()

    def reset(self):
        self.pending = deque(tuple(r) for r in self._rolls)
        self.optional_tail = deque(tuple(r) for r in self._optional)
        self.used = []
        self.optional_used = []

    def roll(self, sides):
        queue = self.pending if self.pending else self.optional_tail
        if not queue:
            raise SituationError(f'Rolagem não prevista: d{sides}.')
        expected_sides, value = queue[0]
        if sides != expected_sides:
            raise SituationError(f'Esperava d{expected_sides}, recebeu d{sides}.')
        queue.popleft()
        if queue is self.optional_tail:
            self.optional_used.append([sides, value])
        self.used.append([sides, value])
        return value


def situation_state(session):
    """Observação mecânica da dungeon, sem calcular resultados esperados."""
    area = session.scene.area_at(session.state.position) if session.scene else None
    dungeon = getattr(session, 'dungeon', None)
    return {
        'social': session.social.context(tuple(session.social.profiles)),
        'knowledge': session.knowledge.store.export(),
        'sensing': session.perception.context(),
        'parley': session.parley.context() if session.parley else None,
        'position': [session.state.position.x + 1, session.state.position.y + 1],
        'area': area.id if area else None, 'mode': session.mode.value,
        'spent_meters': float(session.state.spent_meters),
        'remaining_meters': float(session.state.remaining_meters), 'dash_used': session.state.dash_used,
        'combat': session.combat_context(),
        'creatures': {c.id: [c.position.x + 1, c.position.y + 1] for c in session.creatures},
        'resources': {id: asdict(state) for id, state in session.encounter.states.items()},
        'budgets': {id: asdict(budget) for id, budget in session.encounter.budgets.items()},
        'inventory': sorted(getattr(dungeon, 'inventory', set())), 'discovered': sorted(getattr(dungeon, 'discovered', set())),
        'clothing': getattr(dungeon, 'clothing', 'none'), 'weapons': list(session.encounter.player_sheet.weapons),
        'passages': {p.id: {'is_open': p.is_open, 'locked': p.locked} for p in session.scene.passages} if session.scene else {},
        'last_attack': deepcopy(session.encounter.last_attacks.get('player')),
        'prisoner_awake': getattr(dungeon, 'prisoner_awake', False),
        'prisoner_free': getattr(dungeon, 'prisoner_free', False),
        'escaped': getattr(dungeon, 'escaped', False),
        'disguise': getattr(dungeon, 'disguise', 'untested'), 'guard_alert': getattr(dungeon, 'guard_alert', False),
        'sword_concealed': getattr(dungeon, 'sword_concealed', False),
        'pending_opportunity': session.pending_opportunity is not None,
    }


def declared_intent(data):
    values = dict(data)
    kind = values.pop('intent')
    if kind == 'movement':
        values['segments'] = tuple(MovementSegment(**s) for s in values.get('segments', []))
        values.setdefault('dash', False)
        values.setdefault('clarification', '')
        return MovementIntent(**values)
    if kind == 'narrative' and 'claims' in values:
        values['claims'] = tuple(Claim(**c) for c in values['claims'])
    constructors = {'door': DoorIntent, 'scenario': ScenarioIntent, 'rule': RuleIntent, 'narrative': NarrativeIntent}
    if kind not in constructors:
        raise SituationError(f'Tipo de intenção desconhecido: {kind}.')
    return constructors[kind](**values)


class Situation:
    """Dados de preparação; não contém prompts, adaptadores ou critérios de sucesso live."""

    fields = {'id', 'scenario', 'setup', 'rolls', 'optional_world_rolls', 'preparation_rolls',
              'preconditions', 'passage_variations', 'history', 'start_variation', 'sense_variations', 'lighting_variations',
              'knowledge_variations', 'object_variations', 'social_variations'}

    def __init__(self, data, preparations):
        if not isinstance(data, dict) or not isinstance(preparations, dict):
            raise SituationError('Situação e preparações devem ser objetos.')
        if set(data) - self.fields:
            raise SituationError('Campo de situação desconhecido.')
        if not {'id', 'scenario', 'setup', 'rolls', 'preparation_rolls', 'preconditions'} <= data.keys():
            raise SituationError('Situação incompleta.')
        self.data = deepcopy(data)
        self.preparations = deepcopy(preparations)
        if (not isinstance(data['id'], str) or not data['id'] or
                (not isinstance(data['scenario'], str) or not re.fullmatch(r'[a-z0-9_-]+\.json', data['scenario'])) or not isinstance(data['setup'], list) or
                any(not isinstance(name, str) or name not in preparations for name in data['setup']) or
                type(data['preparation_rolls']) is not int or data['preparation_rolls'] < 0 or
                not isinstance(data['preconditions'], dict) or
                any(not isinstance(k, str) or not k for k in data['preconditions'])):
            raise SituationError('Identificação, cenário ou preparação de situação inválidos.')
        if not files('trama').joinpath('scenarios', data['scenario']).is_file():
            raise SituationError('O cenário da situação não existe no pacote.')
        self.new_roller()  # Valida antes de abrir serviços ou executar operações.
        history = data.get('history')
        if history is not None and (not isinstance(history, dict) or set(history) != {'source', 'messages'}
                                    or not isinstance(history['source'], dict) or not history['source'] or
                                    not isinstance(history['messages'], list)):
            raise SituationError('Histórico registrado exige origem e mensagens.')
        self.initial_history = tuple(DialogueMessage.from_data(m) for m in history['messages']) if history else ()
        for name in data['setup']:
            if not isinstance(preparations[name], list) or not preparations[name]:
                raise SituationError(f'Preparação vazia ou inválida: {name}.')
            for declared in preparations[name]:
                if (not isinstance(declared, dict) or
                        set(declared) - {'steps', 'expected_status', 'expected_world_operations'} or
                        declared.get('expected_status') not in {'completed', 'blocked', 'already_satisfied'} or
                        not isinstance(declared.get('steps'), list) or
                        not isinstance(declared.get('expected_world_operations', []), list) or
                        any(not isinstance(op, str) for op in declared.get('expected_world_operations', [])) or
                        (declared['expected_status'] == 'blocked' and not declared.get('expected_world_operations'))):
                    raise SituationError(f'Preparação inválida: {name}.')
                ActionPlan(tuple(declared_intent(s) for s in declared['steps']))

    def new_roller(self):
        return ScriptedRoller(self.data['rolls'], self.data.get('optional_world_rolls', []))

    def scenario_data(self):
        data = json.loads(files('trama').joinpath('scenarios', self.data['scenario']).read_text(encoding='utf-8'))
        if 'start_variation' in self.data:
            data['start'] = deepcopy(self.data['start_variation'])
        for id, variation in self.data.get('sense_variations', {}).items():
            actor = next((a for a in [*data.get('creatures', []), *data.get('observers', [])] if a['id'] == id), None)
            if actor is None or not isinstance(variation, dict):
                raise SituationError(f'Variação de sentidos inválida: {id}.')
            actor['senses'] = {**actor.get('senses', {}), **variation}
        for id, memories in self.data.get('knowledge_variations', {}).items():
            actor = next((a for a in [*data.get('creatures', []), *data.get('observers', [])] if a['id'] == id), None)
            if actor is None or not isinstance(memories, list):
                raise SituationError(f'Variação de conhecimento inválida: {id}.')
            actor['knowledge'] = deepcopy(memories)
        for id, profile in self.data.get('social_variations', {}).items():
            actor = next((a for a in [*data.get('creatures', []), *data.get('observers', [])] if a['id'] == id), None)
            if actor is None or not isinstance(profile, dict):
                raise SituationError(f'Variação social inválida: {id}.')
            actor['social'] = deepcopy(profile)
        for id, variation in self.data.get('object_variations', {}).items():
            obj = next((o for o in data.get('objects', []) if o['id'] == id), None)
            if obj is None or not isinstance(variation, dict) or set(variation) != {'position'}:
                raise SituationError(f'Variação de objeto inválida: {id}.')
            obj['position'] = deepcopy(variation['position'])
        for kind, positions in self.data.get('lighting_variations', {}).items():
            if kind not in {'dark', 'dim'} or not isinstance(positions, list):
                raise SituationError('Variação de iluminação inválida.')
            data[kind] = deepcopy(positions)
        for id, variation in self.data.get('passage_variations', {}).items():
            passage = next((p for p in data['passages'] if p['id'] == id), None)
            if (passage is None or not isinstance(variation, dict) or
                    variation.keys() - {'is_open', 'locked', 'description'}
                    or any(type(v) is not bool for k, v in variation.items() if k != 'description')
                    or ('description' in variation and not isinstance(variation['description'], str))):
                raise SituationError(f'Variação de passagem inválida: {id}.')
            passage.update(variation)
        return data

    def prepare(self, conversation, roller):
        """Executa operações reais e recusa deriva de estado, dados ou etapas pendentes."""
        for name in self.data['setup']:
            for index, declared in enumerate(self.preparations[name]):
                report = conversation.execute(ActionPlan(tuple(declared_intent(s) for s in declared['steps'])))
                operations = {e['operation'] for e in report.world_events}
                if (report.status != declared['expected_status'] or report.failures or report.unperformed_steps or
                        not set(declared.get('expected_world_operations', [])) <= operations or
                        conversation.session.pending_opportunity or conversation.pending_npc_turn):
                    raise SituationError(f'Preparação inválida de {self.data["id"]}, {name}[{index}]: {report.stop_reason}')
        if len(roller.used) != self.data['preparation_rolls']:
            raise SituationError('A preparação consumiu uma sequência de dados diferente.')
        actual = situation_state(conversation.session)
        for path, expected in self.data['preconditions'].items():
            value = actual
            for key in path.split('.'):
                if not isinstance(value, dict) or key not in value:
                    raise SituationError(f'pré-condição desconhecida: {path}.')
                value = value[key]
            if type(value) is not type(expected) or value != expected:
                # Números JSON inteiros/decimais representam a mesma medida.
                if not (type(value) in {int, float} and type(expected) in {int, float} and value == expected):
                    raise SituationError(f'pré-condição {path}: esperado {expected!r}, obtido {value!r}.')
        logger.info('situation.prepared', extra={'data': {'situation_id': self.data['id'],
                    'preparation_dice_used': len(roller.used), 'state': actual}})

    def initialize(self, conversation, roller):
        """Usado na abertura e no reinício, com a mesma sequência e validação."""
        with log_context(interaction_id=current_context().get('interaction_id') or new_id()):
            roller.reset()
            logger.info('situation.preparation_started', extra={'data': {
                'situation_id': self.data['id'], 'state': situation_state(conversation.session)}})
            try:
                self.prepare(conversation, roller)
            except Exception:
                logger.exception('situation.preparation_failed', extra={'data': {'situation_id': self.data['id']}})
                raise

    def restore_history(self, conversation):
        conversation.extend_history(self.initial_history)


def load_situation(id):
    catalog = json.loads(files('trama').joinpath('scenarios', 'situations.json').read_text(encoding='utf-8'))
    if type(catalog.get('schema_version')) is not int or catalog['schema_version'] != 1:
        raise SituationError('Versão de catálogo de situações não suportada.')
    matches = [s for s in catalog['situations'] if s['id'] == id]
    if len(matches) != 1:
        raise SituationError(f'Situação desconhecida ou duplicada: {id}.')
    return Situation(matches[0], catalog['preparations'])

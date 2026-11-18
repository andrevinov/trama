"""Pedidos contextuais na decisão do Mundo existente; sem chamadas ao provedor.

Os pedidos de acústica descrevem barreiras/categoria de emissão e são reutilizados
enquanto esses fatos persistem. Distância, sentido e CD fixa continuam no motor.
"""

from copy import deepcopy
from dataclasses import asdict
from hashlib import sha256
import json
import logging

from trama.actions import ActionError
from trama.characters import ability_check
from trama.difficulty import Adjudication
from trama.perception import Noise, Observer, Senses

logger = logging.getLogger(__name__)


class AdjudicationSystem:
    def __init__(self, session):
        self.session = session
        self.issued = {}
        self.cached = {}
        self.strict = False
        self.hearing_records = set()
        self.approach = ''

    def _request(self, id, kind, skill, description, facts):
        return dict(id=id, kind=kind, skill=skill, description=description, facts=facts)

    def _fingerprint(self, request):
        return json.dumps(request, sort_keys=True, ensure_ascii=False)

    def _current(self, request):
        entry = self.cached.get(request['id'])
        return entry['decision'] if entry and entry['fingerprint'] == self._fingerprint(request) else None

    def acoustic_request(self, passage_ids, volume, *, speech=False):
        passages = {p.id: p for p in self.session.scene.passages} if self.session.scene else {}
        facts = {f'door:{id}': dict(name=passages[id].name, is_open=passages[id].is_open,
                                  description=passages[id].description,
                                  connects=list(passages[id].connects)) for id in sorted(passage_ids)}
        facts['sound:volume'] = volume
        facts['sound:purpose'] = 'understand_speech' if speech else 'notice_noise'
        return self._request('hearing:' + ('speech:' if speech else 'noise:') + volume + ':' + ','.join(sorted(passage_ids)), 'hearing', 'perception',
            ('Compreender as palavras de uma fala através destas portas. ' if speech else
             'Perceber um ruído através destas portas, sem identificar sua fonte ou compreender palavras. ') +
            'Distância e capacidade do ouvinte são verificadas separadamente pelo código.', facts)

    def prepare(self, steps, *, approach=''):
        self.approach = approach
        requests = {r['id']: r for r in self.session.contextual_check_requests(steps)}
        # Gestos não emitem som; sua possível resposta falada pode precisar de acústica.
        noisy = not steps or any((not s.get('clarification') and s.get('operation') in {'move', 'open', 'close', 'speak', 'challenge', 'gesture', 'sneak', 'wait', 'wake'})
            or s.get('operation') == 'inspect_passage' and s.get('method') == 'mechanism'
            or any(p.get('proposed_path') for p in s.get('preparation', [])) for s in steps)
        s = self.session
        from trama.spatial import Position
        gesture_origin = s.state.position
        for step in steps:
            path = step.get('proposed_path') or next((p['proposed_path'] for p in step.get('preparation', [])
                                                    if p.get('proposed_path')), [])
            if path:
                gesture_origin = Position(path[-1][0] - 1, path[-1][1] - 1)
            if step.get('operation') == 'gesture' and step.get('subtle'):
                for observer in s.perception.observers():
                    if s.perception.sees(observer, gesture_origin):
                        request = self.gesture_request(observer, step['text'], origin=gesture_origin)
                        requests[request['id']] = request
        if noisy and s.scene:
            player = Observer(s.encounter.player_id, 'Jogador', s.state.position,
                              Senses(perception_bonus=s.encounter.player_sheet.skill_bonus('perception')))
            listeners = (*s.perception.observers(), player)
            sources = [(o.id, o.position) for o in listeners]
            # Prévia determinística de caminhos; nenhuma percepção/ação é aplicada.
            for step in steps:
                for path in [step.get('proposed_path', []), *(p.get('proposed_path', []) for p in step.get('preparation', []))]:
                    from trama.spatial import Position
                    sources.extend((player.id, Position(x - 1, y - 1)) for x, y in path)
            for source_id, position in dict.fromkeys(sources):
                for listener in listeners:
                    if listener.id == source_id or not listener.senses.can_hear:
                        continue
                    doors = s.perception.sound_barriers(position, listener.position)
                    if not doors:
                        continue
                    for volume in ('quiet', 'normal', 'loud'):
                        noise = Noise(source_id, position, volume)
                        if not s.perception.hears(listener, noise, adjudicate=False):
                            continue
                        for speech in (False, True):
                            request = self.acoustic_request(doors, volume, speech=speech)
                            requests[request['id']] = request
        self.issued = {id: r for id, r in requests.items() if self._current(r) is None}
        if len(self.issued) > 32:
            raise ActionError('Há mais de 32 avaliações contextuais; reduza o plano.')
        return dict(requests=deepcopy(list(self.issued.values())), cached=[dict(request_id=id,
            **{k: v for k, v in self._current(r).context().items() if k != 'request_id'})
            for id, r in requests.items() if self._current(r) is not None])

    def gesture_request(self, observer, text, *, origin=None):
        s = self.session
        origin = s.state.position if origin is None else origin
        from trama.distances import CELL_METERS
        distance = float(CELL_METERS * max(abs(observer.position.x - origin.x),
                                         abs(observer.position.y - origin.y)))
        id = f'gesture:{observer.id}:{origin.x},{origin.y}:' + sha256(text.encode()).hexdigest()[:12]
        return self._request(id, 'visual_signal', 'perception',
            'Notar este gesto sutil, não decifrar seu significado nem aceitar o pedido. Usa Percepção passiva; sem busca ativa.',
            {'gesture:appearance': text, 'gesture:distance_meters': distance,
             'gesture:observer': observer.senses.context(s.perception.bonus(observer)),
             'gesture:dim': bool(s.scene and origin in s.scene.dim and
                                 distance > float(observer.senses.darkvision_meters))})

    def sees_gesture(self, observer, intent):
        request = self.gesture_request(observer, intent.text)
        decision = self.decision(request, 15)
        s = self.session
        dim = request['facts']['gesture:dim']
        advantage = observer.senses.advantage or decision.advantage
        disadvantage = observer.senses.disadvantage or decision.disadvantage or dim
        total = 10 + s.perception.bonus(observer) + (5 if advantage and not disadvantage
                    else -5 if disadvantage and not advantage else 0)
        seen = decision.outcome == 'automatic' or decision.outcome == 'check' and total >= decision.dc
        logger.info('adjudication.gesture_resolved', extra={'data': dict(actor_id=observer.id,
            request_id=request['id'], outcome=decision.outcome, dc=decision.dc,
            passive_total=total if decision.outcome == 'check' else None, seen=seen)})
        return seen

    def begin(self, decisions, *, strict=False):
        proposed = {a.request_id: a for a in decisions}
        if set(proposed) - self.issued.keys():
            raise ActionError('O Mundo avaliou uma dificuldade não solicitada ou de regra fixa.')
        if strict and self.issued.keys() - proposed.keys():
            raise ActionError('O Mundo não avaliou todas as dificuldades contextuais solicitadas.')
        # Validar tudo antes de instalar qualquer decisão.
        for id, decision in proposed.items():
            if not set(decision.fact_ids) <= self.issued[id]['facts'].keys():
                raise ActionError('A avaliação cita um fato não fornecido pelo estado atual.')
        for id, decision in proposed.items():
            self.cached[id] = dict(decision=decision, fingerprint=self._fingerprint(self.issued[id]))
            logger.info('adjudication.decided', extra={'data': dict(request=self.issued[id], decision=decision.context())})
        self.strict = strict
        self.hearing_records.clear()

    def decision(self, request, fallback_dc):
        decision = self._current(request)
        if decision is not None:
            return decision
        if self.strict:
            raise ActionError('Falta avaliação para o contexto atual: ' + request['id'])
        # Preparações sem IA e consumidores determinísticos mantêm o recorte
        # declarado do cenário. O caminho oficial com Mundo exige adjudicação.
        from trama.difficulty import DIFFICULTY_CLASSES
        level = next((k for k, v in DIFFICULTY_CLASSES.items() if v >= fallback_dc), 'nearly_impossible')
        return Adjudication(request['id'], 'check', level, False, False,
                            (next(iter(request['facts'])),), 'Recorte determinístico sem adjudicador de IA.')

    def check(self, id, actor, skill, fallback_dc):
        request = self.session.contextual_check(id)
        if request is None or request['skill'] != skill:
            raise ActionError('Teste contextual desconhecido ou perícia incompatível.')
        decision = self.decision(request, fallback_dc)
        default = self._current(request) is None
        dc = fallback_dc if default else decision.dc
        passed = decision.outcome == 'automatic'
        result = dict(operation='check', actor_id=actor, skill=skill, changed=False,
                      perceptible=actor == self.session.encounter.player_id,
                      adjudication_id=id, adjudication=decision.context(), automatic=decision.outcome != 'check',
                      dc=dc, dice=[], total=None, passed=passed)
        if default:
            result['adjudication'] = {'source': 'scenario_default', 'dc': fallback_dc,
                                      'reason': 'Preparação/execução determinística sem avaliação de IA.'}
        if decision.outcome == 'check':
            sheet = self.session.encounter.sheets[actor]
            state, roll, total = ability_check(sheet, self.session.encounter.states[actor], skill, dc,
                self.session.encounter.roller, advantage=decision.advantage, disadvantage=decision.disadvantage)
            self.session.encounter.states[actor] = state
            passed = total >= dc
            result.update(dice=list(roll.dice), total=total, passed=passed,
                          advantage=roll.advantage, disadvantage=roll.disadvantage)
        self.session._events.append(result)
        logger.info('adjudication.check_resolved', extra={'data': result})
        return passed, result['total']

    def hearing(self, listener, noise, barriers):
        if not barriers:
            return None
        request = self.acoustic_request(barriers, noise.volume, speech=noise.speech)
        decision = self._current(request)
        if decision is None:
            if self.strict:
                raise ActionError('Falta avaliação acústica: ' + request['id'])
            return None
        return decision

    def record_hearing(self, listener, noise, decision, total, dc, heard):
        if not self.strict:
            return
        key = (listener.id, noise.actor_id, listener.position, noise.position, noise.volume, decision.request_id)
        if key in self.hearing_records:
            return
        self.hearing_records.add(key)
        event = dict(operation='hearing_check', actor_id=listener.id, target_id=noise.actor_id,
            perceptible=listener.id == self.session.encounter.player_id, changed=False,
            adjudication_id=decision.request_id, automatic=decision.outcome != 'check' and dc is None,
            dc=dc, total=total, passed=heard, disadvantage=decision.disadvantage, advantage=decision.advantage,
            purpose='understand_speech' if noise.speech else 'notice_noise', volume=noise.volume)
        self.session._events.append(event)
        logger.info('adjudication.hearing_resolved', extra={'data': event})

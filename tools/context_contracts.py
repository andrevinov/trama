"""Revisão offline dos contratos atuais; a referência nunca alimenta a aplicação.

Executar da raiz: poetry run python tools/context_contracts.py --check
"""

import argparse
from collections import defaultdict, deque
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path

from trama.application.context_contracts import CONTRACTS, INTERNAL, OPTIONAL_INTERNAL, ContextKind
from trama.application.conversation import Conversation
from trama.application.dialogue import Speech
from trama.application.intents import ActionPlan, DoorIntent, InspectionIntent, GestureIntent, MovementIntent, MovementSegment, RequestPart, RuleIntent, ScenarioIntent, NarrativeIntent
from trama.application.scenarios import build_session, load_session
from trama.application.parley import InfluenceRequest
from trama.social import DispositionAssessment, MemoryEffect, PersonaEffect
from trama.application.world import WorldAction, WorldPlan, WorldReaction
from trama.infrastructure import openai_intent_interpreter, openai_narrator, openai_world_director
from trama.spatial import Position
from trama.knowledge import Claim
from trama.difficulty import Adjudication
from trama.agency import IntentDecision
from trama.conversation_state import ConversationUpdate, ConversationPoint, ProposalUpdate, ProposalTerm
from trama.opinions import OptionAssessment, TermAssessment
from trama.relationships import RelationshipEffect, RelationshipEpisode
from trama.bonds import BondUpdate
from trama.application.situations import load_situation
from trama.application.authorization import validate_player_plan

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / 'docs/contracts/ai-contexts.json'
VOLATILE_FIELDS = frozenset({'execution_id', 'session_id', 'interaction_id', 'operation_id', 'ai_call_id',
                             'opportunity_id', 'timestamp', 'event_id'})


class ReviewRoller:
    """Arranjo reproduzível da auditoria; a resolução continua no motor real."""
    def __init__(self, *values):
        self.values = deque(values)

    def roll(self, sides):
        if not self.values:
            raise ValueError(f'A preparação do contrato exige uma nova rolagem de d{sides}; revise o arranjo.')
        value = self.values.popleft()
        if not 1 <= value <= sides:
            raise ValueError('Rolagem incompatível com a preparação do contrato.')
        return value


def action(conversation, prompt, intent):
    """Entrada declarada de preparação, sem interpretação ou chamadas externas."""
    speech = conversation.prepare(prompt)
    operation = getattr(intent, 'operation', 'move')
    plan = ActionPlan((intent,), (RequestPart(speech.on, 'execute', (operation,), (0,)),))
    return speech, plan


def sample_contexts():
    """Observa projeções reais por fase; não simula respostas de IA."""
    samples = []
    gestures = Conversation(build_session(dict(width=9, height=5, start=[2, 2],
        observers=[dict(id='friend', name='Companheiro', position=[3, 2])]), roller=ReviewRoller()))
    speech, plan = action(gestures, 'Faço um sinal ao companheiro.', GestureIntent('friend',
        'Aceno com a mão.', 'Quero que fale.'))
    samples.extend((gestures.interpretation_context(), gestures.world_context(plan)))
    checkpoint = gestures.session.agency.checkpoint()
    report = gestures.execute(plan)
    gestures.session.agency.pending(report, checkpoint)
    samples.extend((gestures.agency_context('friend'), gestures.narration_context(speech, report)))
    _, subtle = action(gestures, 'Dou uma piscadela.', GestureIntent('friend', 'Pisco um olho.', 'Peço apoio.', True))
    samples.append(gestures.world_context(subtle))
    # Aparência desconhecida -> conferência ao alcance, sem alterar a passagem.
    inspection = Conversation(load_session(ROOT / 'src/trama/scenarios/perception_rooms.json', roller=ReviewRoller()))
    for method in ('visual', 'mechanism'):
        speech, plan = action(inspection, 'Confiro a porta.', InspectionIntent('door', method,
            'quiet' if method == 'mechanism' else 'normal', method == 'mechanism'))
        samples.extend((inspection.interpretation_context(), inspection.world_context(plan)))
        report = inspection.execute(plan)
        samples.extend((inspection.narration_context(speech, report), inspection.interpretation_context()))
    # Acompanhamento real de uma abordagem, com cochicho visto e não ouvido.
    agency = Conversation(build_session(dict(width=25,height=6,start=[2,2],creatures=[
        dict(id='sentinel',name='Sentinela',position=[18,2])]), roller=ReviewRoller()))
    agency.session.offer_parley('sentinel','Diga o que deseja.')
    agency.execute(ActionPlan((NarrativeIntent('Conversa reservada.','speak',volume='quiet'),)))
    samples.append(agency.agency_context('sentinel'))
    agency.execute_agency('sentinel',WorldPlan((WorldReaction(0,None,(
        WorldAction('sentinel','say','Preciso de sua resposta.'),)),),
        intent=IntentDecision('sentinel','Obter uma resposta.','Cobrar a resposta.','Resposta à pergunta.')))
    samples.extend((agency.agency_context('sentinel'),agency.narration_context()))
    # Memória inicial -> fala referenciada -> relato do jogador, sem dados de IA.
    c = Conversation(load_session(ROOT / 'src/trama/scenarios/knowledge_rooms.json'))
    speech, plan = action(c, 'Arquivista, onde viu a chave?', NarrativeIntent('Onde viu a chave?', 'speak'))
    samples.extend((c.interpretation_context(), c.world_context(plan)))
    report = c.execute(plan, WorldPlan((WorldReaction(0, None, (WorldAction('archivist', 'say',
        'Na última inspeção, vi a chave na mesa.', memory_ids=('archivist:key-on-desk',)),)),)))
    samples.extend((c.narration_context(speech, report), c.interpretation_context()))
    speech, plan = action(c, 'Disseram que a chave foi para a coluna 18, linha 3.',
        NarrativeIntent('Disseram que a chave foi para a coluna 18, linha 3.', 'speak',
                        claims=(Claim('archive_key', 'location', 'position:18,3'),)))
    report = c.execute(plan)
    samples.extend((c.world_context(plan), c.narration_context(speech, report),
                    c.narration_context(c.prepare('[O que o arquivista sabe?]'))))
    c = Conversation(load_session(ROOT / 'src/trama/scenarios/dungeon_escape.json', roller=ReviewRoller(20, 20)))
    samples.append(c.narration_context(initial=True))
    # Preparação mecânica até a grade aberta: os dados e as regras são os da aplicação.
    c.execute(ActionPlan((ScenarioIntent('sneak', 'gate_4'), DoorIntent('open', 'gate_4'))))
    speech, plan = action(c, 'Eu checo a cela, procurando por algo útil.', ScenarioIntent('investigate', 'cell_4'))
    world_context = c.world_context(plan)
    samples.extend((c.interpretation_context(), world_context))
    decisions = tuple(Adjudication(r['id'], 'check', 'moderate', False, False,
        (next(iter(r['facts'])),), 'Amostra offline da decisão contextual validada.')
        for r in world_context['world']['adjudication']['requests'])
    report = c.execute(plan, WorldPlan(adjudications=decisions), require_adjudications=True)
    samples.append(c.narration_context(speech, report))
    samples.append(c.interpretation_context())  # Itens conhecidos, lista não vazia.
    samples.append(c.narration_context(c.prepare('[O que descobri?]')))
    speech, plan = action(c, 'Olho ao redor.', NarrativeIntent('Olho ao redor.', 'look'))
    report = c.execute(plan)
    samples.append(c.narration_context(speech, report))  # Memória de testes de perícia permanece narrável.

    data = json.loads((ROOT / 'src/trama/scenarios/dungeon_escape.json').read_text())
    data['start'] = [8, 7]
    acoustic = Conversation(build_session(data, roller=ReviewRoller()))
    speech, plan = action(acoustic, 'Falo normalmente.', NarrativeIntent('Falo normalmente.', 'speak'))
    context = acoustic.world_context(plan)
    samples.append(context)
    decisions = tuple(Adjudication(r['id'], 'check', 'moderate', False, True,
        (next(iter(r['facts'])),), 'Porta fechada abafa o som nesta amostra offline.')
        for r in context['world']['adjudication']['requests'])
    report = acoustic.execute(plan, WorldPlan(adjudications=decisions), require_adjudications=True)
    samples.extend((acoustic.world_context(plan), acoustic.narration_context(speech, report)))

    data = json.loads((ROOT / 'src/trama/scenarios/dungeon_escape.json').read_text())
    data['start'] = [9, 3]
    npc = Conversation(build_session(data, roller=ReviewRoller(1, 2, 20)))
    npc.session.execute(RuleIntent('start_combat'))
    samples.append(npc.world_context())  # NPC ativo com as extensões da dungeon.

    data = json.loads((ROOT / 'tests/fixtures/scenarios/legacy_cell_and_guards.json').read_text())
    data['start'] = [14, 5]
    next(p for p in data['passages'] if p['id'] == 'guard_door')['is_open'] = True
    c = Conversation(build_session(data, roller=ReviewRoller(20, 19, 1, 1)))
    speech, plan = action(c, 'Ataco o Guarda 1.', RuleIntent('attack', 'guard_1'))
    samples.extend((c.interpretation_context(), c.world_context(plan)))
    report = c.execute(plan)  # Iniciativa, ataque e last_attack reais.
    samples.extend((c.narration_context(speech, report), c.interpretation_context(), c.world_context(plan)))
    speech, plan = action(c, 'Encerro meu turno.', RuleIntent('end_turn'))
    c.execute(plan)
    samples.append(c.world_context())
    report = c.execute_npc_turn(WorldPlan((WorldReaction(0, 0, (
        WorldAction('guard_1', 'move', 'O guarda tenta alcançar a casa bloqueada.', destination=Position(13, 4)),
        WorldAction('guard_1', 'attack', 'O guarda tenta atacar depois.', 'player'),
    )),)))
    samples.append(c.narration_context(report=report))
    samples.append(c.narration_context(c.prepare('[Por que o guarda não atacou?]')))

    # Limite normal de movimento: relatório real sem manter o turno pendente.
    c = Conversation(build_session(dict(width=26, height=5, start=[2, 2], creatures=[
        dict(id='watcher', name='Vigia', position=[21, 2])]), roller=ReviewRoller(20, 19, 1)))
    c.session.execute(RuleIntent('start_combat'))
    c.session.execute(RuleIntent('end_turn'))
    report = c.execute_npc_turn(WorldPlan((WorldReaction(0, 0, (
        WorldAction('watcher', 'move', 'O vigia avança até o limite do turno.', destination=Position(3, 2)),
    )),)))
    samples.append(c.narration_context(report=report))
    samples.append(c.narration_context(c.prepare('[O vigia ainda está agindo?]')))

    c = Conversation(build_session(dict(width=4, height=4, start=[1, 1], blocked=[[2, 1]])))
    samples.append(c.narration_context(initial=True))
    speech, plan = action(c, 'Ando para leste.', MovementIntent((MovementSegment('east', 2),), False, ''))
    samples.extend((c.interpretation_context(), c.world_context(plan)))
    report = c.execute(plan)
    samples.append(c.narration_context(speech, report))
    samples.append(c.narration_context(c.prepare('[Por que parei?]')))
    # Abordagem e Influence gerais, sem adjudicação da dungeon ou payload alternativo.
    for persuasion_roll in (20, 1):
        c = Conversation(build_session(dict(width=24, height=3, start=[1, 1], creatures=[
            dict(id='watcher', name='Vigia', position=[12, 1], hostile=True,
                social=dict(alignment='neutral', persona=dict(name='Vigia', role='Guarda',
                    background='Protege sua integridade e emprego.', interests=[
                        dict(id=id, description='Interesse afetado por origem nobre.', weight=2,
                             evidence_predicates=['parentage']) for id in ('safety', 'livelihood')])))]),
            roller=ReviewRoller(persuasion_roll, 1, 2, 20)))
        speech, plan = action(c, 'Olho o corredor.', NarrativeIntent('Olho o corredor.', 'look'))
        report = c.execute(plan, WorldPlan((WorldReaction(0, 0, (
            WorldAction('watcher', 'parley', 'Pare! Identifique-se.'),)),)))
        samples.extend((c.interpretation_context(), c.world_context(plan), c.narration_context(speech, report),
                        c.narration_context(c.prepare('[Posso conversar?]'))))
        claim = Claim('player', 'parentage', 'noble_heir')
        text = 'Sou herdeiro de um nobre; ouça minha explicação.'
        speech, plan = action(c, text, NarrativeIntent(text, 'speak', claims=(claim,)))
        report = c.execute(plan, WorldPlan((WorldReaction(0, None, (
            WorldAction('watcher', 'influence', 'O vigia hesita em aceitar a explicação.',
                        influence=InfluenceRequest(skill='persuasion', assessment=DispositionAssessment(
                            'listen', 'player', 'Ouvir sem permitir fuga.', 0, 0, 'Pedido neutro.',
                            tuple(PersonaEffect(id, 0, 'Pedido limitado.') for id in ('safety', 'livelihood')),
                            tuple(MemoryEffect(claim, id, 1, 'Alegação de origem nobre.') for id in ('safety', 'livelihood')),
                            'Fique onde está. Vou ouvir.', 'Não. Volte à cela.', ('Manter posição.',)))),)),)))
        samples.extend((c.narration_context(speech, report), c.interpretation_context(), c.world_context(plan)))
        if c.session.encounter.combat:
            samples.append(c.world_context())
    # Percepção geral: ocultação e busca reais em um mapa que não é a dungeon.
    for search_roll in (1, 20):
        c = Conversation(load_session(ROOT / 'src/trama/scenarios/perception_rooms.json', roller=ReviewRoller(20, search_roll)))
        speech, plan = action(c, 'Eu me escondo.', RuleIntent('hide'))
        report = c.execute(plan)
        samples.extend((c.interpretation_context(), c.world_context(plan), c.narration_context(speech, report)))
        speech, plan = action(c, 'Aguardo em silêncio.', NarrativeIntent('Aguardo em silêncio.', 'wait'))
        report = c.execute(plan, WorldPlan((WorldReaction(0, None, (
            WorldAction('watcher', 'search', 'O vigia busca o fugitivo oculto.', 'player'),)),)))
        samples.extend((c.narration_context(speech, report), c.world_context(plan), c.interpretation_context(),
                        c.narration_context(c.prepare('[O que foi percebido?]'))))
    # Acrescenta a nova cena sem substituir as amostras iniciais de cada fase.
    council = Conversation(load_session(ROOT / 'src/trama/scenarios/generals_council.json'))
    samples.append(council.narration_context(initial=True))
    speech, plan = action(council, 'General, o que aconteceu na última trégua?',
        NarrativeIntent('General, o que aconteceu na última trégua?', 'speak', conversation=ConversationUpdate(
            target_ids=('general_voss',), focus='histórico da última trégua',
            points=(ConversationPoint('question', 'o que aconteceu na última trégua?'),))))
    samples.extend((council.interpretation_context(), council.world_context(plan)))
    report = council.execute(plan, WorldPlan((WorldReaction(0, None, (
        WorldAction('general_voss', 'say', 'Tropas de Auren atacaram nossos postos após a retirada. Auren reconheceu a autoria e rompeu a trégua.',
            memory_ids=('general_voss:broken-truce',), conversation=ConversationUpdate(target_ids=('player',),
                focus='garantias para outro acordo', status='active',
                points=(ConversationPoint('statement', 'Auren reconheceu a autoria e rompeu a trégua.'),),
                resolves=('latest',), goal='Obter garantias para a retirada.', waiting_for='Uma garantia concreta.')),)),)))
    samples.append(council.narration_context(speech, report))
    speech, plan = action(council, 'Retire suas tropas primeiro; depois retiro as minhas.',
        NarrativeIntent('Retire suas tropas primeiro; depois retiro as minhas.', 'speak',
            conversation=ConversationUpdate(target_ids=('general_voss',), focus='tropas', proposal=ProposalUpdate(
                'offer', terms=(ProposalTerm(None, 'request', 'Retire suas tropas primeiro', 'general_voss', 1),
                                ProposalTerm(None, 'counterpart', 'depois retiro as minhas', 'player', 2))))))
    samples.append(council.world_context(plan))
    profile = council.session.social.profiles['general_voss']
    truce = council.session.knowledge.store.get('general_voss', 'general_voss:broken-truce')
    def opinion_term(id, description, impacts, memory_effect=None, relationship_effects=()):
        return TermAssessment(id, description, 0, 0, 'Sem efeito adicional nos eixos neste recorte.',
            tuple(PersonaEffect(i.id, impacts.get(i.id, 0),
                f'{i.description}: efeito deste termo = {impacts.get(i.id, 0)}.') for i in profile.persona.interests),
            () if memory_effect is None else (MemoryEffect(truce.claim, 'guarantees', memory_effect,
                'Os postos atacados depois da retirada sustentam a cautela quanto à ordem da retirada.'),),
            relationship_effects=relationship_effects)
    report = council.execute(plan, WorldPlan((WorldReaction(0, None, (), opinions=(
        OptionAssessment('general_voss', 'latest', 'proposal', 'Retirada unilateral seguida da promessa de retirada.', (
            opinion_term('at:1', 'Retire suas tropas primeiro', {'population': 1, 'guarantees': -1}, -1),
            opinion_term('at:2', 'depois retiro as minhas', {}, relationship_effects=(
                RelationshipEffect('player', 'trust', 1, 'A retirada posterior depende da promessa do interlocutor.'),
                RelationshipEffect('player', 'affection', 0, 'Não há benefício afetivo específico nesta promessa.'),
            ))), proposal_id='latest'),
        OptionAssessment('general_voss', 'latest', 'alternative', 'Cogitar retirada simultânea.', (
            TermAssessment('simultaneous', 'Retirada simultânea de ambos os lados.', 0, 0, 'Sem efeito adicional nos eixos.',
                tuple(PersonaEffect(i.id, 1 if i.id in {'population', 'guarantees'} else 0,
                    'A simultaneidade reduz o risco da retirada isolada sem criar cumprimento.') for i in profile.persona.interests),
                (MemoryEffect(truce.claim, 'guarantees', 0, 'A retirada simultânea evita o intervalo unilateral lembrado.'),),
                kind='condition'),
            ), proposal_id='latest', option_id='simultaneous'),
        OptionAssessment('general_voss', 'latest', 'no_agreement', 'Expectativa privada de guerra prolongada.', (
            opinion_term('war', 'A guerra pode continuar, com perdas para a população.', {'population': -1}),
            ), option_id='continue_war'),
    )),)))
    samples.extend((council.interpretation_context(), council.world_context(plan), council.world_context(),
                    council.narration_context(speech, report)))
    # Acompanhamento comum após a fala e os cálculos, sem parley ou gesto.
    assert council.session.agency.pending(report, {}) == ['general_voss']
    samples.append(council.agency_context('general_voss'))
    report = council.execute_agency('general_voss', WorldPlan((WorldReaction(0, None, (
        WorldAction('general_voss', 'say', 'Retirada simultânea de ambos os lados.', conversation=ConversationUpdate(
            target_ids=('player',), proposal=ProposalUpdate('offer', in_reply_to='proposal_1',
                terms=(ProposalTerm(None, 'condition', 'Retirada simultânea de ambos os lados.'),)))),)),),
        intent=IntentDecision('general_voss', 'Obter garantias executáveis para a paz.', 'Propor retirada simultânea.',
            'Resposta aos termos de retirada.', 'counteroffer',
            'A alternativa atende à população e evita a exposição unilateral lembrada na trégua.', ('opinion_2',))))
    samples.extend((council.agency_context('general_voss'), council.narration_context(speech, report)))
    # Relação inicial baseada em um aspecto de memória: esse aspecto não pontua duas vezes.
    linked_data = json.loads((ROOT / 'src/trama/scenarios/generals_council.json').read_text())
    trust = linked_data['creatures'][0]['relationships'][0]['trust']
    trust.update(reason='Cautela pela quebra de trégua de Auren, sem responsabilidade pessoal do interlocutor.',
                 sources=[dict(memory_id='general_voss:broken-truce', interest_id='guarantees')])
    linked = Conversation(build_session(linked_data))
    speech, plan = action(linked, 'Retire antes da minha promessa.', NarrativeIntent('Retire antes da minha promessa.',
        'speak', conversation=ConversationUpdate(target_ids=('general_voss',), proposal=ProposalUpdate('offer',
            terms=(ProposalTerm(None, 'request', 'Retire antes da minha promessa.'),)))))
    term = TermAssessment('at:1', 'Retire antes da minha promessa.', 0, 0, 'Sem efeito de alinhamento.',
        tuple(PersonaEffect(i.id, 0, 'Sem outra consequência neste controle.') for i in profile.persona.interests),
        (MemoryEffect(truce.claim, 'guarantees', -1, 'Cautela já resumida na confiança inicial.'),),
        relationship_effects=(RelationshipEffect('player', 'trust', 1, 'Este termo depende da promessa recebida.'),))
    report = linked.execute(plan, WorldPlan((WorldReaction(0, None, (), opinions=(
        OptionAssessment('general_voss', 'latest', 'proposal', 'Controle de origem compartilhada.',
                         (term,), proposal_id='latest'),)),)))
    scored = linked.session.social.opinions[-1]
    assert scored['components']['memories'] == 0 and scored['components']['relationships'] == -2
    assert scored['memory_effects'][0]['impacts'][0]['counted'] is False
    samples.extend((linked.world_context(plan), linked.narration_context(speech, report)))
    # Compromisso aceito, ação realmente observada e nova conversa com memória do encontro.
    evolving_data = json.loads((ROOT / 'src/trama/scenarios/generals_council.json').read_text())
    evolving_data['start'] = [5, 6]
    evolving_data['creatures'][0]['relationships'][0]['trust']['value'] = 0
    evolving = Conversation(build_session(evolving_data, roller=ReviewRoller()))
    promise = 'Fecharei a porta do Conselho.'
    speech, plan = action(evolving, promise, NarrativeIntent(promise, 'speak', conversation=ConversationUpdate(
        target_ids=('general_voss',), proposal=ProposalUpdate('offer',
            terms=(ProposalTerm(None, 'counterpart', promise, 'player'),)))))
    term = TermAssessment('at:1', promise, 0, 0, 'Sem efeito adicional.',
        tuple(PersonaEffect(i.id, 0, 'Sem outro efeito neste controle.') for i in profile.persona.interests))
    report = evolving.execute(plan, WorldPlan((WorldReaction(0, None, (), opinions=(
        OptionAssessment('general_voss', 'latest', 'proposal', 'Compromisso local verificável.', (term,), proposal_id='latest'),)),)))
    assert evolving.session.agency.pending(report, {}) == ['general_voss']
    evolving.execute_agency('general_voss', WorldPlan((WorldReaction(0, None, (
        WorldAction('general_voss', 'say', 'Aceito. Quem garante a retirada?', conversation=ConversationUpdate(
            proposal=ProposalUpdate('accept', 'proposal_1', 1),
            points=(ConversationPoint('question', 'Quem garante a retirada?'),))),)),), intent=IntentDecision(
                'general_voss', 'Conferir compromissos locais.', 'Aceitar o compromisso.', 'Cumprimento verificável.',
                'accept', 'Um termo concreto que pode ser conferido.', ('opinion_1',))))
    speech, plan = action(evolving, 'Fecho a porta do Conselho.', DoorIntent('close', 'council_door'))
    report = evolving.execute(plan, WorldPlan((WorldReaction(0, None, (), episodes=(
        RelationshipEpisode('general_voss', 'player', 'promise_kept', 'latest_observation',
            'Observou o responsável fechar a porta após o compromisso aceito.', conversation_id='conversation_1',
            proposal_id='proposal_1', version=1, term_id='at:1'),)),)))
    assert evolving.session.relationships.get('general_voss', 'player').trust.value == 1
    samples.extend((evolving.agency_context('general_voss'), evolving.narration_context(speech, report)))
    speech, plan = action(evolving, 'Lembra do combinado?', NarrativeIntent('Lembra do combinado?', 'speak'))
    term = TermAssessment('at:1', promise, 0, 0, 'Sem efeito adicional.',
        tuple(PersonaEffect(i.id, 0, 'Sem outro efeito neste controle.') for i in profile.persona.interests),
        relationship_effects=(RelationshipEffect('player', 'trust', 1, 'A promessa depende da confiabilidade conhecida.'),))
    evolving.execute(plan, WorldPlan((WorldReaction(0, None, (), opinions=(
        OptionAssessment('general_voss', 'latest', 'proposal', 'Reavaliar com a relação atual.', (term,), proposal_id='latest'),)),)))
    samples.append(evolving.world_context(plan))
    revelation = 'Recebi notícia de que o comboio de alimentos está bloqueado.'
    speech, plan = action(evolving, revelation, NarrativeIntent(revelation, 'speak',
        claims=(Claim('supply_train', 'supply_outlook', 'blocked'),)))
    evolving.execute(plan)
    assert evolving.session.agency.next_review(set()) == 'general_voss'
    samples.append(evolving.agency_context('general_voss', review=True))
    evolving.execute_review('general_voss', WorldPlan((WorldReaction(0, None, (), opinions=(
        OptionAssessment('general_voss', 'latest', 'proposal',
            'O relato exige reconsiderar a prioridade, sem comprovar o bloqueio.', (term,), proposal_id='latest'),)),)))
    samples.append(evolving.agency_context('general_voss'))
    evolving.execute_agency('general_voss', WorldPlan((WorldReaction(0, None, (
        WorldAction('general_voss', 'say', 'Suspendamos para conferir a notícia.',
            conversation=ConversationUpdate(status='suspended', reason='Suspendamos para conferir a notícia.')),)),),
        intent=IntentDecision('general_voss', 'Conferir o abastecimento.', 'Suspender o encontro.', None,
            'suspend', 'O relato pertinente ainda precisa ser conferido.')))
    samples.append(evolving.interpretation_context())
    evolving.session.emit_noise('player', evolving.session.state.position, 'loud')
    assert evolving.session.agency.next_review(set()) == 'general_voss'
    samples.append(evolving.agency_context('general_voss', review=True))
    evolving.execute_review('general_voss', WorldPlan())
    evolving.execute_agency('general_voss', WorldPlan((WorldReaction(0, None, (
        WorldAction('general_voss', 'say', 'Retomemos a audiência.', conversation=ConversationUpdate(
            status='active', reason='Retomemos a audiência.')),)),), intent=IntentDecision(
                'general_voss', 'Retomar a pergunta anterior.', 'Retomar o encontro.', 'Garantias.',
                'resume', 'O ruído não comprova uma agressão.')))
    speech, plan = action(evolving, 'Encerramos.', NarrativeIntent('Encerramos.', 'speak'))
    report = evolving.execute(plan, WorldPlan((WorldReaction(0, None, (
        WorldAction('general_voss', 'say', 'Até a próxima.', conversation=ConversationUpdate(
            status='closed', reason='Até a próxima.')),)),)))
    assert any(m.claim.predicate == 'conversation_commitment' for m in evolving.session.knowledge.store.active('general_voss'))
    samples.extend((evolving.interpretation_context(), evolving.world_context(), evolving.narration_context(speech, report)))
    interrupted = Conversation(build_session(dict(width=6, height=6, start=[2, 2], creatures=[dict(
        id='sentinel', name='Sentinela', position=[3, 2], senses=dict(response='observe'))]),
        roller=ReviewRoller(20, 20, 1)))
    speech, plan = action(interrupted, 'Quem guarda a passagem?', NarrativeIntent('Quem guarda a passagem?',
        'speak', conversation=ConversationUpdate(target_ids=('sentinel',), points=(
            ConversationPoint('question', 'Quem guarda a passagem?'),))))
    interrupted.execute(plan)
    interrupted.session.execute(RuleIntent('start_combat'))
    assert interrupted.session.conversations.view('player')[0]['status'] == 'suspended'
    samples.extend((interrupted.interpretation_context(), interrupted.world_context()))
    # As situações casuais usam a mesma preparação e os mesmos produtores de contexto.
    cases = json.loads((ROOT / 'tests/fixtures/casual_conversations.json').read_text())
    situation = load_situation('conversa-com-amiga')
    friend = Conversation(build_session(situation.scenario_data(), roller=situation.new_roller()))
    situation.initialize(friend, friend.session.encounter.roller)
    for row in cases['friend'][:2]:
        checkpoint = friend.session.agency.checkpoint()
        speech, plan = action(friend, row['prompt'], NarrativeIntent(row['prompt'], 'speak',
            conversation=ConversationUpdate(focus=row['focus'])))
        report = friend.execute(plan)
        assert friend.session.agency.pending(report, checkpoint) == ['lia']
        samples.extend((friend.interpretation_context(), friend.world_context(plan), friend.agency_context('lia')))
        actions = ([WorldAction('lia', 'say', row['reply'])] if row['reply'] else [])
        actions.append(WorldAction('lia', 'wait', 'Ouve sem exigir uma pergunta formal.'))
        report = friend.execute_agency('lia', WorldPlan((WorldReaction(0, None, tuple(actions)),),
            intent=IntentDecision('lia', row['goal'], 'Escutar.', row['waiting_for'], 'listen',
                'Acolher sem impor conselho ou sentimentos ao interlocutor.')))
        assert friend.session.agency.intents['lia']['waits_used'] == 1
        samples.append(friend.narration_context(speech, report))
    situation = load_situation('encontro-com-garoto')
    boy = Conversation(build_session(situation.scenario_data(), roller=situation.new_roller()))
    situation.initialize(boy, boy.session.encounter.roller)
    speech, plan = action(boy, cases['boy']['wait_prompt'], NarrativeIntent(cases['boy']['wait_prompt'], 'wait'))
    checkpoint = boy.session.agency.checkpoint()
    report = boy.execute(plan)
    assert boy.session.agency.pending(report, checkpoint) == ['street_boy']
    context = boy.agency_context('street_boy')
    samples.extend((boy.interpretation_context(), boy.world_context(plan), context))
    target = context['observations']['departure_targets'][0]['position']
    report = boy.execute_agency('street_boy', WorldPlan((WorldReaction(0, None, (
        WorldAction('street_boy', 'say', cases['boy']['thanks'], memory_ids=('street_boy:prior_coin',),
            conversation=ConversationUpdate(status='closed', reason=cases['boy']['close_reason'])),
        WorldAction('street_boy', 'move', 'Segue pela alameda.', destination=Position(target[0]-1, target[1]-1)))),),
        intent=IntentDecision('street_boy', 'Seguir seus próprios afazeres.', 'Agradecer e sair.', None,
            'leave', 'O gesto anterior não cria dívida ou obrigação de acompanhar o jogador.')))
    assert boy.session.scene.area_at(boy.session.creatures[0].position).id == 'north_lane'
    samples.extend((boy.interpretation_context(), boy.narration_context(speech, report)))
    # Vínculos qualitativos: dados autorais, formação e limites realmente ouvidos.
    bonds = json.loads((ROOT / 'tests/fixtures/bond_conversations.json').read_text())
    for sid in ('vinculo-em-formacao', 'vinculo-amizade-sem-atracao',
                'vinculo-afeto-sem-confianca', 'vinculo-interesse-nao-correspondido'):
        situation = load_situation(sid)
        encounter = Conversation(build_session(situation.scenario_data(), roller=situation.new_roller()))
        situation.initialize(encounter, encounter.session.encounter.roller)
        samples.extend((encounter.interpretation_context(), encounter.world_context(),
                        encounter.agency_context('marina')))
        row = bonds['decline']
        speech, plan = action(encounter, row['prompt'], NarrativeIntent(row['prompt'], 'speak',
            conversation=ConversationUpdate(target_ids=('marina',), romance_boundary='declined',
                boundary_text=row['literal'])))
        changes = (BondUpdate('marina', 'player', 'friendship', 'active',
            'História de cuidado percebido nas duas direções.',
            ('marina:marina_care', 'marina:player_care')), ) if sid == 'vinculo-em-formacao' else ()
        response = WorldPlan((WorldReaction(0, None, (), bonds=changes),)) if changes else WorldPlan()
        report = encounter.execute(plan, response)
        assert not report.failures
        assert not encounter.session.bonds.availability('marina', 'player')['can_express']
        samples.extend((encounter.agency_context('marina'), encounter.world_context(plan),
                        encounter.narration_context(speech, report)))
        encounter.session.emit_noise('player', encounter.session.state.position, 'loud')
        assert encounter.session.agency.next_review(set()) == 'marina'
        samples.append(encounter.agency_context('marina', review=True))
    # Citação com intervenção narrativa: ponto reconstruído sem alterar palavras.
    quoted = Conversation(load_session(ROOT / 'src/trama/scenarios/generals_council.json'))
    speech, plan = action(quoted, '“Quero discutir a trégua”, digo.', NarrativeIntent('Quero discutir a trégua.', 'speak',
        conversation=ConversationUpdate(target_ids=('general_voss',), focus='negociação da trégua',
            points=(ConversationPoint('statement', 'Quero discutir a trégua.'),))))
    validate_player_plan(speech.on, plan, quoted.interpretation_context(), stage='context_review')
    samples.extend((quoted.interpretation_context(), quoted.world_context(plan)))
    report = quoted.execute(plan)
    assert not report.failures
    samples.append(quoted.narration_context(speech, report))
    return samples


def describe_contexts(samples):
    result = {}
    for kind in ContextKind:
        shapes, texts = defaultdict(set), defaultdict(set)

        def visit(value, path='$', key=''):
            name = ('object' if isinstance(value, dict) else 'array' if isinstance(value, list) else
                    {str: 'string', bool: 'boolean', int: 'integer', float: 'number', type(None): 'null'}[type(value)])
            shapes[path].add(name)
            if isinstance(value, dict):
                for field, item in value.items():
                    visit(item, f'{path}.{field}', field)
            elif isinstance(value, list):
                for item in value:
                    visit(item, f'{path}[]', key)
            elif isinstance(value, str) and key not in VOLATILE_FIELDS:
                texts[path].add(value)

        selected = [c for c in samples if c.kind == kind]
        if not selected:
            raise ValueError(f'Não há amostra de contexto para {kind}.')
        for context in selected:
            context.require(kind)
            visit(json.loads(json.dumps(context, ensure_ascii=False)))
        result[kind.value] = {
            'shape': {path: '|'.join(sorted(types)) for path, types in sorted(shapes.items())},
            'text': {path: sorted(values) for path, values in sorted(texts.items())},
        }
    return result


def property_order(schema, path='$'):
    """A ordem de properties afeta saída estruturada, mesmo com schemas equivalentes."""
    result = {}
    if isinstance(schema, dict):
        if isinstance(schema.get('properties'), dict):
            result[path] = list(schema['properties'])
        for key, value in schema.items():
            result.update(property_order(value, f'{path}.{key}'))
    elif isinstance(schema, list):
        for index, value in enumerate(schema):
            result.update(property_order(value, f'{path}[{index}]'))
    return result


def build_manifest():
    adapters = {
        'interpretation': (openai_intent_interpreter.INSTRUCTIONS, openai_intent_interpreter.OpenAIIntentInterpreter(None).schema),
        'world': (openai_world_director.INSTRUCTIONS, openai_world_director.WORLD_SCHEMA),
        'narration': (openai_narrator.INSTRUCTIONS, openai_narrator.NARRATION_SCHEMA),
    }
    manifest = {
        'contracts': {kind.value: asdict(contract) for kind, contract in CONTRACTS.items()},
        'internal_fields': INTERNAL, 'optional_internal_fields': sorted(OPTIONAL_INTERNAL),
        'volatile_fields': sorted(VOLATILE_FIELDS),
        'contexts': describe_contexts(sample_contexts()),
        'adapters': {name: {'instructions': text, 'response_schema': schema, 'property_order': property_order(schema)}
                     for name, (text, schema) in adapters.items()},
    }
    # Normaliza tuplas como no transporte e não compartilha os schemas mutáveis.
    return json.loads(json.dumps(manifest, ensure_ascii=False))


def changes(before, after, path='$'):
    if isinstance(before, dict) and isinstance(after, dict):
        result = []
        for key in sorted(before.keys() | after.keys()):
            at = f'{path}.{key}'
            if key not in before:
                result.append(f'Adicionado: {at}')
            elif key not in after:
                result.append(f'Removido: {at}')
            else:
                result.extend(changes(before[key], after[key], at))
        return result
    return [] if before == after else [f'Alterado: {path}']


def digest(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description='Compara os contratos atuais com a referência revisada, sem rede.')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--check', action='store_true', help='Confere o contrato aprovado (padrão).')
    mode.add_argument('--update', action='store_true', help='Registra uma revisão explícita do contrato atual.')
    parser.add_argument('--reason', help='Justificativa obrigatória para registrar a revisão.')
    parser.add_argument('--reference', type=Path, default=REFERENCE)
    args = parser.parse_args(argv)
    if args.update and (not args.reason or not args.reason.strip()):
        parser.error('--update exige --reason com a justificativa da revisão.')
    if args.reason and not args.update:
        parser.error('--reason só se aplica a --update.')
    current = build_manifest()
    previous = json.loads(args.reference.read_text()) if args.reference.exists() else None
    if args.update:
        args.reference.parent.mkdir(parents=True, exist_ok=True)
        record = {'format_version': 1, 'review': {'reason': args.reason.strip(),
                  'previous_sha256': previous['review']['sha256'] if previous else None, 'sha256': digest(current)},
                  'contract': current}
        args.reference.write_text(json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        print(f'Revisão registrada em {args.reference}. Confira o diff antes de versionar.')
        return 0
    differences = changes(previous['contract'], current) if previous else ['Referência aprovada ausente.']
    if previous and previous['review']['sha256'] != digest(previous['contract']):
        differences.insert(0, 'Referência alterada sem registro de revisão: hash inconsistente.')
    if differences:
        print('\n'.join(differences))
        print('Revise os campos/instruções/esquemas e registre a justificativa com --update --reason.')
        return 1
    print('Contratos atuais conferem com a referência aprovada. Nenhuma chamada externa.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

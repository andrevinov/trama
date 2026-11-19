"""Vínculos: runner com decisões fixas e controles parciais de evidência/cronologia."""

from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from conftest import sourced_plan
from trama.actions import ActionError
from trama.agency import IntentDecision
from trama.application.conversation import Conversation
from trama.application.dialogue import Speech
from trama.application.intents import ActionPlan, DoorIntent, MovementIntent, MovementSegment, NarrativeIntent
from trama.application.scenarios import build_session
from trama.application.situations import load_situation
from trama.application.world import WorldAction, WorldPlan, WorldReaction
from trama.bonds import BondUpdate, BondError
from trama.bootstrap import open_situation
from trama.conversation_state import ConversationUpdate
from trama.knowledge import Claim, MemorySource
from trama.relationships import RelationshipEpisode

CASES = json.loads((Path(__file__).resolve().parents[1] / 'fixtures/bond_conversations.json').read_text())
CARE = ('marina:marina_care', 'marina:player_care')
PRIVATE = 'Decisão privada vinculo-593.'


def update(kind, state='active', ids=CARE, owner='marina', target='player'):
    return BondUpdate(owner, target, kind, state, PRIVATE, ids)


def configure(game, world=None, reply=None, *, boundary=None, expression=False, actor='marina'):
    def interpret(prompt, context):
        metadata = ConversationUpdate(target_ids=(actor,), romance_boundary=boundary,
            boundary_text=CASES['decline']['literal'] if boundary == 'declined' else
                          CASES['reopen']['literal'] if boundary == 'open' else None,
            romantic_expression=expression)
        return sourced_plan(ActionPlan((NarrativeIntent(prompt, 'speak', conversation=metadata),)), prompt)
    game.flow.interpreter = SimpleNamespace(interpret=interpret)
    def decide(context):
        if context['phase'] == 'player_action':
            return world or WorldPlan()
        if context['phase'] == 'npc_review':
            return WorldPlan()
        return WorldPlan((WorldReaction(0, None, (WorldAction(actor, 'say', reply or 'Entendido. Respeito sua escolha.'),)),),
            intent=IntentDecision(actor, 'Respeitar o interlocutor e os próprios limites.', 'Responder com franqueza.',
                                  None, 'respond', PRIVATE))
    game.flow.world_director = SimpleNamespace(decide=decide)
    def narrate(context):
        assert PRIVATE not in json.dumps(context)
        assert 'bond_history' not in json.dumps(context)
        return Speech(on='As falas e os efeitos percebidos são narrados.') if context['allow_on'] else Speech(off='Consulta aos fatos percebidos.')
    game.flow.narrator = SimpleNamespace(narrate=narrate)


def test_friendship_forms_from_reciprocal_care_without_romance_points_or_player_feelings():
    with open_situation(load_situation('vinculo-em-formacao'), allow_unconfigured=True) as game:
        s = game.flow.session
        profile, relation = deepcopy(s.social.profiles), s.relationships.get('marina', 'player')
        plan = WorldPlan((WorldReaction(0, None, (), bonds=(update('friendship'),)),))
        configure(game, plan, 'Sua companhia importa. Podemos conversar sem compromisso.')
        result = game.runner.submit(CASES['friendship']['prompt'])
        assert result.status == 'completed' and not result.report.failures
        assert [r.stage for r in result.requests] == ['interpret', 'world', 'npc_agency', 'narrate']
        after = s.relationships.get('marina', 'player')
        assert (after.trust, after.affection) == (relation.trust, relation.affection)
        assert s.relationships.bond('marina', 'player', 'friendship').state == 'active'
        assert all(s.relationships.bond('marina', 'player', k).state == 'absent' for k in ('attraction', 'infatuation', 'love'))
        assert s.social.profiles == profile and not s.social.opinions
        assert not any(m.claim.predicate == 'relationship_bond' for m in s.knowledge.store.active('player'))
        s.bonds.apply((update('friendship'),))
        assert len(s.relationships.bond_history('marina')) == 1
        assert game.runner.submit('[O que foi dito?]').status == 'completed'
        assert len(s.relationships.bond_history('marina')) == 1
        assert game.runner.reset().status == 'completed'
        assert not s.relationships.bond_history('marina')
        assert s.relationships.bond('marina', 'player', 'friendship').state == 'absent'


@pytest.mark.parametrize('sid,key,love,can_express', [
    ('vinculo-amizade-sem-atracao', 'friendship', 'absent', False),
    ('vinculo-afeto-sem-confianca', 'care_without_trust', 'active', True),
    ('vinculo-interesse-nao-correspondido', 'unrequited', 'absent', False),
])
def test_initial_bonds_can_guide_a_frank_reply_without_forcing_reciprocity(sid, key, love, can_express):
    with open_situation(load_situation(sid), allow_unconfigured=True) as game:
        s, row = game.flow.session, CASES[key]
        before = deepcopy(s.social.profiles)
        configure(game, reply=row['reply'], boundary='declined' if key == 'unrequited' else None)
        result = game.runner.submit(row['prompt'])
        assert result.status == 'completed' and not result.report.failures
        actor_context = next(r.context for r in result.requests if r.stage == 'npc_agency')
        relation = actor_context['relationships'][0]
        assert relation['bonds']['love']['state'] == love and relation['romance']['can_express'] == can_express
        if love == 'active':
            assert relation['trust']['value'] < 0 < relation['affection']['value']
        assert s.social.profiles == before and not s.social.opinions
        assert not s.relationships.bond_history('marina')
        assert all(r['owner_id'] == 'marina' for r in actor_context['relationships'])


def test_decline_and_reopening_are_heard_self_declarations_and_do_not_erase_feelings():
    with open_situation(load_situation('vinculo-interesse-nao-correspondido'), allow_unconfigured=True) as game:
        s = game.flow.session
        configure(game, boundary='open')
        opened = game.runner.submit(CASES['reopen']['prompt'])
        assert opened.status == 'completed' and not opened.report.failures
        assert s.bonds.availability('marina', 'player')['can_express']
        configure(game, boundary='declined')
        declined = game.runner.submit(CASES['decline']['prompt'])
        assert declined.status == 'completed' and not declined.report.failures
        assert not s.bonds.availability('marina', 'player')['can_express']
        assert s.relationships.bond('marina', 'player', 'attraction').state == 'active'
        assert s.relationships.bond('marina', 'player', 'friendship').state == 'active'
        own = [m for m in s.knowledge.store.active('player') if m.claim.predicate == 'romance_boundary:marina']
        heard = [m for m in s.knowledge.store.active('marina') if m.claim.predicate == 'romance_boundary:marina']
        assert own[0].source.kind == 'observation' and heard[0].source.kind == 'report'
        assert heard[0].source.actor_id == 'player' and heard[0].claim.value == 'declined'
        count = len(s.knowledge.store.export()['memories'])
        blocked = game.flow.conversation.execute(ActionPlan((NarrativeIntent('Aguardo.', 'wait'),)),
            WorldPlan((WorldReaction(0, None, (WorldAction('marina', 'say', CASES['expression'],
                conversation=ConversationUpdate(target_ids=('player',), romantic_expression=True)),)),)))
        assert blocked.failures and 'limite conhecido' in blocked.stop_reason
        assert len(s.knowledge.store.export()['memories']) == count


@pytest.mark.parametrize('kind', ['friendship', 'attraction', 'infatuation', 'love'])
def test_player_never_receives_an_inferred_bond_and_invalid_batch_is_atomic(kind):
    with open_situation(load_situation('vinculo-em-formacao'), allow_unconfigured=True) as game:
        s = game.flow.session
        before = s.knowledge.store.export()
        with pytest.raises(ActionError):
            s.bonds.apply((update('friendship'), update(kind, owner='player', target='marina')))
        assert s.knowledge.store.export() == before
        assert not s.relationships.bond_history('marina')


def test_scores_one_sided_care_and_reports_do_not_replace_reciprocal_history():
    with open_situation(load_situation('vinculo-em-formacao'), allow_unconfigured=True) as game:
        s = game.flow.session
        with pytest.raises(ActionError, match='duas direções'):
            s.bonds.apply((update('friendship', ids=('marina:player_care',)),))
        report = s.knowledge.store.learn('marina', Claim('alleged_care', 'care_history', 'said'), 'Disseram que o jogador ajudou.',
            MemorySource('report', 'rumor-of-care', 'player'), when='Agora.', context='Relato não confirmado.',
            entities=('player',), topics=('care',))
        with pytest.raises(ActionError, match='duas direções'):
            s.bonds.apply((update('friendship', ids=('marina:marina_care', report.id)),))
        assert s.relationships.bond('marina', 'player', 'friendship').state == 'absent'


def test_romantic_progress_requires_new_significant_observed_episodes_and_can_end_without_losing_friendship():
    # Controle parcial: operações físicas e classificação de cuidado fixas, sem julgamento de modelo real.
    with open_situation(load_situation('vinculo-em-formacao'), allow_unconfigured=True) as game:
        s = game.flow.session
        s.bonds.apply((update('friendship'), update('attraction', ids=('marina:player_care',))))
        with pytest.raises(ActionError, match='novo encontro'):
            s.bonds.apply((update('infatuation', ids=('marina:player_care',)),))
        s.execute(DoorIntent('close', 'courtyard_door'))
        s.relationship_history.apply((RelationshipEpisode('marina', 'player', 'care_shown', 'latest_observation',
            'Cuidado percebido ao fechar a porta, classificação fixa deste controle.'),))
        first = next(m for m in s.knowledge.store.active('marina')
                     if m.claim.subject_id == 'courtyard_door' and m.source.actor_id == 'player')
        s.bonds.apply((update('infatuation', ids=('marina:player_care', first.id)),))
        with pytest.raises(ActionError, match='novo cuidado'):
            s.bonds.apply((update('love', ids=CARE+(first.id,)),))
        s.execute(MovementIntent((MovementSegment('east', 1),), False, ''))
        s.execute(DoorIntent('close', 'side_door'))
        s.relationship_history.apply((RelationshipEpisode('marina', 'player', 'care_shown', 'latest_observation',
            'Outro cuidado efetivamente percebido, em episódio distinto.'),))
        second = next(m for m in s.knowledge.store.active('marina')
                      if m.claim.subject_id == 'side_door' and m.source.actor_id == 'player')
        love = update('love', ids=CARE+(second.id,))
        s.bonds.apply((love,))
        assert s.relationships.bond('marina', 'player', 'love').state == 'active'
        history = len(s.relationships.bond_history('marina'))
        s.bonds.apply((love,))
        assert len(s.relationships.bond_history('marina')) == history
        numeric = (s.relationships.get('marina', 'player').trust, s.relationships.get('marina', 'player').affection)
        game.flow.conversation.execute(ActionPlan((NarrativeIntent(CASES['decline']['prompt'], 'speak',
            conversation=ConversationUpdate(target_ids=('marina',), romance_boundary='declined',
                boundary_text=CASES['decline']['literal'])),)))
        s.bonds.apply((update('love', 'ended', ids=('latest_report',)),))
        assert s.relationships.bond('marina', 'player', 'love').state == 'ended'
        assert s.relationships.bond('marina', 'player', 'friendship').state == 'active'
        assert (s.relationships.get('marina', 'player').trust, s.relationships.get('marina', 'player').affection) == numeric
        s.bonds.apply((love,))
        assert s.relationships.bond('marina', 'player', 'love').state == 'ended'
        assert not s.encounter.roller.used


def test_romance_cannot_be_enabled_for_an_actor_without_adult_declaration():
    with open_situation(load_situation('encontro-com-garoto'), allow_unconfigured=True) as game:
        s = game.flow.session
        with pytest.raises(ActionError, match='adultos'):
            s.bonds.apply((update('attraction', ids=('street_boy:prior_coin',), owner='street_boy'),))
        blocked = game.flow.conversation.execute(ActionPlan((NarrativeIntent('Quero romance.', 'speak',
            conversation=ConversationUpdate(target_ids=('street_boy',), romantic_expression=True)),)))
        assert blocked.failures and 'adultos' in blocked.stop_reason
        assert not s.relationships.bond_history('street_boy')


def test_unheard_declaration_does_not_become_the_npcs_knowledge_and_claims_cannot_forge_it():
    data = load_situation('vinculo-em-formacao').scenario_data()
    data['creatures'][0]['senses']['hearing_range_meters'] = 0
    s = build_session(data)
    c = Conversation(s)
    result = c.execute(ActionPlan((NarrativeIntent(CASES['decline']['prompt'], 'speak',
        conversation=ConversationUpdate(target_ids=('marina',), romance_boundary='declined',
            boundary_text=CASES['decline']['literal'])),)))
    assert not result.failures
    assert s.bonds.boundary('player', 'player', 'marina') == 'declined'
    assert s.bonds.boundary('marina', 'player', 'marina') == 'unknown'
    before = s.knowledge.store.export()
    forged = c.execute(ActionPlan((NarrativeIntent('Olá.', 'speak',
        claims=(Claim('player', 'romance_boundary:marina', 'open'),)),)))
    assert forged.failures and s.knowledge.store.export() == before


def test_a_declaration_needs_a_literal_fragment_and_repetition_does_not_create_new_knowledge():
    with open_situation(load_situation('vinculo-em-formacao'), allow_unconfigured=True) as game:
        s = game.flow.session
        bad = game.flow.conversation.execute(ActionPlan((NarrativeIntent('Olá.', 'speak',
            conversation=ConversationUpdate(target_ids=('marina',), romance_boundary='declined',
                boundary_text='Não quero romance.')),)))
        assert bad.failures and s.bonds.boundary('marina', 'player', 'marina') == 'unknown'
        plan = ActionPlan((NarrativeIntent(CASES['decline']['prompt'], 'speak', conversation=ConversationUpdate(
            target_ids=('marina',), romance_boundary='declined', boundary_text=CASES['decline']['literal'])),))
        assert not game.flow.conversation.execute(plan).failures
        revision = s.knowledge.store.revision
        assert not game.flow.conversation.execute(plan).failures
        assert s.knowledge.store.revision == revision


def test_a_single_batch_cannot_jump_from_attraction_to_infatuation_using_the_same_old_history():
    with open_situation(load_situation('vinculo-em-formacao'), allow_unconfigured=True) as game:
        s = game.flow.session
        with pytest.raises(ActionError, match='novo encontro'):
            s.bonds.apply((update('attraction', ids=('marina:player_care',)),
                           update('infatuation', ids=('marina:player_care',))))
        assert s.relationships.bond('marina', 'player', 'attraction').state == 'absent'
        assert not s.relationships.bond_history('marina')


def test_sharing_an_old_declaration_by_memory_id_cannot_override_a_later_boundary():
    with open_situation(load_situation('vinculo-interesse-nao-correspondido'), allow_unconfigured=True) as game:
        s = game.flow.session
        marina = s.perception.observer('marina')
        for choice, text in [('open', 'Estou aberta a um encontro.'), ('declined', 'Prefiro amizade.')]:
            s.knowledge.communicate('marina', text, marina.position, conversation=ConversationUpdate(
                target_ids=('player',), romance_boundary=choice, boundary_text=text))
            if choice == 'open':
                old = next(m for m in s.knowledge.store.active('marina')
                           if m.claim.predicate == 'romance_boundary:player')
        before = s.knowledge.store.export()
        with pytest.raises(ActionError, match='memory_ids'):
            s.knowledge.communicate('marina', 'Olá.', marina.position, memory_ids=(old.id,))
        assert s.knowledge.store.export() == before
        assert s.bonds.boundary('player', 'marina', 'player') == 'declined'


def test_maximum_numeric_levels_do_not_form_a_bond_automatically():
    data = load_situation('vinculo-em-formacao').scenario_data()
    row = data['creatures'][0]['relationships'][0]
    row['trust']['value'] = row['affection']['value'] = 5
    s = build_session(data)
    assert all(s.relationships.bond('marina', 'player', k).state == 'absent'
               for k in ('friendship', 'attraction', 'infatuation', 'love'))
    with pytest.raises(ActionError):
        s.bonds.apply((update('friendship', ids=('marina:player_care',)),))


def test_initial_history_with_acquisition_sequence_is_not_a_new_event_after_initial_attraction():
    data = load_situation('vinculo-interesse-nao-correspondido').scenario_data()
    for sequence, memory in enumerate(data['creatures'][0]['knowledge'], start=10):
        memory['acquired_at'] = sequence
    s = build_session(data)
    with pytest.raises(ActionError, match='novo encontro'):
        s.bonds.apply((update('infatuation', ids=CARE),))
    assert not s.relationships.bond_history('marina')


def test_perceived_boundary_can_end_a_romantic_bond_in_private_review_without_action():
    with open_situation(load_situation('vinculo-interesse-nao-correspondido'), allow_unconfigured=True) as game:
        s, c = game.flow.session, game.flow.conversation
        c.execute(ActionPlan((NarrativeIntent(CASES['decline']['prompt'], 'speak',
            conversation=ConversationUpdate(target_ids=('marina',), romance_boundary='declined',
                boundary_text=CASES['decline']['literal'])),)))
        assert s.agency.next_review(set()) == 'marina'
        context = c.agency_context('marina', review=True)
        assert context['relationships'][0]['romance']['known_target_choice'] == 'declined'
        c.execute_review('marina', WorldPlan((WorldReaction(0, None, (), bonds=(
            update('attraction', 'ended', ids=('latest_report',)),)),)))
        assert s.relationships.bond('marina', 'player', 'attraction').state == 'ended'
        assert s.relationships.bond('marina', 'player', 'friendship').state == 'active'


@pytest.mark.parametrize('invalid', ['age', 'foreign_source', 'initial_romance'])
def test_scenario_rejects_invalid_age_foreign_history_and_romance_without_adults(invalid):
    data = load_situation('vinculo-amizade-sem-atracao').scenario_data()
    actor = data['creatures'][0]
    if invalid == 'age':
        actor['adult'] = 'yes'
    elif invalid == 'foreign_source':
        actor['relationships'][0]['bonds'][0]['memory_ids'] = ['player:unknown']
    else:
        actor['adult'] = False
        actor['relationships'][0]['bonds'][0]['kind'] = 'love'
    with pytest.raises(BondError):
        build_session(data)


def test_favorable_option_does_not_force_romance_acceptance_or_change_alignment():
    from trama.conversation_state import ProposalTerm, ProposalUpdate
    from trama.opinions import OptionAssessment, TermAssessment
    from trama.relationships import RelationshipEffect
    from trama.social import PersonaEffect
    with open_situation(load_situation('vinculo-amizade-sem-atracao'), allow_unconfigured=True) as game:
        s = game.flow.session
        profile = deepcopy(s.social.profiles)
        text = 'Proponho um encontro.'
        configure(game)
        game.flow.interpreter = SimpleNamespace(interpret=lambda prompt, context: sourced_plan(ActionPlan((
            NarrativeIntent(prompt, 'speak', conversation=ConversationUpdate(target_ids=('marina',),
                romantic_expression=True, proposal=ProposalUpdate('offer', terms=(ProposalTerm(
                    None, 'request', text, 'player'),)))),)), prompt))
        term = TermAssessment('at:1', text, 0, 0, 'Impactos fixos deste controle.',
            tuple(PersonaEffect(i.id, 1, 'Benefício hipotético fornecido pelo controle.') for i in s.social.profiles['marina'].persona.interests),
            relationship_effects=(RelationshipEffect('player', 'affection', 1, 'Benefício ao interlocutor.'),))
        def director(context):
            if context['phase'] == 'player_action':
                return WorldPlan((WorldReaction(0, None, (), opinions=(OptionAssessment('marina', 'latest', 'proposal',
                    'Avaliação favorável não obriga aceitar.', (term,), proposal_id='latest'),)),))
            if context['phase'] == 'npc_review':
                return WorldPlan()
            return WorldPlan((WorldReaction(0, None, (WorldAction('marina', 'say', CASES['friendship']['reply'],
                conversation=ConversationUpdate(target_ids=('player',), romance_boundary='declined',
                    boundary_text=CASES['friendship']['boundary'], proposal=ProposalUpdate('reject', 'proposal_1', 1))),)),),
                intent=IntentDecision('marina', 'Preservar a amizade e seus limites.', 'Recusar com franqueza.', None,
                    'reject', PRIVATE, ('opinion_1',)))
        game.flow.world_director = SimpleNamespace(decide=director)
        result = game.runner.submit(text)
        assert result.status == 'completed' and not result.report.failures
        assert s.social.opinions[-1]['total'] >= 3
        frame = s.conversations.view('player')[0]
        assert frame['proposals'][0]['versions'][0]['responses'][-1]['action'] == 'reject'
        assert s.social.profiles == profile and s.relationships.bond('marina', 'player', 'attraction').state == 'absent'
        assert s.bonds.boundary('player', 'marina', 'player') == 'declined'

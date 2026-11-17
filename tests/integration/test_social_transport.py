"""Transporte da avaliação social real e validação antes de efeitos."""

from dataclasses import asdict, replace
import json

import pytest

from trama.actions import ActionError
from trama.infrastructure.openai_intent_interpreter import parse_intent
from trama.infrastructure.openai_world_director import parse_world_plan
from trama.knowledge import Claim
from trama.social import SocialError, assessment_from_data
from test_social_judgment import assess, game, speak_and_resolve


def test_new_social_assessment_crosses_the_real_world_parser():
    value = assess()
    action = dict(actor_id='guard', operation='influence', text='Avaliação privada.', target_id=None,
        destination=None, weapon='unarmed', volume='normal', memory_ids=[],
        influence=dict(skill='persuasion', attitude='indifferent', assessment=asdict(value)))
    plan = parse_world_plan(json.dumps(dict(reactions=[dict(step_index=0, after_squares=None,
        actions=[action], interrupt=False, reason='', check=None)])))
    request = plan.reactions[0].actions[0].influence
    assert request.assessment == value and request.willingness is None


def test_promise_is_a_claim_about_commitment_without_payment():
    intent = parse_intent(json.dumps(dict(operation='speak', text='Prometo ouro se me ouvir.',volume='normal',
        claims=[dict(subject_id='player',predicate='offer_reward',value='gold_if_listen')])))
    assert intent.claims == (Claim('player','offer_reward','gold_if_listen'),)


def test_unknown_target_does_not_create_decision_or_roll(dice):
    session=game(dice)
    with pytest.raises(ActionError,match='alvo conhecido'):
        speak_and_resolve(session,replace(assess(),target_id='invented'))
    assert not session.social.decisions and not session.encounter.roller.sides


def test_inaudible_request_does_not_resolve_influence(dice):
    from trama.application.intents import NarrativeIntent
    session=game(dice)
    session.offer_parley('guard','Pare.')
    # Sussurro a 12 m não é ouvido; o contexto não autoriza onisciência.
    session.execute(NarrativeIntent('Me ouça.','speak',volume='quiet'))
    from trama.application.parley import InfluenceRequest
    with pytest.raises(ActionError,match='não ouviu'):
        session.resolve_influence('guard',InfluenceRequest(skill='persuasion',assessment=assess()),'Avalia.')
    assert not session.social.decisions and not session.encounter.roller.sides


def test_assessment_rejects_model_supplied_weights_or_final_verdict():
    value=asdict(assess())
    value['willingness']='willing'
    with pytest.raises(SocialError):
        assessment_from_data(value)

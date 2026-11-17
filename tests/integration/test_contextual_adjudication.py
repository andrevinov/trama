"""Dificuldade contextual, regras fixas e referências privadas sem rede."""

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

import pytest

from trama.actions import ActionError
from trama.application.conversation import Conversation
from trama.application.intents import ActionPlan, NarrativeIntent, RuleIntent, ScenarioIntent
from trama.application.scenarios import build_session
from trama.application.situations import load_situation
from trama.application.world import WorldAction, WorldPlan, WorldReaction
from trama.application.world_resolution import WorldExecutor
from trama.bootstrap import open_situation
from trama.difficulty import Adjudication
from trama.infrastructure.openai_world_director import ACTION_SCHEMA, parse_world_plan
from trama.knowledge import Claim

ROOT = Path(__file__).resolve().parents[2]


def dungeon(*, start=(3, 9), roller=None, opened_gate=False):
    data = json.loads((ROOT / 'src/trama/scenarios/dungeon_escape.json').read_text())
    data['start'] = list(start)
    if opened_gate:
        next(p for p in data['passages'] if p['id']=='gate_4')['is_open']=True
    return build_session(data, roller=roller)


def judge(request, outcome='check', difficulty='moderate', disadvantage=False, advantage=False):
    return Adjudication(request['id'], outcome, difficulty if outcome == 'check' else None,
        advantage, disadvantage, (next(iter(request['facts'])),), 'Avaliação local com fatos declarados.')


def decisions(context, **options):
    return tuple(judge(r, **options) for r in context['world']['adjudication']['requests'])


@pytest.mark.parametrize('outcome,rolls,found', [('automatic',(),True),('impossible',(),False),('check',(20,),True),('check',(1,),False)])
def test_contextual_search_resolves_automatic_impossible_or_the_actual_roll(dice, outcome, rolls, found):
    session = dungeon(roller=dice(*rolls))
    conversation = Conversation(session)
    plan = ActionPlan((ScenarioIntent('investigate','cell_4'),))
    context = conversation.world_context(plan)
    assert {r['id'] for r in context['world']['adjudication']['requests']} == {'find_uniform'}
    result = conversation.execute(plan, WorldPlan(adjudications=decisions(context,outcome=outcome)), require_adjudications=True)
    assert not result.failures
    assert ('cleaner_uniform' in session.dungeon.discovered) is found
    check = next(e for e in result.world_events if e['operation']=='check')
    assert check['skill']=='perception' and check['automatic']==(outcome!='check')
    assert session.encounter.roller.sides == ([20] if rolls else [])


def test_active_listening_uses_contextual_disadvantage_and_keeps_the_lowest_die(dice):
    session = dungeon(start=(8,7),roller=dice(20,1))
    conversation = Conversation(session)
    plan = ActionPlan((ScenarioIntent('listen','guard_door'),))
    context = conversation.world_context(plan)
    assert [r['id'] for r in context['world']['adjudication']['requests']] == ['listen:guard_door']
    result = conversation.execute(plan, WorldPlan(adjudications=decisions(context,difficulty='easy',disadvantage=True)),require_adjudications=True)
    check = next(e for e in result.world_events if e['operation']=='check')
    assert check['dice']==[20,1] and check['total']==1+session.encounter.player_sheet.skill_bonus('perception')
    assert check['dc']==10 and not check['passed']
    assert not any(e['operation']=='heard' for e in result.world_events)


def test_passive_hearing_has_minus_five_and_does_not_transmit_words_through_the_door(dice):
    session = dungeon(start=(8,7),roller=dice())
    conversation = Conversation(session)
    plan = ActionPlan((NarrativeIntent('Sou filho de um nobre.','speak',claims=(Claim('player','parentage','noble_heir'),)),))
    context = conversation.world_context(plan)
    requests = context['world']['adjudication']['requests']
    assert any(r['facts']['sound:purpose']=='understand_speech' for r in requests)
    result = conversation.execute(plan,WorldPlan(adjudications=decisions(context,difficulty='easy',disadvantage=True)),require_adjudications=True)
    assert not result.failures and 'guard_1' not in result.events[0]['heard_by']
    hearing = [e for e in result.world_events if e['operation']=='hearing_check' and e['actor_id']=='guard_1']
    assert {e['purpose'] for e in hearing}=={'understand_speech','notice_noise'}
    assert all(e['total']==8 and e['dc']==10 and not e['passed'] for e in hearing)
    assert not session.parley_pending and not session.dungeon.guard_alert
    assert not any(m.claim.predicate=='parentage' for m in session.knowledge.store.active('guard_1'))
    assert not session.encounter.roller.sides


def test_noticing_a_voice_does_not_automatically_teach_its_words(dice):
    session=dungeon(start=(8,7),roller=dice())
    conversation=Conversation(session)
    plan=ActionPlan((NarrativeIntent('Sou herdeiro.','speak',claims=(Claim('player','parentage','noble_heir'),)),))
    context=conversation.world_context(plan)
    choices=tuple(judge(r,outcome='impossible' if r['facts']['sound:purpose']=='understand_speech' else 'automatic')
                  for r in context['world']['adjudication']['requests'])
    report=conversation.execute(plan,WorldPlan(adjudications=choices),require_adjudications=True)
    assert 'guard_1' not in report.events[0]['heard_by']
    assert session.dungeon.guard_alert and session.parley_pending
    assert not any(m.claim.predicate=='parentage' for m in session.knowledge.store.active('guard_1'))


def test_hearing_policy_is_cached_without_another_judgment_and_reset_clears_it(dice):
    session=dungeon(start=(8,7),roller=dice())
    conversation=Conversation(session)
    plan=ActionPlan((NarrativeIntent('Uma voz normal.','speak'),))
    first=conversation.world_context(plan)
    conversation.execute(plan,WorldPlan(adjudications=decisions(first,difficulty='easy',disadvantage=True)),require_adjudications=True)
    second=conversation.world_context(plan)
    assert not second['world']['adjudication']['requests'] and second['world']['adjudication']['cached']
    conversation.execute(plan,require_adjudications=True)
    session.reset()
    assert not session.adjudication.cached


def test_a_world_decision_cannot_supply_a_new_dc_for_hide(dice):
    session=dungeon(roller=dice(20))
    conversation=Conversation(session)
    plan=ActionPlan((RuleIntent('hide'),))
    context=conversation.world_context(plan)
    assert context['world']['adjudication']['requests']==[]
    with pytest.raises(ActionError,match='não solicitada ou de regra fixa'):
        conversation.execute(plan,WorldPlan(adjudications=(Adjudication('hide','check','very_easy',False,False,('fake',),'Falso.'),)),require_adjudications=True)
    report=conversation.execute(plan,require_adjudications=True)
    hide=next(e for e in report.world_events if e['operation']=='hide')
    assert hide['dc']==15 and hide['total']==21


def test_missing_or_invented_contextual_decisions_fail_before_the_action_is_paid(dice):
    session=dungeon(roller=dice())
    conversation=Conversation(session)
    plan=ActionPlan((ScenarioIntent('investigate','cell_4'),))
    context=conversation.world_context(plan)
    before=deepcopy(session.encounter.states)
    with pytest.raises(ActionError,match='não avaliou todas'):
        conversation.execute(plan,require_adjudications=True)
    wrong=replace(judge(context['world']['adjudication']['requests'][0]),fact_ids=('imagined:torch',))
    with pytest.raises(ActionError,match='não fornecido'):
        conversation.execute(plan,WorldPlan(adjudications=(wrong,)),require_adjudications=True)
    assert session.encounter.states==before and not session.dungeon.discovered


def test_schema_forbids_public_memory_ids_outside_say():
    say,influence,other=ACTION_SCHEMA['anyOf']
    assert say['properties']['operation']['enum']==['say']
    assert other['properties']['memory_ids']['maxItems']==0
    assert 'say' not in other['properties']['operation']['enum']
    assert influence['properties']['target_id']=={'type':'null'}
    assert influence['properties']['memory_ids']['maxItems']==0


def test_original_private_reference_is_read_validated_and_never_shared(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    raw=(ROOT/'tests/fixtures/adjudication/world_private_memory_reference.json').read_text()
    plan=parse_world_plan(raw)
    action=plan.reactions[0].actions[0]
    with open_situation(load_situation('memoria-vinculos-original'),allow_unconfigured=True) as game:
        session=game.flow.session
        claims=tuple(dict.fromkeys(e.claim for e in action.influence.assessment.memory_effects if e.claim.subject_id=='player'))
        intent=NarrativeIntent('Meu pai é nobre e prometo dinheiro.','speak',volume='loud',claims=claims)
        report=game.flow.conversation.execute(ActionPlan((intent,)),plan)
        assert not report.failures
        event=next(e for e in report.world_events if e['operation']=='influence')
        assert event['private_memory_ids']==['guard_1:fear-of-reprisals']
        assert not any(e.get('shared_memories') for e in report.world_events)
        narration=game.flow.conversation.narration_context(report=report)
        assert 'private_memory_ids' not in json.dumps(narration)


def test_foreign_or_unrelated_private_references_are_rejected(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    action=parse_world_plan((ROOT/'tests/fixtures/adjudication/world_private_memory_reference.json').read_text()).reactions[0].actions[0]
    with open_situation(load_situation('memoria-vinculos-original'),allow_unconfigured=True) as game:
        with pytest.raises(ValueError,match='não possui'):
            WorldExecutor(game.flow.session).execute(replace(action,memory_ids=('prisoner:key-custodian',)))


def test_active_search_keeps_the_stealth_dc_despite_the_contextual_hearing_dc(dice):
    from test_perception import rooms
    session=build_session(rooms(),roller=dice(20,20,1))
    conversation=Conversation(session)
    conversation.execute(ActionPlan((RuleIntent('hide'),)))
    plan=ActionPlan((NarrativeIntent('Aguardo oculto.','wait'),))
    context=conversation.world_context(plan)
    world=WorldPlan((WorldReaction(0,None,(WorldAction('watcher','search','O vigia procura.','player'),)),),
                    decisions(context,difficulty='easy',disadvantage=True))
    report=conversation.execute(plan,world,require_adjudications=True)
    search=next(e for e in report.world_events if e['operation']=='search')
    assert search['dc']==21 and search['dice']==[20,1] and search['disadvantage']
    assert not search['found'] and session.perception.hidden_total==21


def test_minor_illusion_uses_the_casters_save_dc_without_a_contextual_dc(dice,monkeypatch):
    session=dungeon(roller=dice(20))
    monkeypatch.setattr(session.adjudication,'check',lambda *args: pytest.fail('Magia não pode solicitar CD contextual.'))
    session._illusion()
    events=session.drain_world_events()
    check=next(e for e in events if e['operation']=='check')
    assert check['skill']=='investigation' and check['dc']==13


@pytest.mark.parametrize('operation', ['hide','attack','second_wind','action_surge','start_combat'])
def test_fixed_combat_and_class_rules_do_not_request_contextual_dcs(operation):
    session=build_session(dict(width=5,height=5,start=[1,1],creatures=[dict(id='enemy',name='Inimigo',position=[2,1])]))
    intent=RuleIntent(operation,target_id='enemy' if operation=='attack' else None)
    context=Conversation(session).world_context(ActionPlan((intent,)))
    assert context['world']['adjudication']['requests']==[]


@pytest.mark.parametrize('changes', [dict(difficulty=None),dict(outcome='invented'),dict(advantage=1),
    dict(fact_ids=()),dict(outcome='automatic',difficulty='easy'),dict(reason='')])
def test_adjudication_transport_rejects_invalid_decisions(changes):
    decision=Adjudication('request','check','easy',False,False,('door:one',),'Fato fornecido.')
    with pytest.raises(ValueError,match='Avaliação contextual inválida'):
        replace(decision,**changes)


def test_contextual_reasons_are_private_even_when_a_failed_check_is_narrated(dice):
    session=dungeon(roller=dice(1))
    conversation=Conversation(session)
    plan=ActionPlan((ScenarioIntent('investigate','cell_4'),))
    context=conversation.world_context(plan)
    decision=replace(decisions(context)[0],reason='SEGREDO: uniforme escondido sob a cama.')
    report=conversation.execute(plan,WorldPlan(adjudications=(decision,)),require_adjudications=True)
    narrative=conversation.narration_context(report=report)
    assert 'SEGREDO' not in json.dumps(narrative)
    assert 'adjudication' not in json.dumps(narrative['execution'])
    assert next(e for e in narrative['execution']['reactions'] if e['operation']=='check')['dc']==15


@pytest.mark.parametrize('outcome,advantage,found',[('automatic',False,False),('check',True,True)])
def test_acoustic_judgment_does_not_erase_the_actual_stealth_dc(dice,outcome,advantage,found):
    from test_perception import rooms
    session=build_session(rooms(),roller=dice(15))
    conversation=Conversation(session)
    conversation.execute(ActionPlan((RuleIntent('hide'),)))
    assert session.perception.hidden_total==16
    plan=ActionPlan((NarrativeIntent('Aguardo em silêncio.','wait'),))
    context=conversation.world_context(plan)
    choices=tuple(judge(r,outcome=outcome,difficulty='easy',advantage=advantage)
                  for r in context['world']['adjudication']['requests'])
    session.adjudication.begin(choices,strict=True)
    session.emit_noise('player',session.state.position,'quiet','Passo discreto real.')
    checks=[e for e in session.drain_world_events() if e['operation']=='hearing_check' and e['actor_id']=='watcher']
    assert checks and all(e['dc']==16 and e['passed']==found for e in checks)
    assert (session.perception.hidden_total is None)==found


def test_accepting_disguise_during_approach_does_not_invalidate_the_theft_judgment(dice):
    from trama.application.intents import DoorIntent, MovementIntent
    session=dungeon(roller=dice(20,20,20,20),opened_gate=True)
    conversation=Conversation(session)
    prepared=conversation.execute(ActionPlan((ScenarioIntent('investigate','cell_4'),
        ScenarioIntent('take','cleaner_uniform'),ScenarioIntent('wear','cleaner_uniform'),
        RuleIntent('hide'),MovementIntent((),False,'','guard_door'))))
    assert not prepared.failures and session.dungeon.disguise=='untested'
    plan=ActionPlan((DoorIntent('open','guard_door'),ScenarioIntent('take','cell_key')))
    context=conversation.world_context(plan)
    assert any(r['id']=='steal_key' for r in context['world']['adjudication']['requests'])
    report=conversation.execute(plan,WorldPlan(adjudications=decisions(context)),require_adjudications=True)
    assert not report.failures
    assert session.dungeon.disguise=='accepted' and 'cell_key' in session.dungeon.inventory


def test_observed_redundant_influence_target_is_excluded_by_the_new_schema():
    raw=(ROOT/'tests/fixtures/adjudication/influence_target_response.json').read_text()
    with pytest.raises(ValueError,match='Ação do Mundo inválida'):
        parse_world_plan(raw)
    value=json.loads(raw)
    action=value['reactions'][0]['actions'][0]
    assert action['operation']=='influence' and action['target_id']=='player' and action['memory_ids']==[]
    action['target_id']=None
    assert parse_world_plan(json.dumps(value)).reactions[0].actions[0].influence.assessment.goal=='release'
    branch=next(b for b in ACTION_SCHEMA['anyOf'] if b['properties']['operation'].get('enum')==['influence'])
    assert branch['properties']['target_id']=={'type':'null'}

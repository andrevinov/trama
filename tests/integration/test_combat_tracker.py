"""Iniciativa e pendências da UI com sessão, recursos e turnos reais; sem rede."""

from copy import deepcopy
from types import SimpleNamespace

import pygame
import pytest

from conftest import sourced_plan
from trama.application.combat_tracker import combat_tracker_view
from trama.application.dialogue import Speech
from trama.application.game_flow import GameFlow
from trama.application.intents import ActionPlan, MovementIntent, MovementSegment, RuleIntent
from trama.application.scenarios import build_session
from trama.application.travel import TravelExecutor
from trama.application.world import WorldAction, WorldPlan
from trama.application.world_resolution import WorldExecutor
from trama.spatial import Position
from trama.ui.movement_window import MovementWindow, WINDOW_SIZE, BACKGROUND


@pytest.fixture
def screen(monkeypatch):
    monkeypatch.setenv('SDL_VIDEODRIVER','dummy')
    pygame.display.init()
    pygame.font.init()
    yield pygame.display.set_mode(WINDOW_SIZE)
    pygame.quit()


def game(roller, *, count=1, guard=(5,3)):
    session=build_session(dict(width=20,height=8,start=[2,3],creatures=[
        dict(id=f'g{i}',name=f'Guarda {i}',position=[guard[0]+i-1,guard[1]]) for i in range(1,count+1)]),roller=roller)
    return GameFlow(session)


def start(flow):
    flow.session.execute(RuleIntent('start_combat'))
    return combat_tracker_view(flow)


def row(view,id):
    return next(e for e in view['entries'] if e['id']==id)


def test_tracker_only_exists_during_combat_and_shows_real_initiative(dice,screen):
    flow=game(dice(20,19,10))
    window=MovementWindow(flow.session,None,'local',flow=flow)
    assert combat_tracker_view(flow) is None
    assert window.conversation_rect==pygame.Rect(550,252,458,438)
    view=start(flow)
    assert [(e['id'],e['initiative'],e['phase']) for e in view['entries']]==[
        ('player',21,'current'),('g1',11,'upcoming')]
    assert view['round']==1 and 'Sua vez' in view['pending']
    before=deepcopy((flow.session.encounter.states,flow.session.encounter.budgets,flow.session.state))
    for tab in ('Jogo','Ficha','NPCs'):
        window.active_tab=tab
        window.draw(screen)
        rect=window.turn_panel.rect(view)
        assert rect.bottom<window.conversation_rect.top
        assert window.conversation_rect.bottom<window.input_rect.top
        assert screen.get_at((rect.x+4,rect.centery))[:3]!=BACKGROUND
    assert (flow.session.encounter.states,flow.session.encounter.budgets,flow.session.state)==before
    WorldExecutor(flow.session).execute(WorldAction('g1','end_conflict','O confronto terminou.'))
    assert combat_tracker_view(flow) is None and window.conversation_rect.y==252
    flow.session.reset()
    assert combat_tracker_view(flow) is None and window.conversation_rect.y==252


def test_resources_follow_actual_movement_action_bonus_and_surge(dice):
    flow=game(dice(20,19,10,1,1))
    start(flow)
    session=flow.session
    session.execute(MovementIntent((MovementSegment('east',2),),False,''))
    session.execute(RuleIntent('second_wind'))
    session.execute(RuleIntent('attack','g1','unarmed'))
    session.execute(RuleIntent('action_surge'))
    current=row(combat_tracker_view(flow),'player')
    assert current['movement_meters']==6
    assert current['normal_action_used'] and current['action_available'] and current['extra_actions']==1
    assert not current['bonus_available'] and current['reaction_available'] and current['interaction_available']


def test_actor_phases_and_npc_movement_refresh_when_the_round_advances(dice):
    flow=game(dice(20,19,10))
    start(flow)
    session=flow.session
    session.execute(RuleIntent('end_turn'))
    view=combat_tracker_view(flow)
    assert row(view,'player')['phase']=='finished' and row(view,'g1')['phase']=='current'
    assert 'Guarda 1' in view['pending']
    WorldExecutor(session).execute(WorldAction('g1','move','O guarda anda.',destination=Position(7,3)))
    assert row(combat_tracker_view(flow),'g1')['movement_meters']==6
    session.next_turn()
    view=combat_tracker_view(flow)
    assert view['round']==2 and row(view,'player')['phase']=='current'
    assert row(view,'player')['action_available'] and row(view,'player')['movement_meters']==9
    assert row(view,'g1')['phase']=='upcoming'


@pytest.mark.parametrize('accept',[False,True])
def test_opportunity_is_an_explicit_pending_decision_and_keeps_the_npc_turn(dice,accept):
    flow=game(dice(20,19,10,1),guard=(3,3))
    start(flow)
    flow.session.execute(RuleIntent('end_turn'))
    WorldExecutor(flow.session).execute(WorldAction('g1','move','O guarda tenta sair.',destination=Position(6,3)))
    view=combat_tracker_view(flow)
    assert flow.session.pending_opportunity is not None
    assert view['pending']=='Você: decidir o ataque de oportunidade.'
    assert row(view,'g1')['phase']=='current' and row(view,'player')['reaction_available']
    TravelExecutor(flow.session).resolve(accept)
    resolved=combat_tracker_view(flow)
    assert 'ataque de oportunidade' not in resolved['pending']
    assert row(resolved,'player')['reaction_available'] is not accept
    assert row(resolved,'g1')['phase']=='current'


def test_a_provider_request_is_reported_without_advancing_the_turn(dice):
    flow=game(dice(20,19,10))
    start(flow)
    flow.interpreter=SimpleNamespace(interpret=lambda prompt,context:None)
    assert flow.submit('Aguardo.')
    view=combat_tracker_view(flow)
    assert view['pending']=='Interpretando sua ação…' and view['active_id']=='player'
    request=flow.pending_request
    flow.receive(request.id,ValueError('Falha local do provedor.'))
    assert combat_tracker_view(flow)['pending']=='Falha na resposta. Aguardando nova entrada.'


def test_pending_labels_follow_the_real_flow_through_the_npc_turn_and_narration(dice):
    flow=game(dice(20,19,10))
    start(flow)
    flow.interpreter=SimpleNamespace(interpret=lambda prompt,context:sourced_plan(
        ActionPlan((RuleIntent('end_turn'),)),prompt))
    flow.world_director=SimpleNamespace(decide=lambda context:WorldPlan())
    flow.narrator=SimpleNamespace(narrate=lambda context:Speech(on='É sua vez novamente.'))
    assert flow.submit('Encerro meu turno.')
    for stage,label in [('interpret','Interpretando'),('world','Aguardando resposta do Mundo'),
                        ('npc_turn','Resolvendo o turno de Guarda 1'),('narrate','Preparando a narração')]:
        request=flow.pending_request
        assert request.stage==stage and label in combat_tracker_view(flow)['pending']
        assert flow.receive(request.id,request.run())
    view=combat_tracker_view(flow)
    assert view['round']==2 and view['active_id']=='player' and 'Sua vez' in view['pending']


def test_hidden_actor_identity_initiative_and_resources_are_not_disclosed(dice):
    from test_perception import rooms
    session=build_session(rooms(start=(9,2),opened=True),roller=dice(1,2,20))
    flow=GameFlow(session)
    start(flow)
    WorldExecutor(session).execute(WorldAction('watcher','close','O vigia fecha a porta.','door'))
    view=combat_tracker_view(flow)
    assert view['active_id'] is None and view['active_name']=='Inimigo fora de visão'
    assert [e['id'] for e in view['entries']]==['player']
    assert 'Vigia' not in str(view) and 'watcher' not in str(view)
    assert 'fora de visão' in view['pending']


def test_scroll_is_independent_of_chat_and_follows_the_next_actor(dice,screen,monkeypatch):
    flow=game(dice(20,19,10),count=5)
    start(flow)  # Guardas idênticos compartilham o dado de iniciativa.
    window=MovementWindow(flow.session,None,'local',flow=flow)
    window.draw(screen)
    monkeypatch.setattr(pygame.mouse,'get_pos',lambda:(600,300))
    window.scroll=30
    window.handle_event(pygame.event.Event(pygame.MOUSEWHEEL,y=-3))
    assert window.turn_panel.offset==3 and window.scroll==30
    window.draw(screen)
    assert window.turn_panel.offset==3
    flow.session.execute(RuleIntent('end_turn'))
    window.draw(screen)
    assert window.turn_panel.offset==1
    assert window.conversation_rect.height>=240
    flow.session.reset()
    assert combat_tracker_view(flow) is None

"""Coordena movimento e reações, sem inserir combate no core de movimento."""

from dataclasses import dataclass, replace
from decimal import Decimal

from trama.application.modes import GameMode
from trama.characters import CharacterError
from trama.movement import MovementResult, MovementError, apply_movement, step_cost, MovementRequest
from trama.reactions import provokes_opportunity
from trama.spatial import Position
from trama.vision import field_of_view
import logging

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Opportunity:
    actor_id: str
    target_id: str
    origin: Position
    destination: Position
    weapon: str


@dataclass(frozen=True)
class TravelResult(MovementResult):
    reactions: tuple[dict, ...] = ()


class TravelExecutor:
    def __init__(self, session):
        self.session = session

    def _position(self, actor):
        return (self.session.state.position if actor == self.session.encounter.player_id
                else next(c.position for c in self.session.creatures if c.id == actor))

    def _opportunities(self, mover, origin, destination, protected=False):
        session, encounter = self.session, self.session.encounter
        if encounter.combat is None or protected:
            return []
        members = {e.id for e in encounter.combat.order}
        if mover not in members or encounter.states[mover].hp == 0:
            return []
        if mover == encounter.player_id:
            opponents = [c.id for c in session.creatures if c.hostile]
        else:
            creature = next(c for c in session.creatures if c.id == mover)
            opponents = [encounter.player_id] if creature.hostile else []
        result = []
        for actor in opponents:
            if actor not in members or encounter.states[actor].hp == 0 or encounter.budgets[actor].reaction_used:
                continue
            position = self._position(actor)
            if not provokes_opportunity(position, origin, destination, visible=True):
                continue
            visible = field_of_view(session.grid, position,
                                    opaque=session.scene.opaque if session.scene else session.grid.blocked,
                                    dark=session.scene.dark if session.scene else frozenset())
            if origin not in visible.visible:
                continue
            # Neste cenário, arma principal equipada; a política não escolhe táticas novas.
            weapons = encounter.sheets[actor].weapons
            weapon = weapons[0] if weapons else "unarmed"
            if weapon == "javelin" and not encounter.states[actor].javelins_remaining:
                weapon = "unarmed"
            opportunity = Opportunity(actor, mover, origin, destination, weapon)
            if opportunity != session.suppressed_opportunity:
                result.append(opportunity)
        return result

    def _attack(self, opportunity):
        session, encounter = self.session, self.session.encounter
        result = encounter.attack(opportunity.actor_id, opportunity.target_id, opportunity.weapon, opportunity=True)
        session.state = replace(session.state, speed_reduction_meters=encounter.player_sheet.speed_meters - encounter.speed(encounter.player_id))
        event = {**result.event, "weapon": opportunity.weapon, "perceptible": True,
                 "actor": encounter.sheets[opportunity.actor_id].name,
                 "before_leaving": [opportunity.origin.x + 1, opportunity.origin.y + 1],
                 "destination": [opportunity.destination.x + 1, opportunity.destination.y + 1]}
        logger.info("reaction.opportunity_resolved", extra={"data": event})
        return event

    def resolve(self, accept: bool) -> dict:
        session = self.session
        opportunity = session.pending_opportunity
        if type(accept) is not bool or opportunity is None:
            raise CharacterError("Não há ataque de oportunidade aguardando decisão.")
        if (self._position(opportunity.target_id) != opportunity.origin
                or opportunity not in self._opportunities(opportunity.target_id, opportunity.origin, opportunity.destination)):
            raise CharacterError("A oportunidade não é mais válida.")
        event = self._attack(opportunity) if accept else {
            "operation": "opportunity_declined", "actor_id": opportunity.actor_id,
            "target_id": opportunity.target_id, "changed": False, "perceptible": True,
            "summary": "Você deixou a criatura passar sem usar sua reação.",
        }
        session.suppressed_opportunity = opportunity
        session.pending_opportunity = None
        logger.info("reaction.player_decided", extra={"data": {"accepted": accept, "opportunity": opportunity}})
        return event

    def _commit(self, actor, state):
        if actor == self.session.encounter.player_id:
            self.session.state = state
        else:
            self.session.npc_movement[actor] = state
            self.session.creatures = tuple(replace(c, position=state.position) if c.id == actor else c
                                           for c in self.session.creatures)

    def run(self, actor, grid, state, request) -> MovementResult:
        session, encounter = self.session, self.session.encounter
        if session.pending_opportunity is not None:
            raise MovementError("Resolva o ataque de oportunidade pendente antes de continuar.")
        turn_based = session.mode == GameMode.TURN_BASED
        if turn_based:
            state = replace(state, speed_reduction_meters=encounter.sheets[actor].speed_meters - encounter.speed(actor))
        positions = (state.position, *request.path)
        if (not turn_based or not request.path or not any(
                self._opportunities(actor, origin, destination)
                for origin, destination in zip(positions, request.path))):
            result = apply_movement(grid, state, request, turn_based=turn_based)
            suppressed = session.suppressed_opportunity
            if suppressed and suppressed.target_id == actor and (suppressed.origin, suppressed.destination) in zip(result.path, result.path[1:]):
                session.suppressed_opportunity = None
            return result
        current = state
        path = [state.position]
        cost = protected_cost = Decimal("0")
        events = []
        reason = blocked = None
        stop_code = None
        for index, destination in enumerate(request.path):
            # Não provoca ao tentar um passo bloqueado ou sem orçamento.
            try:
                step = step_cost(grid, current.position, destination)
            except MovementError as error:
                reason, blocked = str(error), destination
                stop_code = error.code
                break
            dash = request.dash and index == 0
            if step > current.remaining_meters + (current.effective_speed_meters if dash else 0):
                result = apply_movement(grid, current, MovementRequest((destination,), dash))
                reason, blocked = result.stop_reason, result.blocked_position
                stop_code = result.stop_code
                break
            for opportunity in self._opportunities(actor, current.position, destination, protected=current.free_meters >= step):
                logger.info("reaction.opportunity_triggered", extra={"data": {"opportunity": opportunity}})
                if opportunity.actor_id == encounter.player_id and not session.auto_opportunity:
                    session.pending_opportunity = opportunity
                    reason = f"{encounter.sheets[actor].name} vai sair do seu alcance. Use sua reação para atacar ou deixe passar."
                    blocked = destination
                    stop_code = "opportunity_pending"
                    break
                events.append(self._attack(opportunity))
                if encounter.states[actor].hp == 0:
                    reason, blocked = "Movimento interrompido: a criatura ficou com 0 PV antes de sair do alcance.", destination
                    stop_code = "zero_hp"
                    break
            if reason:
                break
            current = replace(current, speed_reduction_meters=encounter.sheets[actor].speed_meters - encounter.speed(actor))
            result = apply_movement(grid, current, MovementRequest((destination,), dash))
            current = result.state
            self._commit(actor, current)
            path.extend(result.path[1:])
            cost += result.cost_meters
            protected_cost += result.protected_meters
            session.suppressed_opportunity = None
            if result.stop_reason:
                reason, blocked = result.stop_reason, result.blocked_position
                stop_code = result.stop_code
                break
        self._commit(actor, current)
        return TravelResult(current, tuple(path), cost, reason, blocked, protected_cost, tuple(events), stop_code=stop_code)

"""Coordena intenções e estado: movimento, ações, visão e criaturas."""

from dataclasses import replace
from decimal import Decimal

from trama.movement import (
    Grid, MovementError, MovementRequest, MovementResult, MovementState,
    Position, apply_movement,
)
from trama.scene import Scene
from trama.application.intents import (
    DIRECTIONS, DoorIntent, PlayerIntent, MovementIntent,
)
from trama.application.routing import path_to
from trama.actions import ActionBudget, ActionError, DoorActionResult, operate_door
from trama.creatures import Creature
from trama.vision import Visibility, field_of_view, line_of_sight
from trama.application.context import build_context
from trama.distances import format_meters


class GameSession:
    def __init__(
        self, grid: Grid, initial_state: MovementState, scene: Scene | None = None,
        creatures: tuple[Creature, ...] = (),
    ) -> None:
        if not grid.contains(initial_state.position) or initial_state.position in grid.blocked:
            raise ValueError("O personagem deve começar em uma casa livre do mapa.")
        self.grid = grid
        if scene is not None and scene.grid != grid:
            raise ValueError("O cenário e a sessão devem usar a mesma grade.")
        self.scene = scene
        self.initial_scene = scene
        self.creatures = creatures
        if (len({c.id for c in creatures}) != len(creatures)
                or len({c.position for c in creatures}) != len(creatures)
                or any(not grid.contains(c.position) or c.position in grid.blocked
                       or c.position == initial_state.position for c in creatures)):
            raise ValueError("Criaturas devem ocupar casas livres e distintas.")
        self.budget = ActionBudget(action_used=initial_state.dash_used)
        self._vision_key = None
        self._visibility = Visibility(frozenset())
        self.initial_state = initial_state
        self.state = initial_state
        self.last_path: tuple[Position, ...] = ()

    @property
    def visibility(self) -> Visibility:
        key = (self.state.position, self.grid, self.scene)
        if key != self._vision_key:
            self._visibility = field_of_view(
                self.grid, self.state.position,
                opaque=self.scene.opaque if self.scene else self.grid.blocked,
                dim=self.scene.dim if self.scene else frozenset(),
                dark=self.scene.dark if self.scene else frozenset(),
            )
            self._vision_key = key
        return self._visibility

    def interpreter_context(self) -> dict:
        return build_context(self.grid, self.state, self.scene, self.creatures,
                             self.visibility, self.budget)

    def _movement_grid(self) -> Grid:
        # Guardas Médios hostis e conscientes: não se atravessa o espaço deles.
        return replace(self.grid, blocked=self.grid.blocked | frozenset(c.position for c in self.creatures))

    def execute(self, intent: PlayerIntent) -> MovementResult | DoorActionResult:
        if isinstance(intent, DoorIntent):
            return self._operate_door(intent)
        if intent.clarification:
            raise MovementError(intent.clarification)
        dash_requested = intent.dash
        if dash_requested and self.budget.action_used:
            intent = replace(intent, dash=False)
        grid = self._movement_grid()
        if intent.target_id is not None:
            if self.scene is None:
                raise MovementError("Este mapa não tem destinos nomeados.")
            path = path_to(self.scene, self.state.position, intent.target_id, grid)
            if not path and not intent.dash:
                return self._explain_stop(
                    MovementResult(self.state, (self.state.position,), Decimal("0")),
                    dash_requested and not intent.dash,
                )
            result = apply_movement(grid, self.state, MovementRequest(path, intent.dash))
            self.state = result.state
            self.last_path = result.path
            if intent.dash and result.state.dash_used:
                self.budget = self.budget.spend_action()
            return self._explain_stop(result, dash_requested and not intent.dash)
        position = self.state.position
        path = []
        remainder = Decimal("0")
        for segment in intent.segments:
            dx, dy = DIRECTIONS[segment.direction]
            for _ in range(segment.squares):
                position = Position(position.x + dx, position.y + dy)
                path.append(position)
            if segment.remainder_meters:
                remainder = segment.remainder_meters
                break
        if not path and remainder:
            return MovementResult(self.state, (self.state.position,), Decimal("0"),
                                  "A distância pedida é menor que uma casa de 1,5 m.")
        if not path and not intent.dash:
            raise MovementError("O pedido não contém movimento.")
        result = apply_movement(grid, self.state, MovementRequest(tuple(path), intent.dash))
        self.state = result.state
        self.last_path = result.path
        if intent.dash and result.state.dash_used:
            self.budget = self.budget.spend_action()
        if remainder and result.stop_reason is None:
            result = replace(result, stop_reason=(
                f"Restaram {format_meters(remainder)} do pedido: a grade só permite casas inteiras de 1,5 m."
            ))
        return self._explain_stop(result, dash_requested and not intent.dash)

    def _explain_stop(self, result: MovementResult, dash_unavailable: bool) -> MovementResult:
        reason = result.stop_reason
        if result.blocked_position is not None and self.scene is not None:
            passage = next((p for p in self.scene.passages if p.position == result.blocked_position), None)
            if passage is not None and not passage.is_open:
                reason = f"{passage.name} está fechada e impede a passagem."
            creature = next((c for c in self.creatures if c.position == result.blocked_position
                             and c.position in self.visibility.visible), None)
            if creature is not None:
                reason = f"{creature.name} ocupa a próxima casa e impede a passagem."
        if dash_unavailable:
            note = "Dash indisponível: a ação do turno já foi usada; utilizei somente o movimento restante."
            reason = f"{reason} {note}" if reason else note
        return replace(result, stop_reason=reason)

    def _operate_door(self, intent: DoorIntent) -> DoorActionResult:
        if self.scene is None:
            raise ActionError("Este mapa não tem portas ou grades.")
        passage = next((p for p in self.scene.passages if p.id == intent.target_id), None)
        if passage is None:
            raise ActionError("A passagem informada não existe neste mapa.")
        origin, target = self.state.position, passage.position
        adjacent = max(abs(origin.x - target.x), abs(origin.y - target.y)) <= 1
        reachable = adjacent and line_of_sight(origin, target, self.scene.opaque)
        result = operate_door(
            intent.operation, is_open=passage.is_open, locked=passage.locked,
            in_reach=reachable,
            occupied=target == origin or any(c.position == target for c in self.creatures),
            budget=self.budget,
        )
        if result.changed:
            self.scene = self.scene.with_passage(intent.target_id, result.is_open)
            self.grid = self.scene.grid
            self.budget = result.budget
        return result

    def next_turn(self) -> None:
        self.state = self.state.next_turn()
        self.budget = ActionBudget()

    def reset(self) -> None:
        self.state = self.initial_state
        self.scene = self.initial_scene
        if self.scene is not None:
            self.grid = self.scene.grid
        self.budget = ActionBudget(action_used=self.initial_state.dash_used)
        self.last_path = ()

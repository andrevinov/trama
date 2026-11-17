"""Geometria, passagens e objetos; sem regras de turno ou visualização."""

from dataclasses import dataclass, replace
import logging
from trama.spatial import Grid, Position

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Attachment:
    surface: str = "floor"
    side: str | None = None

    def __post_init__(self) -> None:
        if (self.surface not in {"floor", "wall"}
                or (self.surface == "floor" and self.side is not None)
                or (self.surface == "wall" and self.side not in {"north", "east", "south", "west"})):
            raise ValueError("Fixação inválida: use floor sem lado ou wall com lado cardinal.")


@dataclass(frozen=True)
class SceneObject:
    id: str
    name: str
    position: Position
    kind: str = "object"
    attachment: Attachment = Attachment()
    blocks_movement: bool = False
    blocks_vision: bool = False
    description: str = ""

    def __post_init__(self) -> None:
        if (not self.id or not self.name or not self.kind
                or not isinstance(self.position, Position) or not isinstance(self.attachment, Attachment)
                or type(self.blocks_movement) is not bool or type(self.blocks_vision) is not bool):
            raise ValueError("Objeto de cenário inválido.")


@dataclass(frozen=True)
class Area:
    id: str
    name: str
    x: int
    y: int
    width: int
    height: int
    description: str = ""

    def __post_init__(self) -> None:
        if not self.id or not self.name or self.width <= 0 or self.height <= 0:
            raise ValueError("Um lugar deve ter identificador, nome e dimensões positivas.")

    @property
    def cells(self) -> frozenset[Position]:
        return frozenset(Position(x, y) for y in range(self.y, self.y + self.height)
                         for x in range(self.x, self.x + self.width))


@dataclass(frozen=True)
class Passage:
    id: str
    name: str
    kind: str
    position: Position
    is_open: bool
    locked: bool
    connects: tuple[str, str]
    description: str = ''

    def __post_init__(self) -> None:
        if (not self.id or not self.name or self.kind not in {"gate", "door"}
                or type(self.is_open) is not bool or type(self.locked) is not bool
                or len(self.connects) != 2 or self.connects[0] == self.connects[1]
                or not isinstance(self.description, str) or len(self.description) > 1000):
            raise ValueError("Passagem inválida.")
        if self.is_open and self.locked:
            raise ValueError("Uma passagem aberta não pode estar trancada.")


@dataclass(frozen=True)
class Scene:
    # grid contém somente terreno/passagens. movement_grid acrescenta objetos.
    grid: Grid
    areas: tuple[Area, ...]
    passages: tuple[Passage, ...]
    dim: frozenset[Position] = frozenset()
    dark: frozenset[Position] = frozenset()
    objects: tuple[SceneObject, ...] = ()

    def __post_init__(self) -> None:
        if self.dim & self.dark or any(not self.grid.contains(p) for p in self.dim | self.dark):
            raise ValueError("Iluminação fora do mapa ou sobreposta.")
        ids = [item.id for item in (*self.areas, *self.passages, *self.objects)]
        if len(ids) != len(set(ids)):
            raise ValueError("Os destinos devem ter identificadores únicos.")
        area_ids = {area.id for area in self.areas}
        occupied: set[Position] = set()
        for area in self.areas:
            if any(not self.grid.contains(p) for p in area.cells) or occupied & area.cells:
                raise ValueError("Lugares devem estar dentro do mapa e não podem se sobrepor.")
            occupied.update(area.cells)
        for passage in self.passages:
            if not set(passage.connects) <= area_ids or not self.grid.contains(passage.position):
                raise ValueError("Passagem fora do mapa ou com conexão desconhecida.")
            if passage.is_open == (passage.position in self.grid.blocked):
                raise ValueError("O bloqueio da passagem deve corresponder ao seu estado.")
            p = passage.position
            adjacent = {Position(p.x + dx, p.y + dy)
                        for dx, dy in ((0, -1), (-1, 0), (1, 0), (0, 1))}
            for area in self.areas:
                if area.id in passage.connects and not adjacent & area.cells:
                    raise ValueError("A passagem deve ser adjacente aos dois lugares conectados.")
        passage_cells = {p.position for p in self.passages}
        for obj in self.objects:
            if (not self.grid.contains(obj.position)
                    or (obj.position in self.grid.blocked and obj.position not in passage_cells)):
                raise ValueError("O objeto deve pertencer a uma casa de piso ou passagem do mapa.")
            if obj.attachment.surface == "wall":
                dx, dy = {"north": (0, -1), "east": (1, 0), "south": (0, 1), "west": (-1, 0)}[obj.attachment.side]
                wall = Position(obj.position.x + dx, obj.position.y + dy)
                if self.grid.contains(wall) and (wall not in self.grid.blocked or wall in passage_cells):
                    raise ValueError("Uma fixação na parede exige uma parede no lado indicado.")

    @classmethod
    def from_data(cls, data: dict) -> "Scene":
        areas = tuple(Area(**area) for area in data["areas"])
        passages = tuple(Passage(
            id=p["id"], name=p["name"], kind=p["kind"], position=Position(*p["position"]),
            is_open=p["is_open"], locked=p["locked"], connects=tuple(p["connects"]), description=p.get('description', ''),
        ) for p in data["passages"])
        objects = tuple(SceneObject(
            id=o["id"], name=o["name"], position=Position(*o["position"]),
            kind=o.get("kind", "object"), attachment=Attachment(**o.get("attachment", {})),
            blocks_movement=o.get("blocks_movement", False), blocks_vision=o.get("blocks_vision", False),
            description=o.get("description", ""),
        ) for o in data.get("objects", []))
        floor = frozenset(p for area in areas for p in area.cells)
        floor |= frozenset(p.position for p in passages if p.is_open)
        blocked = frozenset(Position(x, y) for y in range(data["height"])
                            for x in range(data["width"])) - floor
        grid = Grid(data["width"], data["height"], blocked)
        result = cls(grid, areas, passages,
                   frozenset(Position(*p) for p in data.get("dim", [])),
                   frozenset(Position(*p) for p in data.get("dark", [])), objects)
        logger.info("map.loaded", extra={"data": {"width": grid.width, "height": grid.height,
                    "areas": [a.id for a in areas], "passages": [p.id for p in passages],
                    "objects": [o.id for o in objects]}})
        logger.debug("map.objects_loaded", extra={"data": {"objects": objects}})
        return result

    @property
    def movement_blockers(self) -> frozenset[Position]:
        return frozenset(o.position for o in self.objects if o.blocks_movement)

    @property
    def movement_grid(self) -> Grid:
        blockers = self.movement_blockers
        return (replace(self.grid, blocked=self.grid.blocked | blockers,
                        difficult=self.grid.difficult - blockers) if blockers else self.grid)

    @property
    def open_passages_grid(self) -> Grid:
        """Previsão de rota: abre passagens, preservando obstáculos de objetos."""
        blocked = self.grid.blocked - frozenset(p.position for p in self.passages)
        return replace(self.movement_grid, blocked=blocked | self.movement_blockers)

    @property
    def opaque(self) -> frozenset[Position]:
        # Grades impedem passagem quando fechadas, mas permitem ver pelas barras.
        terrain = self.grid.blocked - frozenset(p.position for p in self.passages if p.kind == "gate")
        return terrain | frozenset(o.position for o in self.objects if o.blocks_vision)

    def with_passage(self, passage_id: str, is_open: bool) -> "Scene":
        passage = next((p for p in self.passages if p.id == passage_id), None)
        if passage is None:
            raise ValueError("Passagem desconhecida.")
        updated = replace(passage, is_open=is_open)
        blocked = (self.grid.blocked - {passage.position} if is_open
                   else self.grid.blocked | {passage.position})
        result = replace(self, grid=replace(self.grid, blocked=frozenset(blocked)),
                       passages=tuple(updated if p.id == passage_id else p for p in self.passages))
        logger.debug("map.passage_changed", extra={"data": {"passage_id": passage_id,
                     "before": passage, "after": updated}})
        return result

    def area_at(self, position: Position) -> Area | None:
        return next((area for area in self.areas if position in area.cells), None)

    def destination_cells(self, target_id: str) -> frozenset[Position]:
        blocked = self.movement_grid.blocked
        for area in self.areas:
            if area.id == target_id:
                return area.cells - blocked
        for passage in self.passages:
            if passage.id == target_id:
                p = passage.position
                # "Até" significa aproximar-se pelo lado alcançável, sem atravessar.
                return frozenset(
                    Position(p.x + dx, p.y + dy)
                    for dx, dy in ((0, -1), (-1, 0), (1, 0), (0, 1))
                    if self.grid.contains(Position(p.x + dx, p.y + dy))
                    and Position(p.x + dx, p.y + dy) not in blocked
                )
        for obj in self.objects:
            if obj.id == target_id:
                p = obj.position
                # Aproximação à casa do objeto ou vizinha, sem entrar em casas bloqueadas.
                return frozenset(Position(p.x + dx, p.y + dy)
                                 for dx, dy in ((0, 0), (0, -1), (-1, 0), (1, 0), (0, 1))
                                 if self.grid.contains(Position(p.x + dx, p.y + dy))
                                 and Position(p.x + dx, p.y + dy) not in blocked)
        raise ValueError("O destino informado não existe neste mapa.")


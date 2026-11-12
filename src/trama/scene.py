"""Lugares e passagens nomeados sobre a grade de movimento."""

from dataclasses import dataclass, replace
from trama.spatial import Grid, Position


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

    def __post_init__(self) -> None:
        if (not self.id or not self.name or self.kind not in {"gate", "door"}
                or type(self.is_open) is not bool or type(self.locked) is not bool
                or len(self.connects) != 2 or self.connects[0] == self.connects[1]):
            raise ValueError("Passagem inválida.")
        if self.is_open and self.locked:
            raise ValueError("Uma passagem aberta não pode estar trancada.")


@dataclass(frozen=True)
class Scene:
    grid: Grid
    areas: tuple[Area, ...]
    passages: tuple[Passage, ...]
    dim: frozenset[Position] = frozenset()
    dark: frozenset[Position] = frozenset()

    def __post_init__(self) -> None:
        if self.dim & self.dark or any(not self.grid.contains(p) for p in self.dim | self.dark):
            raise ValueError("Iluminação fora do mapa ou sobreposta.")
        ids = [item.id for item in (*self.areas, *self.passages)]
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

    @classmethod
    def from_data(cls, data: dict) -> "Scene":
        areas = tuple(Area(**area) for area in data["areas"])
        passages = tuple(Passage(
            id=p["id"], name=p["name"], kind=p["kind"], position=Position(*p["position"]),
            is_open=p["is_open"], locked=p["locked"], connects=tuple(p["connects"]),
        ) for p in data["passages"])
        floor = frozenset(p for area in areas for p in area.cells)
        floor |= frozenset(p.position for p in passages if p.is_open)
        blocked = frozenset(Position(x, y) for y in range(data["height"])
                            for x in range(data["width"])) - floor
        grid = Grid(data["width"], data["height"], blocked)
        return cls(grid, areas, passages,
                   frozenset(Position(*p) for p in data.get("dim", [])),
                   frozenset(Position(*p) for p in data.get("dark", [])))

    @property
    def opaque(self) -> frozenset[Position]:
        # Grades impedem passagem quando fechadas, mas permitem ver pelas barras.
        return self.grid.blocked - frozenset(p.position for p in self.passages if p.kind == "gate")

    def with_passage(self, passage_id: str, is_open: bool) -> "Scene":
        passage = next((p for p in self.passages if p.id == passage_id), None)
        if passage is None:
            raise ValueError("Passagem desconhecida.")
        updated = replace(passage, is_open=is_open)
        blocked = (self.grid.blocked - {passage.position} if is_open
                   else self.grid.blocked | {passage.position})
        return replace(self, grid=replace(self.grid, blocked=frozenset(blocked)),
                       passages=tuple(updated if p.id == passage_id else p for p in self.passages))

    def area_at(self, position: Position) -> Area | None:
        return next((area for area in self.areas if position in area.cells), None)

    def destination_cells(self, target_id: str) -> frozenset[Position]:
        for area in self.areas:
            if area.id == target_id:
                return area.cells - self.grid.blocked
        for passage in self.passages:
            if passage.id == target_id:
                p = passage.position
                # "Até" significa aproximar-se pelo lado alcançável, sem atravessar.
                return frozenset(
                    Position(p.x + dx, p.y + dy)
                    for dx, dy in ((0, -1), (-1, 0), (1, 0), (0, 1))
                    if self.grid.contains(Position(p.x + dx, p.y + dy))
                    and Position(p.x + dx, p.y + dy) not in self.grid.blocked
                )
        raise ValueError("O destino informado não existe neste mapa.")


"""Gatilho de oportunidade; PHB 2024, Playing the Game / Opportunity Attacks.

O ataque precede a saída do alcance. Decisão, visão, recursos e dano são
coordenados pela aplicação; este predicado não conhece fichas nem interface.
"""

from trama.spatial import Position


def provokes_opportunity(attacker: Position, origin: Position, destination: Position,
                         *, visible: bool, protected: bool = False,
                         uses_movement: bool = True, reach: int = 1) -> bool:
    def distance(position):
        return max(abs(position.x - attacker.x), abs(position.y - attacker.y))
    return (visible and uses_movement and not protected
            and 0 < distance(origin) <= reach < distance(destination))

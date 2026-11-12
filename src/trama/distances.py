"""Distâncias em metros, com conversão de entrada na convenção de D&D.

    5 pés = 1,5 m. É a convenção do jogo, não a conversão física do SI.
    Decimal evita erros de ponto flutuante nos saldos e na divisão em casas.
"""

from decimal import Decimal

CELL_METERS = Decimal("1.5")
METERS_PER_FOOT = Decimal("0.3")


def meters(value: int | float | Decimal) -> Decimal:
    """Normaliza uma distância finita e não negativa já expressa em metros."""
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ValueError("A distância deve ser um número em metros.")
    result = Decimal(str(value))
    if not result.is_finite() or result < 0:
        raise ValueError("A distância deve ser finita e não negativa.")
    return result


def feet_to_meters(value: int | float | Decimal) -> Decimal:
    """Converte pés de D&D para metros antes de executar as regras."""
    return meters(value) * METERS_PER_FOOT


def to_meters(value: int | float | Decimal, unit: str = "meters") -> Decimal:
    if unit == "meters":
        return meters(value)
    if unit == "feet":
        return feet_to_meters(value)
    if unit == "squares":
        return meters(value) * CELL_METERS
    raise ValueError("Unidade de distância desconhecida.")


def meters_to_squares(value: int | float | Decimal) -> int:
    distance = meters(value)
    squares = distance / CELL_METERS
    if squares != squares.to_integral_value():
        raise ValueError("A distância deve corresponder a casas inteiras de 1,5 m.")
    return int(squares)


def format_meters(value: int | float | Decimal) -> str:
    text = format(meters(value), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text.replace(".", ",") + " m"

"""
validation.py - Validación de entradas (codificación defensiva)
================================================================
Todo dato que llega desde fuera del núcleo del juego (teclado, API HTTP, línea
de comandos o archivo del récord) se verifica aquí en tipo, formato y rango
antes de usarse. Las funciones son puras: no tienen efectos secundarios y
lanzan ValueError con un mensaje claro cuando la entrada no es válida.
"""

from config import (
    DIRECTION_ALIASES,
    DIRECTIONS,
    MAX_BOARD_SIZE,
    MIN_BOARD_SIZE,
)

MIN_PORT = 1
MAX_PORT = 65535


def is_strict_int(value: object) -> bool:
    """True si el valor es un entero de verdad (bool es subclase de int en Python)."""
    return isinstance(value, int) and not isinstance(value, bool)


def normalize_direction(value: object) -> str:
    """
    Convierte una dirección recibida en una de: 'left', 'right', 'up', 'down'.

    Acepta los alias en español, ignora mayúsculas y espacios.

    :raises ValueError: si el valor no es texto o no es una dirección conocida.
    """
    if not isinstance(value, str):
        received = type(value).__name__
        raise ValueError(f"La dirección debe ser texto, se recibió {received}")
    direction = value.strip().lower()
    direction = DIRECTION_ALIASES.get(direction, direction)
    if direction not in DIRECTIONS:
        raise ValueError(f"Dirección inválida: {value!r}")
    return direction


def validate_board_size(value: object) -> int:
    """Verifica que el tamaño del tablero sea un entero entre los límites permitidos."""
    if not is_strict_int(value) or not MIN_BOARD_SIZE <= value <= MAX_BOARD_SIZE:
        raise ValueError(
            f"El tamaño del tablero debe ser un entero entre {MIN_BOARD_SIZE} "
            f"y {MAX_BOARD_SIZE}"
        )
    return value


def validate_score(value: object) -> int:
    """Verifica que una puntuación sea un entero no negativo."""
    if not is_strict_int(value) or value < 0:
        raise ValueError("La puntuación debe ser un entero no negativo")
    return value


def validate_port(value: object) -> int:
    """
    Verifica un número de puerto TCP. Acepta enteros o texto con dígitos
    (como llega desde la línea de comandos).
    """
    if isinstance(value, str) and value.strip().isdigit():
        value = int(value.strip())
    if not is_strict_int(value) or not MIN_PORT <= value <= MAX_PORT:
        raise ValueError(f"El puerto debe ser un entero entre {MIN_PORT} y {MAX_PORT}")
    return value

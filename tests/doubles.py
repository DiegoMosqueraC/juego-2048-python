"""
doubles.py - Dobles de prueba
=============================
Sustituyen dependencias reales para que las pruebas sean rápidas, aisladas y
repetibles:

- FakeHighscoreStorage (fake + spy): guarda el récord en memoria en vez de en
  disco y además registra cada llamada a save() para poder verificarla.
- StubRandom (stub): devuelve respuestas preparadas en lugar de valores al azar,
  para decidir exactamente dónde y con qué valor aparece la próxima ficha.
"""


class FakeHighscoreStorage:
    """Implementación en memoria de HighscoreStorage que registra los guardados."""

    def __init__(self, initial: int = 0):
        self.value = initial
        self.saved_values: list[int] = []
        self.load_calls = 0

    def load(self) -> int:
        self.load_calls += 1
        return self.value

    def save(self, value: int) -> None:
        self.value = value
        self.saved_values.append(value)


class StubRandom:
    """
    Generador "aleatorio" controlado.

    :param cells: celdas que devolverá choice(), en orden; si se agotan, elige la
                  primera celda disponible.
    :param draws: valores que devolverá random(); 0.95 produce un 2 y 0.05 un 4.
    """

    def __init__(self, cells=None, draws=None):
        self.cells = list(cells or [])
        self.draws = list(draws or [])
        self.choice_calls = 0

    def choice(self, options):
        self.choice_calls += 1
        if self.cells:
            cell = self.cells.pop(0)
            assert cell in options, f"La celda {cell} no está vacía"
            return cell
        return options[0]

    def random(self) -> float:
        return self.draws.pop(0) if self.draws else 0.95

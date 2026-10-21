"""
conftest.py - Accesorios (fixtures) compartidos por toda la suite de pruebas.

Centraliza la creación de partidas y del servidor HTTP para que cada prueba sea
rápida, independiente y repetible (principios F.I.R.S.T.): ninguna prueba toca
el archivo real del récord ni depende del azar sin control.
"""

import random
import threading

import pytest

from config import DEFAULT_BOARD_SIZE
from doubles import FakeHighscoreStorage
from logic import Game2048
from web_ui import create_server


@pytest.fixture
def storage():
    """Récord en memoria (doble de prueba "fake"), nuevo para cada prueba."""
    return FakeHighscoreStorage()


@pytest.fixture
def make_game(storage):
    """
    Fábrica de partidas aisladas.

    :param grid: tablero inicial opcional (define también el tamaño).
    :param rng: generador aleatorio; por defecto uno con semilla fija.
    """

    def factory(grid=None, score=0, size=DEFAULT_BOARD_SIZE, rng=None):
        rng = rng if rng is not None else random.Random(2048)
        if grid is None:
            return Game2048(size=size, storage=storage, rng=rng)
        rows = [list(row) for row in grid]
        return Game2048.from_grid(rows, score=score, storage=storage, rng=rng)

    return factory


@pytest.fixture
def api_server(make_game):
    """Levanta el servidor web real en un puerto libre y lo detiene al terminar."""
    server = create_server(make_game(), port=0)
    # Un intervalo de sondeo corto hace que shutdown() termine casi de inmediato.
    thread = threading.Thread(target=server.serve_forever, args=(0.05,), daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()

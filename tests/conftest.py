"""
conftest.py - Accesorios (fixtures) compartidos por toda la suite de pruebas.

Centraliza la creación de partidas y del servidor HTTP para que cada prueba sea
rápida, independiente y repetible (principios F.I.R.S.T.): ninguna prueba toca
el archivo real del récord ni depende del azar sin control.
"""

import random
import threading
from http.server import HTTPServer

import pytest

from logic import Game2048


@pytest.fixture(autouse=True)
def fixed_random_seed():
    """Fija la semilla global para que las fichas aleatorias sean reproducibles."""
    random.seed(2048)


@pytest.fixture
def make_game(tmp_path):
    """Fábrica de partidas aisladas: el récord se guarda en un directorio temporal."""

    def factory(grid=None, score=0):
        game = Game2048(highscore_file=str(tmp_path / "highscore.json"))
        if grid is not None:
            game.grid = [list(row) for row in grid]
            game.score = score
        return game

    return factory


@pytest.fixture
def api_server(tmp_path, monkeypatch):
    """Levanta el servidor web real en un puerto libre y lo detiene al terminar."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("JUEGO2048_DATA_DIR", str(tmp_path))
    import web_ui

    server = HTTPServer(("127.0.0.1", 0), web_ui.Game2048HTTPHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()

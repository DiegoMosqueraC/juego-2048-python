"""
test_regresion.py - Pruebas de regresión de los fallos de la versión base.

Cada prueba reproduce un fallo registrado en docs/REGISTRO_FALLOS.md y lleva su
identificador (BUG-xx) en el nombre, de modo que se conserve la trazabilidad
fallo -> prueba -> corrección (commit). Se escribieron ANTES de corregir el
código (fase roja de TDD) y deben seguir pasando en todas las versiones futuras.
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from helpers import send_raw, send_request
from logic import Game2048

PROJECT_DIR = Path(__file__).resolve().parent.parent
EMPTY_ROW = [0, 0, 0, 0]


# -----------------------------------------------------------------------------
# BUG-01: move() no valida el tipo de la dirección recibida
# -----------------------------------------------------------------------------

@pytest.mark.parametrize("direction", [None, 5, 3.5, ["left"], {"to": "left"}])
def test_bug01_move_rejects_non_text_direction(make_game, direction):
    """Una dirección que no es texto debe producir ValueError, no AttributeError."""
    game = make_game()
    with pytest.raises(ValueError):
        game.move(direction)


# -----------------------------------------------------------------------------
# BUG-02: la API acepta cuerpos malformados y se cae
# -----------------------------------------------------------------------------

@pytest.mark.parametrize(
    "body", [[1, 2], "left", 42, {"direction": 5}, b"{no es json", b"\xff\xfe"]
)
def test_bug02_move_with_malformed_json_returns_400(api_server, body):
    """Un cuerpo inválido o con forma incorrecta responde 400 sin tumbar el hilo."""
    status, _, data = send_request(api_server, "POST", "/api/move", body=body)
    assert status == 400
    assert "error" in data
    # El servidor sigue atendiendo después del error.
    assert send_request(api_server, "GET", "/api/state")[0] == 200


def test_bug02_non_numeric_content_length_returns_400(api_server):
    raw = (
        b"POST /api/move HTTP/1.1\r\nHost: 127.0.0.1\r\n"
        b"Content-Type: application/json\r\nContent-Length: abc\r\n\r\n{}"
    )
    assert send_raw(api_server, raw) == 400


def test_bug02_oversized_body_is_rejected_with_413(api_server):
    """Un cuerpo enorme se rechaza sin intentar leerlo (protección ante DoS)."""
    raw = (
        b"POST /api/move HTTP/1.1\r\nHost: 127.0.0.1\r\n"
        b"Content-Type: application/json\r\nContent-Length: 10485760\r\n\r\n{}"
    )
    assert send_raw(api_server, raw) == 413


# -----------------------------------------------------------------------------
# BUG-03: la API local puede ser manipulada desde otros sitios web
# -----------------------------------------------------------------------------

def test_bug03_api_does_not_allow_any_origin(api_server):
    _, headers, _ = send_request(api_server, "GET", "/api/state")
    assert headers.get("Access-Control-Allow-Origin") != "*"


def test_bug03_post_without_json_content_type_is_rejected(api_server):
    """Un formulario de otro sitio (text/plain) no debe poder reiniciar la partida."""
    status, _, _ = send_request(
        api_server, "POST", "/api/reset", body=b"",
        headers={"Content-Type": "text/plain"},
    )
    assert status == 415


def test_bug03_foreign_host_header_is_rejected(api_server):
    """Protección contra DNS rebinding: solo se aceptan nombres de host locales."""
    status, _, _ = send_request(
        api_server, "GET", "/api/state", headers={"Host": "atacante.example:80"}
    )
    assert status == 403


# -----------------------------------------------------------------------------
# BUG-04: las rutas de la API no admiten parámetros de consulta
# -----------------------------------------------------------------------------

def test_bug04_state_route_accepts_query_string(api_server):
    status, _, data = send_request(api_server, "GET", "/api/state?t=123")
    assert status == 200
    assert "grid" in data


# -----------------------------------------------------------------------------
# BUG-05 y BUG-06: estado de victoria inconsistente
# -----------------------------------------------------------------------------

def test_bug05_continue_before_winning_does_not_disable_victory(make_game):
    game = make_game(grid=[[1024, 1024, 0, 0], EMPTY_ROW, EMPTY_ROW, EMPTY_ROW])
    game.continue_playing()  # se invoca sin haber ganado (p. ej., POST /api/continue)
    game.move("left")
    assert game.won is True


def test_bug06_moves_are_blocked_while_victory_is_pending(make_game):
    game = make_game(grid=[[1024, 1024, 0, 0], EMPTY_ROW, EMPTY_ROW, EMPTY_ROW])
    game.move("left")
    assert game.won is True
    grid_after_win = [row[:] for row in game.grid]
    assert not game.move("down")
    assert game.grid == grid_after_win


# -----------------------------------------------------------------------------
# BUG-07: to_dict() expone el tablero interno por referencia
# -----------------------------------------------------------------------------

def test_bug07_to_dict_returns_a_copy_of_the_grid(make_game):
    game = make_game(grid=[[2, 0, 0, 0], EMPTY_ROW, EMPTY_ROW, EMPTY_ROW])
    state = game.to_dict()
    state["grid"][0][0] = 4096
    assert game.grid[0][0] == 2


# -----------------------------------------------------------------------------
# BUG-08 y BUG-09: persistencia del récord
# -----------------------------------------------------------------------------

def test_bug08_record_file_does_not_depend_on_working_directory(tmp_path, monkeypatch):
    data_dir = tmp_path / "datos"
    work_dir = tmp_path / "trabajo"
    work_dir.mkdir()
    monkeypatch.setenv("JUEGO2048_DATA_DIR", str(data_dir))
    monkeypatch.chdir(work_dir)

    game = Game2048()
    game.grid = [[2, 2, 0, 0], EMPTY_ROW, EMPTY_ROW, EMPTY_ROW]
    game.move("left")

    assert not (work_dir / "highscore.json").exists()
    saved = json.loads((data_dir / "highscore.json").read_text(encoding="utf-8"))
    assert saved["highscore"] == 4


@pytest.mark.parametrize(
    "stored_value, expected",
    [(-50, 0), (12.7, 0), ("abc", 0), (True, 0), (None, 0), (3132, 3132)],
)
def test_bug09_stored_record_is_validated(
    tmp_path, monkeypatch, stored_value, expected
):
    monkeypatch.setenv("JUEGO2048_DATA_DIR", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    (tmp_path / "highscore.json").write_text(
        json.dumps({"highscore": stored_value}), encoding="utf-8"
    )
    assert Game2048().highscore == expected


# -----------------------------------------------------------------------------
# BUG-10: el modo terminal no arranca en Windows (no existe el módulo _curses)
# -----------------------------------------------------------------------------

def test_bug10_terminal_module_loads_without_curses(monkeypatch):
    monkeypatch.setitem(sys.modules, "curses", None)
    spec = importlib.util.spec_from_file_location(
        "terminal_ui_sin_curses", PROJECT_DIR / "terminal_ui.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.CURSES_AVAILABLE is False


# -----------------------------------------------------------------------------
# BUG-11: los mensajes más anchos que la terminal no se mostraban
# -----------------------------------------------------------------------------

@pytest.mark.parametrize("width", [30, 45, 80])
def test_bug11_terminal_messages_fit_the_window_width(make_game, width):
    import terminal_ui

    game = make_game(grid=[[1024, 1024, 0, 0], EMPTY_ROW, EMPTY_ROW, EMPTY_ROW])
    game.move("left")  # victoria pendiente: el mensaje más largo del juego
    lines = terminal_ui.footer_lines(game, width)
    assert all(len(line) <= width for line in lines)
    assert "2048" in " ".join(lines)  # el aviso de victoria no se pierde

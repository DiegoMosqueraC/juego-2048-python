"""
test_terminal_ui.py - Pruebas de la interfaz de terminal
========================================================
- Las funciones que construyen el texto se prueban directamente.
- El modo básico se ejecuta con dobles de prueba: un lector de teclas que
  devuelve una secuencia preparada (stub) y una salida que registra lo impreso
  (spy).
- El modo curses se ejecuta con un módulo curses falso (fake) cuya pantalla
  lanza un error si se escribe fuera de la ventana, igual que curses real.
"""

import importlib.util
import sys
import types
from pathlib import Path

import pytest

import terminal_ui
from terminal_ui import (
    CELL_WIDTH,
    ESCAPE_KEY,
    apply_key,
    board_lines,
    board_width,
    footer_lines,
    header_lines,
    run_basic_terminal_game,
    status_message,
)

PROJECT_DIR = Path(__file__).resolve().parent.parent
EMPTY_ROW = [0, 0, 0, 0]


# --- Construcción del texto ----------------------------------------------------

def test_header_shows_score_and_record(make_game):
    game = make_game(grid=[[2, 2, 0, 0], EMPTY_ROW, EMPTY_ROW, EMPTY_ROW], score=12)
    game.highscore = 3132
    assert header_lines(game) == ["2048 en Python", "Puntuación: 12   Récord: 3132"]


def test_board_lines_have_the_expected_width(make_game):
    game = make_game(grid=[[2, 0, 0, 2048], EMPTY_ROW, EMPTY_ROW, EMPTY_ROW])
    lines = board_lines(game)
    assert len(lines) == 12
    assert all(len(line) == board_width(4) for line in lines)
    assert "2048" in lines[1]


def test_board_width_formula():
    assert board_width(4) == 4 * (CELL_WIDTH + 1) - 1


@pytest.mark.parametrize(
    "grid, over, expected",
    [
        ([[2, 0], [0, 0]], False, ""),
        ([[2, 4], [4, 2]], True, "Fin de la partida"),
    ],
)
def test_status_message(make_game, grid, over, expected):
    game = make_game(grid=grid)
    assert game.game_over is over
    assert status_message(game).startswith(expected)


def test_footer_without_status_only_has_help(make_game):
    lines = footer_lines(make_game(), 120)
    assert len(lines) == 1


# --- Teclas (partición: dirección, comando, salida, sin efecto) -----------------

@pytest.mark.parametrize("key", ["a", "d", "w", "s"])
def test_direction_keys_move(make_game, key):
    game = make_game(grid=[[0, 2, 0, 0], [0, 0, 0, 0], [0, 2, 0, 0], EMPTY_ROW])
    before = [row[:] for row in game.grid]
    assert apply_key(game, key) is True
    assert game.grid != before


def test_command_keys(make_game):
    game = make_game(grid=[[1024, 1024, 0, 0], EMPTY_ROW, EMPTY_ROW, EMPTY_ROW])
    apply_key(game, "a")
    assert game.awaiting_win_decision
    apply_key(game, "c")
    assert not game.awaiting_win_decision
    apply_key(game, "u")
    assert game.grid[0][:2] == [1024, 1024]
    apply_key(game, "r")
    assert game.score == 0


@pytest.mark.parametrize("key", ["q", ESCAPE_KEY])
def test_exit_keys(make_game, key):
    assert apply_key(make_game(), key) is False


def test_unknown_key_does_nothing(make_game):
    game = make_game()
    before = [row[:] for row in game.grid]
    assert apply_key(game, "x") is True
    assert game.grid == before


# --- Modo básico con dobles de prueba ------------------------------------------

def test_basic_mode_plays_until_the_player_quits(make_game):
    game = make_game(grid=[[2, 2, 0, 0], EMPTY_ROW, EMPTY_ROW, EMPTY_ROW])
    keys = iter(["a", "u", "a", "q"])  # stub: teclas preparadas
    screens = []  # spy: registra cada pantalla impresa
    run_basic_terminal_game(game, read_key=lambda: next(keys), output=screens.append,
                            width=40)
    assert len(screens) == 4
    assert "Puntuación: 4" in screens[-1]
    assert all(len(line) <= 40 for screen in screens for line
               in screen.splitlines() if not line.startswith(("┌", "│", "└")))


# --- Modo curses con un módulo falso (fake) ------------------------------------

class FakeCursesError(Exception):
    pass


class FakeScreen:
    """Pantalla de curses en memoria que valida los límites como curses real."""

    def __init__(self, keys, height=24, width=80):
        self.keys = list(keys)
        self.height = height
        self.width = width
        self.cells = {}

    def addstr(self, y, x, text, attr=0):
        if y >= self.height or x + len(text) > self.width:
            raise FakeCursesError(f"texto fuera de la ventana en la fila {y}")
        self.cells[y] = self.cells.get(y, "").ljust(x)[:x] + text

    def getmaxyx(self):
        return self.height, self.width

    def getch(self):
        return self.keys.pop(0)

    def erase(self):
        self.cells = {}

    def refresh(self):
        pass

    def keypad(self, flag):
        pass

    def text(self):
        return "\n".join(self.cells[row] for row in sorted(self.cells))


def build_fake_curses():
    fake = types.ModuleType("curses")
    fake.error = FakeCursesError
    for index, name in enumerate(["BLACK", "RED", "GREEN", "YELLOW", "BLUE",
                                  "MAGENTA", "CYAN", "WHITE"]):
        setattr(fake, f"COLOR_{name}", index)
    fake.KEY_LEFT, fake.KEY_RIGHT, fake.KEY_UP, fake.KEY_DOWN = 260, 261, 259, 258
    fake.A_BOLD, fake.A_DIM, fake.A_NORMAL = 1, 2, 0
    fake.curs_set = lambda visibility: None
    fake.has_colors = lambda: True
    fake.start_color = lambda: None
    fake.use_default_colors = lambda: None
    fake.init_pair = lambda pair, fg, bg: None
    fake.color_pair = lambda pair: pair << 8
    fake.wrapper = lambda function: function(FakeScreen([ord("q")]))
    return fake


@pytest.fixture
def curses_ui(monkeypatch):
    """Carga terminal_ui con el módulo curses falso, sin afectar a otras pruebas."""
    monkeypatch.setitem(sys.modules, "curses", build_fake_curses())
    spec = importlib.util.spec_from_file_location("terminal_ui_fake_curses",
                                                  PROJECT_DIR / "terminal_ui.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_curses_mode_draws_the_board_and_reacts_to_arrows(curses_ui, make_game):
    game = make_game(grid=[[0, 0, 2, 2], EMPTY_ROW, EMPTY_ROW, EMPTY_ROW])
    screen = FakeScreen(keys=[260, ord("q")])  # flecha izquierda y salir
    curses_ui.CursesGame(screen, game).run()
    assert game.grid[0][0] == 4
    assert "2048 en Python" in screen.text()


@pytest.mark.parametrize("width", [37, 50, 80])
def test_curses_mode_fits_messages_in_narrow_windows(curses_ui, make_game, width):
    """BUG-11 en el modo curses: nada se escribe fuera de la ventana."""
    game = make_game(grid=[[2, 4, 2, 4], [4, 2, 4, 2], [2, 4, 2, 4], [4, 2, 4, 2]])
    screen = FakeScreen(keys=[ord("q")], height=24, width=width)
    curses_ui.CursesGame(screen, game).run()
    assert "Fin de la partida" in screen.text().replace("\n", " ")


def test_curses_mode_asks_for_a_bigger_window(curses_ui, make_game):
    screen = FakeScreen(keys=[ord("q")], height=10, width=30)
    curses_ui.CursesGame(screen, make_game()).run()
    assert "Agranda la ventana" in screen.text()


def test_launch_uses_curses_when_available(curses_ui, make_game, capsys):
    curses_ui.launch_terminal_game(make_game())
    assert "Gracias por jugar" in capsys.readouterr().out


def test_launch_falls_back_to_basic_mode(monkeypatch, make_game, capsys):
    monkeypatch.setattr(terminal_ui, "CURSES_AVAILABLE", False)
    monkeypatch.setattr(terminal_ui, "_read_basic_key", lambda: "q")
    terminal_ui.launch_terminal_game(make_game())
    output = capsys.readouterr().out
    assert "modo de texto básico" in output
    assert "Gracias por jugar" in output

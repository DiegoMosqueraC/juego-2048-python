"""
test_game.py - Pruebas unitarias de caja negra de Game2048
==========================================================
Se diseñaron con partición de equivalencia y análisis de valores límite sobre
las entradas y salidas públicas de la clase, sin depender de su implementación.
El azar y el récord se reemplazan por dobles de prueba (StubRandom y
FakeHighscoreStorage) para que cada resultado sea exacto y repetible.
"""

import random

import pytest

from config import MAX_UNDO_HISTORY, WINNING_TILE
from doubles import FakeHighscoreStorage, StubRandom
from logic import Game2048

EMPTY_ROW = [0, 0, 0, 0]


# --- Creación y tamaño del tablero (valores límite: 2 y 8) ---------------------

@pytest.mark.parametrize("size", [2, 4, 8])
def test_valid_board_sizes_start_with_two_tiles(size):
    game = Game2048(size=size, storage=FakeHighscoreStorage(), rng=random.Random(1))
    assert len(game.grid) == size
    assert all(len(row) == size for row in game.grid)
    assert sum(1 for row in game.grid for value in row if value) == 2


@pytest.mark.parametrize("size", [1, 9, 0, -4, "4", 4.0, None, True])
def test_invalid_board_sizes_are_rejected(size):
    with pytest.raises(ValueError):
        Game2048(size=size, storage=FakeHighscoreStorage())


def test_initial_highscore_comes_from_storage():
    storage = FakeHighscoreStorage(initial=3132)
    assert Game2048(storage=storage).highscore == 3132
    assert storage.load_calls == 1


# --- Fichas nuevas (doble de prueba stub para el azar) -------------------------

def test_new_tile_is_two_or_four_depending_on_the_draw():
    rng = StubRandom(cells=[(0, 0), (0, 1)], draws=[0.95, 0.05])
    game = Game2048(storage=FakeHighscoreStorage(), rng=rng)
    assert game.grid[0][:2] == [2, 4]


@pytest.mark.parametrize("draw, expected", [(0.0999, 4), (0.1, 2), (0.0, 4)])
def test_probability_boundary_for_a_four(make_game, draw, expected):
    game = make_game(grid=[EMPTY_ROW] * 4, rng=StubRandom(draws=[draw]))
    assert game.add_random_tile() == (0, 0, expected)  # primera celda vacía


def test_no_tile_is_added_when_the_board_is_full(make_game):
    game = make_game(grid=[[2, 4, 2, 4], [4, 2, 4, 2], [2, 4, 2, 4], [4, 2, 4, 2]])
    assert game.add_random_tile() is None


def test_tile_appears_only_after_a_valid_move(make_game):
    rng = StubRandom(cells=[(3, 3)])
    game = make_game(grid=[[2, 0, 0, 0], EMPTY_ROW, EMPTY_ROW, EMPTY_ROW], rng=rng)
    assert not game.move("left")  # la ficha ya está pegada a la izquierda
    assert rng.choice_calls == 0
    assert game.move("right")
    assert rng.choice_calls == 1
    assert game.grid[3][3] == 2


# --- Direcciones (partición: válidas, alias, formato, inválidas) ---------------

@pytest.mark.parametrize(
    "direction",
    ["left", "LEFT", "  left  ", "izquierda", "Izquierda"],
)
def test_direction_formats_that_are_accepted(make_game, direction):
    game = make_game(grid=[[0, 0, 0, 2], EMPTY_ROW, EMPTY_ROW, EMPTY_ROW])
    assert game.move(direction)
    assert game.grid[0][0] == 2


@pytest.mark.parametrize("direction", ["", "diagonal", "l", "leftt", "norte"])
def test_unknown_directions_raise_value_error(make_game, direction):
    with pytest.raises(ValueError):
        make_game().move(direction)


def test_invalid_direction_is_rejected_even_when_the_game_is_over(make_game):
    game = make_game(grid=[[2, 4, 2, 4], [4, 2, 4, 2], [2, 4, 2, 4], [4, 2, 4, 2]])
    game.game_over = True
    with pytest.raises(ValueError):
        game.move("sideways")


# --- Resultado de una jugada ------------------------------------------------------

def test_move_result_describes_slides_merges_and_new_tile(make_game):
    rng = StubRandom(cells=[(1, 3)])
    game = make_game(grid=[[0, 2, 0, 2], [4, 0, 0, 0], EMPTY_ROW, EMPTY_ROW], rng=rng)
    result = game.move("left")
    assert result.points == 4
    assert result.merged_cells == ((0, 0),)
    assert result.new_tile == (1, 3, 2)
    moves = {(m.from_cell, m.to_cell, m.merged) for m in result.tile_moves}
    # La ficha (1, 0) no se mueve, por eso no aparece.
    assert moves == {((0, 1), (0, 0), True), ((0, 3), (0, 0), True)}
    assert result.to_dict()["new_tile"] == {"row": 1, "col": 3, "value": 2}


def test_vertical_moves_report_column_coordinates(make_game):
    game = make_game(grid=[EMPTY_ROW, [0, 8, 0, 0], EMPTY_ROW, [0, 8, 0, 0]])
    result = game.move("down")
    assert game.grid[3][1] == 16
    assert {m.from_cell for m in result.tile_moves} == {(1, 1), (3, 1)}
    assert result.merged_cells == ((3, 1),)


def test_unchanged_board_returns_falsy_result_without_details(make_game):
    game = make_game(grid=[[2, 4, 8, 16], EMPTY_ROW, EMPTY_ROW, EMPTY_ROW])
    result = game.move("up")
    assert not result
    assert result.to_dict() == {
        "moved": False, "points": 0, "tile_moves": [], "merged_cells": [],
        "new_tile": None,
    }


# --- Puntuación y récord (doble de prueba spy) ----------------------------------

def test_score_accumulates_and_new_record_is_saved(make_game, storage):
    game = make_game(grid=[[2, 2, 4, 4], EMPTY_ROW, EMPTY_ROW, EMPTY_ROW])
    game.move("left")
    assert game.score == 12
    assert game.highscore == 12
    assert storage.saved_values == [12]


def test_record_is_not_saved_when_score_does_not_beat_it(make_game, storage):
    storage.value = 100
    game = make_game(grid=[[2, 2, 0, 0], EMPTY_ROW, EMPTY_ROW, EMPTY_ROW])
    game.highscore = 100
    game.move("left")
    assert storage.saved_values == []


# --- Victoria y fin del juego --------------------------------------------------

def test_status_changes_through_a_victory(make_game):
    game = make_game(grid=[[1024, 1024, 0, 0], EMPTY_ROW, EMPTY_ROW, EMPTY_ROW])
    assert game.status == "playing"
    game.move("left")
    assert (game.status, game.awaiting_win_decision) == ("won", True)
    assert game.continue_playing() is True
    assert game.status == "playing"
    assert game.continue_playing() is False  # ya no hay victoria pendiente


def test_no_second_victory_after_choosing_to_continue(make_game):
    game = make_game(grid=[[2048, 0, 0, 0], [2, 2, 0, 0], EMPTY_ROW, EMPTY_ROW])
    game.won = True
    game.continue_playing()
    game.move("left")
    assert game.won is False


def test_tile_above_goal_also_counts_as_victory(make_game):
    game = make_game(grid=[[4096, 0, 0, 2], EMPTY_ROW, EMPTY_ROW, EMPTY_ROW])
    game.move("left")
    assert game.max_tile() >= WINNING_TILE
    assert game.won is True


def test_last_move_that_fills_the_board_ends_the_game(make_game):
    grid = [[2, 4, 2, 4], [4, 2, 4, 2], [8, 16, 8, 16], [32, 64, 128, 0]]
    game = make_game(grid=grid, rng=StubRandom(cells=[(3, 0)]))
    game.move("right")
    assert game.game_over is True
    assert game.status == "game_over"
    assert not game.move("left")


@pytest.mark.parametrize(
    "grid, expected",
    [
        ([[2, 4], [4, 2]], False),  # 2x2 lleno sin parejas
        ([[2, 2], [4, 8]], True),   # pareja horizontal
        ([[2, 4], [2, 8]], True),   # pareja vertical
        ([[2, 0], [4, 8]], True),   # celda vacía
    ],
)
def test_can_move_on_the_smallest_board(make_game, grid, expected):
    assert make_game(grid=grid).can_move() is expected


# --- Deshacer (valor límite: tamaño del historial) -----------------------------

def test_undo_without_history_returns_false(make_game):
    assert make_game().undo() is False


def test_undo_history_keeps_only_the_last_moves(make_game):
    game = make_game(grid=[[2, 0, 0, 0], EMPTY_ROW, EMPTY_ROW, EMPTY_ROW])
    directions = ["right", "down", "left", "up"]
    valid_moves = 0
    for attempt in range(1000):
        valid_moves += bool(game.move(directions[attempt % 4]))
        if valid_moves == MAX_UNDO_HISTORY + 5:
            break
    assert valid_moves == MAX_UNDO_HISTORY + 5, "no se lograron suficientes jugadas"
    undone = 0
    while game.undo():
        undone += 1
    assert undone == MAX_UNDO_HISTORY


def test_undo_after_game_over_reopens_the_game(make_game):
    grid = [[2, 4, 2, 4], [4, 2, 4, 2], [8, 16, 8, 16], [32, 64, 128, 0]]
    game = make_game(grid=grid, rng=StubRandom(cells=[(3, 0)]))
    game.move("right")
    assert game.undo() is True
    assert game.game_over is False
    assert game.grid[3] == [32, 64, 128, 0]


def test_undo_of_the_winning_move_clears_the_victory(make_game):
    game = make_game(grid=[[1024, 1024, 0, 0], EMPTY_ROW, EMPTY_ROW, EMPTY_ROW])
    game.move("left")
    game.undo()
    assert game.won is False


def test_reset_clears_score_flags_and_history(make_game):
    game = make_game(grid=[[1024, 1024, 0, 0], EMPTY_ROW, EMPTY_ROW, EMPTY_ROW])
    game.move("left")
    game.reset()
    assert (game.score, game.won, game.game_over, game.can_undo) == (0, False, False,
                                                                     False)
    assert game.max_tile() in (2, 4)


# --- Partidas creadas desde un tablero (validación defensiva) ------------------

def test_from_grid_keeps_board_and_score_without_adding_tiles():
    rng = StubRandom()
    game = Game2048.from_grid([[2, 0], [0, 4]], score=40,
                              storage=FakeHighscoreStorage(), rng=rng)
    assert (game.size, game.grid, game.score) == (2, [[2, 0], [0, 4]], 40)
    assert rng.choice_calls == 0


def test_from_grid_detects_a_board_without_moves():
    game = Game2048.from_grid([[2, 4], [4, 2]], storage=FakeHighscoreStorage())
    assert game.game_over is True


@pytest.mark.parametrize(
    "grid",
    [
        None,
        "2048",
        [[2, 0], [0]],              # no es cuadrado
        [[2]],                      # tamaño menor que el mínimo
        [[3, 0], [0, 0]],           # 3 no es potencia de 2
        [[1, 0], [0, 0]],           # 1 no es una ficha válida
        [[-2, 0], [0, 0]],          # negativo
        [[True, 0], [0, 0]],        # bool no cuenta como entero
        [["2", 0], [0, 0]],         # texto
    ],
)
def test_from_grid_rejects_invalid_boards(grid):
    with pytest.raises(ValueError):
        Game2048.from_grid(grid, storage=FakeHighscoreStorage())


# --- Serialización ---------------------------------------------------------------

def test_to_dict_contains_the_public_contract_of_the_api(make_game):
    state = make_game().to_dict()
    assert set(state) == {
        "size", "grid", "score", "highscore", "won", "game_over", "status",
        "max_tile", "winning_tile", "can_undo",
    }


def test_text_representation_aligns_columns(make_game):
    game = make_game(grid=[[2, 0], [16384, 4]])
    lines = str(game).splitlines()
    assert lines == ["    2     ·", "16384     4"]

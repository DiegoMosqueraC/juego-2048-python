"""
test_piedras.py - Piedras: celdas bloqueadas del modo expedición
================================================================
Una piedra (STONE) no se mueve, no se fusiona y parte la línea en tramos que se
desplazan por separado. Se prueban el algoritmo por línea, el tablero completo,
la validación y el multiplicador de puntos y la probabilidad de 4 por partida.
"""

import pytest

from config import STONE
from doubles import FakeHighscoreStorage, StubRandom
from logic import Game2048, slide_line
from validation import validate_grid

S = STONE
EMPTY_ROW = [0, 0, 0, 0]


@pytest.mark.parametrize(
    "line, values, points",
    [
        # Sin piedras se comporta igual que slide_and_merge_line.
        ([2, 0, 2, 4], (4, 4, 0, 0), 4),
        # La piedra se queda en su sitio y frena a las fichas.
        ([0, S, 0, 2], (0, S, 2, 0), 0),
        # Las fichas de lados distintos de la piedra no se fusionan.
        ([2, S, 2, 0], (2, S, 2, 0), 0),
        # Cada tramo se fusiona por su cuenta.
        ([2, 2, S, 4], (4, 0, S, 4), 4),
        ([0, 4, 4, S], (8, 0, 0, S), 8),
        # Varias piedras seguidas.
        ([S, S, 2, 2], (S, S, 4, 0), 4),
        ([S, 0, S, 0], (S, 0, S, 0), 0),
    ],
)
def test_slide_line_respects_stones(line, values, points):
    result = slide_line(line)
    assert result.values == values
    assert result.points == points


def test_slide_line_reports_moves_in_line_indices():
    result = slide_line([2, S, 0, 2])
    assert [(m.source, m.target, m.merged) for m in result.moves] == [
        (0, 0, False), (3, 2, False)]


def test_slide_line_reports_merged_targets_after_a_stone():
    assert slide_line([S, 2, 2, 0]).merged_targets == (1,)


def test_stone_is_a_valid_cell_in_a_grid():
    grid = [[S, 0], [2, 0]]
    assert validate_grid(grid) == grid


def make(grid, **kwargs):
    return Game2048.from_grid(grid, storage=FakeHighscoreStorage(), rng=StubRandom(),
                              **kwargs)


def test_stones_block_tiles_on_the_board():
    game = make([[2, S, 0, 2], [S, 0, 0, 0], EMPTY_ROW, EMPTY_ROW])
    game.move("left")
    assert game.grid[0][:3] == [2, S, 2]
    assert game.grid[1][0] == S


def test_stones_never_count_as_a_possible_merge():
    game = make([[S, S], [2, 4]])
    assert not game.can_move()
    assert game.game_over


def test_max_tile_ignores_stones():
    assert make([[S, 0], [0, 0]]).max_tile() == 0


def test_text_board_draws_stones():
    assert "■" in str(make([[S, 2], [0, 0]]))


def test_points_multiplier_scales_the_score():
    game = make([[2, 2, 0, 0], EMPTY_ROW, EMPTY_ROW, EMPTY_ROW])
    game.points_multiplier = 1.5
    result = game.move("left")
    assert result.points == 6
    assert game.score == 6


def test_probability_of_four_can_change_per_game():
    game = Game2048.from_grid([[0, 0], [0, 0]], storage=FakeHighscoreStorage(),
                              rng=StubRandom(draws=[0.3]))
    game.probability_of_four = 0.4
    assert game.add_random_tile()[2] == 4


def test_clear_history_disables_undo():
    game = make([[2, 2, 0, 0], EMPTY_ROW, EMPTY_ROW, EMPTY_ROW])
    game.move("left")
    game.clear_history()
    assert not game.can_undo

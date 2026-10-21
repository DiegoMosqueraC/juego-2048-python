"""
test_logic.py - Pruebas unitarias originales de la lógica de 2048
=================================================================
Son los 12 casos de la versión base (antes en tests_logic.py con unittest),
migrados a pytest sin cambiar lo que verifican. Que sigan pasando después de
refactorizar demuestra que el comportamiento del juego se conservó.
"""

from logic import slide_and_merge_line

EMPTY_ROW = [0, 0, 0, 0]


def test_row_merge_basic():
    """[2, 0, 2, 0] -> [4, 0, 0, 0] y 4 puntos."""
    result = slide_and_merge_line([2, 0, 2, 0])
    assert result.values == (4, 0, 0, 0)
    assert result.points == 4


def test_row_merge_no_double_combination():
    """[2, 2, 2, 2] -> [4, 4, 0, 0] y no [8, 0, 0, 0]."""
    result = slide_and_merge_line([2, 2, 2, 2])
    assert result.values == (4, 4, 0, 0)
    assert result.points == 8


def test_row_merge_three_elements():
    """[2, 2, 2, 0] prioriza de izquierda a derecha -> [4, 2, 0, 0]."""
    result = slide_and_merge_line([2, 2, 2, 0])
    assert result.values == (4, 2, 0, 0)
    assert result.points == 4


def test_row_no_merge_when_different():
    """Valores distintos solo se compactan: [0, 2, 0, 4] -> [2, 4, 0, 0]."""
    result = slide_and_merge_line([0, 2, 0, 4])
    assert result.values == (2, 4, 0, 0)
    assert result.points == 0


def test_move_left(make_game):
    game = make_game(grid=[[2, 0, 0, 2], [4, 4, 0, 0], EMPTY_ROW, [2, 2, 4, 8]])
    assert game.move("left")
    assert game.grid[0][0] == 4
    assert game.grid[1][0] == 8
    assert game.grid[3][:3] == [4, 4, 8]
    assert game.score == 16  # (2+2) + (4+4) + (2+2)


def test_move_right(make_game):
    game = make_game(grid=[[2, 0, 0, 2], EMPTY_ROW, EMPTY_ROW, EMPTY_ROW])
    assert game.move("right")
    assert game.grid[0][3] == 4


def test_move_up(make_game):
    game = make_game(grid=[[2, 0, 0, 0], [2, 0, 0, 0], [4, 0, 0, 0], [4, 0, 0, 0]])
    assert game.move("up")
    assert game.grid[0][0] == 4
    assert game.grid[1][0] == 8


def test_move_down(make_game):
    game = make_game(grid=[[2, 0, 0, 0], [2, 0, 0, 0], [4, 0, 0, 0], [4, 0, 0, 0]])
    assert game.move("down")
    assert game.grid[2][0] == 4
    assert game.grid[3][0] == 8


def test_invalid_move_returns_false(make_game):
    """Si ninguna ficha puede desplazarse ni fusionarse, move() es falso."""
    game = make_game(grid=[[2, 4, 8, 16], EMPTY_ROW, EMPTY_ROW, EMPTY_ROW])
    assert not game.move("left")


def test_game_over_detection(make_game):
    game = make_game(grid=[[2, 4, 2, 4], [4, 2, 4, 2], [2, 4, 2, 4], [4, 2, 4, 2]])
    assert not game.can_move()
    game.grid[0][0] = 4  # ahora hay dos 4 contiguos
    assert game.can_move()


def test_win_condition(make_game):
    game = make_game(grid=[[1024, 1024, 0, 0], EMPTY_ROW, EMPTY_ROW, EMPTY_ROW])
    game.move("left")
    assert game.won


def test_undo_feature(make_game):
    game = make_game(grid=[[2, 2, 0, 0], EMPTY_ROW, EMPTY_ROW, EMPTY_ROW])
    initial_score = game.score
    game.move("left")
    assert game.grid[0][0] == 4
    assert game.undo()
    assert game.grid[0] == [2, 2, 0, 0]
    assert game.score == initial_score

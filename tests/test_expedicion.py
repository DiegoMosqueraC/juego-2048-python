"""
test_expedicion.py - Modo expedición (roguelike)
================================================
Una expedición son varios pisos con una ficha objetivo cada uno. Al superar un
piso se elige una bendición entre tres; desde el segundo piso cada uno trae una
maldición. Se prueba con semillas fijas y tableros preparados para que cada
resultado sea exacto y repetible.
"""

import pytest

from config import EXPEDITION_TARGETS, STONE
from doubles import FakeHighscoreStorage
from roguelike import BLESSINGS, CURSES, Expedition

S = STONE
EMPTY_ROW = [0, 0, 0, 0]


@pytest.fixture
def expedition():
    return Expedition(storage=FakeHighscoreStorage(), seed=7)


def reach_target(exp):
    """Prepara un tablero que alcanza el objetivo del piso con una jugada."""
    half = exp.target // 2
    exp.game.grid = [[half, half, 0, 0], EMPTY_ROW, EMPTY_ROW, EMPTY_ROW]
    exp.move("left")


# --- Inicio y semilla ----------------------------------------------------------

def test_new_expedition_starts_on_the_first_floor(expedition):
    assert expedition.floor == 1
    assert expedition.target == EXPEDITION_TARGETS[0]
    assert expedition.curse == "calma"
    assert expedition.undo_charges == 1
    assert expedition.moves_left is None
    assert expedition.status == "playing"
    assert expedition.seed == 7


def test_same_seed_gives_the_same_expedition():
    first = Expedition(storage=FakeHighscoreStorage(), seed=123)
    second = Expedition(storage=FakeHighscoreStorage(), seed=123)
    assert first.game.grid == second.game.grid
    for direction in ("left", "up", "right", "down"):
        first.move(direction)
        second.move(direction)
    assert first.game.grid == second.game.grid


def test_without_seed_one_is_drawn():
    assert isinstance(Expedition(storage=FakeHighscoreStorage()).seed, int)


def test_reset_starts_a_new_expedition(expedition):
    reach_target(expedition)
    expedition.choose(0)
    expedition.reset()
    assert expedition.floor == 1
    assert expedition.seed != 7
    assert expedition.undo_charges == 1
    assert expedition.game.points_multiplier == 1.0


def test_reset_can_replay_a_seed(expedition):
    grid = [row[:] for row in expedition.game.grid]
    expedition.move("left")
    expedition.reset(seed=7)
    assert expedition.game.grid == grid


# --- Pisos y bendiciones ---------------------------------------------------------

def test_reaching_the_target_offers_three_blessings(expedition):
    reach_target(expedition)
    assert expedition.status == "choosing"
    ids = [choice["id"] for choice in expedition.to_dict()["expedition"]["choices"]]
    assert len(ids) == 3
    assert len(set(ids)) == 3
    assert set(ids) <= set(BLESSINGS)


def test_moves_are_ignored_while_choosing(expedition):
    reach_target(expedition)
    grid = [row[:] for row in expedition.game.grid]
    assert not expedition.move("right").moved
    assert expedition.game.grid == grid


def test_choosing_advances_to_the_next_floor(expedition):
    reach_target(expedition)
    assert expedition.choose(1) is True
    assert expedition.floor == 2
    assert expedition.target == EXPEDITION_TARGETS[1]
    assert expedition.curse in CURSES
    assert expedition.status == "playing"
    assert not expedition.game.can_undo


@pytest.mark.parametrize("index", [-1, 3, "0", None, 1.0])
def test_invalid_choice_is_rejected(expedition, index):
    reach_target(expedition)
    with pytest.raises(ValueError):
        expedition.choose(index)


def test_choose_without_a_pending_choice_returns_false(expedition):
    assert expedition.choose(0) is False


def test_blessing_undo_adds_two_charges(expedition):
    expedition.apply_blessing("deshacer")
    assert expedition.undo_charges == 3


def test_blessing_greed_raises_the_multiplier(expedition):
    expedition.apply_blessing("codicia")
    expedition.apply_blessing("codicia")
    assert expedition.game.points_multiplier == 2.0


def test_blessing_broom_removes_every_two(expedition):
    expedition.game.grid = [[2, 4, 2, 0], [2, S, 8, 0], EMPTY_ROW, EMPTY_ROW]
    expedition.apply_blessing("escoba")
    assert expedition.game.grid[:2] == [[0, 4, 0, 0], [0, S, 8, 0]]


def test_blessing_clover_raises_the_chance_of_four_up_to_a_limit(expedition):
    for _ in range(5):
        expedition.apply_blessing("trebol")
    assert expedition.game.probability_of_four == 0.5


def test_blessing_dynamite_removes_every_stone(expedition):
    expedition.game.grid = [[S, 2, 0, 0], [0, 0, S, 0], EMPTY_ROW, EMPTY_ROW]
    expedition.apply_blessing("dinamita")
    assert all(value != S for row in expedition.game.grid for value in row)


def test_dynamite_is_only_offered_when_there_are_stones(expedition):
    for _ in range(30):
        expedition.reset()
        reach_target(expedition)
        ids = [c["id"] for c in expedition.to_dict()["expedition"]["choices"]]
        assert "dinamita" not in ids


def test_clover_is_not_offered_at_its_limit(expedition):
    expedition.game.probability_of_four = 0.5
    for _ in range(30):
        expedition.game.grid = [[32, 32, 0, 0], EMPTY_ROW, EMPTY_ROW, EMPTY_ROW]
        expedition.floor, expedition._choices = 1, []
        expedition.move("left")
        assert "trebol" not in expedition._choices


# --- Maldiciones -----------------------------------------------------------------

def test_curse_stone_places_one_stone_on_an_empty_cell(expedition):
    expedition.apply_curse("piedra")
    stones = sum(value == S for row in expedition.game.grid for value in row)
    assert stones == 1
    assert expedition.curse == "piedra"


def test_curse_haste_limits_the_moves_of_the_floor(expedition):
    expedition.apply_curse("prisa")
    assert expedition.moves_left == expedition.target // 3
    expedition.game.grid = [[2, 0, 0, 0], EMPTY_ROW, EMPTY_ROW, EMPTY_ROW]
    expedition.move("right")
    assert expedition.moves_left == expedition.target // 3 - 1


def test_running_out_of_moves_ends_the_expedition(expedition):
    expedition.apply_curse("prisa")
    expedition.moves_left = 1
    expedition.game.grid = [[2, 0, 0, 0], EMPTY_ROW, EMPTY_ROW, EMPTY_ROW]
    expedition.move("right")
    assert expedition.status == "game_over"
    assert expedition.to_dict()["expedition"]["outcome"] == "lost"


def test_curse_calm_changes_nothing(expedition):
    grid = [row[:] for row in expedition.game.grid]
    expedition.apply_curse("calma")
    assert expedition.game.grid == grid
    assert expedition.moves_left is None


# --- Deshacer con cargas ---------------------------------------------------------

def test_undo_spends_a_charge(expedition):
    expedition.game.grid = [[2, 0, 0, 0], EMPTY_ROW, EMPTY_ROW, EMPTY_ROW]
    expedition.move("right")
    assert expedition.undo() is True
    assert expedition.undo_charges == 0
    expedition.move("right")
    assert expedition.undo() is False


def test_undo_gives_back_a_haste_move(expedition):
    expedition.apply_curse("prisa")
    expedition.game.grid = [[2, 0, 0, 0], EMPTY_ROW, EMPTY_ROW, EMPTY_ROW]
    expedition.move("right")
    expedition.undo()
    assert expedition.moves_left == expedition.target // 3


def test_undo_without_history_keeps_the_charge(expedition):
    assert expedition.undo() is False
    assert expedition.undo_charges == 1


# --- Final de la expedición ------------------------------------------------------

def test_reaching_2048_on_the_last_floor_wins(expedition):
    expedition.floor = len(EXPEDITION_TARGETS)
    reach_target(expedition)
    assert expedition.status == "won"
    assert expedition.to_dict()["expedition"]["outcome"] == "won"
    assert not expedition.move("left").moved


def test_a_full_board_loses(expedition):
    # Tras fusionar 8 + 8 solo queda libre (3, 3); con un 2 ahí no hay jugadas.
    expedition.game.grid = [[2, 4, 2, 4], [4, 2, 4, 2], [2, 4, 2, 4], [4, 2, 8, 8]]
    expedition.game.probability_of_four = 0
    expedition.move("left")
    assert expedition.status == "game_over"
    assert expedition.to_dict()["expedition"]["outcome"] == "lost"


def test_continue_is_not_available(expedition):
    assert expedition.continue_playing() is False


@pytest.mark.parametrize("direction", [None, "norte", 5])
def test_invalid_direction_is_rejected(expedition, direction):
    with pytest.raises(ValueError):
        expedition.move(direction)


def test_to_dict_reports_the_expedition(expedition):
    data = expedition.to_dict()
    info = data["expedition"]
    assert data["mode"] == "expedition"
    assert data["status"] == "playing"
    assert info["floor"] == 1
    assert info["floors"] == len(EXPEDITION_TARGETS)
    assert info["target"] == EXPEDITION_TARGETS[0]
    assert info["seed"] == 7
    assert info["curse"]["id"] == "calma"
    assert info["undo_charges"] == 1
    assert info["choices"] == []
    assert data["can_undo"] is False


def test_a_move_that_changes_nothing_does_not_spend_haste(expedition):
    expedition.apply_curse("prisa")
    expedition.game.grid = [[2, 0, 0, 0], EMPTY_ROW, EMPTY_ROW, EMPTY_ROW]
    assert not expedition.move("left").moved
    assert expedition.moves_left == expedition.target // 3


def test_curse_stone_on_a_full_board_places_nothing(expedition):
    full = [[2, 4, 2, 4], [4, 2, 4, 2], [2, 4, 2, 4], [4, 2, 4, 2]]
    expedition.game.grid = [row[:] for row in full]
    expedition.apply_curse("piedra")
    assert expedition.game.grid == full


def test_choosing_with_a_blocked_board_ends_the_expedition(expedition):
    expedition._choices = ["deshacer", "codicia", "escoba"]
    expedition.game.grid = [[2, 4, 2, 4], [4, 2, 4, 2], [2, 4, 2, 4], [4, 2, 4, 64]]
    assert expedition.choose(0) is True
    assert expedition.status == "game_over"

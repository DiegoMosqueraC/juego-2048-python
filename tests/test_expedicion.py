"""
test_expedicion.py - Modo expedición (roguelike)
================================================
Una expedición son varios pisos con una ficha objetivo cada uno. Al superar un
piso los puntos se convierten en oro, se elige una carta gratis y se abre una
tienda; cada piso trae maldiciones y los pisos guardianes traen dos. Se prueba
con semillas fijas y tableros preparados para que cada resultado sea exacto.
"""

import pytest

from config import EXPEDITION_TARGETS, STONE
from doubles import FakeHighscoreStorage
from roguelike import (
    BOARD_GROWTH,
    CALM_UNTIL_FLOOR,
    CARD_PRICES,
    CARDS,
    CURSES,
    GUARDIAN_FLOORS,
    MAX_BOARD_EXPANSION,
    QUAKE_EVERY,
    REROLL_PRICE,
    Expedition,
)

S = STONE
EMPTY_ROW = [0, 0, 0, 0]
BLOCKED = [[2, 4, 2, 4], [4, 2, 4, 2], [2, 4, 2, 4], [4, 2, 4, 2]]


@pytest.fixture
def expedition():
    return Expedition(storage=FakeHighscoreStorage(), seed=7)


def reach_target(exp):
    """Prepara un tablero que alcanza el objetivo del piso con una jugada."""
    half = exp.target // 2
    exp.game.grid = [[half, half, 0, 0], EMPTY_ROW, EMPTY_ROW, EMPTY_ROW]
    exp.move("left")


def open_shop(exp, items=()):
    exp._choices, exp._shop, exp._shop_open = [], list(items), True


def stones(exp):
    return sum(value == S for row in exp.game.grid for value in row)


# --- Inicio y semilla ----------------------------------------------------------

def test_new_expedition_starts_on_the_first_floor(expedition):
    assert expedition.floor == 1
    assert expedition.target == EXPEDITION_TARGETS[0]
    assert expedition.curses == ["calma"]
    assert expedition.undo_charges == 1
    assert expedition.gold == 0
    assert expedition.multiplier == 1.0
    assert expedition.streak == 0
    assert expedition.cards == []
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
    assert expedition.gold == 0
    assert expedition.cards == []
    assert expedition.status == "playing"


def test_reset_can_replay_a_seed(expedition):
    grid = [row[:] for row in expedition.game.grid]
    expedition.move("left")
    expedition.reset(seed=7)
    assert expedition.game.grid == grid


# --- Superar un piso: oro y carta gratis -----------------------------------------

def test_reaching_the_target_offers_three_cards(expedition):
    reach_target(expedition)
    assert expedition.status == "choosing"
    choices = expedition.to_dict()["expedition"]["choices"]
    ids = [choice["id"] for choice in choices]
    assert len(set(ids)) == 3
    assert set(ids) <= set(CARDS)
    assert all(choice["rarity"] in CARD_PRICES for choice in choices)


def test_points_of_the_floor_become_gold(expedition):
    expedition.game.score = 1000
    reach_target(expedition)
    # (1000 + 64 puntos) // 100 = 10 de oro.
    assert expedition.gold == 10
    assert expedition.to_dict()["expedition"]["reward"] == {"gold": 10, "interest": 0}


def test_a_floor_always_gives_at_least_one_gold(expedition):
    reach_target(expedition)
    assert expedition.gold == 1


def test_moves_are_ignored_while_choosing(expedition):
    reach_target(expedition)
    grid = [row[:] for row in expedition.game.grid]
    assert not expedition.move("right").moved
    assert expedition.game.grid == grid


def test_choosing_takes_the_card_and_opens_the_shop(expedition):
    reach_target(expedition)
    offered = list(expedition._choices)
    assert expedition.choose(1) is True
    assert expedition.cards == [offered[1]]
    assert expedition.status == "shop"
    assert expedition._shop == [offered[0], offered[2]]


@pytest.mark.parametrize("index", [-1, 3, "0", None, 1.0])
def test_invalid_choice_is_rejected(expedition, index):
    reach_target(expedition)
    with pytest.raises(ValueError):
        expedition.choose(index)


def test_choose_without_a_pending_choice_returns_false(expedition):
    assert expedition.choose(0) is False


# --- Tienda --------------------------------------------------------------------------

def test_buying_a_card_spends_gold(expedition):
    open_shop(expedition, ["codicia", "escudo"])
    expedition.gold = 10
    assert expedition.shop_action("buy", 1) is True
    assert expedition.gold == 10 - CARD_PRICES["rara"]
    assert expedition.cards == ["escudo"]
    assert expedition._shop == ["codicia"]


def test_buying_without_enough_gold_fails(expedition):
    open_shop(expedition, ["fenix"])
    expedition.gold = CARD_PRICES["legendaria"] - 1
    assert expedition.shop_action("buy", 0) is False
    assert expedition.cards == []


@pytest.mark.parametrize("index", [-1, 2, None, "0"])
def test_buying_an_invalid_item_is_rejected(expedition, index):
    open_shop(expedition, ["codicia", "escoba"])
    expedition.gold = 99
    with pytest.raises(ValueError):
        expedition.shop_action("buy", index)


def test_reroll_spends_gold_and_offers_two_new_cards(expedition):
    open_shop(expedition, [])
    expedition.gold = REROLL_PRICE
    assert expedition.shop_action("reroll") is True
    assert expedition.gold == 0
    assert len(expedition._shop) == 2
    assert expedition.shop_action("reroll") is False


def test_leaving_the_shop_goes_down_one_floor(expedition):
    reach_target(expedition)
    expedition.choose(0)
    assert expedition.shop_action("leave") is True
    assert expedition.floor == 2
    assert expedition.target == EXPEDITION_TARGETS[1]
    assert expedition.status == "playing"
    assert all(curse in CURSES for curse in expedition.curses)
    assert not expedition.game.can_undo


def test_shop_actions_need_an_open_shop(expedition):
    assert expedition.shop_action("leave") is False
    assert expedition.shop_action("reroll") is False
    assert expedition.shop_action("buy", 0) is False


@pytest.mark.parametrize("action", ["steal", "", None, 3])
def test_unknown_shop_action_is_rejected(expedition, action):
    open_shop(expedition)
    with pytest.raises(ValueError):
        expedition.shop_action(action)


def test_leaving_the_shop_with_a_blocked_board_ends_the_expedition(expedition):
    open_shop(expedition)
    expedition.game.grid = [row[:] for row in BLOCKED]
    expedition.shop_action("leave")
    assert expedition.status == "game_over"


# --- Pisos guardianes ----------------------------------------------------------

def test_guardian_floors_bring_two_different_curses(expedition):
    expedition.floor = GUARDIAN_FLOORS[0] - 1
    open_shop(expedition)
    expedition.shop_action("leave")
    assert expedition.floor == GUARDIAN_FLOORS[0]
    assert len(expedition.curses) == 2
    assert len(set(expedition.curses)) == 2
    assert "calma" not in expedition.curses
    assert expedition.to_dict()["expedition"]["guardian"] is True


def test_clearing_a_guardian_floor_offers_only_rare_cards(expedition):
    expedition.floor = GUARDIAN_FLOORS[0]
    reach_target(expedition)
    assert all(CARDS[card].rarity != "comun" for card in expedition._choices)


# --- Cartas --------------------------------------------------------------------------

def test_card_undo_adds_two_charges(expedition):
    expedition.take_card("deshacer")
    assert expedition.undo_charges == 3


def test_card_greed_raises_the_multiplier(expedition):
    expedition.take_card("codicia")
    expedition.take_card("codicia")
    assert expedition.multiplier == 2.0


def test_card_broom_removes_every_two(expedition):
    expedition.game.grid = [[2, 4, 2, 0], [2, S, 8, 0], EMPTY_ROW, EMPTY_ROW]
    expedition.take_card("escoba")
    assert expedition.game.grid[:2] == [[0, 4, 0, 0], [0, S, 8, 0]]


def test_card_clover_raises_the_chance_of_four_up_to_a_limit(expedition):
    for _ in range(5):
        expedition.take_card("trebol")
    assert expedition.game.probability_of_four == 0.5


def test_card_bag_gives_gold(expedition):
    expedition.take_card("bolsa")
    assert expedition.gold == 5


def test_card_dynamite_removes_every_stone(expedition):
    expedition.game.grid = [[S, 2, 0, 0], [0, 0, S, 0], EMPTY_ROW, EMPTY_ROW]
    expedition.take_card("dinamita")
    assert stones(expedition) == 0


def test_card_shield_cancels_the_next_curses_once(expedition):
    expedition.take_card("escudo")
    expedition.floor = GUARDIAN_FLOORS[0] - 1
    open_shop(expedition)
    expedition.shop_action("leave")
    assert expedition.curses == ["calma"]
    assert expedition.to_dict()["expedition"]["event"] == "escudo"
    open_shop(expedition)
    expedition.shop_action("leave")
    assert expedition.to_dict()["expedition"]["shield"] is False


def test_card_alchemy_turns_fours_into_eights(expedition):
    expedition.game.grid = [[4, 2, 4, 0], [16, 0, 0, 4], EMPTY_ROW, EMPTY_ROW]
    expedition.take_card("alquimia")
    assert expedition.game.grid[:2] == [[8, 2, 8, 0], [16, 0, 0, 8]]


def test_card_interest_pays_for_saved_gold(expedition):
    expedition.take_card("interes")
    expedition.gold = 12
    reach_target(expedition)
    # 1 de oro por el piso + 12 // 5 = 2 de interés.
    assert expedition.gold == 12 + 1 + 2
    assert expedition.to_dict()["expedition"]["reward"]["interest"] == 2


def test_interest_has_a_limit_per_card(expedition):
    expedition.take_card("interes")
    expedition.gold = 100
    reach_target(expedition)
    assert expedition.to_dict()["expedition"]["reward"]["interest"] == 5


def test_card_expansion_grows_the_board_and_keeps_the_tiles(expedition):
    expedition.game.grid = [[2, 0, 0, 0], EMPTY_ROW, EMPTY_ROW, [0, 0, 0, 8]]
    expedition.take_card("expansion")
    grid = expedition.game.grid
    assert expedition.game.size == 5
    assert len(grid) == 5 and all(len(row) == 5 for row in grid)
    assert grid[0][0] == 2 and grid[3][3] == 8
    expedition.move("right")
    assert expedition.game.grid[0][4] == 2


def test_expansion_is_not_offered_at_the_maximum_size(expedition):
    while expedition.game.size < MAX_BOARD_EXPANSION:
        expedition.take_card("expansion")
    assert "expansion" not in expedition._draw_cards(len(CARDS), rare_only=True)
    expedition.take_card("expansion")
    assert expedition.game.size == MAX_BOARD_EXPANSION


def test_card_phoenix_saves_the_expedition_once(expedition):
    expedition.take_card("fenix")
    expedition.game.grid = [[2, 4, 2, 4], [4, 2, 4, 2], [2, 4, 2, 4], [4, 2, 8, 8]]
    expedition.game.probability_of_four = 0
    expedition.move("left")
    assert expedition.status == "playing"
    assert expedition.to_dict()["expedition"]["event"] == "fenix"
    assert expedition.to_dict()["expedition"]["phoenix"] == 0
    assert all(value not in (2, 4) for row in expedition.game.grid for value in row)


def test_dynamite_is_only_offered_when_there_are_stones(expedition):
    assert "dinamita" not in expedition._draw_cards(len(CARDS))
    expedition.game.grid[0][0] = S
    assert "dinamita" in expedition._draw_cards(len(CARDS))


def test_clover_is_not_offered_at_its_limit(expedition):
    expedition.game.probability_of_four = 0.5
    assert "trebol" not in expedition._draw_cards(len(CARDS))


def test_every_card_is_offered_with_its_price(expedition):
    open_shop(expedition, list(CARDS))
    items = expedition.to_dict()["expedition"]["shop"]["items"]
    assert [item["price"] for item in items] == [
        CARD_PRICES[CARDS[card].rarity] for card in CARDS]


# --- Maldiciones -----------------------------------------------------------------

def test_curse_stone_places_one_stone(expedition):
    expedition.set_curses(["piedra"])
    assert stones(expedition) == 1


def test_curse_landslide_places_two_stones(expedition):
    expedition.set_curses(["derrumbe"])
    assert stones(expedition) == 2


def test_curse_stone_on_a_full_board_places_nothing(expedition):
    expedition.game.grid = [row[:] for row in BLOCKED]
    expedition.set_curses(["piedra"])
    assert expedition.game.grid == BLOCKED


def test_curse_haste_limits_the_moves_of_the_floor(expedition):
    expedition.set_curses(["prisa"])
    assert expedition.moves_left == expedition.target // 3
    expedition.game.grid = [[2, 0, 0, 0], EMPTY_ROW, EMPTY_ROW, EMPTY_ROW]
    expedition.move("right")
    assert expedition.moves_left == expedition.target // 3 - 1


def test_running_out_of_moves_ends_the_expedition(expedition):
    expedition.set_curses(["prisa"])
    expedition.moves_left = 1
    expedition.game.grid = [[2, 0, 0, 0], EMPTY_ROW, EMPTY_ROW, EMPTY_ROW]
    expedition.move("right")
    assert expedition.status == "game_over"
    assert expedition.to_dict()["expedition"]["outcome"] == "lost"


def test_a_move_that_changes_nothing_does_not_spend_haste(expedition):
    expedition.set_curses(["prisa"])
    expedition.game.grid = [[2, 0, 0, 0], EMPTY_ROW, EMPTY_ROW, EMPTY_ROW]
    assert not expedition.move("left").moved
    assert expedition.moves_left == expedition.target // 3


def test_curse_drought_halves_the_points(expedition):
    expedition.set_curses(["sequia"])
    expedition.game.grid = [[8, 8, 0, 0], EMPTY_ROW, EMPTY_ROW, EMPTY_ROW]
    assert expedition.move("left").points == 8


def test_curse_fog_is_reported_to_the_interface(expedition):
    expedition.set_curses(["niebla"])
    ids = [curse["id"] for curse in expedition.to_dict()["expedition"]["curses"]]
    assert ids == ["niebla"]


def test_curse_quake_shakes_the_board_every_few_moves(expedition):
    expedition.set_curses(["terremoto"])
    expedition.floor_moves = QUAKE_EVERY - 1
    expedition.game.grid = [[2, 0, 0, 0], EMPTY_ROW, EMPTY_ROW, EMPTY_ROW]
    expedition.move("right")
    assert expedition.to_dict()["expedition"]["event"] == "terremoto"
    expedition.move("left")
    assert expedition.to_dict()["expedition"]["event"] is None


def test_curse_calm_changes_nothing(expedition):
    grid = [row[:] for row in expedition.game.grid]
    expedition.set_curses(["calma"])
    assert expedition.game.grid == grid
    assert expedition.moves_left is None


# --- Racha ---------------------------------------------------------------------------

def test_consecutive_merges_raise_the_points(expedition):
    expedition.game.grid = [[2, 2, 0, 0], EMPTY_ROW, EMPTY_ROW, EMPTY_ROW]
    assert expedition.move("left").points == 4
    assert expedition.streak == 1
    expedition.game.grid = [[16, 16, 0, 0], EMPTY_ROW, EMPTY_ROW, EMPTY_ROW]
    # 32 puntos × 1,1 por la racha = 35.
    assert expedition.move("left").points == 35
    assert expedition.streak == 2


def test_a_move_without_merges_breaks_the_streak(expedition):
    expedition.streak = 4
    expedition.game.grid = [[2, 0, 0, 0], EMPTY_ROW, EMPTY_ROW, EMPTY_ROW]
    expedition.move("right")
    assert expedition.streak == 0


def test_streak_bonus_has_a_limit(expedition):
    expedition.streak = 50
    assert expedition.to_dict()["expedition"]["streak_bonus"] == 2.0


def test_best_streak_is_remembered(expedition):
    expedition.game.grid = [[2, 2, 0, 0], EMPTY_ROW, EMPTY_ROW, EMPTY_ROW]
    expedition.move("left")
    expedition.game.grid = [[2, 0, 0, 0], EMPTY_ROW, EMPTY_ROW, EMPTY_ROW]
    expedition.move("right")
    assert expedition.to_dict()["expedition"]["best_streak"] == 1


# --- Deshacer con cargas ---------------------------------------------------------

def test_undo_spends_a_charge_and_breaks_the_streak(expedition):
    expedition.game.grid = [[2, 2, 0, 0], EMPTY_ROW, EMPTY_ROW, EMPTY_ROW]
    expedition.move("left")
    assert expedition.undo() is True
    assert expedition.undo_charges == 0
    assert expedition.streak == 0
    expedition.move("right")
    assert expedition.undo() is False


def test_undo_gives_back_a_haste_move(expedition):
    expedition.set_curses(["prisa"])
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
    expedition.take_card("codicia")
    expedition.take_card("codicia")
    data = expedition.to_dict()
    info = data["expedition"]
    assert data["mode"] == "expedition"
    assert data["status"] == "playing"
    assert info["floor"] == 1
    assert info["floors"] == len(EXPEDITION_TARGETS)
    assert info["target"] == EXPEDITION_TARGETS[0]
    assert info["seed"] == 7
    assert info["guardian"] is False
    assert info["curses"][0]["id"] == "calma"
    assert info["undo_charges"] == 1
    assert info["gold"] == 0
    assert info["multiplier"] == 2.0
    assert info["deck"] == [{"id": "codicia", "name": "Codicia", "rarity": "comun",
                             "count": 2}]
    assert info["choices"] == []
    assert info["shop"] == {"open": False, "items": [], "reroll_price": REROLL_PRICE}
    assert data["can_undo"] is False


# --- Crecimiento del tablero y dificultad por piso ----------------------------------

def go_down_to(exp, floor):
    exp.floor = floor - 1
    open_shop(exp)
    exp.shop_action("leave")


def test_the_mine_widens_on_the_big_floors(expedition):
    for floor, size in BOARD_GROWTH.items():
        go_down_to(expedition, floor)
        assert expedition.game.size == size
        assert expedition.to_dict()["expedition"]["event"] == "crece"


def test_growth_keeps_the_tiles(expedition):
    expedition.game.grid = [[64, 0, 0, 0], EMPTY_ROW, EMPTY_ROW, [0, 0, 0, 8]]
    floor = min(BOARD_GROWTH)
    go_down_to(expedition, floor)
    assert expedition.game.grid[0][0] == 64
    assert expedition.game.grid[3][3] in (8, S)


def test_growth_does_not_shrink_an_expanded_board(expedition):
    while expedition.game.size < MAX_BOARD_EXPANSION:
        expedition.take_card("expansion")
    go_down_to(expedition, min(BOARD_GROWTH))
    assert expedition.game.size == MAX_BOARD_EXPANSION


def test_no_calm_floors_after_the_early_floors(expedition):
    for _ in range(40):
        go_down_to(expedition, CALM_UNTIL_FLOOR + 1)
        assert "calma" not in expedition.curses

"""
roguelike.py - Modo expedición: el 2048 como un roguelike
=========================================================
Una expedición es una partida por pisos. Cada piso tiene una ficha objetivo
(64, 128, ... 2048) y el tablero se conserva de un piso al siguiente:

1. Los puntos del piso se convierten en oro al superarlo (1 por cada 100).
2. Se elige 1 de 3 cartas gratis y después se abre una tienda donde el oro
   compra las otras cartas o renueva la oferta.
3. Las cartas tienen rareza (común, rara, legendaria) y se acumulan en el mazo.
4. Cada piso trae una maldición; los pisos guardianes traen dos, y superarlos
   ofrece solo cartas raras o legendarias.
5. La racha premia fusionar en jugadas seguidas: +10 % de puntos por paso.
6. Deshacer gasta usos. Si el tablero se bloquea o se acaban las jugadas de
   «Prisa», la expedición termina (salvo que el Fénix te rescate).

Cada expedición tiene una semilla: con la misma semilla y las mismas jugadas
se repite exactamente la misma partida.
"""

import random
from dataclasses import dataclass
from typing import Optional

from config import (
    DEFAULT_BOARD_SIZE,
    DIRECTIONS,
    EXPEDITION_TARGETS,
    HASTE_DIVISOR,
    MAX_PROBABILITY_OF_FOUR,
    STARTING_UNDO_CHARGES,
    STONE,
)
from logic import Game2048, MoveResult
from storage import HighscoreStorage
from validation import is_strict_int, normalize_direction


@dataclass(frozen=True)
class Card:
    name: str
    description: str
    rarity: str  # "comun", "rara" o "legendaria"


# El orden es el que ve el jugador en la tienda y en el mazo.
CARDS = {
    "deshacer": Card("Segunda oportunidad", "Suma 2 usos de deshacer.", "comun"),
    "codicia": Card("Codicia", "Las fusiones dan un 50 % más de puntos.", "comun"),
    "escoba": Card("Escoba", "Elimina todas las fichas de 2.", "comun"),
    "trebol": Card("Trébol", "Las fichas nuevas son 4 con más frecuencia.", "comun"),
    "bolsa": Card("Bolsa de oro", "Ganas 5 de oro.", "comun"),
    "dinamita": Card("Dinamita", "Destruye todas las piedras.", "comun"),
    "escudo": Card("Escudo", "Anula las maldiciones del próximo piso.", "rara"),
    "alquimia": Card("Alquimia", "Convierte todas las fichas de 4 en 8.", "rara"),
    "interes": Card("Interés", "Al superar un piso ganas 1 de oro por cada 5 que "
                    "guardes (máx. 5).", "rara"),
    "expansion": Card("Expansión", "El tablero crece una fila y una columna "
                      "(máx. 6×6).", "legendaria"),
    "fenix": Card("Fénix", "Si te quedas sin jugadas, se borran los 2 y los 4 y "
                  "sigues (una vez).", "legendaria"),
}
RARITY_NAMES = {"comun": "Común", "rara": "Rara", "legendaria": "Legendaria"}
# Una carta común sale 6 veces más que una legendaria.
RARITY_WEIGHTS = {"comun": 6, "rara": 3, "legendaria": 1}
CARD_PRICES = {"comun": 4, "rara": 7, "legendaria": 12}
REROLL_PRICE = 2

CURSES = {
    "calma": ("Calma", "Este piso no trae maldición."),
    "piedra": ("Piedra", "Aparece un bloque que no se mueve ni se fusiona."),
    "derrumbe": ("Derrumbe", "Aparecen dos piedras."),
    "prisa": ("Prisa", "Tienes un número limitado de jugadas para el objetivo."),
    "sequia": ("Sequía", "Las fusiones dan la mitad de puntos."),
    "niebla": ("Niebla", "No ves el número de las fichas de 2 y 4."),
    "terremoto": ("Terremoto", "Cada 8 jugadas el tablero se sacude solo hacia "
                  "un lado."),
}
GUARDIAN_FLOORS = (3, 6)
GUARDIAN_CURSES = 2
QUAKE_EVERY = 8

CHOICES_PER_FLOOR = 3
SHOP_REROLL_CARDS = 2
POINTS_PER_GOLD = 100
BAG_GOLD = 5
INTEREST_STEP = 5
MAX_INTEREST = 5
GREED_BONUS = 0.5
CLOVER_BONUS = 0.15
STREAK_BONUS = 0.1
MAX_STREAK_STEPS = 10
MAX_BOARD_EXPANSION = 6


class Expedition:
    """
    Partida del modo expedición. Ofrece la misma interfaz que Game2048 para la
    API web (move, undo, reset, continue_playing, to_dict) y además choose() y
    shop_action().
    """

    MODE = "expedition"

    def __init__(
        self,
        size: int = DEFAULT_BOARD_SIZE,
        storage: Optional[HighscoreStorage] = None,
        seed: Optional[int] = None,
    ):
        self.size = size
        self._storage = storage
        self.reset(seed)

    # --- Inicio ------------------------------------------------------------------

    def reset(self, seed: Optional[int] = None) -> None:
        """Empieza una expedición nueva; sin semilla se sortea una."""
        if seed is None:
            # El azar del juego no protege secretos (B311 revisado en logic.py).
            seed = random.randrange(1_000_000)  # nosec B311
        self.seed = seed
        self._rng = random.Random(seed)  # nosec B311
        self.game = Game2048(size=self.size, storage=self._storage, rng=self._rng)
        # La victoria la decide la expedición, no el diálogo del 2048 clásico.
        self.game.keep_playing_after_win = True
        self._storage = self.game._storage
        self.floor = 1
        self.undo_charges = STARTING_UNDO_CHARGES
        self.gold = 0
        self.multiplier = 1.0
        self.streak = 0
        self.best_streak = 0
        self.cards: list[str] = []
        self.shield = False
        self.phoenix = 0
        self.outcome: Optional[str] = None
        self.event: Optional[str] = None
        self.reward = {"gold": 0, "interest": 0}
        self.floor_moves = 0
        self._floor_start_score = 0
        self._choices: list[str] = []
        self._shop: list[str] = []
        self._shop_open = False
        self.set_curses(["calma"])

    @property
    def target(self) -> int:
        return EXPEDITION_TARGETS[self.floor - 1]

    @property
    def status(self) -> str:
        """'choosing', 'shop', 'won', 'game_over' o 'playing'."""
        if self._choices:
            return "choosing"
        if self._shop_open:
            return "shop"
        if self.outcome == "won":
            return "won"
        if self.outcome == "lost":
            return "game_over"
        return "playing"

    @property
    def streak_bonus(self) -> float:
        return 1 + STREAK_BONUS * min(self.streak, MAX_STREAK_STEPS)

    # --- Jugadas -----------------------------------------------------------------

    def move(self, direction: object) -> MoveResult:
        """Jugada normal más las reglas del piso: racha, maldiciones y objetivo."""
        normalize_direction(direction)  # Se valida siempre, aunque no se juegue.
        self.event = None
        if self.status != "playing":
            return MoveResult(moved=False)
        result = self._play(direction)
        if not result.moved:
            return result
        self.streak = self.streak + 1 if result.merged_cells else 0
        self.best_streak = max(self.best_streak, self.streak)
        self.floor_moves += 1
        if self.moves_left is not None:
            self.moves_left -= 1
        if "terremoto" in self.curses and self.floor_moves % QUAKE_EVERY == 0:
            self._play(self._rng.choice(DIRECTIONS))
            self.event = "terremoto"
        self._check_floor()
        return result

    def _play(self, direction: str) -> MoveResult:
        factor = 0.5 if "sequia" in self.curses else 1.0
        self.game.points_multiplier = self.multiplier * self.streak_bonus * factor
        return self.game.move(direction)

    def _check_floor(self) -> None:
        if self.game.max_tile() >= self.target:
            self._clear_floor()
        elif self.moves_left == 0:
            self.outcome = "lost"
        elif self.game.game_over:
            self._revive_or_lose()

    def _revive_or_lose(self) -> None:
        if self.phoenix:
            self.phoenix -= 1
            self._remove_tiles({2, 4})
            self.event = "fenix"
            self.game.game_over = not self.game.can_move()
        if self.game.game_over:
            self.outcome = "lost"

    def _clear_floor(self) -> None:
        earned = max(1, (self.game.score - self._floor_start_score) // POINTS_PER_GOLD)
        interest_cards = self.cards.count("interes")
        interest = min(MAX_INTEREST, self.gold // INTEREST_STEP) * interest_cards
        self.gold += earned + interest
        self.reward = {"gold": earned, "interest": interest}
        if self.floor == len(EXPEDITION_TARGETS):
            self.outcome = "won"
            return
        guardian = self.floor in GUARDIAN_FLOORS
        self._choices = self._draw_cards(CHOICES_PER_FLOOR, rare_only=guardian)

    def _draw_cards(self, count: int, rare_only: bool = False) -> list[str]:
        """Sortea cartas distintas; las de mayor rareza salen con menos frecuencia."""
        pool = [card for card in CARDS if self._is_useful(card)
                and not (rare_only and CARDS[card].rarity == "comun")]
        drawn = []
        while pool and len(drawn) < count:
            weights = [RARITY_WEIGHTS[CARDS[card].rarity] for card in pool]
            card = self._rng.choices(pool, weights)[0]
            drawn.append(card)
            pool.remove(card)
        return drawn

    def _is_useful(self, card: str) -> bool:
        if card == "dinamita":
            return any(value == STONE for row in self.game.grid for value in row)
        if card == "trebol":
            return self.game.probability_of_four < MAX_PROBABILITY_OF_FOUR
        if card == "expansion":
            return self.game.size < MAX_BOARD_EXPANSION
        return True

    # --- Carta gratis y tienda ---------------------------------------------------

    def choose(self, index: object) -> bool:
        """
        Toma gratis la carta `index` de la oferta; las otras pasan a la tienda.

        :return: False si no hay una elección pendiente.
        :raises ValueError: si el índice no corresponde a una carta ofrecida.
        """
        if not self._choices:
            return False
        self.take_card(self._choices.pop(self._checked_index(index, self._choices)))
        self._shop, self._choices = self._choices, []
        self._shop_open = True
        return True

    def shop_action(self, action: object, index: object = None) -> bool:
        """
        'buy' compra la carta `index`, 'reroll' renueva la oferta y 'leave' baja
        al piso siguiente.

        :return: False si la tienda está cerrada o falta oro.
        :raises ValueError: si la acción o el índice no son válidos.
        """
        if action not in ("buy", "reroll", "leave"):
            raise ValueError("La acción de la tienda debe ser buy, reroll o leave")
        if not self._shop_open:
            return False
        if action == "leave":
            self._shop_open, self._shop = False, []
            self._start_next_floor()
            return True
        if action == "reroll":
            if self.gold < REROLL_PRICE:
                return False
            self.gold -= REROLL_PRICE
            self._shop = self._draw_cards(SHOP_REROLL_CARDS)
            return True
        card = self._shop[self._checked_index(index, self._shop)]
        price = CARD_PRICES[CARDS[card].rarity]
        if self.gold < price:
            return False
        self.gold -= price
        self._shop.remove(card)
        self.take_card(card)
        return True

    @staticmethod
    def _checked_index(index: object, items: list) -> int:
        if not is_strict_int(index) or not 0 <= index < len(items):
            raise ValueError(f"Elige una carta entre 0 y {len(items) - 1}")
        return index

    def take_card(self, card: str) -> None:
        """Agrega la carta al mazo y aplica su efecto."""
        self.cards.append(card)
        game = self.game
        if card == "deshacer":
            self.undo_charges += 2
        elif card == "codicia":
            self.multiplier += GREED_BONUS
        elif card == "trebol":
            game.probability_of_four = min(
                MAX_PROBABILITY_OF_FOUR, game.probability_of_four + CLOVER_BONUS)
        elif card == "bolsa":
            self.gold += BAG_GOLD
        elif card == "escudo":
            self.shield = True
        elif card == "fenix":
            self.phoenix += 1
        elif card == "expansion":
            self._expand_board()
        elif card == "alquimia":
            game.grid = [[8 if value == 4 else value for value in row]
                         for row in game.grid]
        elif card in ("escoba", "dinamita"):
            self._remove_tiles({2} if card == "escoba" else {STONE})
        # "interes" no tiene efecto inmediato: se cobra al superar cada piso.

    def _remove_tiles(self, values: set) -> None:
        self.game.grid = [[0 if value in values else value for value in row]
                          for row in self.game.grid]

    def _expand_board(self) -> None:
        game = self.game
        if game.size >= MAX_BOARD_EXPANSION:
            return
        game.size += 1
        game.grid = [row + [0] for row in game.grid] + [[0] * game.size]
        game.clear_history()  # Deshacer no puede volver a un tablero más pequeño.

    # --- Pisos y maldiciones ---------------------------------------------------------

    def _start_next_floor(self) -> None:
        self.event = None
        self.floor += 1
        self.streak = 0
        self.floor_moves = 0
        self._floor_start_score = self.game.score
        self.game.clear_history()
        if self.floor in GUARDIAN_FLOORS:
            harmful = [curse for curse in CURSES if curse != "calma"]
            curses = self._rng.sample(harmful, GUARDIAN_CURSES)
        else:
            curses = [self._rng.choice(list(CURSES))]
        if self.shield:
            self.shield = False
            self.event = "escudo"
            curses = ["calma"]
        self.set_curses(curses)
        self.game.game_over = not self.game.can_move()
        if self.game.game_over:
            self._revive_or_lose()

    def set_curses(self, curses: list[str]) -> None:
        """Activa las maldiciones del piso y aplica las que actúan al empezar."""
        self.curses = list(curses)
        self.moves_left: Optional[int] = None
        for curse in self.curses:
            if curse in ("piedra", "derrumbe"):
                self._place_stones(1 if curse == "piedra" else 2)
            elif curse == "prisa":
                self.moves_left = self.target // HASTE_DIVISOR

    def _place_stones(self, count: int) -> None:
        empty = self.game.get_empty_cells()
        for row, col in self._rng.sample(empty, min(count, len(empty))):
            self.game.grid[row][col] = STONE

    # --- Deshacer y compatibilidad con la API -----------------------------------------

    def undo(self) -> bool:
        """Deshace gastando un uso; devuelve una jugada de «Prisa» y corta la racha."""
        if self.status != "playing" or self.undo_charges == 0 or not self.game.undo():
            return False
        self.undo_charges -= 1
        self.streak = 0
        if self.moves_left is not None:
            self.moves_left += 1
        return True

    def continue_playing(self) -> bool:
        """La expedición no tiene victoria pendiente: termina al ganar."""
        return False

    def _card_dict(self, card: str) -> dict:
        info = CARDS[card]
        return {"id": card, "name": info.name, "description": info.description,
                "rarity": info.rarity, "rarity_name": RARITY_NAMES[info.rarity],
                "price": CARD_PRICES[info.rarity]}

    def to_dict(self) -> dict:
        data = self.game.to_dict()
        data.update(
            mode=self.MODE,
            status=self.status,
            won=self.outcome == "won",
            game_over=self.outcome == "lost",
            winning_tile=EXPEDITION_TARGETS[-1],
            can_undo=(self.status == "playing" and self.undo_charges > 0
                      and self.game.can_undo),
        )
        deck = []
        for card in dict.fromkeys(self.cards):  # Sin repetidos, en orden de llegada
            deck.append({"id": card, "name": CARDS[card].name,
                         "rarity": CARDS[card].rarity, "count": self.cards.count(card)})
        data["expedition"] = {
            "floor": self.floor,
            "floors": len(EXPEDITION_TARGETS),
            "target": self.target,
            "seed": self.seed,
            "guardian": self.floor in GUARDIAN_FLOORS,
            "curses": [{"id": curse, "name": CURSES[curse][0],
                        "description": CURSES[curse][1]} for curse in self.curses],
            "moves_left": self.moves_left,
            "undo_charges": self.undo_charges,
            "gold": self.gold,
            "multiplier": self.multiplier,
            "streak": self.streak,
            "streak_bonus": round(self.streak_bonus, 2),
            "best_streak": self.best_streak,
            "shield": self.shield,
            "phoenix": self.phoenix,
            "deck": deck,
            "reward": self.reward,
            "choices": [self._card_dict(card) for card in self._choices],
            "shop": {"open": self._shop_open,
                     "items": [self._card_dict(card) for card in self._shop],
                     "reroll_price": REROLL_PRICE},
            "event": self.event,
            "outcome": self.outcome,
        }
        return data

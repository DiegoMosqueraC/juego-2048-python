"""
roguelike.py - Modo expedición: el 2048 como un roguelike
=========================================================
Una expedición es una partida por pisos. Cada piso tiene una ficha objetivo
(64, 128, ... 2048) y el tablero se conserva de un piso al siguiente:

1. Al alcanzar el objetivo se elige 1 de 3 bendiciones sorteadas.
2. Desde el segundo piso, cada piso trae una maldición sorteada.
3. Deshacer ya no es gratis: se gastan cargas, que también son una bendición.
4. Si el tablero se bloquea o se acaban las jugadas de «Prisa», la expedición
   termina; no hay vidas extra.

Cada expedición tiene una semilla: con la misma semilla y las mismas jugadas
se repite exactamente la misma partida.
"""

import random
from typing import Optional

from config import (
    DEFAULT_BOARD_SIZE,
    EXPEDITION_TARGETS,
    HASTE_DIVISOR,
    MAX_PROBABILITY_OF_FOUR,
    STARTING_UNDO_CHARGES,
    STONE,
)
from logic import Game2048, MoveResult
from storage import HighscoreStorage
from validation import is_strict_int, normalize_direction

# Identificador -> (nombre, descripción). El orden es el que ve el jugador.
BLESSINGS = {
    "deshacer": ("Segunda oportunidad", "Suma 2 usos de deshacer."),
    "codicia": ("Codicia", "Cada fusión da un 50 % más de puntos."),
    "escoba": ("Escoba", "Elimina todas las fichas de 2 del tablero."),
    "trebol": ("Trébol", "Las fichas nuevas son 4 con más frecuencia."),
    "dinamita": ("Dinamita", "Destruye todas las piedras."),
}
CURSES = {
    "calma": ("Calma", "Este piso no trae maldición."),
    "piedra": ("Piedra", "Aparece un bloque que no se mueve ni se fusiona."),
    "prisa": ("Prisa", "Tienes un número limitado de jugadas para el objetivo."),
}
CHOICES_PER_FLOOR = 3
GREED_BONUS = 0.5
CLOVER_BONUS = 0.15


class Expedition:
    """
    Partida del modo expedición. Ofrece la misma interfaz que Game2048 para la
    API web (move, undo, reset, continue_playing, to_dict) y además choose().
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
        self.outcome: Optional[str] = None
        self._choices: list[str] = []
        self.apply_curse("calma")

    @property
    def target(self) -> int:
        return EXPEDITION_TARGETS[self.floor - 1]

    @property
    def status(self) -> str:
        """'choosing', 'won', 'game_over' o 'playing'."""
        if self._choices:
            return "choosing"
        if self.outcome == "won":
            return "won"
        if self.outcome == "lost":
            return "game_over"
        return "playing"

    # --- Jugadas -----------------------------------------------------------------

    def move(self, direction: object) -> MoveResult:
        """Jugada normal más las reglas del piso: objetivo, prisa y derrota."""
        normalize_direction(direction)  # Se valida siempre, aunque no se juegue.
        if self.status != "playing":
            return MoveResult(moved=False)
        result = self.game.move(direction)
        if not result.moved:
            return result
        if self.moves_left is not None:
            self.moves_left -= 1
        if self.game.max_tile() >= self.target:
            self._clear_floor()
        elif self.game.game_over or self.moves_left == 0:
            self.outcome = "lost"
        return result

    def _clear_floor(self) -> None:
        if self.floor == len(EXPEDITION_TARGETS):
            self.outcome = "won"
            return
        available = [blessing for blessing in BLESSINGS if self._is_useful(blessing)]
        self._choices = self._rng.sample(available, CHOICES_PER_FLOOR)

    def _is_useful(self, blessing: str) -> bool:
        if blessing == "dinamita":
            return any(value == STONE for row in self.game.grid for value in row)
        if blessing == "trebol":
            return self.game.probability_of_four < MAX_PROBABILITY_OF_FOUR
        return True

    def choose(self, index: object) -> bool:
        """
        Aplica la bendición elegida y pasa al piso siguiente.

        :return: False si no hay una elección pendiente.
        :raises ValueError: si el índice no es un entero entre 0 y 2.
        """
        if not self._choices:
            return False
        if not is_strict_int(index) or not 0 <= index < len(self._choices):
            raise ValueError("Elige una bendición entre 0 y 2")
        self.apply_blessing(self._choices[index])
        self._choices = []
        self.floor += 1
        self.game.clear_history()
        self.apply_curse(self._rng.choice(list(CURSES)))
        self.game.game_over = not self.game.can_move()
        if self.game.game_over:
            self.outcome = "lost"
        return True

    def apply_blessing(self, blessing: str) -> None:
        game = self.game
        if blessing == "deshacer":
            self.undo_charges += 2
        elif blessing == "codicia":
            game.points_multiplier += GREED_BONUS
        elif blessing == "trebol":
            game.probability_of_four = min(
                MAX_PROBABILITY_OF_FOUR, game.probability_of_four + CLOVER_BONUS)
        else:
            removed = 2 if blessing == "escoba" else STONE
            game.grid = [[0 if value == removed else value for value in row]
                         for row in game.grid]

    def apply_curse(self, curse: str) -> None:
        self.curse = curse
        self.moves_left: Optional[int] = None
        if curse == "piedra":
            empty = self.game.get_empty_cells()
            if empty:
                row, col = self._rng.choice(empty)
                self.game.grid[row][col] = STONE
        elif curse == "prisa":
            self.moves_left = self.target // HASTE_DIVISOR

    # --- Deshacer y compatibilidad con la API -----------------------------------------

    def undo(self) -> bool:
        """Deshace gastando una carga; devuelve las jugadas de «Prisa»."""
        if self.status != "playing" or self.undo_charges == 0 or not self.game.undo():
            return False
        self.undo_charges -= 1
        if self.moves_left is not None:
            self.moves_left += 1
        return True

    def continue_playing(self) -> bool:
        """La expedición no tiene victoria pendiente: termina al ganar."""
        return False

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
        name, description = CURSES[self.curse]
        data["expedition"] = {
            "floor": self.floor,
            "floors": len(EXPEDITION_TARGETS),
            "target": self.target,
            "seed": self.seed,
            "curse": {"id": self.curse, "name": name, "description": description},
            "moves_left": self.moves_left,
            "undo_charges": self.undo_charges,
            "multiplier": self.game.points_multiplier,
            "choices": [
                {"id": blessing, "name": BLESSINGS[blessing][0],
                 "description": BLESSINGS[blessing][1]}
                for blessing in self._choices
            ],
            "outcome": self.outcome,
        }
        return data

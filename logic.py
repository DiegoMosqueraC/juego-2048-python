"""
logic.py - Núcleo de lógica del juego 2048
==========================================
Implementación pura de las reglas, el estado y las mecánicas del juego. No
depende de ninguna interfaz (web o terminal) ni del disco: el almacenamiento del
récord y el generador de números aleatorios se reciben por inyección de
dependencias, lo que permite probar cada regla de forma aislada y repetible.

Reglas implementadas:
1. Tablero cuadrado (4x4 por defecto, configurable entre 2x2 y 8x8).
2. Inicio con 2 fichas aleatorias (90 % de probabilidad de 2 y 10 % de 4).
3. Desplazamiento y fusión en 4 direcciones con un único algoritmo por línea.
4. Una ficha se fusiona una sola vez por jugada: [2, 2, 2, 2] -> [4, 4, 0, 0].
5. Solo aparece una ficha nueva si el tablero cambió con la jugada.
6. Victoria al alcanzar 2048; el jugador decide si continúa.
7. Fin de juego cuando no hay celdas vacías ni fusiones posibles.
8. Deshacer las últimas jugadas (historial limitado).
"""

import random
from collections import deque
from dataclasses import dataclass, replace
from typing import Optional, Sequence

from config import (
    DEFAULT_BOARD_SIZE,
    INITIAL_TILE_COUNT,
    MAX_UNDO_HISTORY,
    PROBABILITY_OF_FOUR,
    WINNING_TILE,
)
from storage import HighscoreStorage, JsonHighscoreStorage
from validation import (
    normalize_direction,
    validate_board_size,
    validate_grid,
    validate_score,
)

Cell = tuple[int, int]
Grid = list[list[int]]


# -----------------------------------------------------------------------------
# Resultados de una jugada (datos inmutables)
# -----------------------------------------------------------------------------

@dataclass(frozen=True)
class LineMove:
    """Desplazamiento de una ficha dentro de una línea, en índices de esa línea."""

    source: int
    target: int
    merged: bool


@dataclass(frozen=True)
class LineResult:
    """Resultado de comprimir y fusionar una línea hacia su índice 0."""

    values: tuple[int, ...]
    points: int
    moves: tuple[LineMove, ...]
    merged_targets: tuple[int, ...]


@dataclass(frozen=True)
class TileMove:
    """Desplazamiento de una ficha en el tablero; la interfaz web lo usa para animar."""

    from_cell: Cell
    to_cell: Cell
    value: int
    merged: bool

    def to_dict(self) -> dict:
        return {
            "from": list(self.from_cell),
            "to": list(self.to_cell),
            "value": self.value,
            "merged": self.merged,
        }


@dataclass(frozen=True)
class MoveResult:
    """
    Resumen de una jugada. Se evalúa como True si el tablero cambió, por lo que
    sigue siendo compatible con el uso anterior: `if game.move("left"): ...`.
    """

    moved: bool
    points: int = 0
    tile_moves: tuple[TileMove, ...] = ()
    merged_cells: tuple[Cell, ...] = ()
    new_tile: Optional[tuple[int, int, int]] = None

    def __bool__(self) -> bool:
        return self.moved

    def to_dict(self) -> dict:
        new_tile = None
        if self.new_tile is not None:
            row, col, value = self.new_tile
            new_tile = {"row": row, "col": col, "value": value}
        return {
            "moved": self.moved,
            "points": self.points,
            "tile_moves": [tile_move.to_dict() for tile_move in self.tile_moves],
            "merged_cells": [list(cell) for cell in self.merged_cells],
            "new_tile": new_tile,
        }


# -----------------------------------------------------------------------------
# Algoritmo central: una línea a la vez
# -----------------------------------------------------------------------------

def slide_and_merge_line(line: Sequence[int]) -> LineResult:
    """
    Desplaza las fichas de una línea hacia el índice 0 y fusiona las parejas iguales.

    Recorre las fichas no vacías de izquierda a derecha: si la ficha actual es
    igual a la siguiente, ambas ocupan el mismo destino con el doble de valor y
    se avanza dos posiciones (así una ficha nunca se fusiona dos veces).

    Ejemplo: [2, 0, 2, 4] -> valores (4, 4, 0, 0) y 4 puntos.

    :param line: valores de la línea en el orden en que se desplazan.
    :return: valores resultantes, puntos ganados y movimiento de cada ficha.
    """
    tiles = [(index, value) for index, value in enumerate(line) if value != 0]
    values = [0] * len(line)
    moves: list[LineMove] = []
    merged_targets: list[int] = []
    points = 0
    target = 0
    position = 0

    while position < len(tiles):
        source, value = tiles[position]
        next_tile = tiles[position + 1] if position + 1 < len(tiles) else None
        if next_tile is not None and next_tile[1] == value:
            values[target] = value * 2
            points += value * 2
            moves.append(LineMove(source, target, merged=True))
            moves.append(LineMove(next_tile[0], target, merged=True))
            merged_targets.append(target)
            position += 2
        else:
            values[target] = value
            moves.append(LineMove(source, target, merged=False))
            position += 1
        target += 1

    return LineResult(tuple(values), points, tuple(moves), tuple(merged_targets))


# -----------------------------------------------------------------------------
# Partida
# -----------------------------------------------------------------------------

class Game2048:
    """Gestiona el estado y las reglas de una partida de 2048."""

    def __init__(
        self,
        size: int = DEFAULT_BOARD_SIZE,
        storage: Optional[HighscoreStorage] = None,
        rng: Optional[random.Random] = None,
    ):
        """
        :param size: lado del tablero (entre 2 y 8).
        :param storage: dónde se guarda el récord; por defecto, un archivo JSON.
        :param rng: generador aleatorio; inyectarlo con semilla hace las pruebas
                    repetibles.
        """
        self._setup(size, storage, rng)
        self.reset()

    @classmethod
    def from_grid(
        cls,
        grid: Grid,
        score: int = 0,
        storage: Optional[HighscoreStorage] = None,
        rng: Optional[random.Random] = None,
    ) -> "Game2048":
        """
        Crea una partida a partir de un tablero dado, sin fichas aleatorias
        iniciales (útil para pruebas, demostraciones o partidas guardadas).

        :raises ValueError: si el tablero o la puntuación no son válidos.
        """
        board = validate_grid(grid)
        game = cls.__new__(cls)
        game._setup(len(board), storage, rng)
        game.grid = board
        game.score = validate_score(score)
        game.game_over = not game.can_move()
        return game

    def _setup(
        self,
        size: int,
        storage: Optional[HighscoreStorage],
        rng: Optional[random.Random],
    ) -> None:
        """Inicializa los atributos comunes a __init__ y from_grid."""
        self.size: int = validate_board_size(size)
        self._storage = storage if storage is not None else JsonHighscoreStorage()
        # El azar del juego no protege ningún secreto: no requiere un generador
        # criptográfico (hallazgo B311 de bandit revisado y aceptado).
        self._rng = rng if rng is not None else random.Random()  # nosec B311
        self.grid: Grid = []
        self.score: int = 0
        self.highscore: int = self._storage.load()
        self.won: bool = False
        self.keep_playing_after_win: bool = False
        self.game_over: bool = False
        # Cada elemento guarda (tablero, puntuación) previos a una jugada.
        self._history: deque = deque(maxlen=MAX_UNDO_HISTORY)

    # --- Estado derivado ---------------------------------------------------------

    @property
    def awaiting_win_decision(self) -> bool:
        """True si el jugador llegó a 2048 y aún no decide si continúa."""
        return self.won and not self.keep_playing_after_win

    @property
    def accepts_moves(self) -> bool:
        return not self.game_over and not self.awaiting_win_decision

    @property
    def can_undo(self) -> bool:
        return len(self._history) > 0

    @property
    def status(self) -> str:
        """'won' (victoria pendiente), 'game_over' o 'playing'."""
        if self.awaiting_win_decision:
            return "won"
        if self.game_over:
            return "game_over"
        return "playing"

    # --- Inicialización ----------------------------------------------------------

    def reset(self) -> None:
        """Reinicia el tablero, la puntuación, los indicadores y el historial."""
        self.grid = [[0] * self.size for _ in range(self.size)]
        self.score = 0
        self.won = False
        self.keep_playing_after_win = False
        self.game_over = False
        self._history.clear()
        for _ in range(INITIAL_TILE_COUNT):
            self.add_random_tile()

    # --- Fichas ------------------------------------------------------------------

    def get_empty_cells(self) -> list[Cell]:
        """Coordenadas (fila, columna) de todas las celdas vacías."""
        return [
            (row, col)
            for row in range(self.size)
            for col in range(self.size)
            if self.grid[row][col] == 0
        ]

    def add_random_tile(self) -> Optional[tuple[int, int, int]]:
        """
        Coloca un 2 (90 %) o un 4 (10 %) en una celda vacía al azar.

        :return: (fila, columna, valor) de la ficha nueva, o None si no hay espacio.
        """
        empty_cells = self.get_empty_cells()
        if not empty_cells:
            return None
        row, col = self._rng.choice(empty_cells)
        value = 4 if self._rng.random() < PROBABILITY_OF_FOUR else 2
        self.grid[row][col] = value
        return (row, col, value)

    # --- Jugadas -----------------------------------------------------------------

    def move(self, direction: object) -> MoveResult:
        """
        Ejecuta una jugada en la dirección indicada.

        :param direction: 'left', 'right', 'up', 'down' o su alias en español.
        :return: MoveResult; se evalúa como True si el tablero cambió.
        :raises ValueError: si la dirección no es válida (se valida siempre primero).
        """
        normalized = normalize_direction(direction)
        if not self.accepts_moves:
            return MoveResult(moved=False)

        new_grid, result = self._compute_move(normalized)
        if not result.moved:
            return result

        self._history.append(([row[:] for row in self.grid], self.score))
        self.grid = new_grid
        self.score += result.points
        self._update_highscore()
        new_tile = self.add_random_tile()
        self._update_status()
        return replace(result, new_tile=new_tile)

    def _compute_move(self, direction: str) -> tuple[Grid, MoveResult]:
        """Calcula el tablero resultante sin modificar el estado actual."""
        new_grid = [[0] * self.size for _ in range(self.size)]
        points = 0
        tile_moves: list[TileMove] = []
        merged_cells: list[Cell] = []

        for index in range(self.size):
            cells = self._line_cells(direction, index)
            line = [self.grid[row][col] for row, col in cells]
            line_result = slide_and_merge_line(line)
            for (row, col), value in zip(cells, line_result.values):
                new_grid[row][col] = value
            points += line_result.points
            tile_moves.extend(
                TileMove(cells[step.source], cells[step.target], line[step.source],
                         step.merged)
                for step in line_result.moves
                if step.source != step.target or step.merged
            )
            merged_cells.extend(cells[target] for target in line_result.merged_targets)

        result = MoveResult(
            moved=new_grid != self.grid,
            points=points,
            tile_moves=tuple(tile_moves),
            merged_cells=tuple(merged_cells),
        )
        return new_grid, result

    def _line_cells(self, direction: str, index: int) -> list[Cell]:
        """
        Celdas de la fila o columna `index`, ordenadas desde el borde hacia el que
        se desplazan las fichas. Así las 4 direcciones reutilizan el mismo algoritmo.
        """
        positions = range(self.size)
        if direction in ("right", "down"):
            positions = reversed(positions)
        if direction in ("left", "right"):
            return [(index, position) for position in positions]
        return [(position, index) for position in positions]

    # --- Victoria, derrota y récord ----------------------------------------------

    def _update_highscore(self) -> None:
        if self.score > self.highscore:
            self.highscore = self.score
            self._storage.save(self.highscore)

    def _update_status(self) -> None:
        if not self.keep_playing_after_win and self.max_tile() >= WINNING_TILE:
            self.won = True
        self.game_over = not self.can_move()

    def can_move(self) -> bool:
        """True si queda una celda vacía o dos fichas contiguas iguales."""
        if self.get_empty_cells():
            return True
        last = self.size - 1
        horizontal = any(
            row[col] == row[col + 1] for row in self.grid for col in range(last)
        )
        vertical = any(
            self.grid[row][col] == self.grid[row + 1][col]
            for row in range(last)
            for col in range(self.size)
        )
        return horizontal or vertical

    def continue_playing(self) -> bool:
        """
        Permite seguir jugando tras alcanzar 2048 (buscando 4096, 8192, ...).

        :return: True si había una victoria pendiente; False en otro caso (BUG-05).
        """
        if not self.awaiting_win_decision:
            return False
        self.keep_playing_after_win = True
        self.won = False
        return True

    # --- Deshacer ----------------------------------------------------------------

    def undo(self) -> bool:
        """
        Restaura el tablero y la puntuación previos a la última jugada.

        :return: True si se deshizo una jugada; False si no hay historial.
        """
        if not self._history:
            return False
        self.grid, self.score = self._history.pop()
        self.game_over = False
        self.won = not self.keep_playing_after_win and self.max_tile() >= WINNING_TILE
        return True

    # --- Consulta y serialización ------------------------------------------------

    def max_tile(self) -> int:
        """Valor de la ficha más alta del tablero."""
        return max(max(row) for row in self.grid)

    def to_dict(self) -> dict:
        """Estado serializable para la API web (el tablero se entrega como copia)."""
        return {
            "size": self.size,
            "grid": [row[:] for row in self.grid],
            "score": self.score,
            "highscore": self.highscore,
            "won": self.won,
            "game_over": self.game_over,
            "status": self.status,
            "max_tile": self.max_tile(),
            "winning_tile": WINNING_TILE,
            "can_undo": self.can_undo,
        }

    def __str__(self) -> str:
        """Tablero en texto, alineado según la ficha más larga."""
        width = max(4, len(str(self.max_tile())))
        return "\n".join(
            " ".join(str(value or "·").rjust(width) for value in row)
            for row in self.grid
        )

"""
logic.py - Núcleo de Lógica del Juego 2048
==========================================
Este módulo contiene la implementación pura de las reglas, el estado y las mecánicas
del clásico juego 2048. Está desacoplado de cualquier interfaz gráfica o de terminal,
lo que permite utilizarlo tanto en consolas como en entornos gráficos o web.

Reglas implementadas:
1. Tablero de 4x4 casillas.
2. Inicio con 2 fichas aleatorias (90% de probabilidad de ser 2, 10% de ser 4).
3. Desplazamiento y combinación en 4 direcciones (Izquierda, Derecha, Arriba, Abajo).
4. Regla de combinación única por movimiento: [2, 2, 2, 2] se convierte en [4, 4, 0, 0].
5. Generación de nueva ficha únicamente si el tablero sufrió algún cambio tras el movimiento.
6. Detección de victoria al alcanzar la ficha 2048.
7. Detección de fin de juego (Game Over) cuando no hay celdas vacías ni movimientos posibles.
8. Sistema de Deshacer (Undo) para revertir jugadas.
"""

import copy
import json
import os
import random
from typing import List, Tuple, Optional, Dict, Any

# Variable de entorno que permite elegir dónde se guarda el récord (BUG-08).
DATA_DIR_ENV_VAR = "JUEGO2048_DATA_DIR"
PROGRAM_DIR = os.path.dirname(os.path.abspath(__file__))


def default_highscore_path() -> str:
    """Ruta absoluta del récord: no depende del directorio desde donde se ejecuta."""
    data_dir = os.environ.get(DATA_DIR_ENV_VAR) or PROGRAM_DIR
    return os.path.join(data_dir, "highscore.json")


class Game2048:
    """
    Clase que gestiona el estado y la lógica de una partida de 2048.
    """

    def __init__(self, size: int = 4, highscore_file: Optional[str] = None):
        """
        Inicializa una nueva instancia del juego 2048.

        :param size: Tamaño de la cuadrícula (por defecto 4x4).
        :param highscore_file: Ruta del archivo JSON donde se almacena el récord de puntuación.
        """
        self.size: int = size
        self.highscore_file: str = highscore_file or default_highscore_path()
        self.grid: List[List[int]] = []
        self.score: int = 0
        self.highscore: int = self._load_highscore()
        self.won: bool = False
        self.keep_playing_after_win: bool = False
        self.game_over: bool = False
        
        # Pila de historial para permitir la funcionalidad de 'Deshacer' (Undo)
        # Cada elemento almacena una copia profunda del tablero y el puntaje
        self.history: List[Tuple[List[List[int]], int]] = []

        # Inicializamos el tablero con celdas vacías y generamos las 2 fichas iniciales
        self.reset()

    # -------------------------------------------------------------------------
    # Persistencia del Highscore
    # -------------------------------------------------------------------------

    def _load_highscore(self) -> int:
        """Carga la puntuación máxima guardada en disco si existe."""
        if os.path.exists(self.highscore_file):
            try:
                with open(self.highscore_file, "r", encoding="utf-8") as f:
                    value = json.load(f).get("highscore", 0)
            except (OSError, ValueError, AttributeError):
                return 0
            # BUG-09: solo se aceptan enteros no negativos (bool es subclase de int).
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                return value
        return 0

    def _save_highscore(self) -> None:
        """Guarda la puntuación máxima en disco si se ha superado el récord."""
        if self.score > self.highscore:
            self.highscore = self.score
            try:
                os.makedirs(os.path.dirname(self.highscore_file), exist_ok=True)
                with open(self.highscore_file, "w", encoding="utf-8") as f:
                    json.dump({"highscore": self.highscore}, f, indent=4)
            except Exception as e:
                print(f"Advertencia: No se pudo guardar el récord: {e}")

    # -------------------------------------------------------------------------
    # Inicialización y Reinicio
    # -------------------------------------------------------------------------

    def reset(self) -> None:
        """
        Reinicia el tablero a un estado inicial:
        - Todas las celdas en 0.
        - Puntuación en 0.
        - Dos fichas aleatorias añadidas.
        - Historial de jugadas reiniciado.
        """
        self.grid = [[0 for _ in range(self.size)] for _ in range(self.size)]
        self.score = 0
        self.won = False
        self.keep_playing_after_win = False
        self.game_over = False
        self.history.clear()

        # Generamos las dos primeras fichas del juego
        self.add_random_tile()
        self.add_random_tile()

    # -------------------------------------------------------------------------
    # Manipulación de Fichas
    # -------------------------------------------------------------------------

    def get_empty_cells(self) -> List[Tuple[int, int]]:
        """
        Encuentra y retorna todas las coordenadas (fila, columna) que tienen valor 0.
        """
        empty_cells = []
        for r in range(self.size):
            for c in range(self.size):
                if self.grid[r][c] == 0:
                    empty_cells.append((r, c))
        return empty_cells

    def add_random_tile(self) -> Optional[Tuple[int, int, int]]:
        """
        Coloca una nueva ficha en una celda vacía aleatoria.
        - 90% de probabilidad de generar un 2.
        - 10% de probabilidad de generar un 4.
        
        :return: Tupla (fila, columna, valor) de la nueva ficha generada, o None si no hay espacio.
        """
        empty_cells = self.get_empty_cells()
        if not empty_cells:
            return None

        # Escoger una posición al azar
        r, c = random.choice(empty_cells)
        # 90% probabilidad de 2, 10% probabilidad de 4
        value = 2 if random.random() < 0.9 else 4
        self.grid[r][c] = value
        return (r, c, value)

    # -------------------------------------------------------------------------
    # Mecánicas de Movimiento y Fusión
    # -------------------------------------------------------------------------

    @staticmethod
    def _slide_and_merge_row(row: List[int]) -> Tuple[List[int], int]:
        """
        Aplica la compresión y fusión hacia la izquierda a una sola fila.
        
        Pasos del algoritmo:
        1. Comprimir: Filtrar los ceros hacia la derecha.
           Ejemplo: [2, 0, 2, 4] -> [2, 2, 4]
        2. Fusionar: Comparar celdas adyacentes de izquierda a derecha.
           Si son iguales, duplicar la primera y vaciar la segunda.
           Avanzar para evitar combinaciones múltiples continuas (e.g., [2, 2, 2, 2] -> [4, 4]).
           Ejemplo: [2, 2, 4] -> [4, 0, 4], sumando 4 puntos.
        3. Comprimir de nuevo: Eliminar los huecos dejados por las fusiones y rellenar con ceros.
           Ejemplo: [4, 0, 4] -> [4, 4, 0, 0]
           
        :param row: Lista de enteros representando una fila.
        :return: Tupla con la nueva fila resultante y los puntos obtenidos en las fusiones.
        """
        # Paso 1: Filtrar ceros
        compact = [val for val in row if val != 0]
        
        merged = []
        points = 0
        skip = False

        # Paso 2: Fusionar elementos adyacentes iguales
        for i in range(len(compact)):
            if skip:
                skip = False
                continue
            
            # Si el elemento actual es igual al siguiente, se fusionan
            if i + 1 < len(compact) and compact[i] == compact[i + 1]:
                merged_val = compact[i] * 2
                merged.append(merged_val)
                points += merged_val
                skip = True  # El siguiente elemento ya se fusionó, saltarlo
            else:
                merged.append(compact[i])

        # Paso 3: Completar con ceros hasta alcanzar la longitud original
        while len(merged) < len(row):
            merged.append(0)

        return merged, points

    def _rotate_matrix_clockwise(self, matrix: List[List[int]]) -> List[List[int]]:
        """
        Rota la matriz 90 grados en el sentido de las agujas del reloj.
        Esto permite reusar el movimiento hacia la izquierda para todas las direcciones.
        """
        return [list(row) for row in zip(*matrix[::-1])]

    def _rotate_matrix_counter_clockwise(self, matrix: List[List[int]]) -> List[List[int]]:
        """Rota la matriz 90 grados en sentido antihorario."""
        return [list(row) for row in zip(*matrix)][::-1]

    def _invert_matrix_rows(self, matrix: List[List[int]]) -> List[List[int]]:
        """Invierte horizontalmente cada fila de la matriz (reflejo especular)."""
        return [row[::-1] for row in matrix]

    def _transpose_matrix(self, matrix: List[List[int]]) -> List[List[int]]:
        """Transpone la matriz (filas por columnas)."""
        return [list(row) for row in zip(*matrix)]

    def move(self, direction: str) -> bool:
        """
        Ejecuta un movimiento en la dirección especificada ('left', 'right', 'up', 'down').
        
        :param direction: 'left', 'right', 'up' o 'down' (insensible a mayúsculas/minúsculas).
        :return: True si el tablero cambió y el movimiento fue válido; False si no hubo cambio.
        """
        if not isinstance(direction, str):
            raise ValueError(f"Dirección inválida: {direction!r}")
        dir_lower = direction.strip().lower()
        if dir_lower not in ('left', 'right', 'up', 'down', 'izquierda', 'derecha', 'arriba', 'abajo'):
            raise ValueError(f"Dirección inválida: {direction}")

        # Normalizamos a inglés
        dir_map = {
            'izquierda': 'left',
            'derecha': 'right',
            'arriba': 'up',
            'abajo': 'down',
            'left': 'left',
            'right': 'right',
            'up': 'up',
            'down': 'down'
        }
        target_dir = dir_map[dir_lower]

        # BUG-06: con la partida terminada o una victoria sin decidir no se mueve nada.
        if self.game_over or (self.won and not self.keep_playing_after_win):
            return False

        # Guardamos una copia previa del estado para comprobar si hubo cambios y para el historial
        grid_before = copy.deepcopy(self.grid)
        score_before = self.score

        new_grid: List[List[int]] = []
        earned_points = 0

        # Implementamos todas las direcciones transformando el tablero hacia 'left',
        # aplicando la lógica de fila y devolviendo el tablero a su orientación original:
        if target_dir == 'left':
            for row in self.grid:
                new_row, pts = self._slide_and_merge_row(row)
                new_grid.append(new_row)
                earned_points += pts

        elif target_dir == 'right':
            # Invertimos cada fila, aplicamos 'left' y volvemos a invertir
            for row in self.grid:
                reversed_row = row[::-1]
                new_row, pts = self._slide_and_merge_row(reversed_row)
                new_grid.append(new_row[::-1])
                earned_points += pts

        elif target_dir == 'up':
            # Transponemos la matriz (las columnas pasan a ser filas), aplicamos 'left' y re-transponemos
            transposed = self._transpose_matrix(self.grid)
            processed_transposed = []
            for row in transposed:
                new_row, pts = self._slide_and_merge_row(row)
                processed_transposed.append(new_row)
                earned_points += pts
            new_grid = self._transpose_matrix(processed_transposed)

        elif target_dir == 'down':
            # Transponemos, invertimos filas (como si fuera movimiento hacia la derecha de la transpuesta),
            # procesamos y devolvemos
            transposed = self._transpose_matrix(self.grid)
            processed_transposed = []
            for row in transposed:
                reversed_row = row[::-1]
                new_row, pts = self._slide_and_merge_row(reversed_row)
                processed_transposed.append(new_row[::-1])
                earned_points += pts
            new_grid = self._transpose_matrix(processed_transposed)

        # Verificamos si el tablero realmente cambió
        if new_grid == self.grid:
            # No hubo desplazamiento ni fusiones posibles en esta dirección
            return False

        # Guardar en el historial para permitir 'Deshacer'
        self.history.append((grid_before, score_before))
        # Limitar el historial a las últimas 20 jugadas para evitar consumo excesivo de memoria
        if len(self.history) > 20:
            self.history.pop(0)

        # Actualizar el estado oficial
        self.grid = new_grid
        self.score += earned_points
        self._save_highscore()

        # Añadir nueva ficha aleatoria en una celda vacía
        self.add_random_tile()

        # Verificar condiciones de Victoria y Fin de Juego
        self._check_game_status()

        return True

    # -------------------------------------------------------------------------
    # Verificación de Victoria y Fin de Juego
    # -------------------------------------------------------------------------

    def _check_game_status(self) -> None:
        """
        Comprueba si el jugador ha ganado (ficha 2048) o si ha perdido (no quedan movimientos).
        """
        # Comprobar condición de victoria (aparición de una ficha >= 2048)
        if not self.won and not self.keep_playing_after_win:
            for row in self.grid:
                if any(val >= 2048 for val in row):
                    self.won = True
                    break

        # Comprobar si quedan movimientos posibles
        if not self.can_move():
            self.game_over = True

    def can_move(self) -> bool:
        """
        Determina si aún existe al menos un movimiento válido en cualquier dirección.
        Un movimiento es posible si:
        1. Hay al menos una celda con valor 0.
        2. Dos celdas contiguas horizontalmente tienen el mismo valor.
        3. Dos celdas contiguas verticalmente tienen el mismo valor.
        """
        # Si hay celdas vacías, siempre se puede mover
        if len(self.get_empty_cells()) > 0:
            return True

        # Verificar adyacencias horizontales y verticales
        for r in range(self.size):
            for c in range(self.size):
                val = self.grid[r][c]
                # Comparar con la celda a la derecha
                if c + 1 < self.size and val == self.grid[r][c + 1]:
                    return True
                # Comparar con la celda de abajo
                if r + 1 < self.size and val == self.grid[r + 1][c]:
                    return True

        return False

    def continue_playing(self) -> bool:
        """
        Permite al jugador seguir jugando tras alcanzar la ficha 2048
        para buscar puntuaciones más altas (4096, 8192, etc.).

        :return: True si había una victoria pendiente; False en caso contrario (BUG-05).
        """
        if not self.won:
            return False
        self.keep_playing_after_win = True
        self.won = False
        return True

    # -------------------------------------------------------------------------
    # Función Deshacer (Undo)
    # -------------------------------------------------------------------------

    def undo(self) -> bool:
        """
        Revierte el tablero y la puntuación al estado inmediatamente anterior.
        :return: True si se pudo deshacer; False si no hay historial disponible.
        """
        if not self.history:
            return False

        prev_grid, prev_score = self.history.pop()
        self.grid = prev_grid
        self.score = prev_score
        self.game_over = False
        # Reevaluamos victoria con el tablero actual
        self.won = any(val >= 2048 for row in self.grid for val in row) and not self.keep_playing_after_win
        return True

    # -------------------------------------------------------------------------
    # Utilidades de Inspección y Serialización
    # -------------------------------------------------------------------------

    def max_tile(self) -> int:
        """Devuelve el valor de la ficha más alta presente en el tablero."""
        return max(max(row) for row in self.grid)

    def to_dict(self) -> Dict[str, Any]:
        """
        Serializa el estado del juego en un diccionario (útil para APIs y frontends web).
        """
        return {
            "size": self.size,
            "grid": [row[:] for row in self.grid],
            "score": self.score,
            "highscore": self.highscore,
            "won": self.won,
            "game_over": self.game_over,
            "max_tile": self.max_tile(),
            "can_undo": len(self.history) > 0
        }

    def __str__(self) -> str:
        """Representación simple en texto del tablero para depuración."""
        lines = []
        for row in self.grid:
            lines.append(" ".join(f"{val:4d}" if val != 0 else "   ." for val in row))
        return "\n".join(lines)

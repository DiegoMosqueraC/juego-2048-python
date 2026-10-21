"""
tests_logic.py - Pruebas Unitarias para la Lógica de 2048
=========================================================
Este script verifica que todas las reglas del juego 2048 se cumplan
con exactitud matemática:
1. Compresión y fusión de filas.
2. Comportamiento en movimientos izquierda, derecha, arriba y abajo.
3. Detección precisa de fin de partida (Game Over).
4. Detección de condición de victoria (2048).
5. Sistema de Deshacer (Undo).
"""

import unittest
from logic import Game2048


class TestGame2048Logic(unittest.TestCase):

    def setUp(self):
        # Usamos un archivo de puntuación de prueba para no tocar el real
        self.game = Game2048(size=4, highscore_file="test_highscore.json")

    def tearDown(self):
        import os
        if os.path.exists("test_highscore.json"):
            os.remove("test_highscore.json")

    def test_row_merge_basic(self):
        """Prueba fusiones básicas [2, 0, 2, 0] -> [4, 0, 0, 0]"""
        row = [2, 0, 2, 0]
        res, pts = Game2048._slide_and_merge_row(row)
        self.assertEqual(res, [4, 0, 0, 0])
        self.assertEqual(pts, 4)

    def test_row_merge_no_double_combination(self):
        """Prueba que [2, 2, 2, 2] se convierta en [4, 4, 0, 0] y no [8, 0, 0, 0]"""
        row = [2, 2, 2, 2]
        res, pts = Game2048._slide_and_merge_row(row)
        self.assertEqual(res, [4, 4, 0, 0])
        self.assertEqual(pts, 8)

    def test_row_merge_three_elements(self):
        """Prueba que [2, 2, 2, 0] priorice de izquierda a derecha -> [4, 2, 0, 0]"""
        row = [2, 2, 2, 0]
        res, pts = Game2048._slide_and_merge_row(row)
        self.assertEqual(res, [4, 2, 0, 0])
        self.assertEqual(pts, 4)

    def test_row_no_merge_when_different(self):
        """Prueba que números diferentes solo se compriman: [2, 4, 8, 16]"""
        row = [0, 2, 0, 4]
        res, pts = Game2048._slide_and_merge_row(row)
        self.assertEqual(res, [2, 4, 0, 0])
        self.assertEqual(pts, 0)

    def test_move_left(self):
        """Prueba movimiento hacia la izquierda en una cuadrícula fija."""
        self.game.grid = [
            [2, 0, 0, 2],
            [4, 4, 0, 0],
            [0, 0, 0, 0],
            [2, 2, 4, 8]
        ]
        self.game.score = 0
        moved = self.game.move("left")
        self.assertTrue(moved)
        # Fila 0 debe haber sido [4, 0, 0, 0] antes del random tile
        self.assertEqual(self.game.grid[0][0], 4)
        # Fila 1 debe tener [8, 0, 0, 0]
        self.assertEqual(self.game.grid[1][0], 8)
        # Fila 3 debe tener [4, 4, 8, 0]
        self.assertEqual(self.game.grid[3][:3], [4, 4, 8])
        # Puntos: (2+2=4) + (4+4=8) + (2+2=4) = 16
        self.assertEqual(self.game.score, 16)

    def test_move_right(self):
        """Prueba movimiento hacia la derecha."""
        self.game.grid = [
            [2, 0, 0, 2],
            [0, 0, 0, 0],
            [0, 0, 0, 0],
            [0, 0, 0, 0]
        ]
        moved = self.game.move("right")
        self.assertTrue(moved)
        self.assertEqual(self.game.grid[0][3], 4)

    def test_move_up(self):
        """Prueba movimiento hacia arriba (vertical)."""
        self.game.grid = [
            [2, 0, 0, 0],
            [2, 0, 0, 0],
            [4, 0, 0, 0],
            [4, 0, 0, 0]
        ]
        moved = self.game.move("up")
        self.assertTrue(moved)
        self.assertEqual(self.game.grid[0][0], 4)
        self.assertEqual(self.game.grid[1][0], 8)

    def test_move_down(self):
        """Prueba movimiento hacia abajo (vertical)."""
        self.game.grid = [
            [2, 0, 0, 0],
            [2, 0, 0, 0],
            [4, 0, 0, 0],
            [4, 0, 0, 0]
        ]
        moved = self.game.move("down")
        self.assertTrue(moved)
        self.assertEqual(self.game.grid[2][0], 4)
        self.assertEqual(self.game.grid[3][0], 8)

    def test_invalid_move_returns_false(self):
        """Si las fichas ya están compactadas y no hay fusiones, move() debe retornar False."""
        self.game.grid = [
            [2, 4, 8, 16],
            [0, 0, 0, 0],
            [0, 0, 0, 0],
            [0, 0, 0, 0]
        ]
        moved = self.game.move("left")
        self.assertFalse(moved)

    def test_game_over_detection(self):
        """Comprueba que cuando no hay movimientos ni celdas vacías, can_move() sea False."""
        # Tablero lleno sin adyacencias iguales
        self.game.grid = [
            [2, 4, 2, 4],
            [4, 2, 4, 2],
            [2, 4, 2, 4],
            [4, 2, 4, 2]
        ]
        self.assertFalse(self.game.can_move())

        # Si modificamos dos adyacentes para que sean iguales, can_move() debe ser True
        self.game.grid[0][0] = 4
        self.assertTrue(self.game.can_move())

    def test_win_condition(self):
        """Comprueba detección de victoria al llegar a 2048."""
        self.game.grid = [
            [1024, 1024, 0, 0],
            [0, 0, 0, 0],
            [0, 0, 0, 0],
            [0, 0, 0, 0]
        ]
        self.game.move("left")
        self.assertTrue(self.game.won)

    def test_undo_feature(self):
        """Comprueba que deshacer retorne exactamente al estado anterior."""
        self.game.grid = [
            [2, 2, 0, 0],
            [0, 0, 0, 0],
            [0, 0, 0, 0],
            [0, 0, 0, 0]
        ]
        initial_score = self.game.score
        self.game.move("left")
        self.assertEqual(self.game.grid[0][0], 4)
        
        # Deshacemos
        undone = self.game.undo()
        self.assertTrue(undone)
        self.assertEqual(self.game.grid[0], [2, 2, 0, 0])
        self.assertEqual(self.game.score, initial_score)


if __name__ == "__main__":
    unittest.main()

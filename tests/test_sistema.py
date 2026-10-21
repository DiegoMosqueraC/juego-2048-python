"""
test_sistema.py - Pruebas de sistema y de aceptación
====================================================
Las pruebas de sistema recorren partidas completas a través de la API HTTP
real, como lo haría el navegador, y verifican invariantes del juego en cada
paso. Las pruebas de aceptación expresan las historias de usuario con el
formato Dado / Cuando / Entonces.
"""

import random

from helpers import send_request
from logic import Game2048
from storage import JsonHighscoreStorage
from validation import is_valid_tile

DIRECTIONS = ["left", "down", "right", "up"]
EMPTY_ROW = [0, 0, 0, 0]


def test_complete_game_through_the_api_keeps_the_rules(api_server):
    """Prueba de sistema: se juega por HTTP hasta que no quedan movimientos."""
    previous_score = 0
    points_reported = 0
    requests = 0
    status = "playing"
    while status != "game_over" and requests < 3000:
        direction = DIRECTIONS[requests % 4]
        _, _, data = send_request(api_server, "POST", "/api/move",
                                  body={"direction": direction})
        requests += 1
        if data["status"] == "won":
            send_request(api_server, "POST", "/api/continue", body={})
        points_reported += data["points"]
        assert all(is_valid_tile(value) for row in data["grid"] for value in row)
        assert data["score"] >= previous_score
        assert data["score"] == points_reported
        assert data["highscore"] >= data["score"]
        previous_score = data["score"]
        status = data["status"]
    assert status == "game_over"
    assert not api_server.game.can_move()


def test_every_valid_move_adds_exactly_one_tile(make_game):
    """Prueba de sistema de la lógica: 300 jugadas al azar con semilla fija."""
    game = make_game(rng=random.Random(99))
    chooser = random.Random(7)
    for _ in range(300):
        if game.game_over:
            break
        tiles_before = sum(1 for row in game.grid for value in row if value)
        result = game.move(chooser.choice(DIRECTIONS))
        if result:
            merges = len(result.merged_cells)
            tiles_after = sum(1 for row in game.grid for value in row if value)
            assert tiles_after == tiles_before - merges + 1


# --- Pruebas de aceptación (historias de usuario) ------------------------------

def test_hu01_player_combines_equal_tiles(make_game):
    """
    Dado un tablero con dos fichas de 8 en la misma fila
    Cuando el jugador desliza hacia la izquierda
    Entonces aparece una ficha de 16 y la puntuación aumenta 16 puntos.
    """
    game = make_game(grid=[[8, 0, 8, 0], EMPTY_ROW, EMPTY_ROW, EMPTY_ROW])
    game.move("left")
    assert game.grid[0][0] == 16
    assert game.score == 16


def test_hu02_player_undoes_a_mistake(make_game):
    """
    Dado que el jugador hizo una jugada
    Cuando pulsa Deshacer
    Entonces el tablero y la puntuación vuelven al estado anterior.
    """
    game = make_game(grid=[[4, 4, 0, 0], [2, 0, 0, 0], EMPTY_ROW, EMPTY_ROW])
    game.move("left")
    game.undo()
    assert game.grid == [[4, 4, 0, 0], [2, 0, 0, 0], EMPTY_ROW, EMPTY_ROW]
    assert game.score == 0


def test_hu03_record_survives_between_sessions(tmp_path):
    """
    Dado un récord guardado de 100 puntos
    Cuando el jugador lo supera y cierra el juego
    Entonces la siguiente sesión muestra el nuevo récord.
    """
    path = tmp_path / "highscore.json"
    JsonHighscoreStorage(path).save(100)
    first = Game2048.from_grid([[64, 64, 0, 0], EMPTY_ROW, EMPTY_ROW, EMPTY_ROW],
                               score=0, storage=JsonHighscoreStorage(path))
    first.score = 90
    first.move("left")  # 90 + 128 = 218
    second_session = Game2048(storage=JsonHighscoreStorage(path))
    assert second_session.highscore == 218


def test_hu04_player_decides_to_keep_playing_after_2048(api_server):
    """
    Dado un tablero a una jugada de 2048
    Cuando el jugador forma la ficha 2048
    Entonces se le anuncia la victoria y puede elegir seguir jugando.
    """
    api_server.game.grid = [[1024, 1024, 0, 0], EMPTY_ROW, EMPTY_ROW, EMPTY_ROW]
    _, _, won = send_request(api_server, "POST", "/api/move",
                             body={"direction": "left"})
    assert won["status"] == "won"
    _, _, after = send_request(api_server, "POST", "/api/continue", body={})
    assert after["status"] == "playing"


def test_hu05_game_ends_when_no_moves_remain(api_server):
    """
    Dado un tablero lleno sin parejas salvo un último hueco
    Cuando el jugador hace la última jugada posible
    Entonces la partida termina y puede deshacer esa jugada.
    """
    api_server.game.grid = [[2, 4, 2, 4], [4, 2, 4, 2], [8, 16, 8, 16],
                            [32, 64, 128, 0]]
    _, _, over = send_request(api_server, "POST", "/api/move",
                              body={"direction": "right"})
    # El único hueco queda junto a 8 y 32: la ficha nueva (2 o 4) no tiene pareja.
    assert over["status"] == "game_over"
    _, _, undone = send_request(api_server, "POST", "/api/undo", body={})
    assert undone["status"] == "playing"

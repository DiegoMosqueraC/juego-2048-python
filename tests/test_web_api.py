"""
test_web_api.py - Pruebas de integración de la API HTTP (caja gris)
===================================================================
Se levanta el servidor real en un puerto libre y se le envían peticiones HTTP,
como haría el navegador. Además de las respuestas, se inspecciona el estado
interno de la partida (api_server.game): por eso son pruebas de caja gris.
También se prueban por separado las funciones puras de validación.
"""

import io

import pytest

from helpers import send_request
from web_ui import RequestError, host_is_allowed, parse_json_body

EMPTY_ROW = [0, 0, 0, 0]


# --- Flujo normal de la API ----------------------------------------------------

def test_state_returns_the_current_game(api_server):
    status, headers, data = send_request(api_server, "GET", "/api/state")
    assert status == 200
    assert headers["Content-Type"].startswith("application/json")
    assert headers["Cache-Control"] == "no-store"
    assert data["grid"] == api_server.game.grid
    assert data["status"] == "playing"


def test_move_updates_the_game_and_reports_animation_data(api_server):
    api_server.game.grid = [[2, 2, 0, 0], EMPTY_ROW, EMPTY_ROW, EMPTY_ROW]
    status, _, data = send_request(api_server, "POST", "/api/move",
                                   body={"direction": "left"})
    assert status == 200
    assert data["moved"] is True
    assert data["gained_points"] == data["points"] == 4
    assert data["merged_cells"] == [[0, 0]]
    assert data["new_tile"] is not None
    assert api_server.game.score == 4


def test_move_that_changes_nothing_reports_moved_false(api_server):
    api_server.game.grid = [[2, 4, 8, 16], EMPTY_ROW, EMPTY_ROW, EMPTY_ROW]
    _, _, data = send_request(api_server, "POST", "/api/move", body={"direction": "up"})
    assert data["moved"] is False


def test_move_without_direction_returns_400(api_server):
    status, _, data = send_request(api_server, "POST", "/api/move", body={})
    assert status == 400
    assert "dirección" in data["error"].lower()


def test_undo_and_reset(api_server):
    api_server.game.grid = [[2, 2, 0, 0], EMPTY_ROW, EMPTY_ROW, EMPTY_ROW]
    send_request(api_server, "POST", "/api/move", body={"direction": "left"})
    _, _, undone = send_request(api_server, "POST", "/api/undo", body={})
    assert undone["undone"] is True
    assert undone["grid"][0] == [2, 2, 0, 0]

    _, _, again = send_request(api_server, "POST", "/api/undo", body={})
    assert again["undone"] is False

    _, _, reset = send_request(api_server, "POST", "/api/reset", body={})
    assert reset["score"] == 0
    assert sum(1 for row in reset["grid"] for value in row if value) == 2


def test_continue_only_works_with_a_pending_victory(api_server):
    status, _, data = send_request(api_server, "POST", "/api/continue", body={})
    assert status == 409
    api_server.game.grid = [[1024, 1024, 0, 0], EMPTY_ROW, EMPTY_ROW, EMPTY_ROW]
    _, _, moved = send_request(api_server, "POST", "/api/move",
                               body={"direction": "left"})
    assert moved["status"] == "won"
    status, _, data = send_request(api_server, "POST", "/api/continue", body={})
    assert status == 200
    assert data["status"] == "playing"


# --- Rutas, métodos y cabeceras ------------------------------------------------

@pytest.mark.parametrize("method, path", [("GET", "/api/otra"), ("POST", "/api/otra")])
def test_unknown_api_routes_return_json_404(api_server, method, path):
    status, _, data = send_request(api_server, method, path, body={} if method ==
                                   "POST" else None)
    assert status == 404
    assert "error" in data


def test_static_files_and_security_headers(api_server):
    status, headers, body = send_request(api_server, "GET", "/")
    assert status == 200
    assert "<title>2048: La Mina</title>" in body
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["Cache-Control"] == "no-cache"


def test_favicon_returns_no_content(api_server):
    status, _, _ = send_request(api_server, "GET", "/favicon.ico")
    assert status == 204


def test_head_request_respects_host_validation(api_server):
    ok, _, _ = send_request(api_server, "HEAD", "/index.html")
    forbidden, _, _ = send_request(api_server, "HEAD", "/index.html",
                                   headers={"Host": "evil.example"})
    assert (ok, forbidden) == (200, 403)


def test_options_preflight_is_not_supported(api_server):
    """Sin respuesta CORS válida, otro sitio no puede enviar JSON a la API."""
    status, headers, _ = send_request(api_server, "OPTIONS", "/api/move")
    assert status == 501
    assert headers.get("Access-Control-Allow-Origin") is None


# --- Funciones puras de validación (unitarias) ---------------------------------

@pytest.mark.parametrize(
    "host, allowed",
    [
        (None, True), ("", True), ("127.0.0.1:8080", True), ("localhost", True),
        ("LOCALHOST:9000", True), ("[::1]:8080", True),
        ("evil.example", False), ("127.0.0.1.evil.example:80", False),
        ("[::2]:8080", False), ("localhost.evil.example", False),
    ],
)
def test_host_is_allowed(host, allowed):
    assert host_is_allowed(host) is allowed


def test_parse_json_body_reads_exactly_content_length():
    stream = io.BytesIO(b'{"direction": "up"}EXTRA')
    assert parse_json_body("19", stream.read) == {"direction": "up"}


@pytest.mark.parametrize(
    "length, body, status",
    [("-1", b"", 400), ("x", b"", 400), ("2000", b"", 413), ("2", b"[]", 400),
     ("3", b"{a}", 400), ("2", b"\xff\xfe", 400)],
)
def test_parse_json_body_rejections(length, body, status):
    with pytest.raises(RequestError) as error:
        parse_json_body(length, io.BytesIO(body).read)
    assert error.value.status == status


def test_parse_json_body_without_body_is_an_empty_object():
    assert parse_json_body(None, io.BytesIO(b"").read) == {}


# --- Modo expedición -------------------------------------------------------------

@pytest.fixture
def expedition_server():
    from doubles import FakeHighscoreStorage
    from roguelike import Expedition
    from web_ui import create_server
    import threading

    server = create_server(Expedition(storage=FakeHighscoreStorage(), seed=7), port=0)
    thread = threading.Thread(target=server.serve_forever, args=(0.05,), daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()


def test_expedition_state_reports_the_floor(expedition_server):
    _, _, data = send_request(expedition_server, "GET", "/api/state")
    assert data["mode"] == "expedition"
    assert data["expedition"]["floor"] == 1


def test_choose_takes_a_card_and_the_shop_leads_to_the_next_floor(expedition_server):
    expedition = expedition_server.game
    expedition.game.grid = [[32, 32, 0, 0], EMPTY_ROW, EMPTY_ROW, EMPTY_ROW]
    _, _, moved = send_request(expedition_server, "POST", "/api/move",
                               body={"direction": "left"})
    assert moved["status"] == "choosing"
    status, _, data = send_request(expedition_server, "POST", "/api/choose",
                                   body={"index": 0})
    assert status == 200
    assert data["status"] == "shop"
    _, _, data = send_request(expedition_server, "POST", "/api/shop",
                              body={"action": "leave"})
    assert data["expedition"]["floor"] == 2


def test_shop_without_enough_gold_returns_409(expedition_server):
    expedition = expedition_server.game
    expedition._shop, expedition._shop_open = ["fenix"], True
    status, _, data = send_request(expedition_server, "POST", "/api/shop",
                                   body={"action": "buy", "index": 0})
    assert status == 409
    assert "oro" in data["error"]


@pytest.mark.parametrize("body", [{"action": "steal"}, {"action": "buy", "index": 5}])
def test_invalid_shop_request_returns_400(expedition_server, body):
    expedition_server.game._shop, expedition_server.game._shop_open = ["bolsa"], True
    status, _, _ = send_request(expedition_server, "POST", "/api/shop", body=body)
    assert status == 400


def test_shop_in_classic_mode_returns_409(api_server):
    status, _, _ = send_request(api_server, "POST", "/api/shop",
                                body={"action": "leave"})
    assert status == 409


def test_choose_with_an_invalid_index_returns_400(expedition_server):
    expedition = expedition_server.game
    expedition.game.grid = [[32, 32, 0, 0], EMPTY_ROW, EMPTY_ROW, EMPTY_ROW]
    send_request(expedition_server, "POST", "/api/move", body={"direction": "left"})
    status, _, _ = send_request(expedition_server, "POST", "/api/choose",
                                body={"index": 9})
    assert status == 400


def test_choose_without_a_pending_choice_returns_409(expedition_server):
    status, _, _ = send_request(expedition_server, "POST", "/api/choose",
                                body={"index": 0})
    assert status == 409


def test_choose_in_classic_mode_returns_409(api_server):
    status, _, data = send_request(api_server, "POST", "/api/choose", body={"index": 0})
    assert status == 409
    assert "elección" in data["error"]


# --- Cambio de modo dentro de la aplicación -------------------------------------

def test_classic_state_reports_its_mode(api_server):
    _, _, data = send_request(api_server, "GET", "/api/state")
    assert data["mode"] == "classic"


def test_switching_to_classic_and_back_keeps_each_game(expedition_server):
    expedition = expedition_server.game
    send_request(expedition_server, "POST", "/api/move", body={"direction": "left"})
    status, _, classic = send_request(expedition_server, "POST", "/api/mode",
                                      body={"mode": "classic"})
    assert status == 200
    assert classic["mode"] == "classic"
    assert classic["size"] == expedition.size
    _, _, state = send_request(expedition_server, "GET", "/api/state")
    assert state["mode"] == "classic"
    _, _, back = send_request(expedition_server, "POST", "/api/mode",
                              body={"mode": "expedition"})
    assert back["expedition"]["seed"] == 7
    assert back["grid"] == expedition.game.grid


def test_switching_to_expedition_from_classic_creates_one(api_server):
    status, _, data = send_request(api_server, "POST", "/api/mode",
                                   body={"mode": "expedition"})
    assert status == 200
    assert data["expedition"]["floor"] == 1


@pytest.mark.parametrize("mode", ["arcade", "", None, 1])
def test_unknown_mode_returns_400(api_server, mode):
    status, _, _ = send_request(api_server, "POST", "/api/mode", body={"mode": mode})
    assert status == 400


def test_daily_reset_starts_the_daily_expedition(expedition_server):
    from roguelike import daily_seed
    status, _, data = send_request(expedition_server, "POST", "/api/reset",
                                   body={"daily": True})
    assert status == 200
    assert data["expedition"]["seed"] == daily_seed()


@pytest.mark.parametrize("daily", ["si", 1, None])
def test_daily_must_be_true_or_false(expedition_server, daily):
    status, _, _ = send_request(expedition_server, "POST", "/api/reset",
                                body={"daily": daily})
    assert status == 400


def test_daily_reset_in_classic_mode_returns_409(api_server):
    status, _, _ = send_request(api_server, "POST", "/api/reset", body={"daily": True})
    assert status == 409


def test_blast_route_removes_a_stone(expedition_server):
    expedition_server.game.game.grid[0][0] = -1
    status, _, data = send_request(expedition_server, "POST", "/api/blast",
                                   body={"row": 0, "col": 0})
    assert status == 200
    assert data["grid"][0][0] == 0


def test_blast_route_rejects_a_cell_without_stone(expedition_server):
    expedition_server.game.game.grid[0][0] = 2
    status, _, _ = send_request(expedition_server, "POST", "/api/blast",
                                body={"row": 0, "col": 0})
    assert status == 400


def test_blast_in_classic_mode_returns_409(api_server):
    status, _, _ = send_request(api_server, "POST", "/api/blast",
                                body={"row": 0, "col": 0})
    assert status == 409

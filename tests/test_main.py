"""
test_main.py - Pruebas del punto de entrada y del arranque del servidor
=======================================================================
Usan mocks (unittest.mock) para verificar CÓMO se llama a las dependencias
(servidor, navegador, interfaz de terminal, pytest) sin ejecutarlas de verdad.
"""

import socket
import sys
from unittest import mock

import pytest

import main
import web_ui
from logic import Game2048


# --- Argumentos de la línea de comandos -------------------------------------------

def test_default_arguments():
    args = main.build_parser().parse_args([])
    assert (args.port, args.size, args.web, args.cli, args.test) == (8080, 4, False,
                                                                     False, False)


@pytest.mark.parametrize(
    "argv, message",
    [
        (["--size", "9"], "entre 2 y 8"),
        (["--size", "dos"], "entre 2 y 8"),
        (["--port", "70000"], "entre 1 y 65535"),
        (["--web", "--cli"], "not allowed with"),
    ],
)
def test_invalid_arguments_stop_with_a_clear_message(argv, message, capsys):
    with pytest.raises(SystemExit):
        main.build_parser().parse_args(argv)
    assert message in capsys.readouterr().err


# --- Selección del modo ------------------------------------------------------------

@pytest.mark.parametrize(
    "answer, mode",
    [("1", "web"), ("", "web"), ("2", "cli"), ("3", "test"), ("4", "exit"),
     ("9", "web")],
)
def test_interactive_menu(monkeypatch, answer, mode):
    monkeypatch.setattr("builtins.input", lambda prompt: answer)
    args = main.build_parser().parse_args([])
    assert main.selected_mode(args, interactive=True) == mode


def test_menu_cancelled_with_ctrl_d_exits(monkeypatch):
    def raise_eof(prompt):
        raise EOFError

    monkeypatch.setattr("builtins.input", raise_eof)
    assert main.selected_mode(main.build_parser().parse_args([]), True) == "exit"


def test_non_interactive_start_defaults_to_web():
    args = main.build_parser().parse_args([])
    assert main.selected_mode(args, interactive=False) == "web"


# --- main() con dependencias simuladas (mocks) ------------------------------------

def test_main_starts_the_web_server_with_the_requested_options():
    with mock.patch("web_ui.run_server") as run_server:
        assert main.main(["--web", "--port", "9000", "--size", "5"]) == 0
    run_server.assert_called_once()
    kwargs = run_server.call_args.kwargs
    assert kwargs["port"] == 9000
    assert kwargs["open_browser"] is True
    assert isinstance(kwargs["game"], Game2048)
    assert kwargs["game"].size == 5


def test_main_starts_the_terminal_mode():
    with mock.patch("terminal_ui.launch_terminal_game") as launch:
        assert main.main(["--cli"]) == 0
    launch.assert_called_once()


def test_main_exit_option(monkeypatch, capsys):
    monkeypatch.setattr(main, "selected_mode", lambda args, interactive: "exit")
    assert main.main([]) == 0
    assert "Hasta luego" in capsys.readouterr().out


def test_main_test_option_returns_pytest_exit_code(monkeypatch):
    monkeypatch.setattr(main, "run_tests", lambda: 3)
    assert main.main(["--test"]) == 3


def test_run_tests_calls_pytest_on_the_tests_folder():
    with mock.patch("pytest.main", return_value=0) as pytest_main:
        assert main.run_tests() == 0
    arguments = pytest_main.call_args.args[0]
    assert arguments[0].endswith("tests")


def test_run_tests_without_pytest_installed(monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "pytest", None)
    assert main.run_tests() == 1
    assert "requirements-dev.txt" in capsys.readouterr().out


# --- Arranque del servidor web --------------------------------------------------

def test_run_server_opens_the_browser_with_the_server_url(make_game, capsys):
    with mock.patch.object(web_ui.GameServer, "serve_forever",
                           side_effect=KeyboardInterrupt), \
            mock.patch("webbrowser.open") as browser_open:
        web_ui.run_server(port=0, open_browser=True, game=make_game())
    output = capsys.readouterr().out
    url = browser_open.call_args.args[0]
    browser_open.assert_called_once()
    assert url.startswith("http://127.0.0.1:")
    assert url in output
    assert "Servidor web detenido" in output


def test_run_server_exits_when_no_port_is_free(monkeypatch, capsys):
    def no_ports(*args, **kwargs):
        raise OSError("No hay puertos libres")

    monkeypatch.setattr(web_ui, "create_server", no_ports)
    with pytest.raises(SystemExit) as stop:
        web_ui.run_server(port=8080, open_browser=False)
    assert stop.value.code == 1
    assert "No hay puertos libres" in capsys.readouterr().out


def test_create_server_skips_a_busy_port(make_game):
    with socket.socket() as busy:
        busy.bind(("127.0.0.1", 0))
        busy.listen()
        busy_port = busy.getsockname()[1]
        server = web_ui.create_server(make_game(), port=busy_port, attempts=5)
        try:
            assert server.server_address[1] != busy_port
        finally:
            server.server_close()


def test_create_server_reports_when_every_port_is_busy(make_game):
    with socket.socket() as busy:
        busy.bind(("127.0.0.1", 0))
        busy.listen()
        with pytest.raises(OSError):
            web_ui.create_server(make_game(), port=busy.getsockname()[1], attempts=1)

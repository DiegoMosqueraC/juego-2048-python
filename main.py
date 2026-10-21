"""
main.py - Punto de entrada del juego 2048
=========================================
Uso:
  python main.py                 -> Menú interactivo
  python main.py --web           -> Interfaz gráfica en el navegador
  python main.py --cli           -> Interfaz en la terminal
  python main.py --test          -> Suite de pruebas automatizadas (pytest)
  python main.py --web --port 9000 --size 5

Las interfaces se importan solo cuando se eligen: así el modo web no necesita
'curses' y el programa arranca aunque falte alguna dependencia opcional.
"""

import argparse
import sys
from pathlib import Path

from config import DEFAULT_BOARD_SIZE, DEFAULT_PORT
from logic import Game2048
from validation import validate_board_size, validate_port

PROJECT_DIR = Path(__file__).resolve().parent

MENU_OPTIONS = {"1": "web", "2": "cli", "3": "test", "4": "exit"}
MENU_TEXT = """
==================================================
             BIENVENIDO A 2048 EN PYTHON
==================================================
  [1] Interfaz gráfica web (recomendada)
  [2] Modo terminal
  [3] Ejecutar las pruebas automatizadas
  [4] Salir
=================================================="""


def _argument_type(validator):
    """Adapta un validador para que argparse muestre su mensaje de error."""

    def parse(text: str) -> int:
        try:
            return validator(int(text) if text.strip().isdigit() else text)
        except ValueError as error:
            raise argparse.ArgumentTypeError(str(error)) from None

    return parse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Juego 2048 en Python con interfaz web y modo terminal."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--web", "-w", action="store_true",
                      help="iniciar la interfaz gráfica en el navegador")
    mode.add_argument("--cli", "-c", action="store_true",
                      help="iniciar el modo terminal")
    mode.add_argument("--test", "-t", action="store_true",
                      help="ejecutar las pruebas automatizadas")
    parser.add_argument("--port", "-p", type=_argument_type(validate_port),
                        default=DEFAULT_PORT,
                        help=f"puerto del servidor web (por defecto {DEFAULT_PORT})")
    parser.add_argument("--size", "-s", type=_argument_type(validate_board_size),
                        default=DEFAULT_BOARD_SIZE,
                        help=f"lado del tablero, de 2 a 8 (por defecto "
                             f"{DEFAULT_BOARD_SIZE})")
    return parser


def run_tests() -> int:
    """Ejecuta la suite con pytest; devuelve su código de salida."""
    try:
        import pytest
    except ImportError:
        print("pytest no está instalado. Ejecuta: pip install -r requirements-dev.txt")
        return 1
    return pytest.main([str(PROJECT_DIR / "tests"), "-v",
                        "--rootdir", str(PROJECT_DIR),
                        "-c", str(PROJECT_DIR / "setup.cfg")])


def choose_mode_interactively() -> str:
    print(MENU_TEXT)
    try:
        choice = input("\nIngresa tu opción (1-4) [1]: ").strip() or "1"
    except (KeyboardInterrupt, EOFError):
        return "exit"
    return MENU_OPTIONS.get(choice, "web")


def selected_mode(args: argparse.Namespace, interactive: bool) -> str:
    """Modo pedido por argumentos; sin argumentos, menú o web sin navegador."""
    for mode in ("test", "cli", "web"):
        if getattr(args, mode):
            return mode
    return choose_mode_interactively() if interactive else "web"


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    interactive = sys.stdin.isatty()
    mode = selected_mode(args, interactive)

    if mode == "test":
        return run_tests()
    if mode == "cli":
        from terminal_ui import launch_terminal_game
        launch_terminal_game(Game2048(size=args.size))
    elif mode == "web":
        from web_ui import run_server
        run_server(port=args.port, open_browser=args.web or interactive,
                   game=Game2048(size=args.size))
    else:
        print("¡Hasta luego!")
    return 0


if __name__ == "__main__":
    sys.exit(main())

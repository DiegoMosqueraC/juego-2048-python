"""
main.py - Punto de Entrada Principal para el Juego 2048
=======================================================
Permite iniciar el juego en dos modos de visualización distintos:

1. Modo Web Gráfico (--web o por defecto):
   Inicia un servidor HTTP nativo en Python y abre automáticamente el navegador
   con una interfaz moderna, efectos de sonido sintetizados y animaciones de fichas.

2. Modo Terminal (--cli):
   Inicia la interfaz de consola interactiva con colores y controles mediante 'curses'.

Uso:
  python3 main.py         -> Menú interactivo o inicio directo
  python3 main.py --web   -> Inicia la versión gráfica web
  python3 main.py --cli   -> Inicia la versión en terminal
  python3 main.py --test  -> Ejecuta la suite de pruebas unitarias
"""

import argparse
import sys
import os

from tests_logic import TestGame2048Logic
import unittest


def run_tests() -> None:
    """Ejecuta la suite de pruebas unitarias de la lógica del juego."""
    print("▶ Ejecutando pruebas unitarias de 2048...")
    suite = unittest.TestLoader().loadTestsFromTestCase(TestGame2048Logic)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if result.wasSuccessful():
        print("\n✔ Todas las pruebas pasaron con éxito.")
    else:
        print("\n✖ Se detectaron fallos en las pruebas.")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Recreación completa de 2048 en Python con interfaz gráfica web y modo terminal."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--web", "-w",
        action="store_true",
        help="Iniciar en modo interfaz gráfica web (navegador)"
    )
    group.add_argument(
        "--cli", "-c",
        action="store_true",
        help="Iniciar en modo consola / terminal interactiva"
    )
    group.add_argument(
        "--test", "-t",
        action="store_true",
        help="Ejecutar las pruebas unitarias de las reglas del juego"
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=8080,
        help="Puerto para el servidor web (por defecto 8080)"
    )

    args = parser.parse_args()

    if args.test:
        run_tests()
        return

    if args.cli:
        from terminal_ui import launch_terminal_game
        launch_terminal_game()
        return

    if args.web:
        from web_ui import run_server
        run_server(port=args.port, open_browser=True)
        return

    # Si se ejecuta sin argumentos y la terminal es interactiva, mostrar menú de selección
    if sys.stdin.isatty():
        print("\n" + "=" * 50)
        print("           🎮  BIENVENIDO A 2048 EN PYTHON  🎮")
        print("=" * 50)
        print("  Selecciona el modo en el que deseas jugar:\n")
        print("  [1] Interfaz Gráfica Web (Recomendado: animaciones y sonido)")
        print("  [2] Modo Terminal / Consola interactiva (Curses)")
        print("  [3] Ejecutar pruebas unitarias")
        print("  [4] Salir")
        print("=" * 50)

        try:
            choice = input("\nIngresa tu opción (1-4) [por defecto 1]: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nOperación cancelada.")
            return

        if choice == "2":
            from terminal_ui import launch_terminal_game
            launch_terminal_game()
        elif choice == "3":
            run_tests()
        elif choice == "4":
            print("¡Hasta luego!")
            return
        else:
            # Opción 1 o Enter directo
            from web_ui import run_server
            run_server(port=args.port, open_browser=True)
    else:
        # Si no es un tty interactivo (por ejemplo, ejecución en background o script),
        # iniciamos el servidor web por defecto
        from web_ui import run_server
        run_server(port=args.port, open_browser=False)


if __name__ == "__main__":
    main()

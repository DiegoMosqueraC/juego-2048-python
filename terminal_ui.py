"""
terminal_ui.py - Interfaz de consola para 2048
==============================================
Permite jugar desde la terminal. Si la biblioteca 'curses' está disponible
(Linux, macOS o Windows con el paquete windows-curses) se usa una vista a color
que se redibuja en el sitio; si no, se usa un modo de texto básico.

El texto que se muestra se construye con funciones puras (header_lines,
board_lines, footer_lines, apply_key) que se prueban sin depender de curses.

Controles:
- Flechas del teclado / W, A, S, D: mover fichas
- U: deshacer la última jugada
- R: reiniciar la partida
- C: continuar jugando tras alcanzar 2048
- Q / ESC: salir
"""

import textwrap
from typing import Optional

from logic import Game2048

# BUG-10: en Windows la biblioteca estándar no incluye '_curses'. En lugar de
# fallar al importar, se registra su ausencia y se usa el modo de texto básico.
try:
    import curses
    CURSES_AVAILABLE = True
except ImportError:
    curses = None
    CURSES_AVAILABLE = False

CELL_WIDTH = 8  # Ancho de cada celda dibujada, incluidos sus bordes.
ESCAPE_KEY = "\x1b"
DIRECTION_KEYS = {"a": "left", "d": "right", "w": "up", "s": "down"}
# Con msvcrt, las flechas llegan como un prefijo seguido de uno de estos códigos.
WINDOWS_ARROW_CODES = {"H": "w", "P": "s", "K": "a", "M": "d"}
HELP_TEXT = "Flechas/WASD: mover · U: deshacer · R: reiniciar · Q: salir"


# -----------------------------------------------------------------------------
# Construcción del texto (funciones puras)
# -----------------------------------------------------------------------------

def board_width(size: int) -> int:
    """Columnas que ocupa el tablero: celdas de CELL_WIDTH separadas por un espacio."""
    return size * (CELL_WIDTH + 1) - 1


def header_lines(game: Game2048) -> list[str]:
    return [
        "2048 en Python",
        f"Puntuación: {game.score}   Récord: {game.highscore}",
    ]


def board_lines(game: Game2048) -> list[str]:
    """Tablero con bordes de caja; cada fila de fichas ocupa tres líneas."""
    inner = CELL_WIDTH - 2
    lines = []
    for row in game.grid:
        cells = [f"{value if value else '·':^{inner}}" for value in row]
        lines.append(" ".join("┌" + "─" * inner + "┐" for _ in row))
        lines.append(" ".join("│" + cell + "│" for cell in cells))
        lines.append(" ".join("└" + "─" * inner + "┘" for _ in row))
    return lines


def status_message(game: Game2048) -> str:
    if game.awaiting_win_decision:
        return "¡Llegaste a 2048! C: seguir jugando · R: nueva partida"
    if game.game_over:
        return "Fin de la partida: sin movimientos. U: deshacer · R: nueva partida"
    return ""


def wrap_lines(text: str, width: int) -> list[str]:
    """
    Divide el texto en líneas que caben en el ancho disponible (BUG-11): antes el
    texto que no cabía provocaba un error de curses y el mensaje no se mostraba.
    """
    return textwrap.wrap(text, max(width, 10))


def footer_lines(game: Game2048, width: int) -> list[str]:
    """Ayuda y mensaje de estado, ajustados al ancho de la terminal."""
    lines = wrap_lines(HELP_TEXT, width)
    message = status_message(game)
    if message:
        lines += [""] + wrap_lines(message, width)
    return lines


def apply_key(game: Game2048, key: str) -> bool:
    """
    Ejecuta la acción asociada a una tecla (en minúscula).

    :return: False si el jugador pidió salir; True en cualquier otro caso.
    """
    if key in DIRECTION_KEYS:
        game.move(DIRECTION_KEYS[key])
    elif key == "u":
        game.undo()
    elif key == "r":
        game.reset()
    elif key == "c":
        game.continue_playing()
    elif key in ("q", ESCAPE_KEY):
        return False
    return True


# -----------------------------------------------------------------------------
# Modo de texto básico (sin curses)
# -----------------------------------------------------------------------------

def _read_basic_key() -> str:
    """Lee una tecla: tecla única en Windows (msvcrt) o una línea en otros sistemas."""
    try:
        import msvcrt
    except ImportError:
        return input("Tecla (W/A/S/D, U, R, C, Q) + Enter: ").strip().lower()[:1]
    key = msvcrt.getwch()
    if key in ("\x00", "\xe0"):
        return WINDOWS_ARROW_CODES.get(msvcrt.getwch(), "")
    return key.lower()


def run_basic_terminal_game(game: Game2048, read_key=None, output=print,
                            width: int = 80) -> None:
    """
    Bucle del modo de texto: imprime la pantalla y espera una tecla.
    `read_key` y `output` se pueden sustituir por dobles de prueba.
    """
    read_key = read_key or _read_basic_key
    while True:
        screen = header_lines(game) + [""] + board_lines(game) + [""]
        screen += footer_lines(game, width)
        output("\n" + "\n".join(screen))
        if not apply_key(game, read_key()):
            break


# -----------------------------------------------------------------------------
# Modo a color con curses
# -----------------------------------------------------------------------------

def _curses_tile_colors() -> dict:
    """Colores (texto, fondo) de cada ficha; solo se construye si curses existe."""
    return {
        0: (curses.COLOR_WHITE, curses.COLOR_BLACK),
        2: (curses.COLOR_BLACK, curses.COLOR_WHITE),
        4: (curses.COLOR_BLACK, curses.COLOR_CYAN),
        8: (curses.COLOR_WHITE, curses.COLOR_BLUE),
        16: (curses.COLOR_WHITE, curses.COLOR_MAGENTA),
        32: (curses.COLOR_WHITE, curses.COLOR_RED),
        64: (curses.COLOR_YELLOW, curses.COLOR_RED),
        128: (curses.COLOR_BLACK, curses.COLOR_YELLOW),
        256: (curses.COLOR_WHITE, curses.COLOR_YELLOW),
        512: (curses.COLOR_CYAN, curses.COLOR_YELLOW),
        1024: (curses.COLOR_MAGENTA, curses.COLOR_YELLOW),
        2048: (curses.COLOR_RED, curses.COLOR_WHITE),
    }


class CursesGame:
    """Dibuja la partida con curses y traduce las teclas especiales."""

    TITLE_PAIR, SCORE_PAIR, WIN_PAIR, OVER_PAIR = 2, 3, 4, 5
    FIRST_TILE_PAIR = 10

    def __init__(self, stdscr, game: Game2048):
        self.stdscr = stdscr
        self.game = game
        self.tile_pairs: dict[int, int] = {}
        self.arrow_keys = {
            curses.KEY_LEFT: "a",
            curses.KEY_RIGHT: "d",
            curses.KEY_UP: "w",
            curses.KEY_DOWN: "s",
        }
        curses.curs_set(0)
        self.stdscr.keypad(True)
        self.has_colors = curses.has_colors()
        if self.has_colors:
            curses.start_color()
            curses.use_default_colors()
            self._init_color_pairs()

    def _init_color_pairs(self) -> None:
        curses.init_pair(self.TITLE_PAIR, curses.COLOR_CYAN, -1)
        curses.init_pair(self.SCORE_PAIR, curses.COLOR_GREEN, -1)
        curses.init_pair(self.WIN_PAIR, curses.COLOR_YELLOW, -1)
        curses.init_pair(self.OVER_PAIR, curses.COLOR_RED, -1)
        for offset, (value, (fg, bg)) in enumerate(_curses_tile_colors().items()):
            curses.init_pair(self.FIRST_TILE_PAIR + offset, fg, bg)
            self.tile_pairs[value] = self.FIRST_TILE_PAIR + offset

    def _attr(self, pair: int, bold: bool = True) -> int:
        attr = curses.color_pair(pair) if self.has_colors else curses.A_NORMAL
        return attr | curses.A_BOLD if bold else attr

    def _tile_attr(self, value: int) -> int:
        if not self.has_colors:
            return curses.A_BOLD if value else curses.A_NORMAL
        pair = self.tile_pairs.get(value, self.tile_pairs[2048])
        return self._attr(pair, bold=value >= 8)

    def _draw_lines(self, y: int, x: int, lines: list[str], attr: int = 0) -> int:
        for offset, line in enumerate(lines):
            self.stdscr.addstr(y + offset, x, line, attr)
        return y + len(lines)

    def _draw_board(self, y: int, x: int) -> int:
        """Dibuja las líneas del tablero y luego colorea el número de cada ficha."""
        self._draw_lines(y, x, board_lines(self.game))
        inner = CELL_WIDTH - 2
        for row_index, row in enumerate(self.game.grid):
            for col_index, value in enumerate(row):
                text = f"{value if value else '·':^{inner}}"
                self.stdscr.addstr(y + row_index * 3 + 1,
                                   x + col_index * (CELL_WIDTH + 1) + 1,
                                   text, self._tile_attr(value))
        return y + self.game.size * 3

    def render(self) -> None:
        self.stdscr.erase()
        height, width = self.stdscr.getmaxyx()
        needed_width = board_width(self.game.size) + 1
        needed_height = self.game.size * 3 + 9
        if width < needed_width or height < needed_height:
            notice = (f"Agranda la ventana para jugar: {width}x{height}, "
                      f"se necesitan {needed_width}x{needed_height}.")
            self._draw_lines(0, 0, textwrap.wrap(notice, max(width - 1, 10))[:height])
            self.stdscr.refresh()
            return

        x = (width - needed_width) // 2
        title, score = header_lines(self.game)
        self.stdscr.addstr(0, x, title, self._attr(self.TITLE_PAIR))
        self.stdscr.addstr(1, x, score, self._attr(self.SCORE_PAIR))
        y = self._draw_board(3, x)
        y = self._draw_lines(y + 1, 0, wrap_lines(HELP_TEXT, width - 1), curses.A_DIM)
        status_pair = self.OVER_PAIR if self.game.game_over else self.WIN_PAIR
        message = wrap_lines(status_message(self.game), width - 1)
        self._draw_lines(y + 1, 0, message, self._attr(status_pair))
        self.stdscr.refresh()

    def read_key(self) -> Optional[str]:
        code = self.stdscr.getch()
        if code in self.arrow_keys:
            return self.arrow_keys[code]
        if code == 27:
            return ESCAPE_KEY
        return chr(code).lower() if 0 <= code < 256 else None

    def run(self) -> None:
        while True:
            self.render()
            key = self.read_key()
            if key is not None and not apply_key(self.game, key):
                break


def launch_terminal_game(game: Optional[Game2048] = None) -> None:
    """Punto de entrada del modo terminal: usa curses si existe o el modo básico."""
    game = game if game is not None else Game2048()
    try:
        if CURSES_AVAILABLE:
            curses.wrapper(lambda stdscr: CursesGame(stdscr, game).run())
        else:
            print("Aviso: 'curses' no está disponible; se usa el modo de texto básico.")
            print("Para la vista a color en Windows: pip install windows-curses")
            run_basic_terminal_game(game)
    except KeyboardInterrupt:
        pass
    print("\n¡Gracias por jugar 2048!")


if __name__ == "__main__":
    launch_terminal_game()

"""
terminal_ui.py - Interfaz de Consola / Terminal para 2048
==========================================================
Permite jugar a 2048 directamente desde la terminal de comandos de Linux/macOS/Windows.
Utiliza la biblioteca estándar 'curses' para renderizar el tablero en tiempo real,
con soporte para colores, detección de teclas de flecha y teclas WASD.

Controles:
- Flechas del teclado / W, A, S, D: Mover fichas
- U: Deshacer último movimiento
- R: Reiniciar partida
- C: Continuar jugando tras alcanzar 2048
- Q / ESC: Salir del juego
"""

from logic import Game2048

# BUG-10: en Windows la biblioteca estándar no incluye '_curses'. En lugar de
# fallar al importar, se registra su ausencia y se usa un modo de texto básico.
try:
    import curses
    CURSES_AVAILABLE = True
except ImportError:
    curses = None
    CURSES_AVAILABLE = False

# Teclas de flecha en Windows: msvcrt devuelve un prefijo y luego este código.
WINDOWS_ARROW_CODES = {"H": "w", "P": "s", "K": "a", "M": "d"}
BASIC_KEY_TO_DIRECTION = {"a": "left", "d": "right", "w": "up", "s": "down"}


def _curses_tile_colors() -> dict:
    """Paleta de colores de las fichas (solo se construye si curses existe)."""
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


class TerminalGame:
    """
    Controlador de la interfaz de usuario en terminal mediante curses.
    """

    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.game = Game2048()
        self.cell_width = 8
        self.cell_height = 3

        # Configuración inicial de curses
        curses.curs_set(0)             # Ocultar el cursor parpadeante
        self.stdscr.nodelay(False)      # Esperar a que el usuario presione una tecla
        self.stdscr.keypad(True)       # Habilitar teclas especiales (flechas)

        # Inicialización de colores si la terminal los soporta
        self.has_colors = curses.has_colors()
        if self.has_colors:
            curses.start_color()
            curses.use_default_colors()
            self._init_color_pairs()

    def _init_color_pairs(self) -> None:
        """Inicializa los pares de color para el tablero y las fichas."""
        # Par 1: Fondo de celda vacía
        curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLACK)
        # Par 2: Encabezados y títulos
        curses.init_pair(2, curses.COLOR_CYAN, -1)
        # Par 3: Puntuación
        curses.init_pair(3, curses.COLOR_GREEN, -1)
        # Par 4: Mensaje de alerta / Victoria
        curses.init_pair(4, curses.COLOR_YELLOW, curses.COLOR_BLACK)
        # Par 5: Fin de juego
        curses.init_pair(5, curses.COLOR_RED, -1)

        # Pares del 10 en adelante para cada ficha según su potencia de 2
        pair_id = 10
        self.tile_pair_map = {}
        for val, (fg, bg) in _curses_tile_colors().items():
            curses.init_pair(pair_id, fg, bg)
            self.tile_pair_map[val] = pair_id
            pair_id += 1

    def _get_tile_color_attr(self, val: int) -> int:
        """Retorna el atributo de color curses correspondiente a una ficha."""
        if not self.has_colors:
            return curses.A_NORMAL

        pair_id = self.tile_pair_map.get(val, self.tile_pair_map.get(2048, 1))
        attr = curses.color_pair(pair_id)
        if val >= 8:
            attr |= curses.A_BOLD
        return attr

    def draw_header(self, start_y: int, start_x: int) -> int:
        """Dibuja el título del juego y las puntuaciones actuales."""
        title_attr = curses.color_pair(2) | curses.A_BOLD if self.has_colors else curses.A_BOLD
        score_attr = curses.color_pair(3) | curses.A_BOLD if self.has_colors else curses.A_BOLD

        self.stdscr.addstr(start_y, start_x, "╔═════════════════════════════════════════╗", title_attr)
        self.stdscr.addstr(start_y + 1, start_x, "║                2048 en PYTHON           ║", title_attr)
        self.stdscr.addstr(start_y + 2, start_x, "╚═════════════════════════════════════════╝", title_attr)

        info_line = f" Score: {self.game.score:<8}  |  Récord: {self.game.highscore:<8} "
        self.stdscr.addstr(start_y + 3, start_x, info_line, score_attr)
        return start_y + 5

    def draw_grid(self, start_y: int, start_x: int) -> int:
        """
        Dibuja la cuadrícula 4x4 con formato tipo tarjeta y números centrados.
        """
        board_size = self.game.size
        curr_y = start_y

        for r in range(board_size):
            # Línea superior de cada celda
            for c in range(board_size):
                val = self.game.grid[r][c]
                color = self._get_tile_color_attr(val)
                self.stdscr.addstr(curr_y, start_x + (c * (self.cell_width + 1)), "┌" + "─" * (self.cell_width - 2) + "┐")

            # Línea central con el número
            curr_y += 1
            for c in range(board_size):
                val = self.game.grid[r][c]
                color = self._get_tile_color_attr(val)
                val_str = str(val) if val > 0 else "·"
                padded_val = f"{val_str:^{self.cell_width - 2}}"
                self.stdscr.addstr(curr_y, start_x + (c * (self.cell_width + 1)), "│")
                self.stdscr.addstr(curr_y, start_x + (c * (self.cell_width + 1)) + 1, padded_val, color)
                self.stdscr.addstr(curr_y, start_x + (c * (self.cell_width + 1)) + (self.cell_width - 1), "│")

            # Línea inferior de cada celda
            curr_y += 1
            for c in range(board_size):
                self.stdscr.addstr(curr_y, start_x + (c * (self.cell_width + 1)), "└" + "─" * (self.cell_width - 2) + "┘")
            curr_y += 1

        return curr_y

    def draw_footer(self, start_y: int, start_x: int) -> None:
        """Dibuja los controles y mensajes de estado (victoria o derrota)."""
        help_text = "[↑/↓/←/→ o WASD] Mover | [U] Deshacer | [R] Reiniciar | [Q] Salir"
        self.stdscr.addstr(start_y, start_x, help_text, curses.A_DIM)

        if self.game.won and not self.game.keep_playing_after_win:
            win_attr = curses.color_pair(4) | curses.A_BOLD if self.has_colors else curses.A_BOLD
            msg = "★ ¡FELICIDADES! ¡ALCANZASTE LA FICHA 2048! Presiona [C] para continuar jugando ★"
            self.stdscr.addstr(start_y + 2, start_x, msg, win_attr)
        elif self.game.game_over:
            over_attr = curses.color_pair(5) | curses.A_BOLD if self.has_colors else curses.A_BOLD
            msg = "✖ ¡FIN DE LA PARTIDA! No quedan movimientos válidos. Presiona [R] para reiniciar."
            self.stdscr.addstr(start_y + 2, start_x, msg, over_attr)

    def render(self) -> None:
        """Limpia y redibuja la pantalla completa con protección contra dimensiones reducidas."""
        self.stdscr.erase()
        max_y, max_x = self.stdscr.getmaxyx()
        
        # Verificar si la ventana de la terminal es lo suficientemente grande
        if max_y < 20 or max_x < 42:
            try:
                self.stdscr.addstr(0, 0, "Agranda la ventana de tu terminal para jugar.", curses.A_BOLD)
                self.stdscr.addstr(1, 0, f"Actual: {max_x}x{max_y} | Requerido: 42x20", curses.A_DIM)
            except curses.error:
                pass
            self.stdscr.refresh()
            return

        start_y = 1
        start_x = max(2, (max_x - 38) // 2)  # Centrar horizontalmente si hay espacio

        try:
            next_y = self.draw_header(start_y, start_x)
            next_y = self.draw_grid(next_y, start_x)
            self.draw_footer(next_y + 1, start_x)
        except curses.error:
            # Ignorar desbordamiento si la ventana se encoge bruscamente
            pass
        self.stdscr.refresh()

    def run(self) -> None:
        """Bucle principal de eventos de la terminal."""
        while True:
            self.render()
            key = self.stdscr.getch()

            # Mapeo de teclas para direcciones
            if key in (curses.KEY_LEFT, ord('a'), ord('A')):
                self.game.move('left')
            elif key in (curses.KEY_RIGHT, ord('d'), ord('D')):
                self.game.move('right')
            elif key in (curses.KEY_UP, ord('w'), ord('W')):
                self.game.move('up')
            elif key in (curses.KEY_DOWN, ord('s'), ord('S')):
                self.game.move('down')
            elif key in (ord('u'), ord('U')):
                self.game.undo()
            elif key in (ord('r'), ord('R')):
                self.game.reset()
            elif key in (ord('c'), ord('C')) and self.game.won:
                self.game.continue_playing()
            elif key in (ord('q'), ord('Q'), 27):  # 27 es tecla ESCAPE
                break


def launch_terminal_game() -> None:
    """Función de entrada para iniciar el juego en la terminal."""
    try:
        curses.wrapper(lambda stdscr: TerminalGame(stdscr).run())
    except KeyboardInterrupt:
        pass
    print("\n¡Gracias por jugar 2048!")


if __name__ == "__main__":
    launch_terminal_game()

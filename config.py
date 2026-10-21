"""
config.py - Parámetros de configuración del juego 2048
=======================================================
Reúne en un solo lugar los valores que antes estaban repetidos como "números
mágicos" en varios módulos. Cambiar una regla (por ejemplo, la ficha objetivo o
el tamaño del historial) exige modificar una sola línea.
"""

# --- Reglas del juego --------------------------------------------------------
DEFAULT_BOARD_SIZE = 4
MIN_BOARD_SIZE = 2
MAX_BOARD_SIZE = 8
WINNING_TILE = 2048
INITIAL_TILE_COUNT = 2
# Probabilidad de que una ficha nueva sea 4 en lugar de 2 (regla del 2048 original).
PROBABILITY_OF_FOUR = 0.1
# Jugadas que se pueden deshacer; limita el consumo de memoria del historial.
MAX_UNDO_HISTORY = 20

# --- Direcciones admitidas ---------------------------------------------------
DIRECTIONS = ("left", "right", "up", "down")
# Alias en español aceptados por la API y la interfaz de terminal.
DIRECTION_ALIASES = {
    "izquierda": "left",
    "derecha": "right",
    "arriba": "up",
    "abajo": "down",
}

# --- Persistencia del récord -------------------------------------------------
HIGHSCORE_FILENAME = "highscore.json"
# Permite guardar el récord en otra carpeta (útil en pruebas o instalaciones).
DATA_DIR_ENV_VAR = "JUEGO2048_DATA_DIR"

# --- Servidor web ------------------------------------------------------------
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8080
# Puertos consecutivos que se intentan si el solicitado está ocupado.
PORT_SEARCH_ATTEMPTS = 20
# Un comando del juego ocupa pocos bytes; cualquier cuerpo mayor se rechaza.
MAX_REQUEST_BODY_BYTES = 1024
ALLOWED_HOSTNAMES = ("127.0.0.1", "localhost", "[::1]")

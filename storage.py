"""
storage.py - Persistencia del récord de puntuación
===================================================
Separa el acceso a disco de la lógica del juego. Game2048 depende solo de la
interfaz HighscoreStorage (métodos load y save), por lo que en las pruebas se
puede sustituir por un doble en memoria sin tocar el archivo real del jugador.
"""

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Protocol

from config import DATA_DIR_ENV_VAR, HIGHSCORE_FILENAME
from validation import validate_score

logger = logging.getLogger(__name__)

PROGRAM_DIR = Path(__file__).resolve().parent


class HighscoreStorage(Protocol):
    """Contrato que debe cumplir cualquier almacenamiento del récord."""

    def load(self) -> int:
        """Devuelve el récord guardado o 0 si no existe."""

    def save(self, value: int) -> None:
        """Guarda un nuevo récord."""


def default_highscore_path() -> Path:
    """
    Ruta absoluta del archivo de récord.

    Se ubica junto al programa (no en el directorio de trabajo, BUG-08) salvo
    que la variable de entorno JUEGO2048_DATA_DIR indique otra carpeta.
    """
    data_dir = os.environ.get(DATA_DIR_ENV_VAR)
    base_dir = Path(data_dir) if data_dir else PROGRAM_DIR
    return base_dir / HIGHSCORE_FILENAME


class JsonHighscoreStorage:
    """Guarda el récord en un archivo JSON con el formato {"highscore": <entero>}."""

    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path is not None else default_highscore_path()

    def load(self) -> int:
        """Lee y valida el récord; ante cualquier problema devuelve 0 sin fallar."""
        try:
            with self.path.open(encoding="utf-8") as file:
                data = json.load(file)
        except FileNotFoundError:
            return 0
        except (OSError, ValueError) as error:
            logger.warning("No se pudo leer el récord en %s: %s", self.path, error)
            return 0

        try:
            if not isinstance(data, dict):
                raise ValueError("el archivo no contiene un objeto JSON")
            return validate_score(data.get("highscore", 0))
        except ValueError as error:
            # BUG-09: un valor manipulado o corrupto no debe convertirse en récord.
            logger.warning("Récord inválido en %s: %s", self.path, error)
            return 0

    def save(self, value: int) -> None:
        """
        Guarda el récord de forma atómica: primero en un archivo temporal y luego
        se reemplaza el definitivo, para que un cierre inesperado no lo corrompa.
        """
        value = validate_score(value)
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temp_name = tempfile.mkstemp(
                dir=self.path.parent, prefix=".highscore-", suffix=".tmp"
            )
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8") as file:
                    json.dump({"highscore": value}, file, indent=4)
                os.replace(temp_name, self.path)
            finally:
                if os.path.exists(temp_name):
                    os.remove(temp_name)
        except OSError as error:
            # Perder el récord no debe interrumpir la partida: se avisa en el registro.
            logger.warning("No se pudo guardar el récord en %s: %s", self.path, error)

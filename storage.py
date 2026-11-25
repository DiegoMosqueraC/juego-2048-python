"""
storage.py - Persistencia del récord y de la bitácora de expediciones
=====================================================================
Separa el acceso a disco de la lógica del juego. Game2048 depende solo de la
interfaz HighscoreStorage y Expedition de ProgressStorage (métodos load y save),
por lo que en las pruebas se sustituyen por dobles en memoria sin tocar los
archivos reales del jugador.
"""

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Protocol

from config import DATA_DIR_ENV_VAR, HIGHSCORE_FILENAME, PROGRESS_FILENAME
from validation import validate_score

logger = logging.getLogger(__name__)

PROGRAM_DIR = Path(__file__).resolve().parent


class HighscoreStorage(Protocol):
    """Contrato que debe cumplir cualquier almacenamiento del récord."""

    def load(self) -> int:
        """Devuelve el récord guardado o 0 si no existe."""

    def save(self, value: int) -> None:
        """Guarda un nuevo récord."""


def default_data_dir() -> Path:
    """
    Carpeta de los datos del jugador.

    Es la del programa (no el directorio de trabajo, BUG-08) salvo que la
    variable de entorno JUEGO2048_DATA_DIR indique otra.
    """
    data_dir = os.environ.get(DATA_DIR_ENV_VAR)
    return Path(data_dir) if data_dir else PROGRAM_DIR


def default_highscore_path() -> Path:
    """Ruta absoluta del archivo de récord."""
    return default_data_dir() / HIGHSCORE_FILENAME


def write_json_atomically(path: Path, data: dict) -> None:
    """
    Escribe primero en un archivo temporal y luego reemplaza el definitivo, para
    que un cierre inesperado nunca deje el archivo a medias.

    :raises OSError: si no se puede escribir en la carpeta.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.stem}-", suffix=".tmp"
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=4)
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.remove(temp_name)


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
            write_json_atomically(self.path, {"highscore": value})
        except OSError as error:
            # Perder el récord no debe interrumpir la partida: se avisa en el registro.
            logger.warning("No se pudo guardar el récord en %s: %s", self.path, error)


# -----------------------------------------------------------------------------
# Bitácora de expediciones
# -----------------------------------------------------------------------------

PROGRESS_FIELDS = ("expeditions", "wins", "best_floor", "best_score")


class ProgressStorage(Protocol):
    """Contrato de la bitácora: un diccionario con los campos de PROGRESS_FIELDS."""

    def load(self) -> dict:
        """Devuelve la bitácora guardada; los campos que falten valen 0."""

    def save(self, data: dict) -> None:
        """Guarda la bitácora completa."""


class JsonProgressStorage:
    """Guarda la bitácora en progress.json, junto al récord."""

    def __init__(self, path: Path | str | None = None):
        default = default_data_dir() / PROGRESS_FILENAME
        self.path = Path(path) if path is not None else default

    def load(self) -> dict:
        """Lee y valida la bitácora; si falta o está dañada empieza de cero."""
        empty = dict.fromkeys(PROGRESS_FIELDS, 0)
        try:
            with self.path.open(encoding="utf-8") as file:
                data = json.load(file)
            if not isinstance(data, dict):
                raise ValueError("el archivo no contiene un objeto JSON")
            return {field: validate_score(data.get(field, 0))
                    for field in PROGRESS_FIELDS}
        except FileNotFoundError:
            return empty
        except (OSError, ValueError) as error:
            logger.warning("Bitácora inválida en %s: %s", self.path, error)
            return empty

    def save(self, data: dict) -> None:
        clean = {field: validate_score(data.get(field, 0)) for field in PROGRESS_FIELDS}
        try:
            write_json_atomically(self.path, clean)
        except OSError as error:
            logger.warning("No se pudo guardar la bitácora en %s: %s", self.path, error)

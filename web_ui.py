"""
web_ui.py - Servidor web local para jugar 2048 en el navegador
==============================================================
Usa solo la biblioteca estándar de Python (http.server, json, urllib.parse).
Sirve los archivos de la carpeta static/ y expone una API JSON:

  GET  /api/state     -> Estado actual de la partida.
  POST /api/move      -> {"direction": "left" | "right" | "up" | "down"}
  POST /api/undo      -> Deshace la última jugada.
  POST /api/reset     -> Inicia una partida nueva.
  POST /api/continue  -> Sigue jugando tras alcanzar 2048 (409 si no aplica).

Medidas de seguridad (el servidor solo escucha en 127.0.0.1):
- Solo se aceptan nombres de host locales (protección ante DNS rebinding).
- Los comandos exigen Content-Type application/json, lo que obliga a cualquier
  otro sitio web a pasar por una verificación CORS que este servidor no autoriza.
- El cuerpo se valida en tamaño, codificación, formato JSON y tipo.
- Cabeceras de seguridad (CSP, nosniff, frame-ancestors) en todas las respuestas.
"""

import json
import logging
import os
import socketserver
import sys
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlsplit

from config import (
    ALLOWED_HOSTNAMES,
    DEFAULT_HOST,
    DEFAULT_PORT,
    MAX_REQUEST_BODY_BYTES,
    PORT_SEARCH_ATTEMPTS,
)
from logic import Game2048
from validation import validate_port

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent / "static"

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; "
        "style-src 'self' https://fonts.googleapis.com; "
        "font-src https://fonts.gstatic.com; img-src 'self' data:; "
        "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; "
        "form-action 'none'"
    ),
}


class RequestError(Exception):
    """Petición rechazada; lleva el código HTTP que debe devolverse."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


# -----------------------------------------------------------------------------
# Validaciones puras (se prueban sin levantar el servidor)
# -----------------------------------------------------------------------------

def host_is_allowed(host_header: Optional[str]) -> bool:
    """True si la cabecera Host apunta a este equipo (127.0.0.1, localhost o ::1)."""
    if not host_header:
        return True  # Clientes HTTP/1.0 sin Host: no hay nombre que suplantar.
    host = host_header.strip().lower()
    if host.startswith("["):
        hostname = host.split("]", 1)[0] + "]"
    else:
        hostname = host.split(":", 1)[0]
    return hostname in ALLOWED_HOSTNAMES


def parse_json_body(raw_length: Optional[str], read: Callable[[int], bytes]) -> dict:
    """
    Valida y decodifica el cuerpo de una petición.

    :param raw_length: valor de la cabecera Content-Length (puede faltar).
    :param read: función que lee n bytes del cuerpo (rfile.read en el servidor).
    :raises RequestError: 400 si el cuerpo es inválido, 413 si es demasiado grande.
    """
    try:
        length = int(raw_length or 0)
    except ValueError:
        raise RequestError(400, "Content-Length inválido") from None
    if length < 0:
        raise RequestError(400, "Content-Length inválido")
    if length > MAX_REQUEST_BODY_BYTES:
        raise RequestError(413, "El cuerpo de la petición es demasiado grande")
    if length == 0:
        return {}
    try:
        data = json.loads(read(length).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise RequestError(400, "El cuerpo debe ser JSON válido en UTF-8") from None
    if not isinstance(data, dict):
        raise RequestError(400, "El cuerpo debe ser un objeto JSON")
    return data


# -----------------------------------------------------------------------------
# Servidor y manejador de peticiones
# -----------------------------------------------------------------------------

class GameServer(HTTPServer):
    """
    Servidor HTTP que guarda la partida que atiende. La partida se inyecta, de
    modo que las pruebas pueden usar una con tablero y azar controlados.
    Atiende una petición a la vez, así el estado de la partida nunca se comparte
    entre hilos.
    """

    # En Windows, SO_REUSEADDR permitiría a dos servidores usar el mismo puerto.
    allow_reuse_address = os.name != "nt"

    def __init__(self, address: tuple[str, int], game: Game2048):
        self.game = game
        super().__init__(address, GameRequestHandler)

    def server_bind(self) -> None:
        # HTTPServer resuelve el nombre del equipo con getfqdn(), lo que en algunas
        # redes tarda segundos; para un servidor local basta con la dirección IP.
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = self.server_address[:2]


class GameRequestHandler(SimpleHTTPRequestHandler):
    """Sirve los archivos estáticos y la API JSON del juego."""

    server: GameServer

    # BUG-21: en Windows, mimetypes consulta el registro, que puede asociar .js a
    # text/plain; con la cabecera nosniff el navegador no ejecutaría los scripts.
    extensions_map = {
        ".html": "text/html; charset=utf-8",
        ".js": "text/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".svg": "image/svg+xml",
        ".png": "image/png",
        ".ico": "image/x-icon",
        ".json": "application/json",
        "": "application/octet-stream",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    @property
    def game(self) -> Game2048:
        return self.server.game

    # --- Rutas -------------------------------------------------------------------

    def do_GET(self) -> None:
        path = self._checked_path()
        if path is None:
            return
        if path == "/api/state":
            self._send_json(self.game.to_dict())
        elif path.startswith("/api/"):
            self._send_json({"error": "Ruta no encontrada"}, status=404)
        elif path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
        else:
            super().do_GET()

    def do_HEAD(self) -> None:
        if self._checked_path() is not None:
            super().do_HEAD()

    def do_POST(self) -> None:
        path = self._checked_path()
        if path is None:
            return
        actions = {
            "/api/move": self._api_move,
            "/api/undo": self._api_undo,
            "/api/reset": self._api_reset,
            "/api/continue": self._api_continue,
        }
        action = actions.get(path)
        try:
            if action is None:
                raise RequestError(404, "Ruta no encontrada")
            if not self.headers.get("Content-Type", "").startswith("application/json"):
                raise RequestError(415, "Los comandos deben enviarse como JSON")
            payload = parse_json_body(self.headers.get("Content-Length"),
                                      self.rfile.read)
            self._send_json(action(payload))
        except RequestError as error:
            if error.status == 413:
                self.close_connection = True  # El cuerpo no leído queda descartado.
            self._send_json({"error": str(error)}, status=error.status)

    # --- Acciones de la API --------------------------------------------------------

    def _api_move(self, payload: dict) -> dict:
        try:
            result = self.game.move(payload.get("direction"))
        except ValueError as error:
            raise RequestError(400, str(error)) from None
        response = self.game.to_dict()
        response.update(result.to_dict())
        response["gained_points"] = result.points
        return response

    def _api_undo(self, payload: dict) -> dict:
        undone = self.game.undo()
        return {**self.game.to_dict(), "undone": undone}

    def _api_reset(self, payload: dict) -> dict:
        self.game.reset()
        return self.game.to_dict()

    def _api_continue(self, payload: dict) -> dict:
        if not self.game.continue_playing():
            raise RequestError(409, "No hay una victoria pendiente")
        return self.game.to_dict()

    # --- Utilidades ----------------------------------------------------------------

    def _checked_path(self) -> Optional[str]:
        """Ruta sin query string, o None (ya respondido 403) si el Host no es local."""
        if not host_is_allowed(self.headers.get("Host")):
            self._send_json({"error": "Host no permitido"}, status=403)
            return None
        return urlsplit(self.path).path

    def _send_json(self, data: dict, status: int = 200) -> None:
        payload = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def end_headers(self) -> None:
        for name, value in SECURITY_HEADERS.items():
            self.send_header(name, value)
        super().end_headers()

    def log_message(self, message_format: str, *args) -> None:
        """Omite el registro de cada llamada a la API para no saturar la consola."""
        if urlsplit(self.path).path.startswith("/api/"):
            return
        super().log_message(message_format, *args)


# -----------------------------------------------------------------------------
# Arranque
# -----------------------------------------------------------------------------

def create_server(
    game: Optional[Game2048] = None,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    attempts: int = PORT_SEARCH_ATTEMPTS,
) -> GameServer:
    """
    Crea el servidor en el primer puerto libre a partir de `port`.
    Con port=0 el sistema operativo asigna uno libre (útil en las pruebas).

    :raises OSError: si ninguno de los puertos intentados está disponible.
    """
    game = game if game is not None else Game2048()
    last_error: Optional[OSError] = None
    candidate_ports = [0] if port == 0 else range(port, port + attempts)
    for candidate in candidate_ports:
        try:
            return GameServer((host, candidate), game)
        except OSError as error:
            last_error = error
    raise OSError(
        f"No hay puertos libres entre {port} y {port + attempts - 1}"
    ) from last_error


def _open_browser_quietly(url: str) -> None:
    """Abre el navegador ocultando avisos de bajo nivel de algunos sistemas."""
    try:
        devnull = os.open(os.devnull, os.O_WRONLY)
        saved_stderr = os.dup(2)
        os.dup2(devnull, 2)
        try:
            webbrowser.open(url)
        finally:
            os.dup2(saved_stderr, 2)
            os.close(saved_stderr)
            os.close(devnull)
    except (OSError, webbrowser.Error) as error:
        logger.info("No se pudo abrir el navegador automáticamente: %s", error)


def run_server(
    port: int = DEFAULT_PORT,
    open_browser: bool = True,
    game: Optional[Game2048] = None,
) -> None:
    """Inicia el servidor y atiende peticiones hasta que se presione Ctrl + C."""
    try:
        server = create_server(game, port=port)
    except OSError as error:
        print(f"Error: {error}")
        sys.exit(1)

    host, actual_port = server.server_address[:2]
    url = f"http://{host}:{actual_port}"
    print("\n" + "=" * 55)
    print("  Servidor de 2048 iniciado")
    print(f"  Abre tu navegador en: {url}")
    print("  Presiona Ctrl + C en esta terminal para detenerlo")
    print("=" * 55 + "\n")

    if open_browser:
        _open_browser_quietly(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor web detenido. ¡Hasta pronto!")
    finally:
        server.server_close()


if __name__ == "__main__":
    run_server(port=validate_port(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT)

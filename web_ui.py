"""
web_ui.py - Servidor Web Ligero en Python para 2048
===================================================
Proporciona una interfaz gráfica moderna accesible desde cualquier navegador web
(Chrome, Firefox, Edge, etc.) sin requerir paquetes externos ni pip.
Utiliza únicamente módulos de la biblioteca estándar de Python:
- http.server
- json
- urllib.parse

Expone una API REST para comunicar la interfaz web con la clase Game2048 en Python:
  GET  /api/state     -> Obtiene el estado actual del juego.
  POST /api/move      -> Ejecuta un movimiento ('left', 'right', 'up', 'down').
  POST /api/undo      -> Deshace el último movimiento.
  POST /api/reset     -> Reinicia la partida.
  POST /api/continue  -> Continúa jugando tras alcanzar 2048.
"""

import json
import os
import sys
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler
from typing import Dict, Any

from logic import Game2048

# Instancia global del juego gestionada por el servidor
GAME_INSTANCE = Game2048()

# Ruta al directorio que contiene los archivos estáticos de la interfaz web
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


class Game2048HTTPHandler(SimpleHTTPRequestHandler):
    """
    Controlador HTTP personalizado para servir tanto los archivos estáticos
    del frontend como la API REST del juego 2048.
    """

    def __init__(self, *args, **kwargs):
        # Configuramos el directorio base para servir HTML, CSS y JS desde 'static/'
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

    def _send_json_response(self, data: Dict[str, Any], status: int = 200) -> None:
        """Envía una respuesta JSON con las cabeceras HTTP correspondientes."""
        payload = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        """Maneja peticiones GET. Atiende la API o sirve archivos estáticos."""
        if self.path == "/api/state":
            # Retorna el estado actual del juego
            self._send_json_response(GAME_INSTANCE.to_dict())
            return

        if self.path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return

        # Si se accede a la raíz, redirigir a index.html
        if self.path == "/" or self.path == "":
            self.path = "/index.html"

        super().do_GET()

    def do_POST(self) -> None:
        """Maneja peticiones POST para los comandos de juego."""
        # Leer el cuerpo de la petición si existe
        content_length = int(self.headers.get("Content-Length", 0))
        body_bytes = self.rfile.read(content_length) if content_length > 0 else b""
        
        post_data = {}
        if body_bytes:
            try:
                post_data = json.loads(body_bytes.decode("utf-8"))
            except Exception:
                pass

        if self.path == "/api/move":
            direction = post_data.get("direction", "")
            try:
                score_before = GAME_INSTANCE.score
                moved = GAME_INSTANCE.move(direction)
                gained_points = GAME_INSTANCE.score - score_before
                resp = GAME_INSTANCE.to_dict()
                resp["moved"] = moved
                resp["gained_points"] = gained_points
                self._send_json_response(resp)
            except ValueError as e:
                self._send_json_response({"error": str(e)}, status=400)
            return

        elif self.path == "/api/undo":
            undone = GAME_INSTANCE.undo()
            resp = GAME_INSTANCE.to_dict()
            resp["undone"] = undone
            self._send_json_response(resp)
            return

        elif self.path == "/api/reset":
            GAME_INSTANCE.reset()
            self._send_json_response(GAME_INSTANCE.to_dict())
            return

        elif self.path == "/api/continue":
            GAME_INSTANCE.continue_playing()
            self._send_json_response(GAME_INSTANCE.to_dict())
            return

        # Ruta no encontrada
        self.send_error(404, "Endpoint no encontrado")

    def log_message(self, format, *args):
        """Silenciar logs excesivos en la consola para una salida limpia."""
        if not args:
            return
        first_arg = str(args[0])
        if "GET /api/" in first_arg or "POST /api/" in first_arg:
            return
        super().log_message(format, *args)


def run_server(port: int = 8080, open_browser: bool = True) -> None:
    """
    Inicia el servidor web en el puerto especificado.
    
    :param port: Puerto de red para escuchar conexiones.
    :param open_browser: Si es True, abre automáticamente el navegador predeterminado.
    """
    server_address = ("127.0.0.1", port)
    
    # Intentar asignar el puerto o buscar el siguiente disponible si está ocupado
    for p in range(port, port + 20):
        try:
            httpd = HTTPServer(("127.0.0.1", p), Game2048HTTPHandler)
            actual_port = p
            break
        except OSError:
            continue
    else:
        print("Error: No se pudo enlazar ningún puerto disponible.")
        sys.exit(1)

    url = f"http://127.0.0.1:{actual_port}"
    print(f"\n=======================================================")
    print(f"  🎮 Servidor de 2048 iniciado con éxito")
    print(f"  👉 Abre tu navegador en: {url}")
    print(f"  Presiona Ctrl + C en esta terminal para detener el servidor")
    print(f"=======================================================\n")

    if open_browser:
        try:
            # Redirigir temporalmente stderr de bajo nivel para evitar mensajes de advertencia de sandbox del sistema
            devnull = os.open(os.devnull, os.O_WRONLY)
            old_stderr = os.dup(2)
            os.dup2(devnull, 2)
            try:
                webbrowser.open(url)
            finally:
                os.dup2(old_stderr, 2)
                os.close(old_stderr)
                os.close(devnull)
        except Exception:
            pass

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor web detenido. ¡Hasta pronto!")
        httpd.server_close()


if __name__ == "__main__":
    port_arg = 8080
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        port_arg = int(sys.argv[1])
    run_server(port=port_arg, open_browser=True)

"""
helpers.py - Utilidades HTTP para las pruebas de integración de la API.

Actúan como "driver" de prueba: simulan al navegador enviando peticiones reales
(bien formadas o deliberadamente malformadas) al servidor levantado en conftest.
"""

import http.client
import json
import socket


def send_request(server, method, path, body=None, headers=None, timeout=3):
    """
    Envía una petición HTTP al servidor de pruebas.

    :param body: bytes (se envían tal cual), None (sin cuerpo) o cualquier otro
                 valor, que se serializa a JSON.
    :return: tupla (código de estado, cabeceras, cuerpo decodificado).
    """
    host, port = server.server_address[:2]
    connection = http.client.HTTPConnection(host, port, timeout=timeout)
    request_headers = {"Content-Type": "application/json"}
    request_headers.update(headers or {})
    if body is None or isinstance(body, bytes):
        payload = body
    else:
        payload = json.dumps(body).encode("utf-8")
    try:
        connection.request(method, path, body=payload, headers=request_headers)
        response = connection.getresponse()
        raw = response.read().decode("utf-8")
        content_type = response.getheader("Content-Type", "")
        is_json = raw and "application/json" in content_type
        data = json.loads(raw) if is_json else raw
        # response.headers busca las cabeceras sin distinguir mayúsculas.
        return response.status, response.headers, data
    finally:
        connection.close()


def send_raw(server, raw_request, timeout=3):
    """Envía bytes HTTP crudos (para simular clientes malformados) y lee el estado."""
    host, port = server.server_address[:2]
    with socket.create_connection((host, port), timeout=timeout) as client:
        client.sendall(raw_request)
        status_line = client.makefile("rb").readline().decode("latin-1")
    return int(status_line.split()[1])

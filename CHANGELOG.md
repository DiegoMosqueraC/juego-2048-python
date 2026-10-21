# Registro de cambios

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el
proyecto usa [versionado semántico](https://semver.org/lang/es/). Los
identificadores `BUG-xx` remiten a [docs/REGISTRO_FALLOS.md](docs/REGISTRO_FALLOS.md).

## [2.0.0] - 2026-10-21

### Corregido (mantenimiento correctivo)
- `move()` rechaza con `ValueError` las direcciones que no son texto (BUG-01).
- La API valida `Content-Length`, el formato JSON y el tamaño del cuerpo (BUG-02).
- Las rutas de la API aceptan parámetros de consulta (BUG-04).
- `continue_playing()` solo actúa con una victoria pendiente y no se aceptan
  jugadas mientras el jugador no decide (BUG-05, BUG-06).
- El récord almacenado se valida antes de usarse (BUG-09).
- Los mensajes de la terminal se ajustan al ancho de la ventana (BUG-11).
- `Ctrl+R` ya no reinicia la partida y `R` pide confirmación (BUG-13).
- Los sonidos de victoria y derrota suenan una sola vez (BUG-14).
- Aviso visible cuando se pierde la conexión con el servidor (BUG-16).
- Los archivos `.js` se sirven con el tipo MIME correcto en Windows (BUG-21).
- Las respuestas a `HEAD` no llevan cuerpo (BUG-22).
- «Deshacer última jugada» se deshabilita si no hay historial (BUG-23).

### Seguridad
- Sin CORS abierto; los comandos exigen `application/json` y un `Host` local (BUG-03).
- Cabeceras `Content-Security-Policy`, `X-Content-Type-Options` y `Referrer-Policy`.
- `to_dict()` entrega una copia del tablero (BUG-07).

### Cambiado (mantenimiento adaptativo y preventivo)
- El récord se guarda junto al programa o en `JUEGO2048_DATA_DIR`, nunca en el
  directorio de trabajo, y con escritura atómica (BUG-08, BUG-09).
- El modo terminal funciona en Windows sin `curses` (BUG-10).
- Nuevos módulos `config.py`, `validation.py` y `storage.py`; `logic.py` usa un
  único algoritmo por línea e inyección de dependencias (BUG-17, BUG-19).
- Las pruebas se migran a pytest con dobles de prueba y quedan aisladas del
  disco y del azar (BUG-19).

### Agregado (mantenimiento perfectivo)
- Animaciones de deslizamiento y fusión basadas en los datos de cada jugada (BUG-12).
- Accesibilidad WCAG 2.1: zoom, diálogos con foco, anuncios para lectores de
  pantalla, contraste mínimo 3:1 y respeto por `prefers-reduced-motion` (BUG-15).
- Tableros de 2x2 a 8x8 con la opción `--size` (BUG-20).
- `Game2048.from_grid()` para crear partidas desde un tablero validado.
- 261 casos de prueba nuevos en Python y 10 en JavaScript; pipeline de GitHub Actions y
  `ci_local.py`.

## [1.0.0] - Versión base

- Versión recibida al inicio del trabajo (commit `0d96344`), sin modificaciones.

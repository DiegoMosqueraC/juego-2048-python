# Registro de cambios

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el
proyecto usa [versionado semántico](https://semver.org/lang/es/). Los
identificadores `BUG-xx` remiten a [docs/REGISTRO_FALLOS.md](docs/REGISTRO_FALLOS.md).

## [2.4.0] - 2026-11-25

### Cambiado
- La interfaz cabe en pantalla: en computador, panel a la izquierda y tablero a la
  derecha del alto de la ventana; en celular, el tablero va justo después de los
  botones y la expedición debajo.
- La mina se ensancha sola: 5×5 en el piso de 1024 y 6×6 en el de 2048, con aviso.
- Expansión llega hasta 7×7 y desde el piso 4 ya no sale la maldición Calma.

## [2.3.0] - 2026-11-25

### Agregado (mantenimiento perfectivo)
- Identidad visual «La Mina»: paleta de piedra y antorcha, tipografía Lilita One
  para números y títulos, fichas con bisel y tablero con volumen.
- Más de 30 iconos SVG propios (sin bibliotecas): cartas, maldiciones, oro,
  racha, piso, modos y botones.
- Efectos al puntuar: chispas del color de cada fusión, puntos que suben desde la
  ficha con el color de la racha, marcadores que cuentan hacia arriba y llama de
  racha que crece.
- Lluvia de monedas al superar un piso, cartas repartidas con giro y brillo en las
  legendarias, polvo donde una carta borra fichas, temblor con Terremoto,
  destellos del Fénix y del Escudo y bruma animada con Niebla.
- Sonidos de moneda y de carta.

### Cambiado
- Las etiquetas dejan de estar en mayúsculas; el título de la página es «2048: La Mina».

## [2.2.0] - 2026-11-25

### Agregado (mantenimiento perfectivo)
- Oro: los puntos de cada piso se convierten en oro (1 por cada 100).
- Tienda al final de cada piso: comprar las cartas no elegidas o renovar la oferta
  (`POST /api/shop`).
- Racha: +10 % de puntos por cada jugada seguida con fusión (hasta ×2).
- Rarezas de cartas (común, rara, legendaria) y 6 cartas nuevas: Bolsa de oro,
  Escudo, Alquimia, Interés, Expansión (tablero de hasta 6×6) y Fénix.
- 4 maldiciones nuevas: Derrumbe, Sequía, Niebla y Terremoto.
- Pisos guardianes (3 y 6) con dos maldiciones; superar el 3 ofrece cartas raras.
- Mazo, oro, racha, avisos de sucesos y resumen final en la interfaz web.

### Cambiado
- Elegir carta (`POST /api/choose`) ya no baja de piso: abre la tienda.
- El estado de la expedición informa `curses` (lista) en lugar de `curse`.

## [2.1.0] - 2026-11-25

### Agregado (mantenimiento perfectivo)
- Modo expedición (`roguelike.py`): 6 pisos con ficha objetivo, 5 bendiciones a
  elegir, 3 maldiciones, usos de deshacer limitados y semilla repetible.
- Piedras en el tablero: celdas que no se mueven ni se fusionan (`slide_line`).
- Ruta `POST /api/choose` y opciones `--clasico` y `--semilla`.
- Selector de modo en la interfaz web (Expedición o Clásico) y ruta `POST /api/mode`;
  el servidor guarda una partida por modo, así cambiar no borra el progreso.
- Barra de la expedición, cartas de bendición y piedras en la interfaz web.
- 72 pruebas nuevas (`test_expedicion.py`, `test_piedras.py`, API y `main.py`).

### Cambiado
- La interfaz web abre en el modo expedición; `--clasico` la abre en el modo clásico.
- El estado de la API incluye el campo `mode`.

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
- El flujo de CI calcula la caché de pip con `requirements-dev.txt` y usa las
  acciones v7, basadas en Node.js 24 (falló en su primera ejecución en GitHub).

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

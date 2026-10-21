# 🎮 2048 en Python - Edición Completa

Recreación fiel, moderna y modular del clásico juego **2048**, desarrollada en **Python** puro sin dependencias externas (`pip` no requerido). Incluye tanto un modo de **consola/terminal interactiva** como un **modo gráfico web moderno** con animaciones fluidas y efectos de sonido generados por código.

---

## 🚀 Inicio Rápido

Para iniciar el juego con el menú interactivo:

```bash
python3 main.py
```

### Modos Disponibles

1. **Modo Gráfico Web (Recomendado)**:
   Abre automáticamente tu navegador web con una interfaz moderna, animaciones y audio:
   ```bash
   python3 main.py --web
   ```
   *(También puedes especificar el puerto si lo deseas: `python3 main.py --web --port 8080`)*

2. **Modo Consola / Terminal**:
   Juega directamente en la terminal con una cuadrícula estilizada y colores:
   ```bash
   python3 main.py --cli
   ```

3. **Ejecutar Pruebas Unitarias**:
   Verifica que todas las reglas matemáticas y de combinación funcionen con total precisión:
   ```bash
   python3 main.py --test
   ```

---

## 🎯 Controles del Juego

| Acción | Modo Web | Modo Terminal |
| :--- | :--- | :--- |
| **Mover fichas** | Flechas del teclado / `W`, `A`, `S`, `D` / Deslizar con el dedo / D-Pad táctil | Flechas del teclado / `W`, `A`, `S`, `D` |
| **Deshacer jugada (Undo)** | Tecla `U` o botón en pantalla | Tecla `U` |
| **Reiniciar partida** | Tecla `R` o botón en pantalla | Tecla `R` |
| **Alternar Tema** | Botón de Sol/Luna (Claro / Oscuro) | N/A |
| **Activar/Silenciar sonido** | Botón de Altavoz | N/A |
| **Salir** | Cerrar pestaña del navegador | Tecla `Q` o `ESC` |

---

## 🧩 Arquitectura del Proyecto

El código está estructurado siguiendo principios de separación de responsabilidades y código limpio:

- **[`logic.py`](file:///home/miguelcastillo/Escritorio/Juego2048/logic.py)**:
  Contiene la clase central `Game2048`. Implementa la matriz 4x4, el algoritmo de compresión y fusión hacia la izquierda (reutilizado para las 4 direcciones mediante transformaciones matriciales), la generación aleatoria de fichas (90% de probabilidad de 2, 10% de 4), la pila de historial para deshacer jugadas, y la persistencia del récord en `highscore.json`.
- **[`terminal_ui.py`](file:///home/miguelcastillo/Escritorio/Juego2048/terminal_ui.py)**:
  Interfaz de terminal interactiva desarrollada con la biblioteca estándar `curses`. Renderiza los bloques con colores según su valor y captura las teclas de forma asíncrona.
- **[`web_ui.py`](file:///home/miguelcastillo/Escritorio/Juego2048/web_ui.py)**:
  Servidor HTTP nativo en Python (`http.server`) que expone una API REST (`/api/state`, `/api/move`, `/api/undo`, `/api/reset`, etc.) para controlar el juego desde el navegador.
- **[`static/`](file:///home/miguelcastillo/Escritorio/Juego2048/static)**:
  - `index.html`: Estructura semántica, modales de victoria y Game Over, y controles táctiles.
  - `style.css`: Diseño moderno con tipografía Google Font Outfit, soporte para temas oscuro y claro, micro-animaciones (`popIn`, `mergeBounce`) y brillos para fichas altas.
  - `app.js`: Cliente reactivo en JavaScript que consume la API Python y genera efectos de sonido sintetizados mediante Web Audio API.
- **[`tests_logic.py`](file:///home/miguelcastillo/Escritorio/Juego2048/tests_logic.py)**:
  Suite de 12 pruebas unitarias automatizadas con `unittest`.
- **[`main.py`](file:///home/miguelcastillo/Escritorio/Juego2048/main.py)**:
  Orquestador principal con menú de selección y banderas de línea de comandos.

---

## 📜 Reglas de 2048
1. Desliza las fichas en cualquiera de las cuatro direcciones cardinales.
2. Cuando dos fichas con el mismo número chocan entre sí, se fusionan en una sola con el doble de valor.
3. Tras cada movimiento válido, aparece una nueva ficha en una celda vacía aleatoria (con valor 2 o 4).
4. El objetivo principal es lograr crear una ficha con el valor **2048**, aunque tras conseguirlo puedes optar por seguir jugando para alcanzar números mayores (4096, 8192, etc.).
5. Si el tablero se llena y no es posible realizar ningún movimiento, la partida finaliza.

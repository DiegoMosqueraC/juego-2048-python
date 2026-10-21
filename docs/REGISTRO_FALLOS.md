# Registro de fallos y matriz de trazabilidad

Cada fallo detectado en el juego tiene un identificador, su clasificación, la
característica de calidad afectada según ISO/IEC 25010:2023, el tipo de
mantenimiento según ISO/IEC/IEEE 14764:2022, la prueba que lo detecta o lo
protege contra regresiones y el commit que lo corrige.

**Resumen:** 23 fallos registrados y corregidos.
Por tipo de mantenimiento: adaptativo 2, correctivo 14, perfectivo 3, preventivo 4.
Por severidad: alta 5, media 11, baja 7.

Criterios de severidad: **alta**, impide jugar o compromete la seguridad;
**media**, comportamiento incorrecto con alternativa para el usuario; **baja**,
defecto menor o de presentación.

## Registro

| ID | Componente | Descripción | Tipo de error | Severidad |
| --- | --- | --- | --- | --- |
| BUG-01 | logic.py | move() usaba direction.strip() sin validar el tipo: con None o un número lanzaba AttributeError en lugar de un error controlado. | Ejecución (validación de entradas) | Alta |
| BUG-02 | web_ui.py | La API aceptaba cuerpos malformados: un Content-Length no numérico, un JSON que no es objeto o un tamaño ilimitado producían una excepción no controlada, el cierre de la conexión y riesgo de denegación de servicio. | Seguridad y ejecución | Alta |
| BUG-03 | web_ui.py | La API local podía ser manipulada desde otros sitios web: CORS con «*», comandos POST sin exigir JSON y sin validar el encabezado Host (falsificación de peticiones y DNS rebinding). | Seguridad | Alta |
| BUG-04 | web_ui.py | Las rutas comparaban la URL completa: /api/state?t=1 respondía 404. | Lógico | Baja |
| BUG-05 | logic.py | continue_playing() podía invocarse sin haber ganado y desactivaba para siempre la detección de la victoria. | Lógico | Media |
| BUG-06 | logic.py | Con la victoria pendiente se seguían aceptando jugadas (el teclado movía las fichas detrás del aviso). | Lógico | Media |
| BUG-07 | logic.py | to_dict() entregaba la lista interna del tablero: cualquier consumidor podía modificar la partida. | Lógico (encapsulamiento) | Media |
| BUG-08 | logic.py | El récord se guardaba en highscore.json relativo al directorio de trabajo: al ejecutar el juego desde otra carpeta el récord se «perdía» y quedaban archivos sueltos. | Lógico y de entorno | Media |
| BUG-09 | logic.py | El récord leído no se validaba (aceptaba -50, 12.7 o true) y la escritura no era atómica. | Validación de entradas | Media |
| BUG-10 | terminal_ui.py | El modo terminal no arrancaba en Windows: ModuleNotFoundError: No module named '_curses'. | Ejecución (entorno) | Alta |
| BUG-11 | terminal_ui.py | Los mensajes más anchos que la terminal lanzaban curses.error, que se silenciaba: en terminales de 80 columnas no se mostraba el aviso de victoria ni el de fin de partida. | Lógico (presentación) | Media |
| BUG-12 | static/app.js | Las animaciones comparaban la misma celda antes y después: toda ficha desplazada «aparecía» como nueva y no había deslizamiento. | Lógico (presentación) | Media |
| BUG-13 | static/app.js | Ctrl+R (recargar) también activaba el atajo R y reiniciaba la partida, sin pedir confirmación. | Lógico (usabilidad) | Media |
| BUG-14 | static/app.js | Los sonidos de victoria y de derrota se repetían en cada actualización mientras el estado se mantenía. | Lógico | Baja |
| BUG-15 | static/index.html, style.css | Barreras de accesibilidad: zoom bloqueado, diálogos sin rol ni foco, sin anuncios para lectores de pantalla y 9 de 11 fichas con contraste menor que 3:1. | Usabilidad y accesibilidad | Media |
| BUG-16 | static/app.js | Sin aviso al perder la conexión con el servidor (solo console.error) y localStorage podía lanzar excepciones. | Fiabilidad | Baja |
| BUG-17 | main.py, logic.py, terminal_ui.py, web_ui.py | Deuda técnica: main.py importaba el módulo de pruebas; había cuatro importaciones o variables sin uso, cuatro f-strings sin variables, tres funciones nunca llamadas, move() con cuatro ramas duplicadas (complejidad 13) y números mágicos. | Mantenibilidad | Media |
| BUG-18 | README.md, web_ui.py | Documentación desactualizada: enlaces absolutos a otro equipo (file:///home/miguelcastillo/...) y un docstring que mencionaba urllib.parse sin usarlo. | Documentación | Baja |
| BUG-19 | tests_logic.py | Pruebas no aisladas: dependían del azar global y escribían test_highscore.json en el directorio de trabajo. | Mantenibilidad (capacidad de prueba) | Media |
| BUG-20 | static/* | Tamaño 4×4 fijo en el HTML (16 celdas), en el CSS y en los bucles de JavaScript. | Mantenibilidad | Baja |
| BUG-21 | web_ui.py | Introducido al agregar la cabecera nosniff: en Windows, mimetypes leía del registro text/plain para los .js y el navegador no ejecutaba los scripts (tablero vacío). | Ejecución (entorno) | Alta |
| BUG-22 | web_ui.py | La respuesta 403 a una petición HEAD incluía cuerpo, contrario a HTTP (RFC 9110). | Lógico (protocolo) | Baja |
| BUG-23 | static/app.js | «Deshacer última jugada» seguía activo en el diálogo final aunque no hubiera historial (por ejemplo, tras recargar la página). | Lógico (usabilidad) | Baja |

## Matriz de trazabilidad

| ID | Característica ISO/IEC 25010 | Mantenimiento | Detectado por | Prueba de regresión | Commit |
| --- | --- | --- | --- | --- | --- |
| BUG-01 | Fiabilidad: tolerancia a fallos | Correctivo | Revisión de código | test_bug01 (5 casos) | `4ad303a` |
| BUG-02 | Seguridad: resistencia; Fiabilidad | Correctivo | Revisión de código | test_bug02 (8 casos) | `9774560` |
| BUG-03 | Seguridad: integridad | Correctivo | Revisión de código | test_bug03 (3 casos) | `9774560` |
| BUG-04 | Adecuación funcional: corrección | Correctivo | Revisión de código | test_bug04 | `9774560` |
| BUG-05 | Adecuación funcional: corrección | Correctivo | Revisión de código | test_bug05 | `4ad303a` |
| BUG-06 | Adecuación funcional: corrección | Correctivo | Prueba exploratoria | test_bug06 | `4ad303a` |
| BUG-07 | Seguridad: integridad | Preventivo | Revisión de código | test_bug07 | `4ad303a` |
| BUG-08 | Flexibilidad: adaptabilidad | Adaptativo | Revisión de código | test_bug08 | `4ad303a` |
| BUG-09 | Fiabilidad: ausencia de fallos | Correctivo | Revisión de código | test_bug09 (6 casos) | `4ad303a, 08e8db3` |
| BUG-10 | Flexibilidad: adaptabilidad | Adaptativo | Prueba en Windows | test_bug10 | `974917f` |
| BUG-11 | Capacidad de interacción: operabilidad | Correctivo | Revisión de código | test_bug11 (3 casos) y prueba con curses falso | `b854330` |
| BUG-12 | Capacidad de interacción: compromiso del usuario | Perfectivo | Prueba exploratoria | ST-02 (manual) | `c2d4db9` |
| BUG-13 | Capacidad de interacción: protección frente a errores del usuario | Correctivo | Prueba exploratoria | actionForKey (node:test) y ST-03 | `356c4fe, c2d4db9` |
| BUG-14 | Capacidad de interacción | Correctivo | Revisión de código | statusTransition (node:test) | `356c4fe, c2d4db9` |
| BUG-15 | Capacidad de interacción: inclusividad | Perfectivo | Revisión con WCAG 2.1 | ST-03 a ST-07 y medición de contraste | `c2d4db9` |
| BUG-16 | Fiabilidad: tolerancia a fallos | Correctivo | Revisión de código | ST-08 (manual) | `c2d4db9` |
| BUG-17 | Mantenibilidad: modularidad y analizabilidad | Preventivo | flake8 (C901, F401, F841, F541) | flake8 en el pipeline | `08e8db3, 5c865ce` |
| BUG-18 | Mantenibilidad: analizabilidad | Preventivo | Revisión de documentos | Revisión | `5c865ce, ccb9370` |
| BUG-19 | Mantenibilidad: capacidad de ser probado | Preventivo | Revisión con F.I.R.S.T. | Dobles de prueba en conftest.py | `5c865ce` |
| BUG-20 | Mantenibilidad: modificabilidad | Perfectivo | Revisión de código | ST-11 (manual) | `c2d4db9` |
| BUG-21 | Flexibilidad: adaptabilidad | Correctivo | Prueba de sistema ST-01 | test_bug21 (4 casos) | `45c9ea6` |
| BUG-22 | Compatibilidad: interoperabilidad | Correctivo | Prueba de integración | test_head_request_respects_host_validation | `6bb72f9` |
| BUG-23 | Capacidad de interacción: operabilidad | Correctivo | Revisión de las capturas | ST-12 (manual) | `47e5e10` |

Las pruebas `test_bugXX` están en `tests/test_regresion.py`; las de JavaScript en
`tests/js/game-utils.test.js`; las pruebas de sistema manuales (ST-xx) se
describen en [INFORME_TECNICO.md](INFORME_TECNICO.md).

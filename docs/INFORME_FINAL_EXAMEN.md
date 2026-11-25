# Informe técnico final: Juego 2048 «La Mina»

## Portada

| Dato | Valor |
| --- | --- |
| Asignatura | Codificación y Pruebas del Software, FESC |
| Equipo | Diego Alejandro Mosquera Caicedo, José Miguel Vera Castillo y Manuel Alejandro Suárez Hernández |
| Fecha | 25 de noviembre de 2026 |
| Repositorio | https://github.com/DiegoMosqueraC/juego-2048-python |
| Versión evaluada | 2.4.0, congelada con el tag `examen-final-v2` (commit de fusión en `main`) |

## Resumen ejecutivo

**Aplicación.** Juego 2048 en Python con dos modos (clásico y expedición tipo
roguelike), interfaz web local y modo terminal. Usa solo la biblioteca estándar;
pytest, pytest-cov, flake8, bandit y node:test son dependencias de desarrollo.
Cubre 8 requisitos funcionales (RF-01 a RF-08), más el modo expedición.

**Alcance.** Lógica, validaciones, persistencia, API local, modo terminal e interfaz
web, con la calidad medida en el pipeline de GitHub Actions.

**Resultado de la lista de chequeo** ([LISTA_DE_CHEQUEO.md](LISTA_DE_CHEQUEO.md)):

| Bloque | C | P | N |
| --- | :---: | :---: | :---: |
| Codificación y mantenimiento | 7 | 0 | 0 |
| Pruebas con xUnit | 8 | 0 | 0 |
| Proceso de pruebas e integración continua | 6 | 1 | 0 |

Cifras: 431 pruebas de Python y 10 de JavaScript, cobertura de sentencias y ramas
del 97,7 %, flake8 y bandit en cero, complejidad media A (3,2).

### Los tres hallazgos más críticos

1. **Un solo autor en el historial de Git.** El examen pide commits de todos los
   integrantes y los 70 commits hasta el tag `examen-final` están a nombre de Diego Mosquera.
   *Mitigación:* los otros dos integrantes deben hacer commits propios (por
   ejemplo, la sección de horas reales y la revisión de la lista de chequeo) antes de
   la entrega.
2. **Horas reales de prueba sin registrar.** Solo existe la estimación (56,2 h);
   no se puede comparar con lo ejecutado (D2, parcial).
   *Mitigación:* cada integrante anota sus horas y se completa la tabla de
   `docs/EVIDENCIAS_EXAMEN.md`.
3. **Documentación atrasada respecto al código.** El informe técnico y los
   talleres se escribieron sobre la versión 2.0.0, antes del modo expedición.
   *Mitigación:* la sección «Modo expedición» de `INFORME_TECNICO.md`, el
   `CHANGELOG.md` y `EVIDENCIAS_EXAMEN.md` (EV-01) registran el cambio. Los talleres
   conservan las cifras de entonces (283 pruebas) y deben leerse con esa fecha.

Además, la complejidad de `validate_grid` (C con radon) se corrigió durante la
revisión (preventivo).

## Dónde está cada cosa

| Documento | Contenido |
| --- | --- |
| [LISTA_DE_CHEQUEO.md](LISTA_DE_CHEQUEO.md) | Estado C/P/N y ruta de la evidencia de cada ítem |
| [ARQUITECTURA.md](ARQUITECTURA.md) | Diagramas de componentes y de clases, SOLID |
| [EVIDENCIAS_EXAMEN.md](EVIDENCIAS_EXAMEN.md) | Complejidad, entradas validadas, V(G), integración, dobles, recursos y esfuerzo |
| [INFORME_TECNICO.md](INFORME_TECNICO.md) | Proceso, TDD, análisis estático, estrategia de pruebas y CI |
| [REGISTRO_FALLOS.md](REGISTRO_FALLOS.md) | 23 fallos y matriz de trazabilidad |
| [talleres/](talleres/) | Talleres de la unidad 3 (plan de pruebas, automatización, CI) |
| [entregas/](entregas/) | Informe en PDF, lista de chequeo en el formato de la FESC y registro de horas reales |

Normas de referencia: IEEE 829, ISO/IEC/IEEE 29119-3 (documentación de pruebas),
ISO/IEC 25010 (calidad del producto) y PEP 8 (guía de estilo de Python).

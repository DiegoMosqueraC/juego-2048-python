# Lista de chequeo del examen final

Versión diligenciada en el formato de la FESC: [Lista_de_Chequeo_Examen_Final_Juego2048.pdf](entregas/Lista_de_Chequeo_Examen_Final_Juego2048.pdf).

Estado: **C** cumple, **P** parcial, **N** no cumple. Rutas relativas a la raíz del
repositorio. Cada evidencia está enlazada desde el [informe final](INFORME_FINAL_EXAMEN.md).

## Codificación y mantenimiento

| Ítem | Estado | Evidencia |
| --- | :---: | --- |
| B1 Estándar y analizador estático | C | `setup.cfg`; `docs/evidencias/04_resultado_final/flake8.txt` y `bandit.txt` (0 hallazgos) |
| B2 Legibilidad y complejidad ≤ 10 | C | `docs/evidencias/05_examen_final/radon_complejidad.txt`; explicación en `docs/EVIDENCIAS_EXAMEN.md` (B2) |
| B3 Modularidad y SOLID | C | `docs/ARQUITECTURA.md` (secciones 3 y 4) |
| B4 Codificación defensiva y seguridad | C | `docs/EVIDENCIAS_EXAMEN.md` (B4); `validation.py`; `bandit_secretos.txt` |
| B5 TDD rojo-verde-refactor | C | `f3b76d8` (rojo), `4ad303a` (verde), `5c865ce` (refactor); `docs/evidencias/02_tdd_fase_roja/`, `03_tdd_fase_verde/` |
| B6 Control de versiones | C | `git log --oneline --graph`: 70 commits hasta el tag `examen-final`, Conventional Commits, `main`, `develop`, `feat/*`, `fix/*`, `docs/*` |
| B7 Mantenimiento | C | `docs/REGISTRO_FALLOS.md` (23 fallos); cambio evolutivo EV-01 en `docs/EVIDENCIAS_EXAMEN.md` |

## Pruebas de software con xUnit

| Ítem | Estado | Evidencia |
| --- | :---: | --- |
| C1 xUnit, ≥ 15 pruebas, AAA | C | `tests/` (431 pruebas); `docs/evidencias/05_examen_final/pytest_cobertura.txt` |
| C2 Caja negra | C | `tests/test_game.py`, `tests/test_validation.py`; tablas en `docs/INFORME_TECNICO.md` y en el taller de proceso de prueba |
| C3 Caja blanca y V(G) | C | `docs/EVIDENCIAS_EXAMEN.md` (C3): dos grafos, V(G) = 3 y 5, y casos del camino base |
| C4 Integración | C | `docs/EVIDENCIAS_EXAMEN.md` (estrategia bottom-up); `tests/test_storage.py`, `tests/test_web_api.py` |
| C4 Dobles de prueba | C | `tests/doubles.py`, `tests/test_terminal_ui.py`; justificación en `docs/EVIDENCIAS_EXAMEN.md` |
| C5 Sistema y aceptación | C | `tests/test_sistema.py`; escenarios ST-01 a ST-13 en `docs/INFORME_TECNICO.md` (sección 6) |
| C6 Cobertura | C | 97,7 %; `docs/evidencias/05_examen_final/pytest_cobertura.txt` |
| C7 Regresión y trazabilidad | C | `docs/REGISTRO_FALLOS.md` (matriz); `tests/test_regresion.py` |

## Proceso de pruebas e integración continua

| Ítem | Estado | Evidencia |
| --- | :---: | --- |
| D1 Plan de pruebas | C | `docs/talleres/Taller_Unidad3_Proceso_de_Prueba_Juego2048.docx` (PP-2048-v1.0); recursos en `docs/EVIDENCIAS_EXAMEN.md` (D1) |
| D2 Esfuerzo y priorización | P | Estimación y prioridad por riesgo en el taller; horas reales por diligenciar en `docs/entregas/Registro_de_Horas_Reales_Juego2048.docx` |
| D3 Métricas y criterios de salida | C | Taller de proceso de prueba, sección de métricas |
| D4 Qué se automatiza | C | `docs/talleres/` y `Documentacion/Taller_Unidad3_Automatizacion_de_Pruebas_Juego2048.docx` |
| D5 Pipeline CI | C | `.github/workflows/ci.yml` |
| D6 Retroalimentación del CI | C | Ejecuciones 44427411761 (verde), 44427449715 (fallida a propósito), 44427834592 (corregida); `--cov-fail-under=90` |
| D7 Informe de CI | C | `docs/talleres/Taller_Unidad3_Integracion_Continua_Juego2048.docx` |

## Conteo por bloque

| Bloque | C | P | N |
| --- | :---: | :---: | :---: |
| Codificación y mantenimiento (7) | 7 | 0 | 0 |
| Pruebas con xUnit (8) | 8 | 0 | 0 |
| Proceso de pruebas e integración continua (7) | 6 | 1 | 0 |
| **Total (22)** | **21** | **1** | **0** |

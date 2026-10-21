"""
ci_local.py - Ejecuta localmente los mismos pasos del pipeline de CI
====================================================================
Uso (con las dependencias de requirements-dev.txt instaladas):

    python ci_local.py

Corre, en orden, flake8, bandit, pytest con cobertura y las pruebas de la
interfaz en Node. Se detiene en el primer paso que falle, igual que el
pipeline de GitHub Actions (.github/workflows/ci.yml).
"""

import shutil
import subprocess  # nosec B404 - solo se ejecutan comandos fijos de este archivo
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent

STEPS = [
    ("Análisis estático (flake8)", [sys.executable, "-m", "flake8", "."]),
    ("Análisis de seguridad (bandit)",
     [sys.executable, "-m", "bandit", "-q", "-r", ".", "-x", "./tests,./docs"]),
    ("Pruebas y cobertura (pytest)",
     [sys.executable, "-m", "pytest", "--cov", "--cov-report=term-missing",
      "--cov-fail-under=90"]),
    ("Pruebas de la interfaz (node:test)", ["node", "--test", "tests/js/*.test.js"]),
]


def run_step(title: str, command: list[str]) -> bool:
    print(f"\n=== {title} ===", flush=True)
    if shutil.which(command[0]) is None and command[0] != sys.executable:
        print(f"Se omite: '{command[0]}' no está instalado.")
        return True
    # Lista de argumentos sin shell: no hay interpretación de texto externo.
    completed = subprocess.run(command, cwd=PROJECT_DIR)  # nosec B603
    return completed.returncode == 0


def main() -> int:
    for title, command in STEPS:
        if not run_step(title, command):
            print(f"\nFALLÓ: {title}. Corrige el problema antes de integrar.")
            return 1
    print("\nTodos los pasos del pipeline terminaron correctamente.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

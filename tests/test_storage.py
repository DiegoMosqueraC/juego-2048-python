"""
test_storage.py - Pruebas de integración de la persistencia del récord
======================================================================
Usan un directorio temporal real (tmp_path) para verificar la lectura, la
escritura atómica y la tolerancia a archivos dañados, sin tocar el récord del
jugador.
"""

import json
import logging

import pytest

from storage import JsonHighscoreStorage, default_highscore_path


def test_missing_file_means_no_record(tmp_path):
    assert JsonHighscoreStorage(tmp_path / "no-existe.json").load() == 0


def test_saved_record_can_be_read_back(tmp_path):
    storage = JsonHighscoreStorage(tmp_path / "datos" / "highscore.json")
    storage.save(5120)
    assert storage.load() == 5120
    assert json.loads(storage.path.read_text(encoding="utf-8")) == {"highscore": 5120}


def test_save_leaves_no_temporary_files(tmp_path):
    storage = JsonHighscoreStorage(tmp_path / "highscore.json")
    storage.save(10)
    storage.save(20)
    assert [path.name for path in tmp_path.iterdir()] == ["highscore.json"]


@pytest.mark.parametrize(
    "content",
    ["{no es json", "[1, 2, 3]", '"texto"', '{"highscore": -5}', '{"otro": 1}'],
)
def test_damaged_or_unexpected_content_is_ignored(tmp_path, caplog, content):
    path = tmp_path / "highscore.json"
    path.write_text(content, encoding="utf-8")
    with caplog.at_level(logging.WARNING):
        assert JsonHighscoreStorage(path).load() == 0


def test_damaged_file_is_reported_in_the_log(tmp_path, caplog):
    path = tmp_path / "highscore.json"
    path.write_text("{roto", encoding="utf-8")
    with caplog.at_level(logging.WARNING):
        JsonHighscoreStorage(path).load()
    assert "No se pudo leer el récord" in caplog.text


def test_write_errors_do_not_interrupt_the_game(tmp_path, caplog):
    blocked = tmp_path / "archivo"
    blocked.write_text("x", encoding="utf-8")  # un archivo donde iría la carpeta
    storage = JsonHighscoreStorage(blocked / "highscore.json")
    with caplog.at_level(logging.WARNING):
        storage.save(100)  # no debe lanzar excepción
    assert "No se pudo guardar el récord" in caplog.text


def test_invalid_values_are_never_saved(tmp_path):
    storage = JsonHighscoreStorage(tmp_path / "highscore.json")
    with pytest.raises(ValueError):
        storage.save(-1)
    assert not storage.path.exists()


def test_default_path_uses_environment_variable(tmp_path, monkeypatch):
    monkeypatch.setenv("JUEGO2048_DATA_DIR", str(tmp_path))
    assert default_highscore_path() == tmp_path / "highscore.json"


def test_default_path_is_absolute_without_environment_variable(monkeypatch):
    monkeypatch.delenv("JUEGO2048_DATA_DIR", raising=False)
    path = default_highscore_path()
    assert path.is_absolute()
    assert path.name == "highscore.json"

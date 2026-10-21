"""
test_validation.py - Partición de equivalencia y valores límite de las entradas
===============================================================================
Para cada validador se prueba al menos un representante de cada clase válida e
inválida y los valores en las fronteras de los rangos permitidos.
"""

import pytest

from validation import (
    is_strict_int,
    is_valid_tile,
    normalize_direction,
    validate_board_size,
    validate_port,
    validate_score,
)


@pytest.mark.parametrize(
    "value, expected",
    [(0, True), (-3, True), (10**12, True), (True, False), (1.0, False), ("1", False)],
)
def test_is_strict_int(value, expected):
    assert is_strict_int(value) is expected


@pytest.mark.parametrize(
    "value, expected",
    [
        ("right", "right"), ("  DOWN ", "down"), ("arriba", "up"), ("Abajo", "down"),
        ("izquierda", "left"), ("derecha", "right"),
    ],
)
def test_normalize_direction_valid_partitions(value, expected):
    assert normalize_direction(value) == expected


@pytest.mark.parametrize("value", ["", "   ", "norte", "upp", None, 1, b"left"])
def test_normalize_direction_invalid_partitions(value):
    with pytest.raises(ValueError):
        normalize_direction(value)


@pytest.mark.parametrize("value", [2, 3, 7, 8])
def test_board_size_inside_limits(value):
    assert validate_board_size(value) == value


@pytest.mark.parametrize("value", [1, 9, 0, -1, 2.5, "4"])
def test_board_size_outside_limits(value):
    with pytest.raises(ValueError):
        validate_board_size(value)


@pytest.mark.parametrize("value", [0, 1, 2_000_000])
def test_score_valid(value):
    assert validate_score(value) == value


@pytest.mark.parametrize("value", [-1, 1.5, "10", None, False])
def test_score_invalid(value):
    with pytest.raises(ValueError):
        validate_score(value)


@pytest.mark.parametrize(
    "value, expected", [(1, 1), (65535, 65535), ("8080", 8080), (" 9000 ", 9000)]
)
def test_port_valid_limits(value, expected):
    assert validate_port(value) == expected


@pytest.mark.parametrize("value", [0, 65536, -80, "abc", "80.5", None, 8080.0])
def test_port_invalid(value):
    with pytest.raises(ValueError):
        validate_port(value)


@pytest.mark.parametrize(
    "value, expected",
    [(0, True), (2, True), (4096, True), (1, False), (3, False), (6, False),
     (-2, False), (2.0, False), (False, False)],
)
def test_is_valid_tile(value, expected):
    assert is_valid_tile(value) is expected

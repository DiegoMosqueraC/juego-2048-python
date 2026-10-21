"""
test_slide_merge.py - Pruebas de caja blanca del algoritmo central
==================================================================
Los casos se diseñaron mirando el código de slide_and_merge_line() para recorrer
todas sus ramas (cobertura de decisiones):

    while position < len(tiles)            -> 0 iteraciones / varias iteraciones
    next_tile is not None                  -> hay siguiente / es la última ficha
    next_tile[1] == value                  -> se fusiona / no se fusiona
"""

import pytest

from logic import LineMove, slide_and_merge_line


@pytest.mark.parametrize(
    "line, values, points",
    [
        # Rama: el bucle no se ejecuta (línea vacía).
        ([0, 0, 0, 0], (0, 0, 0, 0), 0),
        # Rama: una sola ficha, next_tile es None.
        ([0, 0, 0, 8], (8, 0, 0, 0), 0),
        # Rama: hay siguiente pero es distinta.
        ([2, 4, 0, 0], (2, 4, 0, 0), 0),
        # Rama: hay siguiente igual (fusión) separada por huecos.
        ([2, 0, 0, 2], (4, 0, 0, 0), 4),
        # Fusión seguida de ficha sin pareja.
        ([4, 4, 8, 0], (8, 8, 0, 0), 8),
        # Dos fusiones en la misma línea.
        ([8, 8, 16, 16], (16, 32, 0, 0), 48),
        # Una ficha fusionada no vuelve a fusionarse en la misma jugada.
        ([4, 2, 2, 0], (4, 4, 0, 0), 4),
        # Tres iguales: se fusionan las dos primeras.
        ([0, 2, 2, 2], (4, 2, 0, 0), 4),
        # Líneas de otros tamaños (tableros 2x2 y 5x5).
        ([2, 2], (4, 0), 4),
        ([2, 2, 2, 2, 2], (4, 4, 2, 0, 0), 8),
    ],
)
def test_values_and_points_for_each_branch(line, values, points):
    result = slide_and_merge_line(line)
    assert result.values == values
    assert result.points == points


def test_merge_records_both_sources_and_the_target():
    result = slide_and_merge_line([0, 2, 0, 2])
    assert result.moves == (
        LineMove(source=1, target=0, merged=True),
        LineMove(source=3, target=0, merged=True),
    )
    assert result.merged_targets == (0,)


def test_tiles_that_do_not_move_are_reported_with_same_source_and_target():
    result = slide_and_merge_line([2, 4, 0, 8])
    assert result.moves == (
        LineMove(0, 0, False),
        LineMove(1, 1, False),
        LineMove(3, 2, False),
    )
    assert result.merged_targets == ()


def test_input_line_is_not_modified():
    line = [2, 2, 0, 4]
    slide_and_merge_line(line)
    assert line == [2, 2, 0, 4]


def test_result_keeps_the_length_of_the_line():
    for size in range(2, 9):
        assert len(slide_and_merge_line([2] * size).values) == size

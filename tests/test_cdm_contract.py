from __future__ import annotations

from zona4_graph_loader.io.sources_ingestor import (
    ALLOWED_SOURCE_KEYS,
    empty_canonical_dataset,
)


def test_cdm_tiene_siete_colecciones():
    assert ALLOWED_SOURCE_KEYS == {
        "personas",
        "lugares",
        "relaciones_interpersonales",
        "eventos_espaciales",
        "jerarquias",
        "entidades_contexto",
        "relaciones_contexto",
    }


def test_dataset_vacio_tiene_todas_las_claves():
    dataset = empty_canonical_dataset()
    assert set(dataset) == ALLOWED_SOURCE_KEYS
    assert all(value == [] for value in dataset.values())

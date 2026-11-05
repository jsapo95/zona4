"""El notebook es la especificación del modelo: sus celdas con la etiqueta
`contrato` afirman, con ejemplos, qué tiene que hacer el código. Este test las
ejecuta en orden, en un mismo espacio de nombres, sin Jupyter. Si el código y
el notebook dejan de coincidir, falla."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

NOTEBOOK = (
    Path(__file__).resolve().parents[2]
    / "src" / "zona4_graph_loader" / "fellegi_sunter" / "fellegi-Sunter.ipynb"
)


def _celdas_contrato():
    cuaderno = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    return [
        "".join(celda["source"])
        for celda in cuaderno["cells"]
        if celda["cell_type"] == "code" and "contrato" in celda.get("metadata", {}).get("tags", [])
    ]


def test_el_notebook_tiene_celdas_de_contrato():
    assert len(_celdas_contrato()) >= 5


def test_las_celdas_de_contrato_se_cumplen():
    espacio: dict = {}
    for i, fuente in enumerate(_celdas_contrato()):
        try:
            exec(compile(fuente, f"contrato[{i}]", "exec"), espacio)
        except Exception as error:  # pragma: no cover - el mensaje es lo que importa
            pytest.fail(f"Celda de contrato {i} del notebook falló: {error!r}\n\n{fuente}")

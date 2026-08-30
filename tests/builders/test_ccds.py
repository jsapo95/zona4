"""Regresión: Fix E (hallazgo I1 de la auditoría semántica 2026-08-29).

`build_ccd_rows` asignaba `PARIO_EN` a partir de la relación literal
`pario_en` de la fuente, sin mirar el género de la persona. La fuente usa
esa etiqueta de forma laxa para "el parto de su hije ocurrió aquí" y se la
aplica por igual al padre y a la madre del mismo hecho -Raúl Eugenio Metz
(género masculino, figura como padre en `nietos_y_nietas.json`) recibía la
misma arista `PARIO_EN` que Graciela Alicia Romero, la madre.
"""
from __future__ import annotations

from zona4_graph_loader.builders.ccds import _ccd_rel_to_tipo, build_ccd_rows
from zona4_graph_loader.io.files import CCDS_PATH, DETALLES_PATH, read_json


def test_pario_en_se_mantiene_para_genero_femenino():
    assert _ccd_rel_to_tipo("pario_en", "FEMENINO") == "PARIO_EN"


def test_pario_en_se_convierte_a_presente_en_para_genero_masculino():
    assert _ccd_rel_to_tipo("pario_en", "MASCULINO") == "PRESENTE_EN"


def test_pario_en_se_mantiene_para_genero_indeterminado():
    # No hay evidencia de que los casos sin género registrado estén mal; sólo
    # se corrige el caso confirmado (masculino).
    assert _ccd_rel_to_tipo("pario_en", "INDETERMINADO") == "PARIO_EN"


def test_otras_relaciones_no_se_afectan():
    assert _ccd_rel_to_tipo("presente", "FEMENINO") == "PRESENTE_EN"
    assert _ccd_rel_to_tipo("presente", "MASCULINO") == "PRESENTE_EN"


def test_sobre_los_datos_reales_ningun_pario_en_cae_sobre_un_registro_masculino():
    detalles = read_json(DETALLES_PATH)
    ccds = read_json(CCDS_PATH)

    resultado = build_ccd_rows(detalles, ccds, use_georef=False)
    eventos = resultado["eventos_espaciales"]

    genero_por_registro = {
        item.get("registro"): (item.get("detalle") or {}).get("Sexo")
        for item in detalles
        if item.get("registro") is not None
    }

    pario_en = [e for e in eventos if e["tipo_relacion"] == "PARIO_EN"]
    presente_en = [e for e in eventos if e["tipo_relacion"] == "PRESENTE_EN"]

    for evento in pario_en:
        registro = int(evento["persona_key"].split(":", 1)[1])
        sexo = (genero_por_registro.get(registro) or "").strip().lower()
        assert "masc" not in sexo, (
            f"PARIO_EN no debería caer sobre un registro masculino: {evento}"
        )

    # 41 aristas PARIO_EN en la fuente, 2 sobre registros masculinos (hallazgo
    # I1): deberían quedar 39 PARIO_EN y los 2 casos masculinos pasar a
    # PRESENTE_EN (que ya tenía 204 de origen "ccds_json").
    assert len(pario_en) == 39
    presente_en_ccds = [e for e in presente_en if e["origen"] == "ccds_json"]
    assert len(presente_en_ccds) == 204 + 2

"""Regresión: Fix E (hallazgos I1 e I2 de la auditoría semántica 2026-08-29).

I1: `build_ccd_rows` asignaba `PARIO_EN` a partir de la relación literal
`pario_en` de la fuente, sin mirar el género de la persona. La fuente usa
esa etiqueta de forma laxa para "el parto de su hije ocurrió aquí" y se la
aplica por igual al padre y a la madre del mismo hecho -Raúl Eugenio Metz
(género masculino, figura como padre en `nietos_y_nietas.json`) recibía la
misma arista `PARIO_EN` que Graciela Alicia Romero, la madre.

I2: `_parse_ccd_fecha` fabricaba precisión de día a partir de fechas
`AAAA/MM` o `AAAA` de la fuente (245 de 278 valores no son `AAAA/MM/DD`), y
cuando la fuente traía más de un valor de fecha, descartaba todos menos el
de inicio más temprano.
"""
from __future__ import annotations

from zona4_graph_loader.builders.ccds import _ccd_rel_to_tipo, _parse_ccd_fecha, build_ccd_rows
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


# --- I2: precisión de fecha ---


def test_fecha_mes_no_fabrica_precision_de_dia():
    resultado = _parse_ccd_fecha(["1977/06"])
    assert resultado["fecha"] == "1977-06-01"
    assert resultado["fecha_fin"] == "1977-06-30"
    assert resultado["precision_fecha"] == "MONTH"


def test_fecha_anio_no_fabrica_precision_de_dia():
    resultado = _parse_ccd_fecha(["1978"])
    assert resultado["fecha"] == "1978-01-01"
    assert resultado["fecha_fin"] == "1978-12-31"
    assert resultado["precision_fecha"] == "YEAR"


def test_fecha_dia_exacto_mantiene_precision_de_dia():
    resultado = _parse_ccd_fecha(["1977/06/01"])
    assert resultado["fecha"] == "1977-06-01"
    assert resultado["fecha_fin"] == "1977-06-01"
    assert resultado["precision_fecha"] == "DAY"


def test_rango_de_dos_meses_no_pierde_el_segundo_mes():
    # Casado, Olga Noemi en la fuente real: ["1978/01", "1978/02"]. Antes de
    # este fix, el segundo mes se descartaba por completo
    # (`fecha:"1978-01-01"` y nada más).
    resultado = _parse_ccd_fecha(["1978/01", "1978/02"])
    assert resultado["fecha"] == "1978-01-01"
    assert resultado["fecha_fin"] == "1978-02-28"
    assert resultado["precision_fecha"] == "MONTH"


def test_sin_valores_parseables_conserva_el_crudo_sin_fecha_fin():
    resultado = _parse_ccd_fecha(["no consta"])
    assert resultado["fecha"] == "no consta"
    assert resultado["fecha_fin"] is None
    assert resultado["precision_fecha"] is None


def test_sobre_los_datos_reales_precision_fecha_nunca_es_day_para_valores_de_mes():
    detalles = read_json(DETALLES_PATH)
    ccds = read_json(CCDS_PATH)
    resultado = build_ccd_rows(detalles, ccds, use_georef=False)
    eventos = [e for e in resultado["eventos_espaciales"] if e["origen"] == "ccds_json"]

    con_precision = [e for e in eventos if e.get("precision_fecha")]
    assert con_precision  # el fix debe estar activo sobre datos reales
    for evento in con_precision:
        assert evento["precision_fecha"] in {"DAY", "MONTH", "YEAR"}
        if evento["precision_fecha"] != "DAY":
            # Si no es precisión de día, fecha no debería mentir con
            # segundos/día exactos sin fecha_fin que lo acompañe.
            assert evento.get("fecha_fin") is not None


# --- I5: DirecciónCCD debe declarar tipo_direccion="CCD" en este builder ---


def test_direcciones_generadas_por_este_builder_son_siempre_ccd():
    # Fix E (auditoría 2026-08-29, hallazgo I5): a diferencia de
    # builders/lugares.py (que genera DirecciónCCD a partir de texto libre
    # sobre domicilios/vía pública), este builder sólo produce direcciones
    # de centros clandestinos reales de `ccds.json`.
    detalles = read_json(DETALLES_PATH)
    ccds = read_json(CCDS_PATH)
    resultado = build_ccd_rows(detalles, ccds, use_georef=False)
    direcciones = [l for l in resultado["lugares"] if l.get("tipo_entidad") == "DireccionCCD"]
    assert direcciones
    assert all(d["tipo_direccion"] == "CCD" for d in direcciones)

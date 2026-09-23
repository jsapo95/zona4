"""Regresión: Fix C (hallazgos C3 y C4 de la auditoría semántica 2026-08-29).

C4 -- `_can_assume_buenos_aires` inventaba una ciudad de Buenos Aires para
cualquier cadena corta sin pista provincial ni dígitos, sin importar que
fuera un fragmento de prosa narrativa, una duda del registro ("posiblemente")
o directamente una dirección completa. `resolve_place` debe rechazar esos
casos (devolver `None`) en lugar de crear un nodo.

C3 -- cuando la fuente trae "LOCALIDAD. PROVINCIA" (p.ej. "Rosario. Santa
Fe"), `PlaceGazetteer.resolve` matchea por n-gramas contra la cadena
completa, y el nombre de la provincia (que muchas veces es también nombre de
ciudad, como "Santa Fe") le gana al de la localidad real por tener más
palabras. `resolve_place` debe preferir la provincia que la fuente nombra
explícitamente.

También se fija acá la regla de "no restar precisión": los partidos de
Buenos Aires con número en el propio nombre ("25 de Mayo", "9 de Julio",
"Tres de Febrero", "3 de Febrero") deben seguir resolviendo -no son
direcciones sólo porque tengan un dígito.

`test_ningun_valor_real_antes_resuelto_se_pierde_sin_estar_en_la_lista_de_rechazos_esperados`
es la prueba de no-regresión más importante de este archivo: corre
`resolve_place` sobre los ~2.400 valores distintos de
`descripcion_lugar_de_secuestro` / `Lugar de nacimiento` / `Lugar de
asesinato` de `parque_de_la_memoria.json` (fuente real) y falla si CUALQUIER
valor que hoy resuelve deja de resolver, salvo los 8 casos ya identificados y
confirmados como fragmentos manufacturados (ver semantic-fixes-report.md).
"""
from __future__ import annotations

import json
from pathlib import Path

from zona4_graph_loader.domain.place_norm import resolve_place
from zona4_graph_loader.io.files import DETALLES_PATH, read_json

FIXTURES_DIR = Path(__file__).parent / "fixtures"


BUENOS_AIRES = "lugar:PROVINCIA:buenos_aires|lugar:PAIS:argentina"


# --- C4: fragmentos narrativos, dudas y direcciones no deben volverse nodos ---


def test_hedge_word_posiblemente_no_resuelve():
    assert resolve_place("SE DESCONOCE (posiblemente Bs As)") is None


def test_fragmento_prov_de_no_resuelve():
    assert resolve_place("Prov. de Bs As") is None


def test_fragmento_cercanias_con_capital_federal_no_resuelve():
    # La fuente nombra Capital Federal explícitamente; antes del fix el
    # heurístico de Buenos Aires igual creaba una ciudad ficticia
    # "EN LAS CERCANIAS DE SU".
    resultado = resolve_place(
        "Secuestrado en las cercanías de su lugar de trabajo, "
        "en Maipú y Corrientes (Capital Federal)"
    )
    assert resultado is None


def test_direccion_completa_glued_no_resuelve():
    assert resolve_place("San Nicolas (Cangallo 1671, 2º C). MARTINEZ. BS. AS.") is None


def test_bar_glued_a_ciudad_no_resuelve():
    assert resolve_place("Agronomía (bar en Av San Martin y Fco Beiró). MERCEDES. BS. AS.") is None


def test_oruro_resuelve_a_bolivia_no_a_buenos_aires():
    resultado = resolve_place("Oruro")
    assert resultado is not None
    assert resultado["nombre_canonico"] == "ORURO"
    assert resultado["lugar_key"] == "lugar:CIUDAD:oruro|lugar:PAIS:bolivia"


def test_esquina_entre_dos_calles_no_inventa_ciudad():
    # "Entre San Juan y Córdoba" es una esquina (calle San Juan y calle
    # Córdoba), no una localidad. No debe crear "ENTRE SAN JUAN Y" como
    # ciudad de Córdoba.
    resultado = resolve_place("Entre San Juan y Córdoba")
    assert resultado is None or resultado["nombre_canonico"] != "ENTRE SAN JUAN Y"


# --- C3: LOCALIDAD. PROVINCIA debe preferir la provincia que la fuente nombra ---


def test_rosario_santa_fe_se_queda_en_rosario_no_en_la_capital():
    resultado = resolve_place("ROSARIO. SANTA FE")
    assert resultado is not None
    assert resultado["nombre_canonico"] == "ROSARIO"
    assert "lugar:PROVINCIA:santa_fe" in resultado["lugar_key"]


def test_jose_leon_suarez_bs_as_no_termina_en_jujuy():
    resultado = resolve_place("JOSE LEON SUAREZ. BS. AS.")
    assert resultado is not None
    assert "jujuy" not in resultado["lugar_key"]
    assert resultado["parent_key"] == BUENOS_AIRES or "buenos_aires" in resultado["lugar_key"]


def test_villa_elisa_bs_as_no_termina_en_santa_fe():
    resultado = resolve_place("VILLA ELISA. BS. AS.")
    assert resultado is not None
    assert "santa_fe" not in resultado["lugar_key"]
    assert "buenos_aires" in resultado["lugar_key"]


def test_general_sarmiento_bs_as_no_termina_en_cordoba():
    resultado = resolve_place("GENERAL SARMIENTO. BS. AS.")
    assert resultado is not None
    assert "cordoba" not in resultado["lugar_key"]
    assert "buenos_aires" in resultado["lugar_key"]


def test_san_andres_bs_as_no_termina_en_tucuman():
    resultado = resolve_place("SAN ANDRES. BS. AS.")
    assert resultado is not None
    assert "tucuman" not in resultado["lugar_key"]
    assert "buenos_aires" in resultado["lugar_key"]


def test_cruz_alta_tucuman_se_queda_en_tucuman():
    resultado = resolve_place("CRUZ ALTA. TUCUMAN")
    assert resultado is not None
    assert "lugar:PROVINCIA:tucuman" in resultado["lugar_key"]


# --- localidades con número propio: no son direcciones ---


def test_25_de_mayo_resuelve_a_buenos_aires():
    resultado = resolve_place("25 de mayo, BsAs")
    assert resultado is not None
    assert resultado["nombre_canonico"] == "25 DE MAYO"
    assert "buenos_aires" in resultado["lugar_key"]


def test_9_de_julio_resuelve_a_buenos_aires():
    resultado = resolve_place("9 de julio, Buenos Aires")
    assert resultado is not None
    assert resultado["nombre_canonico"] == "9 DE JULIO"
    assert "buenos_aires" in resultado["lugar_key"]


def test_3_de_febrero_resuelve_a_buenos_aires():
    resultado = resolve_place("3 de Febrero, BsAs")
    assert resultado is not None
    assert resultado["nombre_canonico"] == "3 DE FEBRERO"
    assert "buenos_aires" in resultado["lugar_key"]


# --- no regresión contra un match real que el fix no debe romper ---


def test_narracion_con_dos_palabras_narrativas_no_rompe_un_match_real():
    # "Trayecto" y "Zona rural" son dos palabras de la lista de fragmentos
    # narrativos, pero el resto de la cadena nombra una localidad real y
    # específica (Ingenio Fronterita, Famaillá, Tucumán) que el matcher por
    # n-gramas encuentra correctamente. No hay que bloquear el intento de
    # cadena completa sólo por la presencia de esas palabras.
    resultado = resolve_place(
        "Trayecto a pie e/Colonia 6 de Ingenio Fronterita y Sauce Huascho - "
        "Zona rural (Sauce Huascho - Famaillá, Tucumán)"
    )
    assert resultado is not None
    assert resultado["nombre_canonico"] == "INGENIO FRONTERITA"


# --- no regresión a escala, contra los datos reales ---

# Los únicos valores de la fuente real para los que se acepta perder una
# resolución previa: todos fragmentos manufacturados confirmados en
# semantic-fixes-report.md (direcciones completas, dudas explícitas del
# registro, o prosa sin ningún topónimo real). Si aparece un valor nuevo en
# esta lista de "pérdidas", hay que investigarlo -no agregarlo a ciegas.
RECHAZOS_ESPERADOS = {
    "(24/03/76 SDH) TIGRE. BS. AS.",
    "Agronomía (bar en Av San Martin y Fco Beiró). MERCEDES. BS. AS.",
    "Cámara de Almaceneros, lugar de trabajo. (Olavarría, Buenos Aires)",
    "Prov. de Bs As",
    "SE DESCONOCE (posiblemente Bs As)",
    "San Nicolas (Cangallo 1671, 2º C). MARTINEZ. BS. AS.",
    "Santa Fé y Urquiza - Parada de colectivo (Acassuso - San isidro - Buenos Aires)",
    "Secuestrado en las cercanías de su lugar de trabajo, en Maipú y Corrientes (Capital Federal)",
}

_CAMPOS = ("descripcion_lugar_de_secuestro", "Lugar de nacimiento", "Lugar de asesinato")


def _valores_reales_de_lugar():
    data = read_json(DETALLES_PATH)
    valores = set()
    for item in data:
        detalle = item.get("detalle", {})
        for campo in _CAMPOS:
            v = detalle.get(campo)
            if v:
                valores.add(v)
    return valores


def _valores_antes_resueltos_por_head():
    # Congelado corriendo `resolve_place` sobre los ~2.400 valores reales de
    # `parque_de_la_memoria.json` con el código de HEAD (commit 01d41a7, antes
    # de este Fix C): la lista completa de valores para los que el resolver
    # devolvía algo distinto de `None`. Ver semantic-fixes-report.md, sección
    # "Fix C", para el procedimiento exacto (diff antes/después sobre los
    # datos reales).
    path = FIXTURES_DIR / "place_norm_c3_c4_valores_antes_resueltos.json"
    with path.open("r", encoding="utf-8") as f:
        return set(json.load(f))


def test_ningun_valor_real_antes_resuelto_se_pierde_sin_estar_en_la_lista_de_rechazos_esperados():
    valores = _valores_reales_de_lugar()
    assert len(valores) > 2000  # guarda contra un archivo vacío/roto

    antes_resueltos = _valores_antes_resueltos_por_head()
    assert antes_resueltos <= valores  # la fixture debe ser un subconjunto de la fuente actual

    perdidos_inesperados = []
    for v in antes_resueltos:
        resultado = resolve_place(v)
        if resultado is None and v not in RECHAZOS_ESPERADOS:
            perdidos_inesperados.append(v)

    assert perdidos_inesperados == []


def test_rechazos_esperados_siguen_rechazados():
    # Complementaria de la anterior: si algún día alguno de estos empieza a
    # resolver de nuevo hay que revisar que no haya vuelto el defecto
    # original (manufacturar una ciudad a partir de prosa).
    for v in RECHAZOS_ESPERADOS:
        resultado = resolve_place(v)
        assert resultado is None, f"{v!r} debería seguir sin resolver, pero dio {resultado!r}"

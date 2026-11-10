from __future__ import annotations

import pytest

from zona4_graph_loader.fellegi_sunter.comparaciones import (
    FALTA,
    NIVELES,
    Fecha,
    nivel_centro,
    nivel_fecha,
    nivel_tokens,
    parsear_fecha,
    separar_nombre,
)


def _t(*tokens):
    return frozenset(tokens)


def _nivel_nombre(i):
    return NIVELES["apellido"][i]


@pytest.mark.parametrize("a, b, esperado", [
    (_t("perez"), _t("perez"), "exacto"),
    (_t("godoy"), _t("godoy", "ruiz"), "contenido"),
    (_t("castineira"), _t("castineyra"), "errata"),
    (_t("perez"), _t("peres", "gomez"), "errata"),
    (_t("juan", "carlos"), _t("juan", "pedro"), "comparte"),
    # Comparten un token sólo tras corregir una errata.
    (_t("perez", "lopez"), _t("peres", "gomez"), "comparte"),
    (_t("perez"), _t("gomez"), "distinto"),
    # Tokens cortos: una letra de diferencia no es errata.
    (_t("li"), _t("lu"), "distinto"),
])
def test_nivel_tokens(a, b, esperado):
    assert _nivel_nombre(nivel_tokens(a, b)) == esperado
    assert nivel_tokens(b, a) == nivel_tokens(a, b), "el nivel no depende del orden"


def test_nivel_tokens_falta():
    assert nivel_tokens(None, _t("perez")) is FALTA
    assert nivel_tokens(_t("perez"), frozenset()) is FALTA


def test_separar_nombre():
    assert separar_nombre("Castiñeiras, José María") == (_t("castineiras"), _t("jose", "maria"))
    # Las partículas y las iniciales no son tokens.
    assert separar_nombre("de la Fuente, Juan C.") == (_t("fuente"), _t("juan"))
    assert separar_nombre("Toranzo - Palacín") == (None, None)


@pytest.mark.parametrize("valor, esperado", [
    ("1976-03-24", Fecha(1976, 3, 24)),
    ("1948-07", Fecha(1948, 7)),
    ("1948", Fecha(1948)),
    ("DESCONOCIDA", None),
    (None, None),
    ("1976-13-45", None),
    ("1976-02-30", None),
    ("1976-00", None),
])
def test_parsear_fecha(valor, esperado):
    assert parsear_fecha(valor) == esperado


@pytest.mark.parametrize("a, b, esperado", [
    ("1976-03-24", "1976-03-24", "exacta"),
    ("1976-04-05", "1976-05-04", "dia_mes_invertidos"),
    ("1976-03-24", "1976-03-25", "mismo_año_mes"),
    ("1976-03-24", "1976-08-24", "mismo_año"),
    ("1976-03-24", "1977-03-24", "distinta"),
    # Con precisión parcial se compara hasta donde llegan las dos.
    ("1948", "1948-07-17", "mismo_año"),
    ("1948-07", "1948-07-17", "mismo_año_mes"),
    ("1948-07", "1948-08-17", "mismo_año"),
])
def test_nivel_fecha(a, b, esperado):
    nivel = nivel_fecha(parsear_fecha(a), parsear_fecha(b))
    assert NIVELES["fecha_secuestro"][nivel] == esperado
    assert nivel_fecha(parsear_fecha(b), parsear_fecha(a)) == nivel


def test_nivel_fecha_falta():
    assert nivel_fecha(None, Fecha(1976)) is FALTA


def test_nivel_centro():
    assert NIVELES["centro"][nivel_centro(_t("ccd:a", "ccd:b"), _t("ccd:b"))] == "comparte"
    assert NIVELES["centro"][nivel_centro(_t("ccd:a"), _t("ccd:b"))] == "ninguno_en_comun"
    assert nivel_centro(None, _t("ccd:a")) is FALTA

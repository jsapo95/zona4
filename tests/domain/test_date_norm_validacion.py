"""Regresión: Fix E (hallazgo I6 de la auditoría semántica 2026-08-29).

`validar_fecha_de_hecho` / `validar_fecha_de_nacimiento` descartan fechas
fuera de un rango real y verificado contra los datos crudos (ver el
comentario junto a las constantes en `domain/date_norm.py`), en vez de
persistir un valor imposible.
"""
from __future__ import annotations

from zona4_graph_loader.domain.date_norm import (
    validar_fecha_de_hecho,
    validar_fecha_de_nacimiento,
)


def test_fecha_de_hecho_none_pasa_intacta():
    assert validar_fecha_de_hecho(None) is None


def test_fecha_de_hecho_dentro_de_rango_se_conserva():
    assert validar_fecha_de_hecho("1976-07-13") == "1976-07-13"


def test_fecha_de_hecho_limites_inclusive():
    assert validar_fecha_de_hecho("1966-01-01") == "1966-01-01"
    assert validar_fecha_de_hecho("1990-12-31") == "1990-12-31"


def test_fecha_de_hecho_anterior_al_rango_se_rechaza():
    assert validar_fecha_de_hecho("1965-12-31") is None


def test_fecha_de_hecho_futura_se_rechaza():
    # Casos reales de la auditoría: 1997, 2023, 2024, 2077.
    for anio_malo in ("1997-04-11", "2023-11-12", "2024-03-30", "2077-05-26"):
        assert validar_fecha_de_hecho(anio_malo) is None


def test_fecha_de_nacimiento_dentro_de_rango_se_conserva():
    assert validar_fecha_de_nacimiento("1925-10-19") == "1925-10-19"
    assert validar_fecha_de_nacimiento("1894-01-01") == "1894-01-01"


def test_fecha_de_nacimiento_limite_1983_inclusive():
    assert validar_fecha_de_nacimiento("1983-12-31") == "1983-12-31"


def test_fecha_de_nacimiento_posterior_a_1983_se_rechaza():
    # Casos reales de la auditoría: Massera (2010), y los 7 NACIO_EN de
    # Parque de la Memoria (2021-2052).
    for fecha_mala in ("2010-11-08", "2021-07-18", "2052-12-23"):
        assert validar_fecha_de_nacimiento(fecha_mala) is None


def test_valor_no_parseable_pasa_intacto():
    # No es responsabilidad de este validador decidir si un string es una
    # fecha ISO válida -sólo filtra fechas ISO ya parseadas pero
    # implausibles. Un valor no-ISO (p.ej. ya en "DESCONOCIDA") no se toca.
    assert validar_fecha_de_hecho("DESCONOCIDA") == "DESCONOCIDA"
    assert validar_fecha_de_nacimiento("DESCONOCIDA") == "DESCONOCIDA"

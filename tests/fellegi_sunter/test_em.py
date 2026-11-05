from __future__ import annotations

import math
import random
from collections import Counter

from zona4_graph_loader.fellegi_sunter.em import (
    Parametros,
    ajustar_em,
    ajustar_em_varios_inicios,
    peso,
    pesos_por_campo,
    probabilidad_match,
)

# Tres campos binarios-ternarios con m y u conocidos: el mínimo para que la
# mezcla sea identificable (ver la sección 5 del notebook).
NUM_NIVELES = [3, 3, 2]
VERDAD = Parametros(
    pi=0.2,
    m=[[0.8, 0.15, 0.05], [0.7, 0.2, 0.1], [0.9, 0.1]],
    u=[[0.1, 0.3, 0.6], [0.05, 0.15, 0.8], [0.2, 0.8]],
)


def _simular(params, n, rng, p_falta=0.0):
    conteos = Counter()
    for _ in range(n):
        dist = params.m if rng.random() < params.pi else params.u
        g = tuple(
            None if rng.random() < p_falta else rng.choices(range(len(f)), weights=f)[0]
            for f in dist
        )
        conteos[g] += 1
    return conteos


def test_em_recupera_los_parametros_de_datos_simulados():
    conteos = _simular(VERDAD, 60_000, random.Random(7))
    ajuste = ajustar_em(conteos, NUM_NIVELES)
    assert ajuste.convergio
    assert abs(ajuste.pi - VERDAD.pi) < 0.02
    for k in range(len(NUM_NIVELES)):
        for nivel in range(NUM_NIVELES[k]):
            assert abs(ajuste.m[k][nivel] - VERDAD.m[k][nivel]) < 0.03
            assert abs(ajuste.u[k][nivel] - VERDAD.u[k][nivel]) < 0.03


def test_em_con_faltantes_al_azar():
    conteos = _simular(VERDAD, 60_000, random.Random(8), p_falta=0.3)
    ajuste = ajustar_em(conteos, NUM_NIVELES)
    assert abs(ajuste.pi - VERDAD.pi) < 0.02
    assert abs(ajuste.m[0][0] - VERDAD.m[0][0]) < 0.03


def test_el_objetivo_nunca_baja():
    conteos = _simular(VERDAD, 5_000, random.Random(9))
    historia = ajustar_em(conteos, NUM_NIVELES).historia
    assert all(b >= a - 1e-9 for a, b in zip(historia, historia[1:]))


def test_varios_inicios_llegan_a_la_misma_solucion():
    conteos = _simular(VERDAD, 20_000, random.Random(10))
    mejor, ajustes = ajustar_em_varios_inicios(conteos, NUM_NIVELES, inicios_aleatorios=5, semilla=1)
    assert mejor.objetivo == max(a.objetivo for a in ajustes)
    cerca = [a for a in ajustes if abs(a.objetivo - mejor.objetivo) < 1e-4]
    assert all(abs(a.pi - mejor.pi) < 1e-3 for a in cerca)


def test_etiquetas_m_es_la_clase_de_mas_acuerdo():
    conteos = _simular(VERDAD, 20_000, random.Random(11))
    invertido = Parametros(pi=0.8, m=[list(f) for f in VERDAD.u], u=[list(f) for f in VERDAD.m])
    ajuste = ajustar_em(conteos, NUM_NIVELES, inicio=invertido)
    assert ajuste.m[0][0] > ajuste.u[0][0]
    assert ajuste.pi < 0.5


def test_peso_y_probabilidad():
    g = (0, None, 1)
    esperado = math.log2(0.8 / 0.1) + math.log2(0.1 / 0.8)
    assert math.isclose(peso(g, VERDAD), esperado)
    assert pesos_por_campo(g, VERDAD)[1] is None
    # logit P(M|γ) = logit π + w·ln 2
    p = probabilidad_match(g, VERDAD)
    assert math.isclose(math.log(p / (1 - p)), math.log(0.2 / 0.8) + esperado * math.log(2))

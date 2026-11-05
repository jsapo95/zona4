from __future__ import annotations

import math

from zona4_graph_loader.fellegi_sunter.decision import (
    NO_VINCULAR,
    REVISAR,
    VINCULAR,
    Umbrales,
    calcular_umbrales,
    decidir,
)
from zona4_graph_loader.fellegi_sunter.em import Parametros, peso, probabilidad_match

# Un solo campo con tres niveles: los pesos son log2(8), log2(1) y log2(1/8).
PARAMS = Parametros(pi=0.1, m=[[0.8, 0.1, 0.1]], u=[[0.1, 0.1, 0.8]])
CONTEOS = {(0,): 100, (1,): 100, (2,): 800}


def _masas():
    """(masa en U, masa en M) por patrón, como las define decision._por_peso."""
    return {
        g: (n * (1 - probabilidad_match(g, PARAMS)), n * probabilidad_match(g, PARAMS))
        for g, n in CONTEOS.items()
    }


def test_umbrales_con_tasas_holgadas_dejan_revisar_en_el_medio():
    masas = _masas()
    total_u = sum(u for u, _ in masas.values())
    total_m = sum(m for _, m in masas.values())
    mu = masas[(0,)][0] / total_u + 1e-9
    lam = masas[(2,)][1] / total_m + 1e-9
    umbrales = calcular_umbrales(CONTEOS, PARAMS, mu, lam)
    assert math.isclose(umbrales.t_mu, 3.0)
    assert math.isclose(umbrales.t_lambda, -3.0)
    assert decidir(peso((0,), PARAMS), umbrales) == VINCULAR
    assert decidir(peso((1,), PARAMS), umbrales) == REVISAR
    assert decidir(peso((2,), PARAMS), umbrales) == NO_VINCULAR


def test_umbrales_nunca_se_pasan_de_la_tasa():
    umbrales = calcular_umbrales(CONTEOS, PARAMS, mu=0.0, lam=0.0)
    assert umbrales.t_mu == math.inf and umbrales.t_lambda == -math.inf
    assert decidir(peso((0,), PARAMS), umbrales) == REVISAR


def test_si_los_umbrales_se_cruzan_gana_no_vincular():
    umbrales = Umbrales(t_mu=-1.0, t_lambda=1.0, mu_estimado=0.0, lambda_estimado=0.0)
    assert decidir(0.0, umbrales) == NO_VINCULAR
    assert decidir(2.0, umbrales) == VINCULAR

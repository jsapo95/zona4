"""Regla de decisión de Fellegi y Sunter (sección 6 del notebook).

Es un test de razón de verosimilitud con dos umbrales sobre el peso
w = log2(m(γ)/u(γ)):

    w ≤ T_λ           → no vincular
    w ≥ T_μ           → vincular
    T_λ < w < T_μ     → revisar (revisión humana)

T_μ es el umbral más bajo que mantiene la tasa estimada de vínculos falsos,
P(vincular | U), en a lo sumo μ. T_λ es el más alto que mantiene la tasa
estimada de vínculos perdidos, P(no vincular | M), en a lo sumo λ. Las tasas
se estiman con el modelo ajustado sobre los pares observados, así que valen
sólo si el modelo es correcto.

Las decisiones son por par: no garantizan transitividad y no se aplican al
grafo.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from zona4_graph_loader.fellegi_sunter.em import Conteos, Parametros, peso, probabilidad_match

VINCULAR = "vincular"
REVISAR = "revisar"
NO_VINCULAR = "no_vincular"


@dataclass(frozen=True)
class Umbrales:
    t_mu: float
    t_lambda: float
    mu_estimado: float
    lambda_estimado: float


def _por_peso(conteos: Conteos, params: Parametros) -> List[Tuple[float, float, float]]:
    """(peso, masa en U, masa en M) de cada peso distinto, de mayor a menor.

    La masa en U de un patrón es n·(1 − P(M|γ)): cuántos de sus pares el
    modelo atribuye a personas distintas. La masa en M es n·P(M|γ).
    """
    acum: Dict[float, List[float]] = {}
    for g, n in conteos.items():
        w = round(peso(g, params), 12)
        p = probabilidad_match(g, params)
        masa = acum.setdefault(w, [0.0, 0.0])
        masa[0] += n * (1.0 - p)
        masa[1] += n * p
    return sorted(((w, mu, mm) for w, (mu, mm) in acum.items()), reverse=True)


def calcular_umbrales(conteos: Conteos, params: Parametros, mu: float, lam: float) -> Umbrales:
    """Umbrales para las tasas de error objetivo `mu` y `lam`.

    Como los pesos toman pocos valores, no siempre se puede llegar a la tasa
    exacta. Convención: nunca pasarse. Si ni el peso más alto cumple `mu`, no
    se vincula nada (T_μ = +∞); si ni el más bajo cumple `lam`, no se descarta
    nada (T_λ = −∞).

    Si los umbrales se cruzan (T_λ ≥ T_μ), las dos reglas aceptan los pesos
    del medio. En este dominio un vínculo falso es el peor error, así que gana
    "no vincular": sólo se vincula con w > T_λ.
    """
    filas = _por_peso(conteos, params)
    total_u = sum(f[1] for f in filas)
    total_m = sum(f[2] for f in filas)

    t_mu, mu_estimado, acum_u = float("inf"), 0.0, 0.0
    for w, masa_u, _ in filas:
        acum_u += masa_u
        if acum_u / total_u > mu:
            break
        t_mu, mu_estimado = w, acum_u / total_u

    t_lambda, lambda_estimado, acum_m = float("-inf"), 0.0, 0.0
    for w, _, masa_m in reversed(filas):
        acum_m += masa_m
        if acum_m / total_m > lam:
            break
        t_lambda, lambda_estimado = w, acum_m / total_m

    if t_lambda >= t_mu:
        # Con el cruce, `decidir` vincula sólo con w > T_λ: la tasa de vínculos
        # falsos que se reporta tiene que ser la de esa regla.
        mu_estimado = sum(masa_u for w, masa_u, _ in filas if w > t_lambda) / total_u

    return Umbrales(t_mu, t_lambda, mu_estimado, lambda_estimado)


def decidir(w: float, umbrales: Umbrales) -> str:
    # Mismo redondeo que _por_peso, para que un par caiga del mismo lado del
    # umbral que el patrón con el que se calculó.
    w = round(w, 12)
    if w <= umbrales.t_lambda:
        return NO_VINCULAR
    if w >= umbrales.t_mu:
        return VINCULAR
    return REVISAR

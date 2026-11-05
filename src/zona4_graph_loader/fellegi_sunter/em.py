"""Estimación de m, u y π con EM (sección 4 y 5 del notebook).

El modelo es una mezcla de dos clases, M (misma persona) y U (personas
distintas). Dada la clase, los campos son independientes y cada uno sigue una
distribución categórica sobre sus niveles:

    P(γ | M) = Π_k m_k(γ_k)        P(γ | U) = Π_k u_k(γ_k)

donde el producto recorre sólo los campos observados. Que un campo `FALTA` no
aporte nada supone que qué campos faltan no depende de la clase ni de los
valores que faltan. El EM trabaja sobre los conteos
de cada patrón, que son pocos aunque los pares sean muchos.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

Patron = Tuple[Optional[int], ...]
Conteos = Dict[Patron, int]

# Pseudo-conteo que se suma a cada nivel en el paso M. Evita probabilidades
# exactamente 0 (que darían pesos infinitos) en niveles que no aparecen en
# alguna de las dos clases. Equivale a estimar por máximo a posteriori con una
# previa Dirichlet(1 + PSEUDO_CONTEO) en cada m_k y u_k.
PSEUDO_CONTEO = 1.0


@dataclass
class Parametros:
    pi: float
    m: List[List[float]]
    u: List[List[float]]
    objetivo: float = float("nan")
    iteraciones: int = 0
    convergio: bool = False
    historia: List[float] = field(default_factory=list)


def _probabilidad(patron: Patron, dist: List[List[float]]) -> float:
    prob = 1.0
    for k, nivel in enumerate(patron):
        if nivel is not None:
            prob *= dist[k][nivel]
    return prob


def probabilidad_match(patron: Patron, params: Parametros) -> float:
    """P(M | γ) por la regla de Bayes."""
    pm = params.pi * _probabilidad(patron, params.m)
    pu = (1.0 - params.pi) * _probabilidad(patron, params.u)
    return pm / (pm + pu)


def pesos_por_campo(patron: Patron, params: Parametros) -> List[Optional[float]]:
    """log2(m_k / u_k) del nivel observado en cada campo, o None si falta."""
    return [
        None if nivel is None else math.log2(params.m[k][nivel] / params.u[k][nivel])
        for k, nivel in enumerate(patron)
    ]


def peso(patron: Patron, params: Parametros) -> float:
    """log2 de la razón de verosimilitud m(γ)/u(γ), en bits: la suma de los
    pesos de cada campo observado."""
    return sum(w for w in pesos_por_campo(patron, params) if w is not None)


def objetivo(conteos: Conteos, params: Parametros, pseudo: float = PSEUDO_CONTEO) -> float:
    """Log-verosimilitud de los conteos más el logaritmo de la previa (sin su
    constante). Es lo que el EM con pseudo-conteo no deja de aumentar."""
    loglik = sum(
        n * math.log(
            params.pi * _probabilidad(g, params.m) + (1.0 - params.pi) * _probabilidad(g, params.u)
        )
        for g, n in conteos.items()
    )
    log_previa = pseudo * sum(
        math.log(p) for dist in (params.m, params.u) for fila in dist for p in fila
    )
    return loglik + log_previa


def paso_e(conteos: Conteos, params: Parametros) -> Dict[Patron, float]:
    """Para cada patrón, la probabilidad de que un par con ese patrón sea M."""
    return {g: probabilidad_match(g, params) for g in conteos}


def paso_m(
    conteos: Conteos,
    responsabilidad: Dict[Patron, float],
    num_niveles: Sequence[int],
    pseudo: float = PSEUDO_CONTEO,
) -> Parametros:
    """Promedios ponderados: cada par cuenta como `g` en M y `1 - g` en U.

    Para el campo k se usan sólo los pares que lo tienen observado.
    """
    total = sum(conteos.values())
    peso_m = sum(n * responsabilidad[g] for g, n in conteos.items())
    pi = peso_m / total

    acum_m = [[pseudo] * L for L in num_niveles]
    acum_u = [[pseudo] * L for L in num_niveles]
    for g, n in conteos.items():
        r = responsabilidad[g]
        for k, nivel in enumerate(g):
            if nivel is not None:
                acum_m[k][nivel] += n * r
                acum_u[k][nivel] += n * (1.0 - r)

    def normalizar(filas: List[List[float]]) -> List[List[float]]:
        return [[x / sum(fila) for x in fila] for fila in filas]

    return Parametros(pi=pi, m=normalizar(acum_m), u=normalizar(acum_u))


def inicio_por_defecto(
    conteos: Conteos, num_niveles: Sequence[int], pseudo: float = PSEUDO_CONTEO
) -> Parametros:
    """Punto de partida determinista.

    En m, cada nivel tiene la mitad de probabilidad que el anterior (los
    niveles van de más a menos acuerdo). En u, la frecuencia observada de cada
    nivel, porque casi todos los pares son de personas distintas.
    """
    m = []
    u = []
    for k, L in enumerate(num_niveles):
        geom = [2.0 ** -l for l in range(L)]
        m.append([x / sum(geom) for x in geom])
        frec = [pseudo] * L
        for g, n in conteos.items():
            if g[k] is not None:
                frec[g[k]] += n
        u.append([x / sum(frec) for x in frec])
    return Parametros(pi=0.1, m=m, u=u)


def inicio_aleatorio(num_niveles: Sequence[int], rng: random.Random) -> Parametros:
    """m y u sorteados de una Dirichlet(1) por campo, π uniforme en (0,01; 0,5)."""
    def dirichlet(L: int) -> List[float]:
        x = [rng.gammavariate(1.0, 1.0) for _ in range(L)]
        return [v / sum(x) for v in x]

    return Parametros(
        pi=rng.uniform(0.01, 0.5),
        m=[dirichlet(L) for L in num_niveles],
        u=[dirichlet(L) for L in num_niveles],
    )


def ordenar_etiquetas(params: Parametros) -> Parametros:
    """La mezcla no sabe cuál de sus dos clases es M. Se llama M a la clase en
    la que el mejor nivel (el 0) es más probable, sumando sobre los campos."""
    diferencia = sum(fm[0] - fu[0] for fm, fu in zip(params.m, params.u))
    if diferencia >= 0:
        return params
    return Parametros(
        pi=1.0 - params.pi, m=params.u, u=params.m, objetivo=params.objetivo,
        iteraciones=params.iteraciones, convergio=params.convergio, historia=params.historia,
    )


def ajustar_em(
    conteos: Conteos,
    num_niveles: Sequence[int],
    inicio: Optional[Parametros] = None,
    max_iter: int = 5000,
    tolerancia: float = 1e-10,
    pseudo: float = PSEUDO_CONTEO,
) -> Parametros:
    """Alterna pasos E y M hasta que ningún parámetro cambie más que `tolerancia`."""
    params = inicio or inicio_por_defecto(conteos, num_niveles, pseudo)
    historia = [objetivo(conteos, params, pseudo)]
    convergio = False
    iteracion = 0
    for iteracion in range(1, max_iter + 1):
        nuevo = paso_m(conteos, paso_e(conteos, params), num_niveles, pseudo)
        cambio = max(
            [abs(nuevo.pi - params.pi)]
            + [abs(a - b) for d1, d2 in ((nuevo.m, params.m), (nuevo.u, params.u))
               for f1, f2 in zip(d1, d2) for a, b in zip(f1, f2)]
        )
        params = nuevo
        historia.append(objetivo(conteos, params, pseudo))
        if cambio < tolerancia:
            convergio = True
            break
    params.objetivo = historia[-1]
    params.iteraciones = iteracion
    params.convergio = convergio
    params.historia = historia
    return ordenar_etiquetas(params)


def ajustar_em_varios_inicios(
    conteos: Conteos,
    num_niveles: Sequence[int],
    inicios_aleatorios: int = 10,
    semilla: int = 0,
    **kwargs,
) -> Tuple[Parametros, List[Parametros]]:
    """Corre el EM desde el inicio por defecto y desde `inicios_aleatorios`
    inicios sorteados. Devuelve el de mayor objetivo y todos, para poder ver
    si distintos inicios llegan a la misma solución."""
    rng = random.Random(semilla)
    pseudo = kwargs.get("pseudo", PSEUDO_CONTEO)
    inicios = [inicio_por_defecto(conteos, num_niveles, pseudo)] + [
        inicio_aleatorio(num_niveles, rng) for _ in range(inicios_aleatorios)
    ]
    ajustes = [ajustar_em(conteos, num_niveles, inicio=i, **kwargs) for i in inicios]
    mejor = max(ajustes, key=lambda p: p.objetivo)
    return mejor, ajustes

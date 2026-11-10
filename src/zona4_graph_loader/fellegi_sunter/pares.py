"""Qué registros entran al modelo y qué pares se comparan (sección 3 del
notebook).

Entra cada persona de `FUENTES` con el nombre en formato "Apellido, Nombre".
Se comparan los pares que cumplen las tres condiciones:

1. vienen de fuentes distintas (la misma regla que la resolución de
   identidades: una fuente nunca se compara consigo misma);
2. sus roles son compatibles (nunca víctima con represor);
3. el apellido base no cae en el nivel "distinto": comparten un token, o
   tienen dos tokens que son errata uno del otro.

El apellido base es el que trae el nombre de la persona en el CDM. Para
Parque de la Memoria es sólo el primer apellido ("Abad, Ana Catalina"); el
nivel del apellido, en cambio, se calcula con el apellido completo, que suma
los tokens extra de su `descripcion_nombre` ("Ana Catalina Abad Scarlatta").
Así el filtro deja pasar los mismos pares que antes y el segundo apellido
sirve para distinguir.

Todo par que no cumple la condición 3 queda fuera del modelo y se trata como
"no es la misma persona". Sadinle (2018) hace lo mismo con los pares que caen
en el peor nivel de nombre o de apellido; acá sólo se mira el apellido.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, Iterator, List, Optional, Set, Tuple

from zona4_graph_loader.builders.base import CanonicalDataset
from zona4_graph_loader.domain.identity_resolution import (
    _fechas_de,
    _fechas_de_aristas,
    _roles_incompatibles,
)
from zona4_graph_loader.domain.name_similarity import name_token_set
from zona4_graph_loader.fellegi_sunter.comparaciones import (
    CAMPOS,
    LARGO_MINIMO_ERRATA,
    NIVELES,
    Fecha,
    Tokens,
    nivel_centro,
    nivel_fecha,
    nivel_tokens,
    parsear_fecha,
    separar_nombre,
)

# Fuentes que entran al modelo. Abuelas (`nietxs_relacion`) queda afuera: su
# `nombre` es el identificador del caso ("Apellido1 - Apellido2"), no el
# nombre de una persona.
FUENTES = (
    "detalles_personas",
    "archivo_memoria",
    "minjus_victimas",
    "minjus_imputados",
    "juicios_condenados",
)

Patron = Tuple[Optional[int], ...]


@dataclass(frozen=True)
class Registro:
    clave: str
    fuente: str
    roles: FrozenSet[str]
    apellido: Optional[Tokens]
    nombre: Optional[Tokens]
    fecha_nacimiento: Optional[Fecha]
    fecha_secuestro: Optional[Fecha]
    centro: Optional[FrozenSet[str]]
    # Apellido del filtro de pares. None quiere decir que es igual a `apellido`.
    apellido_base: Optional[Tokens] = None

    @property
    def apellido_filtro(self) -> Optional[Tokens]:
        return self.apellido if self.apellido_base is None else self.apellido_base


def apellido_extra(nombre_largo: Optional[str], apellido: Tokens, nombre: Optional[Tokens]) -> Tokens:
    """Tokens de `nombre_largo` que no están ni en el apellido ni en el nombre
    de pila: los apellidos que el nombre corto no trae."""
    if not nombre_largo:
        return frozenset()
    return frozenset(name_token_set(nombre_largo)) - apellido - (nombre or frozenset())


def nombres_largos_parque(detalles: List[Dict[str, Any]]) -> Dict[str, str]:
    """`persona_key` → `detalle.descripcion_nombre` de cada ficha de Parque de
    la Memoria, para pasarle a `construir_registros`."""
    return {
        f"registro:{item['registro']}": (item.get("detalle") or {}).get("descripcion_nombre")
        for item in detalles
        if item.get("registro") is not None and (item.get("detalle") or {}).get("descripcion_nombre")
    }


def construir_registros(
    dataset: CanonicalDataset, nombres_largos: Optional[Dict[str, str]] = None
) -> List[Registro]:
    """Un `Registro` por persona de `FUENTES`, antes de resolver identidades.

    Las fechas salen de `identity_resolution._fechas_de`: la del nodo y, si
    falta, la de su arista `NACIO_EN`/`SECUESTRADO_EN` (así llegan las de
    Parque de la Memoria). El centro es el conjunto de lugares de sus aristas
    `PRESENTE_EN`.

    `nombres_largos` (clave → nombre completo, ver `nombres_largos_parque`)
    completa el apellido con los apellidos que el nombre del CDM no trae; el
    apellido original queda como `apellido_base`, para el filtro de pares.
    """
    nombres_largos = nombres_largos or {}
    fechas_aristas = _fechas_de_aristas(dataset)
    centros: Dict[str, Set[str]] = defaultdict(set)
    for fila in dataset.get("eventos_espaciales") or []:
        if fila.get("tipo_relacion") == "PRESENTE_EN" and fila.get("lugar_key"):
            centros[fila["persona_key"]].add(fila["lugar_key"])

    registros = []
    for persona in dataset.get("personas") or []:
        if persona.get("fuente") not in FUENTES:
            continue
        apellido, nombre = separar_nombre(persona.get("nombre"))
        if apellido is None:
            continue
        fechas = _fechas_de(persona, fechas_aristas)
        extra = apellido_extra(nombres_largos.get(persona["persona_key"]), apellido, nombre)
        registros.append(Registro(
            clave=persona["persona_key"],
            fuente=persona["fuente"],
            roles=frozenset(persona.get("roles") or []),
            apellido=apellido | extra,
            nombre=nombre,
            fecha_nacimiento=parsear_fecha(fechas.get("fecha_nacimiento")),
            fecha_secuestro=parsear_fecha(fechas.get("fecha_secuestro")),
            centro=frozenset(centros[persona["persona_key"]]) or None,
            apellido_base=apellido if extra else None,
        ))
    return registros


_COMPARADOR = {
    "apellido": nivel_tokens,
    "nombre": nivel_tokens,
    "fecha_nacimiento": nivel_fecha,
    "fecha_secuestro": nivel_fecha,
    "centro": nivel_centro,
}


def patron(a: Registro, b: Registro) -> Patron:
    """Vector de comparación γ(a, b): un nivel (o `FALTA`) por campo de `CAMPOS`."""
    return tuple(_COMPARADOR[campo](getattr(a, campo), getattr(b, campo)) for campo in CAMPOS)


_DISTINTO = NIVELES["apellido"].index("distinto")


def _claves_de_indice(token: str) -> Set[str]:
    """El token y, si es largo, cada variante con una letra borrada.

    Dos tokens a distancia de Levenshtein 1 comparten siempre al menos una de
    estas claves (si uno tiene una letra de más, borrarla da el otro; si
    difieren en una letra, borrarla en los dos da lo mismo).
    """
    claves = {token}
    if len(token) >= LARGO_MINIMO_ERRATA:
        claves.update(token[:i] + token[i + 1:] for i in range(len(token)))
    return claves


def estrato(a: Registro, b: Registro) -> Tuple[str, str]:
    """Par de fuentes, en orden fijo. El modelo se estima por separado en cada uno."""
    return tuple(sorted((a.fuente, b.fuente)))  # type: ignore[return-value]


def generar_pares(registros: List[Registro]) -> Iterator[Tuple[Registro, Registro, Patron]]:
    """Cada par que cumple las tres condiciones del módulo, una sola vez, con su patrón.

    Usa un índice por token de apellido para no recorrer todos los pares: sólo
    se miran los que comparten alguna clave de `_claves_de_indice`, y después
    se confirma con el nivel real.
    """
    indice: Dict[str, List[int]] = defaultdict(list)
    for i, registro in enumerate(registros):
        claves: Set[str] = set()
        for token in registro.apellido_filtro or ():
            claves |= _claves_de_indice(token)
        for clave in claves:
            indice[clave].append(i)

    for i, a in enumerate(registros):
        vecinos: Set[int] = set()
        for token in a.apellido_filtro or ():
            for clave in _claves_de_indice(token):
                vecinos.update(j for j in indice[clave] if j > i)
        for j in sorted(vecinos):
            b = registros[j]
            if a.fuente == b.fuente or _roles_incompatibles(
                {"roles": a.roles}, {"roles": b.roles}
            ):
                continue
            if pasa_filtro(a, b):
                yield a, b, patron(a, b)


def pasa_filtro(a: Registro, b: Registro) -> bool:
    """Condición 3: el nivel del apellido base no es "distinto"."""
    return nivel_tokens(a.apellido_filtro, b.apellido_filtro) != _DISTINTO

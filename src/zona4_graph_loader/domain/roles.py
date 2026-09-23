from __future__ import annotations

from typing import Any, Dict, List

VALID_ROLES = {"VICTIMA", "REPRESOR", "COMPLICE", "NIETX"}
VALID_COMPLICE_TIPOS = {"CIVIL", "CLERICAL", "EMPRESARIAL"}

# El CDM transporta los roles en mayúsculas (contrato documentado, spec §4.1 y
# NEO4J_DATA_MODEL.md regla 1.4) y VALID_ROLES no se toca por eso. Pero Neo4j
# labels son case-sensitive y NEO4J_DATA_MODEL.md declara (y qa.py consulta, y
# el constraint complice_tipo_exist apunta a) las labels en título:
# :Victima, :Represor, :Complice, :Nietx. Este mapeo traduce el vocabulario del
# CDM al vocabulario de labels justo en el límite del escritor, sin tocar el
# campo `roles` que el resto del pipeline sigue leyendo en mayúsculas (p.ej.
# para partir personas_detalles vs. protagonistas por "NIETX" in roles).
ROLE_LABELS: Dict[str, str] = {
    "VICTIMA": "Victima",
    "REPRESOR": "Represor",
    "COMPLICE": "Complice",
    "NIETX": "Nietx",
}


def graph_labels(roles: List[str]) -> List[str]:
    """Traduce roles del CDM (mayúsculas) a labels de Neo4j (título) para
    `apoc.create.addLabels`. No valida pertenencia a VALID_ROLES: se asume que
    `roles` ya pasó por `normalize_roles`.
    """
    return [ROLE_LABELS[rol] for rol in roles]


def normalize_roles(persona: Dict[str, Any]) -> List[str]:
    """Resuelve los roles de una fila `personas` del CDM.

    Retrocompatibilidad: una fila sin `roles` cae en `es_nietx` y, si tampoco
    está, en `["VICTIMA"]`, que es el comportamiento histórico del loader.
    """
    key = persona.get("persona_key", "(sin persona_key)")
    roles = persona.get("roles")

    if roles is None:
        return ["NIETX"] if persona.get("es_nietx") else ["VICTIMA"]

    if not isinstance(roles, list):
        raise ValueError(f"'roles' debe ser una lista en {key}, recibido: {type(roles).__name__}")
    if not roles:
        raise ValueError(f"'roles' no puede ser una lista vacía en {key}")

    desconocidos = sorted({r for r in roles if r not in VALID_ROLES})
    if desconocidos:
        raise ValueError(
            f"Rol(es) desconocido(s) {', '.join(desconocidos)} en {key}. "
            f"Válidos: {', '.join(sorted(VALID_ROLES))}"
        )

    if "COMPLICE" in roles and persona.get("complice_tipo") not in VALID_COMPLICE_TIPOS:
        raise ValueError(
            f"Rol COMPLICE requiere 'complice_tipo' en {key}. "
            f"Válidos: {', '.join(sorted(VALID_COMPLICE_TIPOS))}"
        )

    return sorted(set(roles))

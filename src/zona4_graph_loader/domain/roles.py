from __future__ import annotations

from typing import Any, Dict, List

VALID_ROLES = {"VICTIMA", "REPRESOR", "COMPLICE", "NIETX"}
VALID_COMPLICE_TIPOS = {"CIVIL", "CLERICAL", "EMPRESARIAL"}


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

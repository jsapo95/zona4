"""Regresión: Fix E (hallazgo M1 de la auditoría semántica 2026-08-29).

`CYPHER_UPSERT_REL_PERSONA` aplicaba `coalesce(row.fecha_sentencia,
"DESCONOCIDA")` a TODAS las relaciones interpersonales, no sólo a
TORTURO_A/IMPUTADO_POR (las únicas que la fuente MinJus puebla con una
fecha de sentencia real). Resultado: 2.710 aristas de parentesco del Parque
de la Memoria (PAREJA_DE, HERMANX_DE, HIJE_DE, etc.) -que no tienen nada
que ver con una sentencia judicial- quedaban con `fecha_sentencia:
"DESCONOCIDA"`, implicando que existe una sentencia cuya fecha se
desconoce.

No hay una base Neo4j en el suite de tests (son todos unitarios sobre
Python), así que esta prueba verifica el string de la plantilla Cypher en
sí: no debe volver a aparecer un `coalesce(row.fecha_sentencia, ...)` en la
consulta que persiste relaciones interpersonales genéricas.
"""
from __future__ import annotations

import re

from zona4_graph_loader.db.cypher import CYPHER_UPSERT_REL_PERSONA


def test_cypher_upsert_rel_persona_no_coalesce_fecha_sentencia():
    assert "fecha_sentencia" in CYPHER_UPSERT_REL_PERSONA
    assert not re.search(r"coalesce\(row\.fecha_sentencia", CYPHER_UPSERT_REL_PERSONA)
    # row.fecha_sentencia se pasa tal cual: null para las filas que no lo
    # traen (todo excepto TORTURO_A/IMPUTADO_POR de MinJus, que ya escriben
    # el string "DESCONOCIDA" en Python cuando corresponde), y Neo4j no
    # escribe una propiedad cuyo valor es null.
    assert "fecha_sentencia: row.fecha_sentencia" in CYPHER_UPSERT_REL_PERSONA

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

from zona4_graph_loader.db.cypher import CYPHER_APPLY_SAFE_PLACE_MERGES, CYPHER_UPSERT_REL_PERSONA


def test_fusion_de_lugares_traslada_aristas_de_cualquier_tipo():
    # Regresión 2026-10-28: la lista fija de tipos dejaba afuera NACIO_EN,
    # PARIO_EN, MURIO_EN, LIBERADO_EN y UBICADA_EN, que el DETACH DELETE
    # borraba. El comportamiento real se prueba contra Neo4j en
    # test_place_merge_neo4j.py; esto cubre el suite sin base.
    q = CYPHER_APPLY_SAFE_PLACE_MERGES
    assert "MATCH (o)-[r]->(src)" in q
    assert "MATCH (src)-[r]->(o)" in q
    assert "type(r)" in q
    for tipo in ("NACIO_EN", "SECUESTRADO_EN", "ASESINADO_EN", "PRESENTE_EN", "PARIO_EN"):
        assert tipo not in q, f"{tipo} no debería estar listado: el traslado es genérico"


def test_fusion_de_lugares_copia_todas_las_propiedades():
    # Antes se copiaban sólo rp.fecha y rp.origen (se perdían fecha_fin y
    # precision_fecha).
    assert "properties(r)" in CYPHER_APPLY_SAFE_PLACE_MERGES
    assert "rp.fecha" not in CYPHER_APPLY_SAFE_PLACE_MERGES


def test_fusion_de_lugares_traslada_antes_de_borrar():
    q = CYPHER_APPLY_SAFE_PLACE_MERGES
    assert q.rindex("apoc.create.relationship") < q.index("DETACH DELETE src")


def test_fusion_de_lugares_compara_propiedades_exactas():
    # MERGE y apoc.merge.relationship matchean por subconjunto de
    # propiedades: colapsarían un hecho {fecha, origen} con otro distinto
    # {fecha, origen, fecha_fin} que ya estuviera en el destino.
    q = CYPHER_APPLY_SAFE_PLACE_MERGES
    assert "properties(x) = properties(r)" in q
    assert "apoc.merge.relationship" not in q
    assert "MERGE" not in q


def test_cypher_upsert_rel_persona_no_coalesce_fecha_sentencia():
    assert "fecha_sentencia" in CYPHER_UPSERT_REL_PERSONA
    assert not re.search(r"coalesce\(row\.fecha_sentencia", CYPHER_UPSERT_REL_PERSONA)
    # row.fecha_sentencia se pasa tal cual: null para las filas que no lo
    # traen (todo excepto TORTURO_A/IMPUTADO_POR de MinJus, que ya escriben
    # el string "DESCONOCIDA" en Python cuando corresponde), y Neo4j no
    # escribe una propiedad cuyo valor es null.
    assert "fecha_sentencia: row.fecha_sentencia" in CYPHER_UPSERT_REL_PERSONA

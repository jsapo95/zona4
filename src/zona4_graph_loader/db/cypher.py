from __future__ import annotations

CONSTRAINTS = [
    # Technical unique constraints for merges
    "CREATE CONSTRAINT persona_key_unique IF NOT EXISTS FOR (p:Persona) REQUIRE p.persona_key IS UNIQUE",
    "CREATE CONSTRAINT lugar_key_unique IF NOT EXISTS FOR (l:Lugar) REQUIRE l.lugar_key IS UNIQUE",
    "CREATE CONSTRAINT alias_lugar_key_unique IF NOT EXISTS FOR (a:AliasLugar) REQUIRE a.alias_key IS UNIQUE",
    "CREATE CONSTRAINT direccion_ccd_key_unique IF NOT EXISTS FOR (d:DirecciónCCD) REQUIRE d.direccion_ccd_key IS UNIQUE",
    
    # Existence constraints from NEO4J_DATA_MODEL.md
    "CREATE CONSTRAINT persona_nombre_exist IF NOT EXISTS FOR (p:Persona) REQUIRE p.nombre IS NOT NULL",
    "CREATE CONSTRAINT persona_genero_exist IF NOT EXISTS FOR (p:Persona) REQUIRE p.genero IS NOT NULL",
    "CREATE CONSTRAINT persona_fuente_exist IF NOT EXISTS FOR (p:Persona) REQUIRE p.fuente IS NOT NULL",
    
    "CREATE CONSTRAINT nietx_caso_exist IF NOT EXISTS FOR (n:Nietx) REQUIRE n.caso IS NOT NULL",
    "CREATE CONSTRAINT nietx_adn_exist IF NOT EXISTS FOR (n:Nietx) REQUIRE n.ADN IS NOT NULL",
    
    "CREATE CONSTRAINT complice_tipo_exist IF NOT EXISTS FOR (c:Complice) REQUIRE c.tipo IS NOT NULL",

    # Performance Indexes
    "CREATE INDEX persona_nombre_idx IF NOT EXISTS FOR (p:Persona) ON (p.nombre)",
    "CREATE INDEX lugar_nombre_tipo_idx IF NOT EXISTS FOR (l:Lugar) ON (l.nombre, l.tipoGeopolitico)",
    "CREATE INDEX lugar_tipo_ccd_idx IF NOT EXISTS FOR (l:Lugar) ON (l.tipoGeopolitico, l.id_ccd)",
    "CREATE INDEX lugar_geo_idx IF NOT EXISTS FOR (l:Lugar) ON (l.geo_point)",
    "CREATE INDEX alias_lugar_norm_idx IF NOT EXISTS FOR (a:AliasLugar) ON (a.alias_norm)",
]

# UPSERT Base Person (labeled: Persona:Victima)
CYPHER_UPSERT_PERSONAS = """
UNWIND $rows AS row
MERGE (p:Persona {persona_key: row.persona_key})
SET p.nombre = row.nombre,
    p.genero = row.genero,
    p.fuente = row.fuente,
    p.registro = coalesce(row.registro, p.registro)
SET p:Victima
"""

# UPSERT Grandkid Person (labeled: Persona:Nietx)
CYPHER_UPSERT_PROTAGONISTAS = """
UNWIND $rows AS row
MERGE (p:Persona {persona_key: row.persona_key})
SET p.nombre = row.nombre,
    p.genero = row.genero,
    p.fuente = row.fuente,
    p.caso = row.caso,
    p.ADN = row.ADN
SET p:Nietx
"""

# Dynamic Family relationship (uses apoc.create.relationship for specific V1.1 labels)
CYPHER_UPSERT_REL_FAMILIAR = """
UNWIND $rows AS row
MATCH (s:Persona {persona_key: row.source_key})
MERGE (t:Persona {persona_key: row.target_key})
SET t.nombre = coalesce(row.target_nombre, t.nombre),
    t.genero = coalesce(row.target_genero, t.genero, "INDETERMINADO"),
    t.fuente = coalesce(row.target_fuente, t.fuente, row.fuente)
WITH s, t, row
CALL apoc.create.relationship(s, row.tipo, {fecha: coalesce(row.fecha, "DESCONOCIDA"), origen: row.fuente}, t) YIELD rel
RETURN count(*)
"""

# Dynamic Person relationship (uses apoc.create.relationship for specific V1.1 labels)
CYPHER_UPSERT_REL_PERSONA = """
UNWIND $rows AS row
MATCH (s:Persona {persona_key: row.source_key})
MERGE (t:Persona {persona_key: row.target_key})
SET t.nombre = coalesce(row.target_nombre, t.nombre),
    t.genero = coalesce(row.target_genero, t.genero, "INDETERMINADO"),
    t.fuente = coalesce(row.target_fuente, t.fuente, row.fuente)
WITH s, t, row
CALL apoc.create.relationship(s, row.tipo, {fecha: coalesce(row.fecha, "DESCONOCIDA"), origen: row.fuente}, t) YIELD rel
RETURN count(*)
"""

# Dynamic spatiotemporal relationship Persona -> Lugar (uses apoc.create.relationship for dynamic event mapping)
CYPHER_LINK_PERSONA_LUGAR_DYNAMIC = """
UNWIND $rows AS row
MATCH (p:Persona {persona_key: row.persona_key})
MATCH (l:Lugar {lugar_key: row.lugar_key})
WITH p, l, row
CALL apoc.create.relationship(p, row.tipo_relacion, {fecha: coalesce(row.fecha, "DESCONOCIDA"), origen: row.origen}, l) YIELD rel
RETURN count(*)
"""

# UPSERT Place (Labeled: Lugar)
CYPHER_UPSERT_LUGARES = """
UNWIND $rows AS row
MERGE (l:Lugar {lugar_key: row.lugar_key})
SET l.nombre = row.nombre,
    l.tipoGeopolitico = row.tipoGeopolitico,
    l.pais_code = row.pais_code,
    l.fuente = row.fuente,
    l.lat = coalesce(row.lat, l.lat),
    l.lon = coalesce(row.lon, l.lon),
    l.id_ccd = coalesce(row.id_ccd, l.id_ccd),
    l.zona = coalesce(row.zona, l.zona),
    l.subzona = coalesce(row.subzona, l.subzona),
    l.area = coalesce(row.area, l.area),
    l.jurisdiccion = coalesce(row.jurisdiccion, l.jurisdiccion),
    l.ubicacion = coalesce(row.ubicacion, l.ubicacion),
    l.emplazamiento_propiedad = coalesce(row.emplazamiento_propiedad, l.emplazamiento_propiedad),
    l.geo_point = CASE
        WHEN coalesce(row.lat, l.lat) IS NOT NULL AND coalesce(row.lon, l.lon) IS NOT NULL
             THEN point({latitude: coalesce(row.lat, l.lat), longitude: coalesce(row.lon, l.lon)})
        ELSE l.geo_point
    END
"""

# Link Lugar -> Lugar (hierarchical relationship)
CYPHER_LINK_LUGAR_PARENT = """
UNWIND $rows AS row
MATCH (child:Lugar {lugar_key: row.child_key})
MATCH (parent:Lugar {lugar_key: row.parent_key})
MERGE (child)-[r:PARTE_DE]->(parent)
SET r.fecha = "ETERNA",
    r.origen = "normalizacion_lugar"
"""

# UPSERT AliasLugar
CYPHER_UPSERT_ALIAS_LUGAR = """
UNWIND $rows AS row
MERGE (a:AliasLugar {alias_norm: row.alias_norm, tipo: row.tipo, parent_key: row.parent_key})
ON CREATE SET a.alias_key = row.alias_key,
              a.nombreAlternativo = row.alias_raw,
              a.fuente = row.fuente,
              a.campo_fuente = row.campo_fuente
SET a.nombreAlternativo = row.alias_raw,
    a.fuente = row.fuente,
    a.campo_fuente = row.campo_fuente,
    a.tipo = row.tipo,
    a.parent_key = row.parent_key
WITH a, row
MATCH (l:Lugar {lugar_key: row.lugar_key})
OPTIONAL MATCH (a)-[old:ALIAS_DE]->(prev:Lugar)
WHERE prev <> l
DELETE old
MERGE (a)-[r:ALIAS_DE]->(l)
SET r.fecha = "ETERNA",
    r.origen = row.fuente
"""

# UPSERT DirecciónCCD (representing precise CCD coordinates/addresses)
CYPHER_UPSERT_DIRECCION_CCD = """
UNWIND $rows AS row
MERGE (d:DirecciónCCD {direccion_ccd_key: row.direccion_ccd_key})
SET d.coordenadas = row.coordenadas,
    d.direccionExacta = row.direccionExacta
"""

# Link DirecciónCCD -> Lugar
CYPHER_LINK_DIRECCION_CCD_LUGAR = """
UNWIND $rows AS row
MATCH (d:DirecciónCCD {direccion_ccd_key: row.direccion_ccd_key})
MATCH (l:Lugar {lugar_key: row.lugar_key})
MERGE (d)-[r:UBICADA_EN]->(l)
SET r.fecha = "ETERNA",
    r.origen = "normalizacion_lugar"
"""

# Reconciled Candidate links
CYPHER_UPSERT_CANDIDATO_MERGE = """
UNWIND $rows AS row
MATCH (p:Persona {persona_key: row.placeholder_key})
MATCH (c:Persona {persona_key: row.candidate_key})
MERGE (p)-[r:CANDIDATO_MERGE {metodo: row.metodo}]->(c)
SET r.score = row.score,
    r.slug = row.slug,
    r.confianza = row.confianza,
    r.fuente = row.fuente,
    r.fecha = "PROBABILÍSTICA",
    r.origen = "name_similarity"
"""

# Clean V1.1 project nodes and relationships
CYPHER_CLEAN_PROJECT = """
MATCH (n)
WHERE n:Persona OR n:Profesión OR n:Cargo OR n:Org OR n:Institución OR n:DirecciónCCD OR n:Lugar OR n:AliasLugar OR n:AliasPersona
DETACH DELETE n
"""

CYPHER_CLEAN_ALL = """
MATCH (n)
DETACH DELETE n
"""

# Safe merges for Place types (updated for V1.1 variables)
CYPHER_APPLY_SAFE_PLACE_MERGES = """
UNWIND $rows AS row
MATCH (src:Lugar {lugar_key: row.source_key})
MATCH (dst:Lugar {lugar_key: row.target_key})
WHERE src <> dst
WITH src, dst, row
OPTIONAL MATCH (a:AliasLugar)-[ad:ALIAS_DE]->(src)
FOREACH (_ IN CASE WHEN ad IS NULL THEN [] ELSE [1] END |
    MERGE (a)-[r:ALIAS_DE]->(dst)
    SET r.fecha = ad.fecha, r.origen = ad.origen
    DELETE ad
)
WITH src, dst, row
OPTIONAL MATCH (p:Persona)-[rp:SECUESTRADO_EN]->(src)
FOREACH (_ IN CASE WHEN rp IS NULL THEN [] ELSE [1] END |
    MERGE (p)-[rp2:SECUESTRADO_EN {fecha: rp.fecha, origen: rp.origen}]->(dst)
    DELETE rp
)
WITH src, dst, row
OPTIONAL MATCH (p:Persona)-[rp:ASESINADO_EN]->(src)
FOREACH (_ IN CASE WHEN rp IS NULL THEN [] ELSE [1] END |
    MERGE (p)-[rp2:ASESINADO_EN {fecha: rp.fecha, origen: rp.origen}]->(dst)
    DELETE rp
)
WITH src, dst, row
OPTIONAL MATCH (p:Persona)-[rp:PRESENTE_EN]->(src)
FOREACH (_ IN CASE WHEN rp IS NULL THEN [] ELSE [1] END |
    MERGE (p)-[rp2:PRESENTE_EN {fecha: rp.fecha, origen: rp.origen}]->(dst)
    DELETE rp
)
WITH src, dst, row
OPTIONAL MATCH (src)-[r1:PARTE_DE]->(parent:Lugar)
FOREACH (_ IN CASE WHEN r1 IS NULL THEN [] ELSE [1] END |
    MERGE (dst)-[r1_new:PARTE_DE]->(parent)
    SET r1_new.fecha = r1.fecha, r1_new.origen = r1.origen
    DELETE r1
)
WITH src, dst, row
OPTIONAL MATCH (child:Lugar)-[r2:PARTE_DE]->(src)
FOREACH (_ IN CASE WHEN r2 IS NULL THEN [] ELSE [1] END |
    MERGE (child)-[r2_new:PARTE_DE]->(dst)
    SET r2_new.fecha = r2.fecha, r2_new.origen = r2.origen
    DELETE r2
)
WITH src, row
SET src.merged_into = row.target_key,
    src.merge_reason = row.reason,
    src.merge_score = row.score
DETACH DELETE src
"""

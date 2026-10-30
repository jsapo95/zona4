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
    # Fix D (V1.3): `estado` es el campo que distingue un nietx restituido de
    # uno que sigue en búsqueda; la fuente lo trae en el 100% de los 392
    # registros.
    "CREATE CONSTRAINT nietx_estado_exist IF NOT EXISTS FOR (n:Nietx) REQUIRE n.estado IS NOT NULL",
    
    "CREATE CONSTRAINT complice_tipo_exist IF NOT EXISTS FOR (c:Complice) REQUIRE c.tipo IS NOT NULL",

    # Performance Indexes
    "CREATE INDEX persona_nombre_idx IF NOT EXISTS FOR (p:Persona) ON (p.nombre)",
    "CREATE INDEX lugar_nombre_tipo_idx IF NOT EXISTS FOR (l:Lugar) ON (l.nombre, l.tipoGeopolitico)",
    "CREATE INDEX lugar_tipo_ccd_idx IF NOT EXISTS FOR (l:Lugar) ON (l.tipoGeopolitico, l.id_ccd)",
    "CREATE INDEX lugar_geo_idx IF NOT EXISTS FOR (l:Lugar) ON (l.geo_point)",
    "CREATE INDEX alias_lugar_norm_idx IF NOT EXISTS FOR (a:AliasLugar) ON (a.alias_norm)",

    "CREATE CONSTRAINT entidad_contexto_key_unique IF NOT EXISTS FOR (e:EntidadContexto) REQUIRE e.entidad_key IS UNIQUE",
]

# UPSERT Base Person (labels dinámicas según row.roles)
# `estudiante_universitario` (Fix E, V1.3, hallazgo I4): sólo la puebla
# `archivo_memoria` (True cuando la fuente lo trae; nunca False). Se lee con
# coalesce igual que `fecha_nacimiento`/`fecha_secuestro` para no perder el
# valor si la persona ya existía por otra fuente sin este dato.
CYPHER_UPSERT_PERSONAS = """
UNWIND $rows AS row
MERGE (p:Persona {persona_key: row.persona_key})
SET p.nombre = row.nombre,
    p.genero = row.genero,
    p.fuente = row.fuente,
    p.registro = coalesce(row.registro, p.registro),
    p.fecha_nacimiento = coalesce(row.fecha_nacimiento, p.fecha_nacimiento),
    p.fecha_secuestro = coalesce(row.fecha_secuestro, p.fecha_secuestro),
    p.edad = coalesce(row.edad, p.edad),
    p.claves_alt = coalesce(row.claves_alt, p.claves_alt),
    p.tipo = coalesce(row.complice_tipo, p.tipo),
    p.estudiante_universitario = coalesce(row.estudiante_universitario, p.estudiante_universitario),
    p.fuerza = coalesce(row.fuerza, p.fuerza)
WITH p, row
CALL apoc.create.addLabels(p, row.role_labels) YIELD node
RETURN count(*)
"""

# UPSERT Grandkid Person (labeled: Persona:Nietx)
# Fix D (V1.3): `estado` se persiste junto a `ADN` -es el campo que distingue
# un nietx restituido de uno que sigue en búsqueda; sin él, "ADN":
# "DESCONOCIDA" no se puede diferenciar de "aún no identificadx" vs
# "identificadx pero sin fecha de ADN registrada en la fuente".
CYPHER_UPSERT_PROTAGONISTAS = """
UNWIND $rows AS row
MERGE (p:Persona {persona_key: row.persona_key})
SET p.nombre = row.nombre,
    p.genero = row.genero,
    p.fuente = row.fuente,
    p.caso = row.caso,
    p.ADN = row.ADN,
    p.estado = row.estado
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
CALL apoc.merge.relationship(
    s,
    row.tipo,
    {origen: row.fuente},
    {fecha: coalesce(row.fecha, "DESCONOCIDA")},
    t,
    {fecha: coalesce(row.fecha, "DESCONOCIDA")}
) YIELD rel
RETURN count(*)
"""

# Dynamic Person relationship (uses apoc.merge.relationship for specific V1.1 labels, idempotent per origen)
# `fecha_sentencia` sólo la pueblan las filas TORTURO_A/IMPUTADO_POR de los
# builders de MinJus, que ya escriben el string "DESCONOCIDA" en Python
# cuando la sentencia no trae fecha (ver minjus_imputados.py / minjus_victimas.py)
# -nunca dependen de un coalesce acá. Fix E (auditoría 2026-08-29, hallazgo M1):
# antes este coalesce completaba `fecha_sentencia` con "DESCONOCIDA" para
# CUALQUIER tipo de relación, incluidos los 2.710 vínculos de parentesco del
# Parque de la Memoria (PAREJA_DE, HERMANX_DE, HIJE_DE, etc.), que no tienen
# nada que ver con una sentencia judicial y para los que `row.fecha_sentencia`
# es null. Ya no se coalesce: cuando la fila no trae valor, Neo4j no escribe
# la propiedad (mismo comportamiento que `delitos`, que nunca tuvo este
# coalesce y nunca tuvo este problema).
CYPHER_UPSERT_REL_PERSONA = """
UNWIND $rows AS row
MATCH (s:Persona {persona_key: row.source_key})
MERGE (t:Persona {persona_key: row.target_key})
SET t.nombre = coalesce(row.target_nombre, t.nombre),
    t.genero = coalesce(row.target_genero, t.genero, "INDETERMINADO"),
    t.fuente = coalesce(row.target_fuente, t.fuente, row.fuente)
WITH s, t, row
CALL apoc.merge.relationship(
    s,
    row.tipo,
    {origen: row.fuente},
    {fecha: coalesce(row.fecha, "DESCONOCIDA"), fecha_sentencia: row.fecha_sentencia, delitos: row.delitos},
    t,
    {fecha: coalesce(row.fecha, "DESCONOCIDA"), fecha_sentencia: row.fecha_sentencia, delitos: row.delitos}
) YIELD rel
RETURN count(*)
"""

# Dynamic spatiotemporal relationship Persona -> Lugar (uses apoc.merge.relationship, idempotent per origen)
# `fecha_fin` / `precision_fecha` (Fix E, V1.3, hallazgo I2): sólo las
# puebla `builders/ccds.py` (fuente `ccds_json`), cuando la fecha original
# no tiene precisión de día. Para el resto de las filas `row.fecha_fin` y
# `row.precision_fecha` son null y Neo4j no escribe esas propiedades (mismo
# patrón que `delitos` en `CYPHER_UPSERT_REL_PERSONA`).
CYPHER_LINK_PERSONA_LUGAR_DYNAMIC = """
UNWIND $rows AS row
MATCH (p:Persona {persona_key: row.persona_key})
MATCH (l:Lugar {lugar_key: row.lugar_key})
WITH p, l, row
CALL apoc.merge.relationship(
    p,
    row.tipo_relacion,
    {origen: row.origen},
    {fecha: coalesce(row.fecha, "DESCONOCIDA"), fecha_fin: row.fecha_fin, precision_fecha: row.precision_fecha},
    l,
    {fecha: coalesce(row.fecha, "DESCONOCIDA"), fecha_fin: row.fecha_fin, precision_fecha: row.precision_fecha}
) YIELD rel
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
# `tipo_direccion` (Fix E, V1.3, hallazgo I5): la label `:DirecciónCCD` se
# usa para tres cosas distintas -un centro clandestino real ("CCD"), un
# domicilio o lugar de un hecho narrado por la fuente ("HECHO_NARRATIVO",
# 188 de 393 nodos: domicilios de víctimas, vía pública, lugares de
# trabajo), o un cementerio/enterramiento de EAAF ("CEMENTERIO"/
# "ENTERRAMIENTO"/"SITIO_HALLAZGO", 82 de 393). No se renombra la label
# -cambiarla afecta la constraint única y toda consulta existente sobre
# `:DirecciónCCD`, un cambio estructural mayor fuera de alcance de un fix
# aditivo- pero ahora cada nodo declara honestamente cuál de los tres es.
CYPHER_UPSERT_DIRECCION_CCD = """
UNWIND $rows AS row
MERGE (d:DirecciónCCD {direccion_ccd_key: row.direccion_ccd_key})
SET d.coordenadas = row.coordenadas,
    d.direccionExacta = row.direccionExacta,
    d.tipo_direccion = row.tipo_direccion
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
# `score_nombre` (Fix E, V1.3, hallazgo I7): antes `score`. Es similitud de
# cadena tras normalización de erratas, no una confianza de identidad -el
# nombre viejo invitaba a leerlo como tal (un par víctima-represor con
# `score` 1.0 y `confianza` "baja" a la vez).
CYPHER_UPSERT_CANDIDATO_MERGE = """
UNWIND $rows AS row
MATCH (p:Persona {persona_key: row.placeholder_key})
MATCH (c:Persona {persona_key: row.candidate_key})
MERGE (p)-[r:CANDIDATO_MERGE {metodo: row.metodo}]->(c)
SET r.score_nombre = row.score_nombre,
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
# Traslada TODAS las aristas de `src` a `dst`, de cualquier tipo y en ambos
# sentidos, antes del DETACH DELETE. Antes se trasladaba una lista fija
# (ALIAS_DE, SECUESTRADO_EN, ASESINADO_EN, PRESENTE_EN, PARTE_DE) y el DETACH
# DELETE borraba en silencio el resto: NACIO_EN (verificado en el grafo el
# 2026-10-28: 2.159 sin fusionar contra 2.158 fusionando), PARIO_EN,
# MURIO_EN, LIBERADO_EN y UBICADA_EN. Además, los hechos trasladados
# conservaban sólo `fecha` y `origen` y perdían `fecha_fin`/`precision_fecha`.
#
# Identidad de la arista trasladada:
# - Estructurales (PARTE_DE, ALIAS_DE, UBICADA_EN): una por par de nodos; si
#   `dst` ya la tiene, se le copian las propiedades de la de `src` (mismo
#   comportamiento que la lista fija anterior).
# - Todo lo demás (hechos persona->lugar): tipo + TODAS sus propiedades. Sólo
#   se colapsa con un duplicado exacto en `dst`; dos hechos que difieren en
#   `fecha`, `origen` o `fecha_fin` se conservan los dos. La igualdad es
#   `properties(x) = properties(r)` y no un MERGE/apoc.merge.relationship,
#   que matchean por subconjunto: `{fecha, origen}` se colapsaría con un
#   `{fecha, origen, fecha_fin}` distinto que ya estuviera en `dst`.
# Cada arista se traslada en su propio CALL para que la siguiente vea lo que
# creó la anterior. Las aristas entre `src` y `dst` (o un lazo de `src` sobre
# sí mismo) no se trasladan: quedarían como lazo de `dst` sobre sí mismo.
CYPHER_APPLY_SAFE_PLACE_MERGES = """
UNWIND $rows AS row
MATCH (src:Lugar {lugar_key: row.source_key})
MATCH (dst:Lugar {lugar_key: row.target_key})
WHERE src <> dst
CALL (src, dst) {
    MATCH (o)-[r]->(src)
    WHERE o <> src AND o <> dst
    CALL (o, r, dst) {
        WITH o, r, dst, type(r) IN ["PARTE_DE", "ALIAS_DE", "UBICADA_EN"] AS estructural
        OPTIONAL MATCH (o)-[x]->(dst)
        WHERE type(x) = type(r) AND (estructural OR properties(x) = properties(r))
        WITH o, r, dst, estructural, collect(x) AS existentes
        FOREACH (x IN CASE WHEN estructural THEN existentes ELSE [] END | SET x += properties(r))
        WITH o, r, dst, existentes
        WHERE existentes = []
        CALL apoc.create.relationship(o, type(r), properties(r), dst) YIELD rel
        RETURN count(rel) AS creadas
    }
    DELETE r
}
CALL (src, dst) {
    MATCH (src)-[r]->(o)
    WHERE o <> src AND o <> dst
    CALL (o, r, dst) {
        WITH o, r, dst, type(r) IN ["PARTE_DE", "ALIAS_DE", "UBICADA_EN"] AS estructural
        OPTIONAL MATCH (dst)-[x]->(o)
        WHERE type(x) = type(r) AND (estructural OR properties(x) = properties(r))
        WITH o, r, dst, estructural, collect(x) AS existentes
        FOREACH (x IN CASE WHEN estructural THEN existentes ELSE [] END | SET x += properties(r))
        WITH o, r, dst, existentes
        WHERE existentes = []
        CALL apoc.create.relationship(dst, type(r), properties(r), o) YIELD rel
        RETURN count(rel) AS creadas
    }
    DELETE r
}
WITH src, row
SET src.merged_into = row.target_key,
    src.merge_reason = row.reason,
    src.merge_score = row.score
DETACH DELETE src
"""

# --- Entidades de contexto (V1.2) ---
# Todas llevan la label técnica :EntidadContexto, que sostiene el índice único
# de entidad_key compartido entre los cinco tipos.

CYPHER_UPSERT_ORG = """
UNWIND $rows AS row
MERGE (e:EntidadContexto {entidad_key: row.entidad_key})
SET e:Org,
    e.nombre = row.nombre,
    e.tipoOrg = coalesce(row.tipoOrg, e.tipoOrg),
    e.fuente = row.fuente
"""

CYPHER_UPSERT_INSTITUCION = """
UNWIND $rows AS row
MERGE (e:EntidadContexto {entidad_key: row.entidad_key})
SET e:Institución,
    e.nombre = row.nombre,
    e.fuente = row.fuente
"""

CYPHER_UPSERT_PROFESION = """
UNWIND $rows AS row
MERGE (e:EntidadContexto {entidad_key: row.entidad_key})
SET e:Profesión,
    e.descripcion = row.descripcion,
    e.fuente = row.fuente
"""

CYPHER_UPSERT_CARGO = """
UNWIND $rows AS row
MERGE (e:EntidadContexto {entidad_key: row.entidad_key})
SET e:Cargo,
    e.titulo = row.titulo,
    e.fuente = row.fuente
"""

CYPHER_UPSERT_ALIAS_PERSONA = """
UNWIND $rows AS row
MERGE (e:EntidadContexto {entidad_key: row.entidad_key})
SET e:AliasPersona,
    e.alias = row.alias,
    e.fuente = row.fuente
"""

# Persona -> entidad de contexto (PARTE_DE, FUNDO, EJERCIO, ESTUDIO_EN, TRABAJO_EN)
CYPHER_LINK_PERSONA_ENTIDAD = """
UNWIND $rows AS row
MATCH (p:Persona {persona_key: row.persona_key})
MATCH (e:EntidadContexto {entidad_key: row.entidad_key})
WITH p, e, row
CALL apoc.merge.relationship(
    p,
    row.tipo_relacion,
    {origen: row.origen},
    {fecha: coalesce(row.fecha, "DESCONOCIDA")},
    e,
    {fecha: coalesce(row.fecha, "DESCONOCIDA")}
) YIELD rel
RETURN count(*)
"""

# AliasPersona -> Persona. Va invertida respecto de las demás: la arista
# IDENTIFICA_A nace en el alias y apunta a la persona real.
CYPHER_LINK_ALIAS_PERSONA = """
UNWIND $rows AS row
MATCH (e:EntidadContexto:AliasPersona {entidad_key: row.entidad_key})
MATCH (p:Persona {persona_key: row.persona_key})
WITH p, e, row
CALL apoc.merge.relationship(
    e,
    "IDENTIFICA_A",
    {origen: row.origen},
    {fecha: coalesce(row.fecha, "DESCONOCIDA")},
    p,
    {fecha: coalesce(row.fecha, "DESCONOCIDA")}
) YIELD rel
RETURN count(*)
"""

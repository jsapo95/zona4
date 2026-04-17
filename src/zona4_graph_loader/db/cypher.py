from __future__ import annotations

CONSTRAINTS = [
    "CREATE CONSTRAINT persona_key_unique IF NOT EXISTS FOR (p:Persona) REQUIRE p.persona_key IS UNIQUE",
    "CREATE CONSTRAINT caso_nietx_id_unique IF NOT EXISTS FOR (c:CasoNietx) REQUIRE c.id_nietx IS UNIQUE",
    "CREATE CONSTRAINT evento_key_unique IF NOT EXISTS FOR (e:Evento) REQUIRE e.evento_key IS UNIQUE",
    "CREATE CONSTRAINT pagina_listado_key_unique IF NOT EXISTS FOR (pg:PaginaListado) REQUIRE pg.pagina_key IS UNIQUE",
    "CREATE CONSTRAINT lugar_key_unique IF NOT EXISTS FOR (l:Lugar) REQUIRE l.lugar_key IS UNIQUE",
    "CREATE CONSTRAINT alias_lugar_key_unique IF NOT EXISTS FOR (a:AliasLugar) REQUIRE a.alias_key IS UNIQUE",
    "CREATE CONSTRAINT alias_lugar_scope_unique IF NOT EXISTS FOR (a:AliasLugar) REQUIRE (a.alias_norm, a.tipo, a.parent_key) IS UNIQUE",
    "CREATE CONSTRAINT direccion_key_unique IF NOT EXISTS FOR (d:Direccion) REQUIRE d.direccion_key IS UNIQUE",
    "CREATE CONSTRAINT direccion_scope_unique IF NOT EXISTS FOR (d:Direccion) REQUIRE (d.direccion_norm, d.lugar_key) IS UNIQUE",
    "CREATE INDEX persona_registro_idx IF NOT EXISTS FOR (p:Persona) ON (p.registro)",
    "CREATE INDEX persona_nombre_idx IF NOT EXISTS FOR (p:Persona) ON (p.nombre_completo)",
    "CREATE INDEX persona_estado_idx IF NOT EXISTS FOR (p:Persona) ON (p.estado_desaparicion)",
    "CREATE INDEX evento_tipo_idx IF NOT EXISTS FOR (e:Evento) ON (e.tipo)",
    "CREATE INDEX evento_fecha_idx IF NOT EXISTS FOR (e:Evento) ON (e.fecha)",
    "CREATE INDEX evento_anio_idx IF NOT EXISTS FOR (e:Evento) ON (e.anio)",
    "CREATE INDEX evento_tipo_anio_idx IF NOT EXISTS FOR (e:Evento) ON (e.tipo, e.anio)",
    "CREATE INDEX evento_tipo_inicio_idx IF NOT EXISTS FOR (e:Evento) ON (e.tipo, e.fecha_inicio)",
    "CREATE INDEX evento_ccd_idx IF NOT EXISTS FOR (e:Evento) ON (e.id_ccd)",
    "CREATE INDEX pagina_listado_num_idx IF NOT EXISTS FOR (pg:PaginaListado) ON (pg.pagina)",
    "CREATE INDEX lugar_nombre_tipo_idx IF NOT EXISTS FOR (l:Lugar) ON (l.nombre_canonico, l.tipo)",
    "CREATE INDEX lugar_tipo_ccd_idx IF NOT EXISTS FOR (l:Lugar) ON (l.tipo, l.id_ccd)",
    "CREATE INDEX lugar_geo_idx IF NOT EXISTS FOR (l:Lugar) ON (l.geo_point)",
    "CREATE INDEX alias_lugar_norm_idx IF NOT EXISTS FOR (a:AliasLugar) ON (a.alias_norm)",
    "CREATE INDEX direccion_norm_idx IF NOT EXISTS FOR (d:Direccion) ON (d.direccion_norm)",
]

CYPHER_UPSERT_PERSONAS = """
UNWIND $rows AS row
MERGE (p:Persona {persona_key: row.persona_key})
SET p.registro = coalesce(row.registro, p.registro),
    p.nombre_completo = coalesce(row.nombre_completo, p.nombre_completo),
    p.nombre = coalesce(row.nombre, p.nombre),
    p.apellido = coalesce(row.apellido, p.apellido),
    p.sexo = coalesce(row.sexo, p.sexo),
    p.estado_desaparicion = coalesce(row.estado_desaparicion, p.estado_desaparicion),
    p.fecha_nacimiento = coalesce(row.fecha_nacimiento, p.fecha_nacimiento),
    p.fecha_secuestro = coalesce(row.fecha_secuestro, p.fecha_secuestro),
    p.fecha_asesinato = coalesce(row.fecha_asesinato, p.fecha_asesinato),
    p.lugar_nacimiento = coalesce(row.lugar_nacimiento, p.lugar_nacimiento),
    p.lugar_secuestro = coalesce(row.lugar_secuestro, p.lugar_secuestro),
    p.es_placeholder = coalesce(p.es_placeholder, false),
    p.fuentes = CASE
      WHEN p.fuentes IS NULL THEN row.fuentes
      ELSE reduce(acc = p.fuentes, f IN row.fuentes |
        CASE WHEN f IN acc THEN acc ELSE acc + f END)
    END
"""

CYPHER_UPSERT_CASOS = """
UNWIND $rows AS row
MERGE (c:CasoNietx {id_nietx: row.id_nietx})
SET c.nombre_caso = row.nombre_caso,
    c.estado = row.estado,
    c.imagen_url = row.imagen_url,
    c.conoce_la_historia_url = row.conoce_la_historia_url,
    c.resumen_data = row.resumen_data,
    c.detalle_data = row.detalle_data,
    c.fecha_adn = row.fecha_adn,
    c.fecha_restitucion = row.fecha_restitucion
"""

CYPHER_UPSERT_PROTAGONISTAS = """
UNWIND $rows AS row
MERGE (p:Persona {persona_key: row.persona_key})
SET p.nombre_completo = coalesce(row.nombre_completo, p.nombre_completo),
    p.es_placeholder = false,
    p.fuentes = CASE
      WHEN p.fuentes IS NULL THEN row.fuentes
      ELSE reduce(acc = p.fuentes, f IN row.fuentes |
        CASE WHEN f IN acc THEN acc ELSE acc + f END)
    END
SET p:Nietx
WITH p, row
MATCH (c:CasoNietx {id_nietx: row.id_nietx})
MERGE (c)-[:TIENE_PROTAGONISTA]->(p)
"""

CYPHER_UPSERT_REL_FAMILIAR = """
UNWIND $rows AS row
MATCH (s:Persona {persona_key: row.source_key})
MERGE (t:Persona {persona_key: row.target_key})
SET t.registro = coalesce(row.target_registro, t.registro),
    t.nombre_completo = coalesce(row.target_nombre, t.nombre_completo),
    t.es_placeholder = coalesce(row.target_placeholder, t.es_placeholder, false),
    t.fuentes = CASE
      WHEN t.fuentes IS NULL THEN [row.fuente]
      WHEN row.fuente IN t.fuentes THEN t.fuentes
      ELSE t.fuentes + row.fuente
    END
MERGE (s)-[r:VINCULO_FAMILIAR {tipo: row.tipo, fuente: row.fuente}]->(t)
SET r.tipo_raw = row.tipo_raw
"""

CYPHER_UPSERT_REL_PERSONA = """
UNWIND $rows AS row
MATCH (s:Persona {persona_key: row.source_key})
MERGE (t:Persona {persona_key: row.target_key})
SET t.registro = coalesce(row.target_registro, t.registro),
    t.nombre_completo = coalesce(row.target_nombre, t.nombre_completo),
    t.es_placeholder = coalesce(row.target_placeholder, t.es_placeholder, false),
    t.fuentes = CASE
      WHEN t.fuentes IS NULL THEN [row.fuente]
      WHEN row.fuente IN t.fuentes THEN t.fuentes
      ELSE t.fuentes + row.fuente
    END
MERGE (s)-[r:VINCULO_PERSONA {tipo: row.tipo, fuente: row.fuente}]->(t)
SET r.tipo_raw = row.tipo_raw
"""

CYPHER_UPSERT_SIMULT = """
UNWIND $rows AS row
MATCH (s:Persona {persona_key: row.source_key})
MERGE (t:Persona {persona_key: row.target_key})
SET t.registro = coalesce(row.target_registro, t.registro),
    t.nombre_completo = coalesce(row.target_nombre, t.nombre_completo),
    t.es_placeholder = coalesce(row.target_placeholder, t.es_placeholder, false),
    t.fuentes = CASE
      WHEN t.fuentes IS NULL THEN [row.fuente]
      WHEN row.fuente IN t.fuentes THEN t.fuentes
      ELSE t.fuentes + row.fuente
    END
MERGE (s)-[:VICTIMA_SIMULTANEA {fuente: row.fuente}]->(t)
"""

CYPHER_UPSERT_EVENTOS = """
UNWIND $rows AS row
MERGE (e:Evento {evento_key: row.evento_key})
SET e.tipo = row.tipo,
    e.fecha = coalesce(row.fecha, e.fecha),
    e.fecha_inicio = coalesce(row.fecha_inicio, e.fecha_inicio),
    e.fecha_fin = coalesce(row.fecha_fin, e.fecha_fin),
    e.fecha_precision = coalesce(row.fecha_precision, e.fecha_precision),
    e.anio = coalesce(
        row.anio,
        e.anio,
        CASE WHEN coalesce(row.fecha, e.fecha) IS NOT NULL
             THEN toInteger(substring(coalesce(row.fecha, e.fecha), 0, 4))
             ELSE NULL
        END
    ),
    e.anio_inicio = coalesce(
        row.anio_inicio,
        e.anio_inicio,
        CASE WHEN coalesce(row.fecha_inicio, row.fecha, e.fecha_inicio, e.fecha) IS NOT NULL
             THEN toInteger(substring(coalesce(row.fecha_inicio, row.fecha, e.fecha_inicio, e.fecha), 0, 4))
             ELSE NULL
        END
    ),
    e.anio_fin = coalesce(
        row.anio_fin,
        e.anio_fin,
        CASE WHEN coalesce(row.fecha_fin, row.fecha, e.fecha_fin, e.fecha) IS NOT NULL
             THEN toInteger(substring(coalesce(row.fecha_fin, row.fecha, e.fecha_fin, e.fecha), 0, 4))
             ELSE NULL
        END
    ),
    e.lugar = coalesce(row.lugar, e.lugar),
    e.descripcion_raw = coalesce(row.descripcion_raw, e.descripcion_raw),
    e.fuente = row.fuente,
    e.id_ccd = coalesce(row.id_ccd, e.id_ccd),
    e.ccd_relacion = coalesce(row.ccd_relacion, e.ccd_relacion),
    e.ccd_certeza = coalesce(row.ccd_certeza, e.ccd_certeza),
    e.ccd_denominacion = coalesce(row.ccd_denominacion, e.ccd_denominacion)
"""

CYPHER_LINK_PERSONA_EVENTO = """
UNWIND $rows AS row
MATCH (p:Persona {persona_key: row.persona_key})
MATCH (e:Evento {evento_key: row.evento_key})
MERGE (p)-[r:PARTICIPO_EN {rol: row.rol, fuente: row.fuente}]->(e)
SET r.descripcion_raw = row.descripcion_raw,
    r.ccd_certeza = coalesce(row.ccd_certeza, r.ccd_certeza),
    r.id_ccd = coalesce(row.id_ccd, r.id_ccd)
"""

CYPHER_LINK_CASO_EVENTO = """
UNWIND $rows AS row
MATCH (c:CasoNietx {id_nietx: row.id_nietx})
MATCH (e:Evento {evento_key: row.evento_key})
MERGE (c)-[:REGISTRA_EVENTO {fuente: row.fuente}]->(e)
"""

CYPHER_UPSERT_PAGINAS_LISTADO = """
UNWIND $rows AS row
MERGE (pg:PaginaListado {pagina_key: row.pagina_key})
SET pg.pagina = row.pagina,
    pg.url = row.url,
    pg.fuente = row.fuente,
    pg.registros_count = row.registros_count
"""

CYPHER_LINK_PERSONA_PAGINA = """
UNWIND $rows AS row
MATCH (p:Persona {registro: row.registro})
MATCH (pg:PaginaListado {pagina_key: row.pagina_key})
MERGE (p)-[r:LISTADA_EN {fuente: row.fuente}]->(pg)
SET r.detail_url = row.detail_url,
    r.estado_raw = row.estado_raw,
    r.edad = row.edad,
    r.anio = row.anio,
    r.embarazo_estado = row.embarazo_estado,
    r.embarazo_meses = row.embarazo_meses
"""

CYPHER_CLEAN_PROJECT = """
MATCH (n)
WHERE n:Persona OR n:CasoNietx OR n:Evento OR n:PaginaListado OR n:Lugar OR n:AliasLugar OR n:Direccion
DETACH DELETE n
"""

CYPHER_CLEAN_ALL = """
MATCH (n)
DETACH DELETE n
"""

CYPHER_UPSERT_CANDIDATO_MERGE = """
UNWIND $rows AS row
MATCH (p:Persona {persona_key: row.placeholder_key})
MATCH (c:Persona {persona_key: row.candidate_key})
MERGE (p)-[r:CANDIDATO_MERGE {metodo: row.metodo}]->(c)
SET r.score = row.score,
    r.slug = row.slug,
    r.confianza = row.confianza,
    r.fuente = row.fuente
"""

CYPHER_UPSERT_LUGARES = """
UNWIND $rows AS row
MERGE (l:Lugar {lugar_key: row.lugar_key})
SET l.nombre_canonico = row.nombre_canonico,
    l.tipo = row.tipo,
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

CYPHER_LINK_LUGAR_PARENT = """
UNWIND $rows AS row
MATCH (child:Lugar {lugar_key: row.child_key})
MATCH (parent:Lugar {lugar_key: row.parent_key})
MERGE (child)-[:PARTE_DE]->(parent)
"""

CYPHER_UPSERT_ALIAS_LUGAR = """
UNWIND $rows AS row
MERGE (a:AliasLugar {alias_norm: row.alias_norm, tipo: row.tipo, parent_key: row.parent_key})
ON CREATE SET a.alias_key = row.alias_key,
              a.alias_raw = row.alias_raw,
              a.fuente = row.fuente,
              a.campo_fuente = row.campo_fuente
SET a.alias_norm = row.alias_norm,
    a.alias_raw = row.alias_raw,
    a.fuente = row.fuente,
    a.campo_fuente = row.campo_fuente,
    a.tipo = row.tipo,
    a.parent_key = row.parent_key
WITH a, row
MATCH (l:Lugar {lugar_key: row.lugar_key})
OPTIONAL MATCH (a)-[old:ALIAS_DE]->(prev:Lugar)
WHERE prev <> l
DELETE old
MERGE (a)-[:ALIAS_DE]->(l)
"""

CYPHER_LINK_PERSONA_LUGAR = """
UNWIND $rows AS row
MATCH (p:Persona {registro: row.registro})
MATCH (l:Lugar {lugar_key: row.lugar_key})
MERGE (p)-[r:LUGAR_REFERENCIA {campo: row.campo, fuente: row.fuente}]->(l)
SET r.alias_raw = row.alias_raw
"""

CYPHER_LINK_EVENTO_LUGAR = """
UNWIND $rows AS row
MATCH (e:Evento {evento_key: row.evento_key})
MATCH (l:Lugar {lugar_key: row.lugar_key})
MERGE (e)-[r:OCURRIO_EN {fuente: row.fuente, campo_fuente: row.campo_fuente}]->(l)
SET r.alias_raw = row.alias_raw
"""

CYPHER_UPSERT_DIRECCIONES = """
UNWIND $rows AS row
MERGE (d:Direccion {direccion_norm: row.direccion_norm, lugar_key: row.lugar_key})
ON CREATE SET d.direccion_key = row.direccion_key
SET d.direccion_raw = row.direccion_raw,
    d.via = coalesce(row.via, d.via),
    d.numero = coalesce(row.numero, d.numero),
    d.piso_depto = coalesce(row.piso_depto, d.piso_depto),
    d.confianza_parseo = coalesce(row.confianza_parseo, d.confianza_parseo),
    d.fuente = row.fuente,
    d.campo_fuente = row.campo_fuente
"""

CYPHER_LINK_DIRECCION_LUGAR = """
UNWIND $rows AS row
MATCH (d:Direccion {direccion_key: row.direccion_key})
MATCH (l:Lugar {lugar_key: row.lugar_key})
MERGE (d)-[:UBICADA_EN]->(l)
"""

CYPHER_LINK_EVENTO_DIRECCION = """
UNWIND $rows AS row
MATCH (e:Evento {evento_key: row.evento_key})
MATCH (d:Direccion {direccion_key: row.direccion_key})
MERGE (e)-[r:OCURRIO_EN_DIRECCION {fuente: row.fuente, campo_fuente: row.campo_fuente}]->(d)
SET r.alias_raw = row.alias_raw
"""

CYPHER_APPLY_SAFE_PLACE_MERGES = """
UNWIND $rows AS row
MATCH (src:Lugar {lugar_key: row.source_key})
MATCH (dst:Lugar {lugar_key: row.target_key})
WHERE src <> dst
WITH src, dst, row
OPTIONAL MATCH (a:AliasLugar)-[ad:ALIAS_DE]->(src)
FOREACH (_ IN CASE WHEN ad IS NULL THEN [] ELSE [1] END |
    MERGE (a)-[:ALIAS_DE]->(dst)
    DELETE ad
)
WITH src, dst, row
OPTIONAL MATCH (p:Persona)-[rp:LUGAR_REFERENCIA]->(src)
FOREACH (_ IN CASE WHEN rp IS NULL THEN [] ELSE [1] END |
    MERGE (p)-[rp2:LUGAR_REFERENCIA {campo: rp.campo, fuente: rp.fuente}]->(dst)
    SET rp2.alias_raw = coalesce(rp2.alias_raw, rp.alias_raw)
    DELETE rp
)
WITH src, dst, row
OPTIONAL MATCH (e:Evento)-[re:OCURRIO_EN]->(src)
FOREACH (_ IN CASE WHEN re IS NULL THEN [] ELSE [1] END |
    MERGE (e)-[re2:OCURRIO_EN {fuente: re.fuente, campo_fuente: re.campo_fuente}]->(dst)
    SET re2.alias_raw = coalesce(re2.alias_raw, re.alias_raw)
    DELETE re
)
WITH src, dst, row
OPTIONAL MATCH (src)-[r1:PARTE_DE]->(parent:Lugar)
FOREACH (_ IN CASE WHEN r1 IS NULL THEN [] ELSE [1] END |
    MERGE (dst)-[:PARTE_DE]->(parent)
    DELETE r1
)
WITH src, dst, row
OPTIONAL MATCH (child:Lugar)-[r2:PARTE_DE]->(src)
FOREACH (_ IN CASE WHEN r2 IS NULL THEN [] ELSE [1] END |
    MERGE (child)-[:PARTE_DE]->(dst)
    DELETE r2
)
WITH src, row
SET src.merged_into = row.target_key,
        src.merge_reason = row.reason,
        src.merge_score = row.score
DETACH DELETE src
"""

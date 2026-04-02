// Constraints base para capa de lugares/fechas/estudio/embarazo

CREATE CONSTRAINT lugar_key_unique IF NOT EXISTS
FOR (l:Lugar) REQUIRE l.lugar_key IS UNIQUE;

CREATE CONSTRAINT alias_lugar_key_unique IF NOT EXISTS
FOR (a:AliasLugar) REQUIRE a.alias_key IS UNIQUE;

// Evita duplicar alias dentro del mismo ambito (tipo + parent)
CREATE CONSTRAINT alias_lugar_scope_unique IF NOT EXISTS
FOR (a:AliasLugar) REQUIRE (a.alias_norm, a.tipo, a.parent_key) IS UNIQUE;

CREATE CONSTRAINT fecha_iso_unique IF NOT EXISTS
FOR (f:Fecha) REQUIRE f.fecha_iso IS UNIQUE;

CREATE CONSTRAINT anio_unique IF NOT EXISTS
FOR (y:Anio) REQUIRE y.anio IS UNIQUE;

CREATE CONSTRAINT institucion_key_unique IF NOT EXISTS
FOR (i:Institucion) REQUIRE i.institucion_key IS UNIQUE;

CREATE CONSTRAINT carrera_key_unique IF NOT EXISTS
FOR (c:Carrera) REQUIRE c.carrera_key IS UNIQUE;

CREATE CONSTRAINT embarazo_key_unique IF NOT EXISTS
FOR (e:CondicionEmbarazo) REQUIRE e.embarazo_key IS UNIQUE;

CREATE INDEX lugar_nombre_tipo_idx IF NOT EXISTS
FOR (l:Lugar) ON (l.nombre_canonico, l.tipo);

CREATE INDEX alias_lugar_norm_idx IF NOT EXISTS
FOR (a:AliasLugar) ON (a.alias_norm);

CREATE INDEX institucion_nombre_idx IF NOT EXISTS
FOR (i:Institucion) ON (i.nombre_canonico);

CREATE INDEX carrera_nombre_idx IF NOT EXISTS
FOR (c:Carrera) ON (c.nombre_canonico);

// ---- Plantillas de merge deterministico (ejemplos) ----

// 1) Merge de lugar por llave canonica
// MERGE (l:Lugar {lugar_key: $lugar_key})
// SET l.nombre_canonico = $nombre_canonico,
//     l.tipo = $tipo,
//     l.pais_code = coalesce($pais_code, l.pais_code)

// 2) Alias hacia lugar
// MERGE (a:AliasLugar {alias_key: $alias_key})
// SET a.alias_norm = $alias_norm,
//     a.alias_raw = $alias_raw,
//     a.fuente = $fuente,
//     a.campo_fuente = $campo_fuente,
//     a.tipo = $tipo,
//     a.parent_key = $parent_key
// WITH a
// MATCH (l:Lugar {lugar_key: $lugar_key})
// MERGE (a)-[:ALIAS_DE]->(l)

// 3) Jerarquia lugar
// MATCH (child:Lugar {lugar_key: $child_key})
// MATCH (parent:Lugar {lugar_key: $parent_key})
// MERGE (child)-[:PARTE_DE]->(parent)

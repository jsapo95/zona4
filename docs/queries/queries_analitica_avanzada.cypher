// =============================================
// QUERIES ANALITICAS AVANZADAS (MODELO ACTUAL)
// Incluye Lugar jerarquico, Direccion y CCD integrados
// =============================================

// 1) Hotspots globales por Lugar de ocurrencia
MATCH (e:Evento)-[:OCURRIO_EN]->(l:Lugar)
RETURN l.lugar_key AS lugar_key,
       l.nombre_canonico AS lugar,
       l.tipo AS tipo,
       count(e) AS eventos_total
ORDER BY eventos_total DESC
LIMIT 50;

// 2) Hotspots por tipo de evento y Lugar
MATCH (e:Evento)-[:OCURRIO_EN]->(l:Lugar)
RETURN e.tipo AS tipo_evento,
       l.nombre_canonico AS lugar,
       l.tipo AS tipo_lugar,
       count(e) AS eventos_total
ORDER BY eventos_total DESC
LIMIT 100;

// 3) Evolucion anual de eventos (incluye tipos CCD)
MATCH (e:Evento)
WHERE e.anio IS NOT NULL
RETURN e.anio AS anio,
       count(*) AS eventos_total,
       count(CASE WHEN e.tipo = 'SECUESTRO' THEN 1 END) AS secuestros,
       count(CASE WHEN e.tipo = 'ASESINATO' THEN 1 END) AS asesinatos,
       count(CASE WHEN e.tipo = 'SECUESTRO_CCD' THEN 1 END) AS secuestros_ccd,
       count(CASE WHEN e.tipo = 'PARTO_CAUTIVERIO_CCD' THEN 1 END) AS partos_cautiverio_ccd
ORDER BY anio;

// 4) Evolucion anual por jurisdiccion (usando lugar CCD o anclado)
MATCH (e:Evento)-[:OCURRIO_EN]->(l:Lugar)
WHERE e.anio IS NOT NULL
WITH e,
     coalesce(l.jurisdiccion, l.provincia, l.nombre_canonico) AS jurisdiccion
WHERE jurisdiccion IS NOT NULL
RETURN e.anio AS anio,
       jurisdiccion,
       count(*) AS eventos_total
ORDER BY anio, eventos_total DESC;

// 5) Personas con mayor cantidad de eventos
MATCH (p:Persona)-[:PARTICIPO_EN]->(e:Evento)
RETURN p.persona_key AS persona_key,
       coalesce(p.nombre_completo, p.persona_key) AS persona,
       count(e) AS eventos_total,
       count(DISTINCT e.tipo) AS tipos_evento_distintos
ORDER BY eventos_total DESC
LIMIT 100;

// 6) Personas con trayectorias multisitio
MATCH (p:Persona)-[:PARTICIPO_EN]->(:Evento)-[:OCURRIO_EN]->(l:Lugar)
RETURN p.persona_key AS persona_key,
       coalesce(p.nombre_completo, p.persona_key) AS persona,
       count(DISTINCT l.lugar_key) AS lugares_distintos,
       collect(DISTINCT l.nombre_canonico)[0..10] AS muestra_lugares
ORDER BY lugares_distintos DESC
LIMIT 100;

// 7) Red de co-ocurrencia por victimas simultaneas
MATCH (p1:Persona)-[:VICTIMA_SIMULTANEA]->(p2:Persona)
RETURN p1.persona_key AS source,
       p2.persona_key AS target,
       coalesce(p1.nombre_completo, p1.persona_key) AS source_nombre,
       coalesce(p2.nombre_completo, p2.persona_key) AS target_nombre
LIMIT 500;

// 8) Calidad de conciliacion de placeholders
MATCH (p:Persona {es_placeholder:true})
OPTIONAL MATCH (p)-[r:CANDIDATO_MERGE]->(:Persona)
RETURN count(DISTINCT p) AS placeholders_total,
       count(DISTINCT CASE WHEN r IS NOT NULL THEN p END) AS placeholders_con_candidato,
       count(r) AS relaciones_candidato_total,
       avg(r.score) AS score_promedio;

// 9) Placeholders mas ambiguos
MATCH (p:Persona {es_placeholder:true})-[r:CANDIDATO_MERGE]->(c:Persona)
RETURN p.persona_key AS placeholder,
       count(r) AS candidatos,
       max(r.score) AS mejor_score,
       collect(c.persona_key)[0..10] AS muestra_candidatos
ORDER BY candidatos DESC, mejor_score DESC
LIMIT 100;

// 10) Cobertura de eventos con direccion especifica
MATCH (e:Evento)
OPTIONAL MATCH (e)-[:OCURRIO_EN_DIRECCION]->(d:Direccion)
RETURN count(e) AS eventos_total,
       count(CASE WHEN d IS NOT NULL THEN 1 END) AS eventos_con_direccion,
       round(100.0 * count(CASE WHEN d IS NOT NULL THEN 1 END) / count(e), 2) AS pct_eventos_con_direccion;

// 11) Direcciones mas frecuentes y su lugar ancla
MATCH (e:Evento)-[:OCURRIO_EN_DIRECCION]->(d:Direccion)-[:UBICADA_EN]->(l:Lugar)
RETURN d.direccion_norm AS direccion,
       l.nombre_canonico AS lugar,
       l.tipo AS tipo_lugar,
       count(e) AS eventos_total,
       max(d.confianza_parseo) AS confianza_max
ORDER BY eventos_total DESC
LIMIT 100;

// 12) Cobertura de anclaje jerarquico en CCD
MATCH (ccd:Lugar {tipo:'CCD'})
OPTIONAL MATCH (ccd)-[:PARTE_DE]->(p:Lugar)
WITH ccd, collect(DISTINCT p) AS parents
RETURN count(ccd) AS total_ccd,
       count(CASE WHEN size(parents)=0 THEN 1 END) AS ccd_sin_parent,
       count(CASE WHEN size(parents)>0 THEN 1 END) AS ccd_con_parent;

// 13) Sitios CCD mas activos por eventos
MATCH (e:Evento)
WHERE e.id_ccd IS NOT NULL
MATCH (e)-[:OCURRIO_EN]->(l:Lugar)
RETURN e.id_ccd AS id_ccd,
       coalesce(e.ccd_denominacion, l.nombre_canonico) AS ccd,
       l.nombre_canonico AS lugar_ocurrencia,
       l.tipo AS tipo_lugar,
       count(*) AS eventos_total,
       count(CASE WHEN e.ccd_certeza = 'confirmado' THEN 1 END) AS confirmados,
       count(CASE WHEN e.ccd_certeza = 'posible' THEN 1 END) AS posibles
ORDER BY eventos_total DESC
LIMIT 100;

// 14) Densidad de eventos con coordenadas (mapas)
MATCH (e:Evento)-[:OCURRIO_EN]->(l:Lugar)
WHERE l.geo_point IS NOT NULL
RETURN l.geo_point.latitude AS lat,
       l.geo_point.longitude AS lon,
       l.nombre_canonico AS lugar,
       l.tipo AS tipo,
       count(e) AS eventos_total
ORDER BY eventos_total DESC
LIMIT 500;

// 15) Personas por anio de evento principal
MATCH (p:Persona)-[:PARTICIPO_EN]->(e:Evento)
WHERE p.estado_desaparicion IS NOT NULL
  AND e.anio IS NOT NULL
  AND e.tipo IN ['SECUESTRO', 'ASESINATO', 'SECUESTRO_CCD']
RETURN p.estado_desaparicion AS estado,
       e.anio AS anio,
       count(DISTINCT p.persona_key) AS personas
ORDER BY anio, estado;

// 16) Lugares con mayor diversidad de personas
MATCH (p:Persona)-[:PARTICIPO_EN]->(:Evento)-[:OCURRIO_EN]->(l:Lugar)
RETURN l.lugar_key AS lugar_key,
       l.nombre_canonico AS lugar,
       l.tipo AS tipo,
       count(DISTINCT p.persona_key) AS personas_distintas
ORDER BY personas_distintas DESC
LIMIT 100;

// 17) Secuencia temporal de lugares por persona
MATCH (p:Persona)-[:PARTICIPO_EN]->(e:Evento)-[:OCURRIO_EN]->(l:Lugar)
WHERE e.fecha_inicio IS NOT NULL
WITH p, e, l
ORDER BY p.persona_key, e.fecha_inicio
RETURN p.persona_key AS persona_key,
       coalesce(p.nombre_completo, p.persona_key) AS persona,
       collect({fecha_inicio: e.fecha_inicio, tipo: e.tipo, lugar: l.nombre_canonico, tipo_lugar: l.tipo})[0..50] AS secuencia
LIMIT 200;

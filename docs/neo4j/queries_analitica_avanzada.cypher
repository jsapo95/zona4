// =============================================
// QUERIES ANALITICAS AVANZADAS (PERSONAS/LUGARES/EVENTOS)
// =============================================

// 1) Hotspots de eventos por lugar (top global)
MATCH (e:Evento)-[:OCURRIO_EN]->(l:Lugar)
RETURN l.lugar_key AS lugar_key,
       l.nombre_canonico AS lugar,
       l.tipo AS tipo,
       count(e) AS eventos_total
ORDER BY eventos_total DESC
LIMIT 50;

// 2) Hotspots por tipo de evento y lugar
MATCH (e:Evento)-[:OCURRIO_EN]->(l:Lugar)
RETURN e.tipo AS tipo_evento,
       l.nombre_canonico AS lugar,
       l.tipo AS tipo_lugar,
       count(e) AS eventos_total
ORDER BY eventos_total DESC
LIMIT 100;

// 3) Evolucion temporal anual de eventos
MATCH (e:Evento)
WHERE e.anio IS NOT NULL
RETURN e.anio AS anio,
       count(*) AS eventos_total,
       count(CASE WHEN e.tipo = 'SECUESTRO' THEN 1 END) AS secuestros,
       count(CASE WHEN e.tipo = 'ASESINATO' THEN 1 END) AS asesinatos,
       count(CASE WHEN e.tipo = 'SECUESTRO_CCD' THEN 1 END) AS secuestros_ccd,
       count(CASE WHEN e.tipo = 'PARTO_CAUTIVERIO_CCD' THEN 1 END) AS partos_cautiverio_ccd
ORDER BY anio;

// 4) Evolucion anual por jurisdiccion de CCD
MATCH (e:Evento)-[:OCURRIO_EN]->(l:Lugar)
WHERE e.anio IS NOT NULL AND l.jurisdiccion IS NOT NULL
RETURN e.anio AS anio,
       l.jurisdiccion AS jurisdiccion,
       count(*) AS eventos_total
ORDER BY anio, eventos_total DESC;

// 5) Personas con mayor cantidad de eventos registrados
MATCH (p:Persona)-[:PARTICIPO_EN]->(e:Evento)
RETURN p.persona_key AS persona_key,
       coalesce(p.nombre_completo, p.persona_key) AS persona,
       count(e) AS eventos_total,
       count(DISTINCT e.tipo) AS tipos_evento_distintos
ORDER BY eventos_total DESC
LIMIT 100;

// 6) Personas con trayectorias multisitio (cantidad de lugares distintos)
MATCH (p:Persona)-[:PARTICIPO_EN]->(:Evento)-[:OCURRIO_EN]->(l:Lugar)
RETURN p.persona_key AS persona_key,
       coalesce(p.nombre_completo, p.persona_key) AS persona,
       count(DISTINCT l.lugar_key) AS lugares_distintos,
       collect(DISTINCT l.nombre_canonico)[0..10] AS muestra_lugares
ORDER BY lugares_distintos DESC
LIMIT 100;

// 7) Red de co-ocurrencia por victimas simultaneas
MATCH (p1:Persona)-[:VICTIMA_SIMULTANEA]->(p2:Persona)
WITH p1, p2
RETURN p1.persona_key AS source,
       p2.persona_key AS target,
       coalesce(p1.nombre_completo, p1.persona_key) AS source_nombre,
       coalesce(p2.nombre_completo, p2.persona_key) AS target_nombre
LIMIT 500;

// 8) Calidad de conciliacion de personas (placeholders con candidatos)
MATCH (p:Persona {es_placeholder:true})
OPTIONAL MATCH (p)-[r:CANDIDATO_MERGE]->(c:Persona)
RETURN count(DISTINCT p) AS placeholders_total,
       count(DISTINCT CASE WHEN r IS NOT NULL THEN p END) AS placeholders_con_candidato,
       count(r) AS relaciones_candidato_total,
       avg(r.score) AS score_promedio
;

// 9) Placeholders mas ambiguos (muchos candidatos)
MATCH (p:Persona {es_placeholder:true})-[r:CANDIDATO_MERGE]->(c:Persona)
RETURN p.persona_key AS placeholder,
       count(r) AS candidatos,
       max(r.score) AS mejor_score,
       collect(c.persona_key)[0..10] AS muestra_candidatos
ORDER BY candidatos DESC, mejor_score DESC
LIMIT 100;

// 10) Cobertura de reutilizacion de lugares CCD vs nodo CCD propio
MATCH (e:Evento)
WHERE e.id_ccd IS NOT NULL
MATCH (e)-[:OCURRIO_EN]->(l:Lugar)
RETURN count(*) AS eventos_ccd_total,
       count(CASE WHEN l.tipo <> 'CCD' THEN 1 END) AS eventos_ccd_en_lugar_reutilizado,
       count(CASE WHEN l.tipo = 'CCD' THEN 1 END) AS eventos_ccd_en_lugar_ccd
;

// 11) Sitios CCD mas activos (por eventos)
MATCH (e:Evento)
WHERE e.id_ccd IS NOT NULL
MATCH (e)-[:OCURRIO_EN]->(l:Lugar)
RETURN e.id_ccd AS id_ccd,
       coalesce(e.ccd_denominacion, l.nombre_canonico) AS ccd,
       count(*) AS eventos_total,
       count(CASE WHEN e.ccd_certeza = 'confirmado' THEN 1 END) AS confirmados,
       count(CASE WHEN e.ccd_certeza = 'posible' THEN 1 END) AS posibles
ORDER BY eventos_total DESC
LIMIT 100;

// 12) Densidad de eventos con coordenadas (para mapas)
MATCH (e:Evento)-[:OCURRIO_EN]->(l:Lugar)
WHERE l.geo_point IS NOT NULL
RETURN l.geo_point.latitude AS lat,
       l.geo_point.longitude AS lon,
       l.nombre_canonico AS lugar,
       l.tipo AS tipo,
       count(e) AS eventos_total
ORDER BY eventos_total DESC
LIMIT 500;

// 13) Personas desaparecidas/asesinadas por anio de evento principal
MATCH (p:Persona)-[:PARTICIPO_EN]->(e:Evento)
WHERE p.estado_desaparicion IS NOT NULL
  AND e.anio IS NOT NULL
  AND e.tipo IN ['SECUESTRO', 'ASESINATO', 'SECUESTRO_CCD']
RETURN p.estado_desaparicion AS estado,
       e.anio AS anio,
       count(DISTINCT p.persona_key) AS personas
ORDER BY anio, estado;

// 14) Lugares con mayor diversidad de personas afectadas
MATCH (p:Persona)-[:PARTICIPO_EN]->(:Evento)-[:OCURRIO_EN]->(l:Lugar)
RETURN l.lugar_key AS lugar_key,
       l.nombre_canonico AS lugar,
       l.tipo AS tipo,
       count(DISTINCT p.persona_key) AS personas_distintas
ORDER BY personas_distintas DESC
LIMIT 100;

// 15) Trayectorias de lugar por persona (secuencia temporal)
MATCH (p:Persona)-[:PARTICIPO_EN]->(e:Evento)-[:OCURRIO_EN]->(l:Lugar)
WHERE e.fecha_inicio IS NOT NULL
WITH p, e, l
ORDER BY p.persona_key, e.fecha_inicio
RETURN p.persona_key AS persona_key,
       coalesce(p.nombre_completo, p.persona_key) AS persona,
       collect({fecha_inicio: e.fecha_inicio, tipo: e.tipo, lugar: l.nombre_canonico, tipo_lugar: l.tipo})[0..50] AS secuencia
LIMIT 200;

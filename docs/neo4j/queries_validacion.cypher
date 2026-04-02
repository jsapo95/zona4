// Conteo por label principal
MATCH (n)
RETURN labels(n) AS labels, count(*) AS c
ORDER BY c DESC;

// Personas por fuente
MATCH (p:Persona)
UNWIND coalesce(p.fuentes, ['(sin_fuente)']) AS fuente
RETURN fuente, count(*) AS c
ORDER BY c DESC;

// Cobertura de relaciones familiares de nietxs con registro
MATCH (:Persona:Nietx)-[r:VINCULO_FAMILIAR {fuente:'nietxs_relacion'}]->(f:Persona)
RETURN count(r) AS total_rel,
       count(CASE WHEN f.registro IS NOT NULL THEN 1 END) AS rel_con_registro,
       count(CASE WHEN f.es_placeholder = true THEN 1 END) AS rel_placeholder;

// Top tipos de vinculo en nietxs
MATCH (:Persona:Nietx)-[r:VINCULO_FAMILIAR {fuente:'nietxs_relacion'}]->(:Persona)
RETURN r.tipo AS tipo, count(*) AS c
ORDER BY c DESC;

// Top tipos de vinculo en detalles_personas
MATCH (:Persona)-[r:VINCULO_PERSONA {fuente:'detalles_personas'}]->(:Persona)
RETURN r.tipo AS tipo, count(*) AS c
ORDER BY c DESC;

// Casos por estado
MATCH (c:CasoNietx)
RETURN c.estado AS estado, count(*) AS c
ORDER BY c DESC;

// Eventos por tipo
MATCH (e:Evento)
RETURN e.tipo AS tipo, count(*) AS c
ORDER BY c DESC;

// Cobertura de personas con evento de secuestro
MATCH (p:Persona)
OPTIONAL MATCH (p)-[:PARTICIPO_EN {fuente:'detalles_personas'}]->(e:Evento {tipo:'SECUESTRO'})
RETURN count(p) AS total_personas,
       count(CASE WHEN e IS NOT NULL THEN 1 END) AS personas_con_evento_secuestro;

// Casos con eventos de ADN y restitucion
MATCH (c:CasoNietx)
OPTIONAL MATCH (c)-[:REGISTRA_EVENTO]->(eadn:Evento {tipo:'ADN'})
OPTIONAL MATCH (c)-[:REGISTRA_EVENTO]->(er:Evento {tipo:'RESTITUCION'})
RETURN count(c) AS total_casos,
       count(CASE WHEN eadn IS NOT NULL THEN 1 END) AS casos_con_adn,
       count(CASE WHEN er IS NOT NULL THEN 1 END) AS casos_con_restitucion;

// Candidatos de merge generados (v3)
MATCH (p:Persona {es_placeholder:true})-[r:CANDIDATO_MERGE]->(c:Persona)
RETURN count(r) AS total_candidatos,
       count(DISTINCT p) AS placeholders_con_candidato,
       count(DISTINCT c) AS personas_candidatas;

// Cobertura de indexacion por listado_paginas
MATCH (pg:PaginaListado)
OPTIONAL MATCH (p:Persona)-[r:LISTADA_EN]->(pg)
RETURN count(DISTINCT pg) AS total_paginas,
       count(r) AS total_links_listado,
       count(DISTINCT p) AS personas_listadas;

// Ambiguedad de candidatos por placeholder
MATCH (p:Persona {es_placeholder:true})-[r:CANDIDATO_MERGE]->(:Persona)
RETURN p.persona_key AS placeholder, count(r) AS candidatos
ORDER BY candidatos DESC, placeholder
LIMIT 25;

// Protagonistas sin fecha de restitucion
MATCH (c:CasoNietx)-[:TIENE_PROTAGONISTA]->(n:Nietx)
WHERE c.fecha_restitucion IS NULL
RETURN c.id_nietx AS id_nietx, c.nombre_caso AS nombre
ORDER BY id_nietx;

// Colisiones de alias de lugar por scope (no deberia haber >1 Lugar por alias/tipo/parent)
MATCH (a:AliasLugar)-[:ALIAS_DE]->(l:Lugar)
WITH a.alias_norm AS alias_norm,
     a.tipo AS tipo,
     a.parent_key AS parent_key,
     collect(DISTINCT l.lugar_key) AS lugares
WHERE size(lugares) > 1
RETURN alias_norm, tipo, parent_key, size(lugares) AS lugares_distintos, lugares
ORDER BY lugares_distintos DESC, alias_norm
LIMIT 50;

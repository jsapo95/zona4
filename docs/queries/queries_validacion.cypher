// =====================================================================
// QUERIES DE VALIDACIÓN — modelo V1.3 (grafo sin nodo :Evento)
// =====================================================================
// Reescritas el 2026-09-11 contra el grafo vivo (bolt://localhost:17687).
// Cada bloque dice qué invariante controla y cuál era el resultado en esa
// corrida, para poder comparar después de cada recarga.
//
// Convención: los bloques marcados "DEBE DAR 0" son invariantes duras; si
// devuelven otra cosa hay un bug en el loader. Los marcados "COBERTURA" son
// métricas que se comparan contra la corrida anterior.


// ---------------------------------------------------------------------
// 1. INVENTARIO
// ---------------------------------------------------------------------

// 1.1) Nodos por combinación de labels. Total esperado: 21.426.
MATCH (n)
RETURN labels(n) AS labels, count(*) AS nodos
ORDER BY nodos DESC;

// 1.2) Relaciones por tipo. Total esperado: 42.068.
MATCH ()-[r]->()
RETURN type(r) AS relacion, count(*) AS aristas
ORDER BY aristas DESC;

// 1.3) Personas por fuente y rol.
MATCH (p:Persona)
RETURN p.fuente AS fuente,
       count(*) AS personas,
       count(CASE WHEN p:Victima  THEN 1 END) AS victimas,
       count(CASE WHEN p:Represor THEN 1 END) AS represores,
       count(CASE WHEN p:Complice THEN 1 END) AS complices,
       count(CASE WHEN p:Nietx    THEN 1 END) AS nietxs
ORDER BY personas DESC;

// 1.4) Aristas aportadas por cada fuente (`origen`). Sirve para detectar que
//      un builder dejó de escribir.
MATCH ()-[r]->()
WITH CASE WHEN r.origen CONTAINS ':' THEN split(r.origen, ':')[0] ELSE r.origen END AS fuente,
     type(r) AS relacion
RETURN fuente, relacion, count(*) AS aristas
ORDER BY fuente, aristas DESC;


// ---------------------------------------------------------------------
// 2. CLAVES, LABELS Y ROLES (invariantes duras)
// ---------------------------------------------------------------------

// 2.1) DEBE DAR 0 en las cinco filas: claves duplicadas pese al constraint.
MATCH (p:Persona)        WITH p.persona_key AS k, count(*) AS c WHERE c > 1
RETURN 'Persona.persona_key' AS clave, count(*) AS duplicadas
UNION ALL
MATCH (l:Lugar)          WITH l.lugar_key AS k, count(*) AS c WHERE c > 1
RETURN 'Lugar.lugar_key' AS clave, count(*) AS duplicadas
UNION ALL
MATCH (e:EntidadContexto) WITH e.entidad_key AS k, count(*) AS c WHERE c > 1
RETURN 'EntidadContexto.entidad_key' AS clave, count(*) AS duplicadas
UNION ALL
MATCH (a:AliasLugar)     WITH a.alias_key AS k, count(*) AS c WHERE c > 1
RETURN 'AliasLugar.alias_key' AS clave, count(*) AS duplicadas
UNION ALL
MATCH (d:DirecciónCCD)   WITH d.direccion_ccd_key AS k, count(*) AS c WHERE c > 1
RETURN 'DirecciónCCD.direccion_ccd_key' AS clave, count(*) AS duplicadas;

// 2.2) DEBE DAR 0 en todas las columnas: propiedades obligatorias faltantes.
//      (Neo4j Community no soporta constraints de existencia, así que esto se
//      controla por query.)
MATCH (p:Persona)
RETURN count(CASE WHEN p.nombre IS NULL OR trim(p.nombre) = '' THEN 1 END) AS persona_sin_nombre,
       count(CASE WHEN p.fuente IS NULL THEN 1 END) AS persona_sin_fuente,
       count(CASE WHEN p.genero IS NULL THEN 1 END) AS persona_sin_genero;

// 2.3) DEBE DAR 0 en todas las columnas: combinaciones de rol imposibles.
MATCH (p:Persona)
RETURN count(CASE WHEN p:Victima  AND p:Represor THEN 1 END) AS victima_y_represor,
       count(CASE WHEN p:Complice AND NOT p:Represor THEN 1 END) AS complice_sin_represor,
       count(CASE WHEN p:Nietx    AND p:Represor THEN 1 END) AS nietx_y_represor;

// 2.4) DEBE DAR 0: nodos de contexto sin subtipo (Org / Institución /
//      AliasPersona) o con más de uno.
MATCH (e:EntidadContexto)
WITH e, size([x IN labels(e) WHERE x IN ['Org','Institución','AliasPersona']]) AS subtipos
RETURN count(CASE WHEN subtipos = 0 THEN 1 END) AS sin_subtipo,
       count(CASE WHEN subtipos > 1 THEN 1 END) AS con_varios_subtipos;

// 2.5) DEBE DAR 0: auto-relaciones (una persona pariente/represor de sí misma).
//      2026-09-11: 1 caso, `HIJE_DE` sobre "Ponce, Enrique" (detalles_personas).
MATCH (a)-[r]->(a)
RETURN type(r) AS relacion, count(*) AS auto_relaciones, collect(a.nombre)[0..5] AS muestra
ORDER BY auto_relaciones DESC;


// ---------------------------------------------------------------------
// 3. RESPONSABILIDAD PENAL (invariante del fix V1.3 / hallazgo C1)
// ---------------------------------------------------------------------

// 3.1) DEBE DAR 0 en ambas columnas: TORTURO_A se emite sólo si la sentencia
//      imputa tormentos a ese par, y IMPUTADO_POR sólo si NO los imputa.
//      Ojo: la fuente escribe tanto "Tormentos" como "Tormentos seguidos de
//      muerte", por eso se compara con CONTAINS y no con igualdad.
MATCH ()-[t:TORTURO_A]->()
WITH count(CASE WHEN none(d IN t.delitos WHERE d CONTAINS 'Tormentos') THEN 1 END) AS torturo_a_sin_tormentos
MATCH ()-[i:IMPUTADO_POR]->()
RETURN torturo_a_sin_tormentos,
       count(CASE WHEN any(d IN i.delitos WHERE d CONTAINS 'Tormentos') THEN 1 END) AS imputado_por_con_tormentos;

// 3.2) Las dos primeras columnas DEBEN DAR 0. La tercera es cobertura de la
//      fuente: 2026-09-11 son 9 aristas, todas de la sentencia
//      `minjus_sentencias:139-comisaria-de-ramos-mejia`, que viene sin fecha
//      (`DESCONOCIDA`) en el origen.
MATCH ()-[r:TORTURO_A|IMPUTADO_POR]->()
RETURN count(CASE WHEN r.delitos IS NULL OR size(r.delitos) = 0 THEN 1 END) AS sin_delitos,
       count(CASE WHEN r.origen IS NULL THEN 1 END) AS sin_origen,
       count(CASE WHEN r.fecha_sentencia IS NULL OR size(r.fecha_sentencia) <> 10 THEN 1 END) AS sin_fecha_sentencia_iso;

// 3.3) DEBE DAR 0: el extremo imputado de una arista penal siempre es
//      :Represor, y el imputado nunca es su propia víctima.
MATCH (a)-[r:TORTURO_A|IMPUTADO_POR]->(b)
RETURN count(CASE WHEN NOT a:Represor THEN 1 END) AS imputado_sin_label_represor,
       count(CASE WHEN a = b THEN 1 END) AS imputado_de_si_mismo;

// 3.4) COBERTURA: represores sin fuerza/estructura declarada.
//      2026-09-11: 261 de 1.691 (185 de juicios_condenados, 76 de MinJus).
//      Es esperable: el centinela "SIN ESPECIFICAR" ya no fabrica un :Org
//      (fix V1.3 / hallazgo I3d), queda como `Persona.fuerza` en crudo.
MATCH (r:Represor)
WHERE NOT (r)-[:PARTE_DE]->(:Org)
RETURN r.fuente AS fuente, count(*) AS represores_sin_org, collect(DISTINCT r.fuerza)[0..5] AS valores_crudos
ORDER BY represores_sin_org DESC;

// 3.5) DEBE DAR 0: centinelas materializados como organización real
//      (regresión del fix V1.3 / hallazgo I3d).
MATCH (o:Org)
WHERE toUpper(o.nombre) IN ['SIN ESPECIFICAR', 'CIVIL', 'POLICIA (SIN ESPECIFICAR)', 'NO CONSTA', 'DESCONOCIDA']
RETURN o.nombre AS org_centinela, count { (o)<-[:PARTE_DE]-() } AS miembros;


// ---------------------------------------------------------------------
// 4. FECHAS
// ---------------------------------------------------------------------

// 4.1) COBERTURA: fechas utilizables por tipo de relación. Los valores no-ISO
//      son centinelas del modelo: 'DESCONOCIDA' (dato ausente), 'ETERNA'
//      (relación atemporal: alias, jerarquía geográfica) y 'PROBABILÍSTICA'.
MATCH ()-[r]->()
WHERE r.fecha IS NOT NULL
RETURN type(r) AS relacion,
       count(*) AS aristas,
       count(CASE WHEN size(r.fecha) = 10 THEN 1 END) AS fecha_iso,
       collect(DISTINCT CASE WHEN size(r.fecha) <> 10 THEN r.fecha END)[0..3] AS centinelas
ORDER BY aristas DESC;

// 4.2) DEBE DAR 0: valores de fecha que no son ni ISO ni un centinela conocido.
MATCH ()-[r]->()
WHERE r.fecha IS NOT NULL
  AND size(r.fecha) <> 10
  AND NOT r.fecha IN ['DESCONOCIDA', 'ETERNA', 'PROBABILÍSTICA']
RETURN type(r) AS relacion, r.fecha AS valor_inesperado, count(*) AS aristas
ORDER BY aristas DESC;

// 4.3) DEBE DAR 0: hechos fechados fuera del rango histórico plausible
//      (1969-1983) o con fecha de sentencia anterior al juicio de las Juntas.
MATCH ()-[r:SECUESTRADO_EN|ASESINADO_EN|PRESENTE_EN|PARIO_EN]->()
WHERE size(r.fecha) = 10 AND (r.fecha < '1969-01-01' OR r.fecha > '1983-12-31')
RETURN type(r) AS relacion, left(r.fecha, 4) AS anio, count(*) AS aristas
ORDER BY anio;

// 4.4) DEBE DAR 0: rangos invertidos (fecha_fin anterior a fecha).
MATCH ()-[r]->()
WHERE r.fecha_fin IS NOT NULL AND size(r.fecha) = 10 AND size(r.fecha_fin) = 10
  AND r.fecha_fin < r.fecha
RETURN type(r) AS relacion, count(*) AS rangos_invertidos;

// 4.5) DEBE DAR 0: `Persona.fecha_secuestro` mal formada.
MATCH (p:Persona)
WHERE p.fecha_secuestro IS NOT NULL AND size(p.fecha_secuestro) <> 10
RETURN p.fuente AS fuente, p.fecha_secuestro AS valor, count(*) AS personas
ORDER BY personas DESC;


// ---------------------------------------------------------------------
// 5. GEOGRAFÍA, CCDs Y DIRECCIONES
// ---------------------------------------------------------------------

// 5.1) COBERTURA: anclaje jerárquico de lugares por tipo.
//      2026-09-11 sin padre: 72 CCD, 29 PAIS (correcto), 3 INDETERMINADO y
//      1 CIUDAD (ver 5.2).
MATCH (l:Lugar)
RETURN l.tipoGeopolitico AS tipo,
       count(*) AS lugares,
       count(CASE WHEN NOT (l)-[:PARTE_DE]->(:Lugar) THEN 1 END) AS sin_padre
ORDER BY lugares DESC;

// 5.2) DEBE DAR 0: ciudades sin anclaje provincial, ordenadas por los hechos
//      que cuelgan de ellas. 2026-09-11 FALLA: "CIUDAD AUTONOMA DE BUENOS
//      AIRES" (sin tilde) quedó huérfana con 2.386 hechos encima, duplicando
//      al nodo tildado que sí cuelga de ARGENTINA. Todo roll-up por provincia
//      subcuenta CABA hasta que se unifiquen.
MATCH (l:Lugar {tipoGeopolitico:'CIUDAD'})
WHERE NOT (l)-[:PARTE_DE]->(:Lugar)
RETURN l.nombre AS lugar,
       l.lugar_key AS lugar_key,
       count { (l)<-[:SECUESTRADO_EN|ASESINADO_EN|NACIO_EN|PRESENTE_EN|PARIO_EN]-() } AS hechos
ORDER BY hechos DESC;

// 5.3) DEBE DAR 0: el mismo topónimo cargado dos veces, una de ellas sin
//      anclaje jerárquico. Es la firma del duplicado por tilde/abreviatura.
//      2026-09-11 FALLA: 1 caso, el par CABA de 5.2.
MATCH (l:Lugar)
WITH apoc.text.clean(l.nombre) AS nombre_limpio, l.tipoGeopolitico AS tipo, collect(l) AS nodos
WHERE size(nodos) > 1
  AND any(n IN nodos WHERE NOT (n)-[:PARTE_DE]->(:Lugar))
RETURN nombre_limpio, tipo,
       size(nodos) AS nodos_duplicados,
       [n IN nodos | n.lugar_key] AS claves
ORDER BY nodos_duplicados DESC;

// 5.3b) REVISIÓN (no es un error): topónimos repetidos con jerarquía distinta.
//       La mayoría son homónimos legítimos ("Capital" en 11 provincias, tres
//       "San Pedro"); sirve para vigilar la desambiguación de georef.
MATCH (l:Lugar)
WITH apoc.text.clean(l.nombre) AS nombre_limpio, l.tipoGeopolitico AS tipo, collect(l) AS nodos
WHERE size(nodos) > 1
RETURN nombre_limpio, tipo,
       size(nodos) AS nodos,
       [n IN nodos | n.lugar_key] AS claves
ORDER BY nodos DESC
LIMIT 25;

// 5.4) COBERTURA: anclaje de los CCD al territorio y a su dirección.
MATCH (c:Lugar {tipoGeopolitico:'CCD'})
RETURN count(*) AS ccd_total,
       count(CASE WHEN (c)-[:PARTE_DE]->(:Lugar) THEN 1 END) AS con_lugar_geografico,
       count(CASE WHEN (:DirecciónCCD)-[:UBICADA_EN]->(c) THEN 1 END) AS con_direccion,
       count(CASE WHEN c.zona IS NOT NULL THEN 1 END) AS con_zona_militar,
       count(CASE WHEN c.geo_point IS NOT NULL THEN 1 END) AS con_coordenadas;

// 5.5) DEBE DAR 0: direcciones huérfanas o sin dirección textual.
MATCH (d:DirecciónCCD)
RETURN count(CASE WHEN NOT (d)-[:UBICADA_EN]->(:Lugar) THEN 1 END) AS sin_anclaje,
       count(CASE WHEN d.direccionExacta IS NULL OR trim(d.direccionExacta) = '' THEN 1 END) AS sin_texto,
       count(CASE WHEN d.tipo_direccion IS NULL THEN 1 END) AS sin_tipo;

// 5.6) DEBE DAR 0: coordenadas imposibles para Argentina y su entorno
//      (control del fix V1.3 / hallazgo I5, coordenadas corruptas de EAAF).
MATCH (l:Lugar)
WHERE l.lat IS NOT NULL
  AND (l.lat > -19 OR l.lat < -56 OR l.lon > -52 OR l.lon < -76)
RETURN l.nombre AS lugar, l.lat AS lat, l.lon AS lon, l.fuente AS fuente;

// 5.7) DEBE DAR 0: ciclos en la jerarquía geográfica.
MATCH (a:Lugar)-[:PARTE_DE]->(b:Lugar)-[:PARTE_DE]->(a)
RETURN a.nombre AS lugar_a, b.nombre AS lugar_b, count(*) AS ciclos;


// ---------------------------------------------------------------------
// 6. ALIAS
// ---------------------------------------------------------------------

// 6.1) DEBE DAR 0: un mismo alias normalizado apuntando a más de un lugar
//      (colisión que arruina la desambiguación).
MATCH (a:AliasLugar)-[:ALIAS_DE]->(l:Lugar)
WITH a.alias_norm AS alias, collect(DISTINCT l.nombre) AS lugares
WHERE size(lugares) > 1
RETURN alias, lugares, size(lugares) AS colisiones
ORDER BY colisiones DESC
LIMIT 25;

// 6.2) DEBE DAR 0: alias huérfanos (de lugar y de persona).
MATCH (a:AliasLugar) WHERE NOT (a)-[:ALIAS_DE]->(:Lugar)
RETURN 'AliasLugar' AS tipo, count(*) AS huerfanos
UNION ALL
MATCH (a:AliasPersona) WHERE NOT (a)-[:IDENTIFICA_A]->(:Persona)
RETURN 'AliasPersona' AS tipo, count(*) AS huerfanos;

// 6.3) COBERTURA: alias de bajo soporte por campo de origen. Son los que
//      conviene revisar para mejorar las reglas de normalización.
MATCH (a:AliasLugar)
RETURN a.campo_fuente AS campo_origen, a.tipo AS tipo_alias, count(*) AS alias
ORDER BY alias DESC;


// ---------------------------------------------------------------------
// 7. COBERTURA POR ENTIDAD (no son errores: miden qué tan completo está el grafo)
// ---------------------------------------------------------------------

// 7.1) Personas sin ninguna relación. 2026-09-11: 707.
//      archivo_memoria aporta 303 por diseño (no tiene aristas geográficas:
//      su campo `lugar` fue descartado en la auditoría V1.3 / hallazgo C2).
MATCH (p:Persona)
WHERE NOT (p)--()
RETURN p.fuente AS fuente, count(*) AS personas_aisladas
ORDER BY personas_aisladas DESC;

// 7.2) Cobertura de hechos por víctima.
MATCH (v:Persona:Victima)
RETURN v.fuente AS fuente,
       count(*) AS victimas,
       count(CASE WHEN (v)-[:SECUESTRADO_EN]->() THEN 1 END) AS con_lugar_de_secuestro,
       count(CASE WHEN (v)-[:PRESENTE_EN]->() THEN 1 END) AS con_ccd,
       count(CASE WHEN (v)-[:ASESINADO_EN]->() THEN 1 END) AS con_lugar_de_asesinato,
       count(CASE WHEN (v)-[:PARTE_DE]->(:Org) THEN 1 END) AS con_militancia_u_org,
       count(CASE WHEN v.fecha_secuestro IS NOT NULL THEN 1 END) AS con_fecha_secuestro_propia
ORDER BY victimas DESC;

// 7.3) Entidades de contexto sin personas asociadas (ruido del extractor).
MATCH (e:EntidadContexto)
WHERE NOT (e)--()
RETURN [x IN labels(e) WHERE x <> 'EntidadContexto'][0] AS subtipo, count(*) AS sin_vinculos;

// 7.4) Cobertura de los casos de nietxs.
MATCH (n:Nietx)
RETURN n.estado AS estado,
       count(*) AS casos,
       count(CASE WHEN n.ADN <> 'DESCONOCIDA' THEN 1 END) AS con_fecha_adn,
       count(CASE WHEN (n)<-[:MADRE_DE|PADRE_DE]-() THEN 1 END) AS con_madre_o_padre_en_el_grafo
ORDER BY casos DESC;


// ---------------------------------------------------------------------
// 8. RESOLUCIÓN DE IDENTIDADES
// ---------------------------------------------------------------------

// 8.1) COBERTURA: propuestas de merge generadas por el pipeline.
MATCH (a:Persona)-[r:CANDIDATO_MERGE]->(b:Persona)
RETURN r.metodo AS metodo, r.confianza AS confianza, count(*) AS propuestas,
       round(avg(r.score_nombre), 3) AS score_promedio;

// 8.2) COBERTURA: homónimos exactos entre fuentes distintas todavía no
//      propuestos como merge. Es la cola de trabajo de identidades.
MATCH (p:Persona)
WITH toUpper(p.nombre) AS nombre, collect(p) AS fichas
WHERE size(fichas) > 1
  AND size(apoc.coll.toSet([f IN fichas | f.fuente])) > 1
  AND none(f IN fichas WHERE (f)-[:CANDIDATO_MERGE]-())
RETURN count(*) AS nombres_con_fichas_en_varias_fuentes;

// 8.3) DEBE DAR 0: propuestas de merge entre personas de roles incompatibles.
MATCH (a:Persona)-[:CANDIDATO_MERGE]-(b:Persona)
WHERE (a:Victima AND b:Represor) OR (a:Represor AND b:Victima)
RETURN a.nombre AS ficha_a, b.nombre AS ficha_b;

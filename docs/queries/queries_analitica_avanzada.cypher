// =====================================================================
// ANALÍTICA AVANZADA — modelo V1.3 (grafo sin nodo :Evento)
// =====================================================================
// Reescritas el 2026-09-11 contra el grafo vivo (bolt://localhost:17687).
//
// Diferencia con `queries_preguntas_de_interes.cypher`: aquel archivo responde
// preguntas historiográficas concretas; éste provee las piezas de análisis
// reutilizables — roll-ups territoriales, series temporales, listas de aristas
// para exportar a Gephi/QGIS y algoritmos de grafos con GDS.
//
// Recordatorios del modelo (ver README):
//   * Los hechos son relaciones fechadas, no nodos.
//   * `fecha` es STRING y admite los centinelas 'DESCONOCIDA', 'ETERNA' y
//     'PROBABILÍSTICA' -> filtrar con size(r.fecha) = 10.
//   * `Persona.edad` es STRING -> toInteger().
//   * `PRESENTE_EN.fecha` es la fecha del caso, no la de ingreso a cada CCD.


// ---------------------------------------------------------------------
// 1. ROLL-UP TERRITORIAL
// ---------------------------------------------------------------------

// 1.1) Hotspots: todos los hechos que ocurren en cada lugar, desagregados.
MATCH (p:Persona)-[h:SECUESTRADO_EN|ASESINADO_EN|PRESENTE_EN|NACIO_EN|PARIO_EN]->(l:Lugar)
RETURN l.nombre           AS lugar,
       l.tipoGeopolitico  AS tipo,
       l.zona             AS zona_militar,
       count(*)           AS hechos,
       count(DISTINCT p)  AS personas,
       count(CASE WHEN type(h) = 'SECUESTRADO_EN' THEN 1 END) AS secuestros,
       count(CASE WHEN type(h) = 'PRESENTE_EN'    THEN 1 END) AS cautiverios,
       count(CASE WHEN type(h) = 'ASESINADO_EN'   THEN 1 END) AS asesinatos
ORDER BY hechos DESC
LIMIT 60;

// 1.2) Roll-up por provincia subiendo la jerarquía PARTE_DE.
//      CAVEAT: el nodo "CIUDAD AUTONOMA DE BUENOS AIRES" (sin tilde) está
//      huérfano y arrastra 2.386 hechos que este roll-up no ve
//      (validación 5.2/5.3). Hasta unificarlo, CABA queda subcontada.
MATCH (p:Persona)-[h:SECUESTRADO_EN|ASESINADO_EN|PRESENTE_EN]->(l:Lugar)
MATCH (l)-[:PARTE_DE*0..3]->(prov:Lugar {tipoGeopolitico:'PROVINCIA'})
RETURN prov.nombre AS provincia,
       count(DISTINCT p) AS personas,
       count(*)          AS hechos,
       count(DISTINCT l) AS lugares_distintos
ORDER BY hechos DESC;

// 1.3) Matriz provincia x año de secuestro (insumo de heatmap).
MATCH (p:Persona)-[s:SECUESTRADO_EN]->(l:Lugar)
WHERE size(s.fecha) = 10
MATCH (l)-[:PARTE_DE*0..3]->(prov:Lugar {tipoGeopolitico:'PROVINCIA'})
WITH prov.nombre AS provincia, left(s.fecha, 4) AS anio, count(*) AS secuestros
WHERE anio >= '1974' AND anio <= '1983'
RETURN provincia, anio, secuestros
ORDER BY provincia, anio;

// 1.4) Peso relativo de cada zona militar sobre el total de cautiverios.
MATCH (v:Persona)-[:PRESENTE_EN]->(c:Lugar {tipoGeopolitico:'CCD'})
WITH coalesce(c.zona, '(CCD sin zona declarada)') AS zona,
     count(DISTINCT v) AS victimas,
     count(DISTINCT c) AS ccds
WITH collect({zona: zona, victimas: victimas, ccds: ccds}) AS filas,
     sum(victimas) AS total
UNWIND filas AS f
RETURN f.zona AS zona_militar,
       f.ccds AS ccds,
       f.victimas AS victimas,
       round(100.0 * f.victimas / total, 1) AS pct_del_total
ORDER BY victimas DESC;


// ---------------------------------------------------------------------
// 2. SERIES TEMPORALES
// ---------------------------------------------------------------------

// 2.1) Serie mensual de hechos fechados, por tipo.
MATCH ()-[h:SECUESTRADO_EN|ASESINADO_EN|PRESENTE_EN|PARIO_EN]->()
WHERE size(h.fecha) = 10 AND h.fecha >= '1974-01-01' AND h.fecha <= '1983-12-31'
RETURN left(h.fecha, 7) AS anio_mes,
       count(*) AS hechos,
       count(CASE WHEN type(h) = 'SECUESTRADO_EN' THEN 1 END) AS secuestros,
       count(CASE WHEN type(h) = 'ASESINADO_EN'   THEN 1 END) AS asesinatos
ORDER BY anio_mes;

// 2.2) Estacionalidad: mismo mes agregando todos los años.
MATCH ()-[s:SECUESTRADO_EN]->()
WHERE size(s.fecha) = 10 AND s.fecha >= '1976-03-24' AND s.fecha <= '1983-12-10'
RETURN substring(s.fecha, 5, 2) AS mes, count(*) AS secuestros
ORDER BY mes;

// 2.3) Ventana de actividad de cada CCD según las fechas de los casos.
//      Es una aproximación: `PRESENTE_EN.fecha` es la fecha del secuestro de
//      la víctima, no su fecha de ingreso al centro.
MATCH (v:Persona)-[p:PRESENTE_EN]->(c:Lugar {tipoGeopolitico:'CCD'})
WHERE size(p.fecha) = 10
WITH c, count(DISTINCT v) AS victimas, min(p.fecha) AS primera, max(p.fecha) AS ultima
RETURN c.nombre AS ccd,
       c.zona   AS zona_militar,
       victimas,
       primera,
       ultima,
       duration.inDays(date(primera), date(ultima)).days AS dias_de_actividad
ORDER BY victimas DESC
LIMIT 40;

// 2.4) Rezago entre el hecho y la condena: años transcurridos hasta la
//      sentencia, por víctima con fecha de secuestro conocida.
MATCH (r:Represor)-[x:TORTURO_A|IMPUTADO_POR]->(v:Persona)
WHERE size(x.fecha_sentencia) = 10 AND v.fecha_secuestro IS NOT NULL
WITH toInteger(left(x.fecha_sentencia, 4)) - toInteger(left(v.fecha_secuestro, 4)) AS anios_hasta_sentencia
RETURN min(anios_hasta_sentencia) AS minimo,
       round(avg(anios_hasta_sentencia), 1) AS promedio,
       max(anios_hasta_sentencia) AS maximo,
       count(*) AS pares_imputado_victima;


// ---------------------------------------------------------------------
// 3. REDES (listas de aristas listas para exportar)
// ---------------------------------------------------------------------

// 3.1) Red CCD - CCD ponderada por víctimas compartidas (circuitos de traslado).
MATCH (v:Persona)-[:PRESENTE_EN]->(a:Lugar {tipoGeopolitico:'CCD'}),
      (v)-[:PRESENTE_EN]->(b:Lugar {tipoGeopolitico:'CCD'})
WHERE a.lugar_key < b.lugar_key
WITH a, b, count(DISTINCT v) AS peso
WHERE peso >= 5
RETURN a.nombre AS source, b.nombre AS target, peso AS weight,
       a.zona AS zona_source, b.zona AS zona_target
ORDER BY weight DESC;

// 3.2) Red represor - represor ponderada por víctimas en común.
MATCH (r1:Represor)-[:TORTURO_A|IMPUTADO_POR]->(v:Persona)<-[:TORTURO_A|IMPUTADO_POR]-(r2:Represor)
WHERE r1.persona_key < r2.persona_key
WITH r1, r2, count(DISTINCT v) AS peso
WHERE peso >= 25
RETURN r1.nombre AS source, r2.nombre AS target, peso AS weight
ORDER BY weight DESC
LIMIT 500;

// 3.3) Grado y alcance de cada represor (centralidad simple, sin GDS).
MATCH (r:Represor)-[x:TORTURO_A|IMPUTADO_POR]->(v:Persona)
OPTIONAL MATCH (v)-[:PRESENTE_EN]->(c:Lugar {tipoGeopolitico:'CCD'})
RETURN r.nombre AS represor,
       count(DISTINCT v)       AS victimas,
       count(DISTINCT x.origen) AS sentencias,
       count(DISTINCT c)       AS ccds_alcanzados,
       count(DISTINCT c.zona)  AS zonas_militares
ORDER BY victimas DESC
LIMIT 50;

// 3.4) Red persona - organización (bipartita) para proyecciones de militancia.
MATCH (p:Persona)-[:PARTE_DE]->(o:Org)
RETURN p.nombre AS persona,
       CASE WHEN p:Represor THEN 'represor' ELSE 'victima' END AS rol,
       o.nombre AS organizacion,
       coalesce(o.tipoOrg, 'MILITANCIA') AS tipo_org
LIMIT 1000;


// ---------------------------------------------------------------------
// 4. GRAPH DATA SCIENCE (requiere plugin GDS; ver README)
// ---------------------------------------------------------------------

// 4.1) Proyectar la red de imputaciones (Persona - TORTURO_A - Persona) en
//      memoria. Dropear antes por si quedó de una corrida anterior.
CALL gds.graph.exists('zona4_penal') YIELD exists
WITH exists WHERE exists
CALL gds.graph.drop('zona4_penal') YIELD graphName
RETURN graphName AS proyeccion_eliminada;

CALL gds.graph.project(
  'zona4_penal',
  'Persona',
  { IMPUTACION: { type: 'TORTURO_A', orientation: 'UNDIRECTED' } }
) YIELD graphName, nodeCount, relationshipCount
RETURN graphName, nodeCount, relationshipCount;

// 4.2) Comunidades de Louvain sobre esa red: agrupan represores y víctimas que
//      comparten causa, es decir, circuitos represivos regionales.
CALL gds.louvain.stream('zona4_penal')
YIELD nodeId, communityId
WITH communityId, collect(gds.util.asNode(nodeId)) AS miembros
WITH communityId,
     size(miembros) AS integrantes,
     size([m IN miembros WHERE m:Represor]) AS represores,
     size([m IN miembros WHERE m:Victima])  AS victimas,
     [m IN miembros WHERE m:Represor | m.nombre][0..6] AS muestra_represores
WHERE integrantes >= 20
RETURN communityId, integrantes, represores, victimas, muestra_represores
ORDER BY integrantes DESC;

// 4.3) PageRank sobre la misma red: qué imputados son estructuralmente
//      centrales, no sólo los que acumulan más víctimas.
CALL gds.pageRank.stream('zona4_penal')
YIELD nodeId, score
WITH gds.util.asNode(nodeId) AS p, score
WHERE p:Represor
RETURN p.nombre AS represor, round(score, 3) AS pagerank
ORDER BY pagerank DESC
LIMIT 30;

// 4.4) Liberar la proyección al terminar.
CALL gds.graph.drop('zona4_penal', false) YIELD graphName
RETURN graphName AS proyeccion_eliminada;

// 4.5) Núcleos familiares: componentes conexas de los vínculos de parentesco.
CALL gds.graph.project(
  'zona4_familias',
  'Persona',
  {
    PAREJA:  { type: 'PAREJA_DE',  orientation: 'UNDIRECTED' },
    HERMANX: { type: 'HERMANX_DE', orientation: 'UNDIRECTED' },
    MADRE:   { type: 'MADRE_DE',   orientation: 'UNDIRECTED' },
    PADRE:   { type: 'PADRE_DE',   orientation: 'UNDIRECTED' },
    HIJE:    { type: 'HIJE_DE',    orientation: 'UNDIRECTED' }
  }
) YIELD graphName, nodeCount, relationshipCount
RETURN graphName, nodeCount, relationshipCount;

CALL gds.wcc.stream('zona4_familias')
YIELD nodeId, componentId
WITH componentId, collect(gds.util.asNode(nodeId)) AS miembros
WITH componentId, [m IN miembros | m.nombre] AS nombres, size(miembros) AS integrantes
WHERE integrantes >= 4
RETURN componentId, integrantes, nombres
ORDER BY integrantes DESC
LIMIT 25;

CALL gds.graph.drop('zona4_familias', false) YIELD graphName
RETURN graphName AS proyeccion_eliminada;


// ---------------------------------------------------------------------
// 5. PERFILES Y COBERTURA APLICADA
// ---------------------------------------------------------------------

// 5.1) Pirámide etaria por género (sólo detalles_personas tiene estos campos).
MATCH (v:Persona:Victima)
WHERE v.edad IS NOT NULL
WITH v, (toInteger(v.edad) / 5) * 5 AS franja
RETURN franja AS edad_desde,
       franja + 4 AS edad_hasta,
       count(*) AS victimas,
       count(CASE WHEN v.genero = 'FEMENINO'  THEN 1 END) AS mujeres,
       count(CASE WHEN v.genero = 'MASCULINO' THEN 1 END) AS varones
ORDER BY edad_desde;

// 5.2) Militancia x año de secuestro (matriz para heatmap).
MATCH (v:Persona:Victima)-[:PARTE_DE]->(o:Org)
WHERE o.tipoOrg IS NULL AND v.fecha_secuestro IS NOT NULL
RETURN o.nombre AS organizacion, left(v.fecha_secuestro, 4) AS anio, count(*) AS victimas
ORDER BY organizacion, anio;

// 5.3) Trabajo y estudio: instituciones con más víctimas, en un solo listado.
MATCH (v:Persona:Victima)-[r:TRABAJO_EN|ESTUDIO_EN]->(i:Institución)
WITH i, type(r) AS vinculo, count(DISTINCT v) AS victimas
WHERE victimas >= 3
RETURN i.nombre AS institucion, vinculo, victimas
ORDER BY victimas DESC
LIMIT 50;

// 5.4) Capa de mapa: lugares con coordenadas y su peso.
MATCH (l:Lugar)
WHERE l.geo_point IS NOT NULL
OPTIONAL MATCH (p:Persona)-[h:SECUESTRADO_EN|ASESINADO_EN|PRESENTE_EN]->(l)
RETURN l.nombre AS lugar,
       l.tipoGeopolitico AS tipo,
       l.geo_point.latitude  AS lat,
       l.geo_point.longitude AS lon,
       count(h) AS hechos,
       count(DISTINCT p) AS personas
ORDER BY hechos DESC;

// 5.5) Capa de mapa de CCDs con su dirección exacta (export a GeoJSON).
MATCH (c:Lugar {tipoGeopolitico:'CCD'})<-[:UBICADA_EN]-(d:DirecciónCCD)
OPTIONAL MATCH (v:Persona)-[:PRESENTE_EN]->(c)
RETURN c.nombre AS ccd,
       c.zona AS zona_militar,
       c.emplazamiento_propiedad AS fuerza_a_cargo,
       d.direccionExacta AS direccion,
       d.coordenadas AS coordenadas,
       count(DISTINCT v) AS victimas
ORDER BY victimas DESC;

// 5.6) Qué porción de cada análisis se apoya en datos fechados (para poner al
//      pie de cualquier gráfico de series).
MATCH ()-[h:SECUESTRADO_EN|ASESINADO_EN|PRESENTE_EN|PARIO_EN]->()
RETURN type(h) AS hecho,
       count(*) AS aristas,
       count(CASE WHEN size(h.fecha) = 10 THEN 1 END) AS con_fecha_iso,
       round(100.0 * count(CASE WHEN size(h.fecha) = 10 THEN 1 END) / count(*), 1) AS pct_fechado
ORDER BY aristas DESC;

// =====================================================================
// PREGUNTAS DE INTERÉS — consultas de investigación sobre el grafo V1.3
// =====================================================================
// Cada bloque lleva la pregunta en lenguaje natural que responde.
// Verificadas en vivo contra bolt://localhost:17687 (2026-09-11).
//
// Notas de modelo imprescindibles para leer/adaptar estas queries:
//   * Las fechas viajan como STRING en las relaciones (`fecha`, `fecha_fin`,
//     `fecha_sentencia`) y admiten el centinela 'DESCONOCIDA'. Filtrar
//     siempre con size(x.fecha) = 10 antes de hacer date(x.fecha).
//   * `Persona.edad` también es STRING -> usar toInteger().
//   * La fecha del secuestro vive en dos lugares según la fuente:
//       - detalles_personas  -> propiedad `fecha` de [:SECUESTRADO_EN]
//       - minjus_victimas / archivo_memoria -> `Persona.fecha_secuestro`
//   * `Persona.genero` y `Persona.edad` sólo tienen valor real en
//     detalles_personas; el resto de las fuentes traen 'INDETERMINADO'/null.
//   * Org con tipoOrg='FUERZA' = fuerza represiva; Org con tipoOrg null =
//     militancia política/gremial/estudiantil de la víctima.
//   * TORTURO_A se emite sólo cuando la sentencia imputa tormentos a ese par
//     imputado-víctima; el resto de los cargos van en IMPUTADO_POR.


// ---------------------------------------------------------------------
// A. TERRITORIO Y CENTROS CLANDESTINOS
// ---------------------------------------------------------------------

// 1) ¿Cuáles son los CCD por los que pasaron más personas, y en qué zona
//    militar y localidad estaban?
MATCH (v:Persona)-[:PRESENTE_EN]->(c:Lugar {tipoGeopolitico:'CCD'})
WITH c, count(DISTINCT v) AS victimas
OPTIONAL MATCH (c)-[:PARTE_DE]->(g:Lugar)
OPTIONAL MATCH (d:DirecciónCCD)-[:UBICADA_EN]->(c)
RETURN c.nombre                AS ccd,
       c.zona                  AS zona_militar,
       c.area                  AS area,
       c.emplazamiento_propiedad AS fuerza_a_cargo,
       g.nombre                AS localidad,
       d.direccionExacta       AS direccion,
       victimas
ORDER BY victimas DESC
LIMIT 30;

// 2) ¿Qué muestra el grafo sobre la Zona 4 (Campo de Mayo y el conurbano
//    norte), que es el foco del proyecto?
MATCH (c:Lugar {tipoGeopolitico:'CCD'})
WHERE c.zona STARTS WITH 'Zona 4'
OPTIONAL MATCH (v:Persona)-[:PRESENTE_EN]->(c)
RETURN c.nombre                  AS ccd,
       c.area                    AS area,
       c.emplazamiento_propiedad AS fuerza_a_cargo,
       count(DISTINCT v)         AS victimas_registradas
ORDER BY victimas_registradas DESC;

// 3) ¿Qué CCD funcionaban como circuito? (pares de centros por los que pasó
//    la misma gente: evidencia de traslados sistemáticos)
MATCH (v:Persona)-[:PRESENTE_EN]->(a:Lugar {tipoGeopolitico:'CCD'}),
      (v)-[:PRESENTE_EN]->(b:Lugar {tipoGeopolitico:'CCD'})
WHERE a.lugar_key < b.lugar_key
WITH a, b, count(DISTINCT v) AS victimas_compartidas
WHERE victimas_compartidas >= 10
RETURN a.nombre AS ccd_a, a.zona AS zona_a,
       b.nombre AS ccd_b, b.zona AS zona_b,
       victimas_compartidas
ORDER BY victimas_compartidas DESC
LIMIT 40;

// 4) ¿Quiénes pasaron por más centros clandestinos?
//    OJO: `PRESENTE_EN.fecha` es la fecha del caso (secuestro), no la fecha de
//    ingreso a cada CCD -> se repite igual en todos los centros de una misma
//    persona. El grafo dice POR DÓNDE pasó cada quien, no en qué orden.
MATCH (v:Persona)-[p:PRESENTE_EN]->(c:Lugar {tipoGeopolitico:'CCD'})
WITH v, min(p.fecha) AS fecha_caso,
     count(DISTINCT c) AS ccds,
     collect(DISTINCT {ccd: c.nombre, zona: c.zona}) AS centros
WHERE ccds >= 4
RETURN v.nombre AS persona, fecha_caso, ccds, centros
ORDER BY ccds DESC
LIMIT 30;

// 5) ¿Hubo traslados entre jurisdicciones? (secuestrades en una localidad y
//    vistes en un CCD de otra)
MATCH (v:Persona)-[:SECUESTRADO_EN]->(origen:Lugar),
      (v)-[:PRESENTE_EN]->(c:Lugar {tipoGeopolitico:'CCD'})-[:PARTE_DE]->(destino:Lugar)
WHERE origen.lugar_key <> destino.lugar_key
RETURN origen.nombre  AS localidad_secuestro,
       c.nombre       AS ccd,
       destino.nombre AS localidad_ccd,
       c.zona         AS zona_ccd,
       count(DISTINCT v) AS personas
ORDER BY personas DESC
LIMIT 30;


// ---------------------------------------------------------------------
// B. RESPONSABILIDAD Y JUSTICIA
// ---------------------------------------------------------------------

// 6) ¿Qué represores acumulan más víctimas imputadas por sentencia, y de qué
//    fuerza eran?
MATCH (r:Persona:Represor)-[x:TORTURO_A|IMPUTADO_POR]->(v:Persona)
OPTIONAL MATCH (r)-[:PARTE_DE]->(o:Org)
RETURN r.nombre                  AS represor,
       collect(DISTINCT o.nombre) AS fuerzas,
       count(DISTINCT v)         AS victimas,
       count(DISTINCT CASE WHEN type(x) = 'TORTURO_A' THEN v END) AS victimas_con_tormentos,
       count(DISTINCT x.origen)  AS sentencias
ORDER BY victimas DESC
LIMIT 30;

// 7) ¿Cómo se reparte la responsabilidad entre las fuerzas?
MATCH (r:Represor)-[:PARTE_DE]->(o:Org {tipoOrg:'FUERZA'})
OPTIONAL MATCH (r)-[x:TORTURO_A|IMPUTADO_POR]->(v:Persona)
RETURN o.nombre           AS fuerza,
       count(DISTINCT r)  AS represores_condenados,
       count(DISTINCT v)  AS victimas_alcanzadas,
       round(1.0 * count(DISTINCT v) / count(DISTINCT r), 1) AS victimas_por_represor
ORDER BY victimas_alcanzadas DESC
LIMIT 25;

// 8) ¿Quiénes operaban juntos? (pares de represores imputados por las mismas
//    víctimas: reconstruye la patota / el grupo de tareas)
MATCH (r1:Represor)-[:TORTURO_A|IMPUTADO_POR]->(v:Persona)<-[:TORTURO_A|IMPUTADO_POR]-(r2:Represor)
WHERE r1.persona_key < r2.persona_key
WITH r1, r2, count(DISTINCT v) AS victimas_en_comun
WHERE victimas_en_comun >= 50
RETURN r1.nombre AS represor_a, r2.nombre AS represor_b, victimas_en_comun
ORDER BY victimas_en_comun DESC
LIMIT 40;

// 9) ¿Qué delitos concentran las condenas?
MATCH (:Represor)-[x:TORTURO_A|IMPUTADO_POR]->(:Persona)
UNWIND x.delitos AS delito
RETURN delito,
       count(*)                 AS imputaciones,
       count(DISTINCT x.origen) AS sentencias_que_lo_incluyen
ORDER BY imputaciones DESC
LIMIT 25;

// 10) ¿A qué ritmo llegó la justicia? (sentencias, represores y víctimas
//     alcanzadas por año de sentencia)
MATCH (r:Represor)-[x:TORTURO_A|IMPUTADO_POR]->(v:Persona)
WHERE x.fecha_sentencia IS NOT NULL AND size(x.fecha_sentencia) = 10
RETURN left(x.fecha_sentencia, 4) AS anio,
       count(DISTINCT x.origen)   AS sentencias,
       count(DISTINCT r)          AS represores,
       count(DISTINCT v)          AS victimas
ORDER BY anio;

// 11) ¿Dónde está la brecha de impunidad? (CCD con muchas víctimas
//     registradas pero baja proporción de víctimas con algún imputado)
MATCH (v:Persona)-[:PRESENTE_EN]->(c:Lugar {tipoGeopolitico:'CCD'})
WITH c, collect(DISTINCT v) AS victimas
WITH c, victimas,
     [v IN victimas WHERE exists((:Represor)-[:TORTURO_A|IMPUTADO_POR]->(v))] AS con_causa
WHERE size(victimas) >= 20
RETURN c.nombre AS ccd,
       c.zona   AS zona_militar,
       size(victimas)   AS victimas,
       size(con_causa)  AS victimas_con_imputado,
       round(100.0 * size(con_causa) / size(victimas), 1) AS pct_con_imputado
ORDER BY pct_con_imputado ASC, victimas DESC
LIMIT 25;

// 12) ¿Quiénes son los cómplices civiles condenados y desde qué estructura
//     colaboraron? (jueces, personal civil de inteligencia, Triple A...)
//     Nota: los 197 :Complice vienen de juicios_condenados, que no trae el par
//     imputado-víctima; por eso no cuelgan de ellos aristas TORTURO_A /
//     IMPUTADO_POR (esas vienen sólo de las sentencias de MinJus GBA).
MATCH (c:Persona:Complice)
OPTIONAL MATCH (c)-[:PARTE_DE]->(o:Org)
WITH coalesce(o.nombre, '(sin estructura declarada)') AS estructura,
     collect(c.nombre) AS complices
RETURN estructura,
       size(complices)   AS cantidad,
       complices[0..10]  AS muestra
ORDER BY cantidad DESC;


// ---------------------------------------------------------------------
// C. PERFIL DE LAS VÍCTIMAS
// ---------------------------------------------------------------------

// 13) ¿Cómo se distribuyen los secuestros en el tiempo? (curva mensual del
//     terror, 1974-1983)
MATCH ()-[s:SECUESTRADO_EN]->()
WHERE size(s.fecha) = 10 AND s.fecha >= '1974-01-01' AND s.fecha <= '1983-12-31'
RETURN left(s.fecha, 4) AS anio,
       substring(s.fecha, 5, 2) AS mes,
       count(*) AS secuestros
ORDER BY anio, mes;

// 14) ¿Qué edad y qué género tenían las personas secuestradas, año por año?
MATCH (v:Persona:Victima)-[s:SECUESTRADO_EN]->()
WHERE size(s.fecha) = 10 AND v.edad IS NOT NULL
WITH left(s.fecha, 4) AS anio, v
WHERE anio >= '1974' AND anio <= '1983'
RETURN anio,
       count(*)                        AS victimas,
       round(avg(toInteger(v.edad)), 1) AS edad_promedio,
       count(CASE WHEN toInteger(v.edad) < 18 THEN 1 END) AS menores_de_18,
       round(100.0 * count(CASE WHEN v.genero = 'FEMENINO' THEN 1 END) / count(*), 1) AS pct_mujeres
ORDER BY anio;

// 15) ¿Qué organizaciones políticas, gremiales y estudiantiles fueron las más
//     golpeadas, y cuándo?
MATCH (v:Persona:Victima)-[:PARTE_DE]->(o:Org)
WHERE o.tipoOrg IS NULL
WITH o, v, CASE WHEN v.fecha_secuestro IS NOT NULL THEN left(v.fecha_secuestro, 4) END AS anio
RETURN o.nombre       AS organizacion,
       count(v)       AS victimas,
       count(CASE WHEN anio IN ['1976','1977'] THEN 1 END) AS victimas_1976_1977,
       min(anio)      AS primer_anio,
       max(anio)      AS ultimo_anio
ORDER BY victimas DESC
LIMIT 30;

// 16) ¿En qué empresas y lugares de trabajo se concentró la represión?
//     (rastro de complicidad empresarial)
MATCH (v:Persona:Victima)-[:TRABAJO_EN]->(i:Institución)
WITH i, collect(DISTINCT v) AS vs
WHERE size(vs) >= 4
RETURN i.nombre       AS lugar_de_trabajo,
       size(vs)       AS victimas,
       [v IN vs | v.nombre][0..8] AS muestra
ORDER BY victimas DESC
LIMIT 30;

// 17) ¿Qué escuelas y facultades perdieron más estudiantes?
MATCH (v:Persona:Victima)-[:ESTUDIO_EN]->(i:Institución)
WITH i, count(DISTINCT v) AS victimas
WHERE victimas >= 3
RETURN i.nombre AS institucion_educativa, victimas
ORDER BY victimas DESC
LIMIT 30;


// ---------------------------------------------------------------------
// D. FAMILIAS, NACIMIENTOS EN CAUTIVERIO E IDENTIDAD
// ---------------------------------------------------------------------

// 18) ¿A qué familias se llevaron completas? (parientes secuestrades con
//     menos de 4 días de diferencia)
MATCH (a:Persona)-[f:HERMANX_DE|PAREJA_DE|MADRE_DE|PADRE_DE|HIJE_DE]->(b:Persona)
WHERE a.persona_key < b.persona_key
MATCH (a)-[sa:SECUESTRADO_EN]->(la:Lugar),
      (b)-[sb:SECUESTRADO_EN]->(lb:Lugar)
WHERE size(sa.fecha) = 10 AND size(sb.fecha) = 10
  AND abs(duration.inDays(date(sa.fecha), date(sb.fecha)).days) <= 3
RETURN a.nombre AS persona_a, b.nombre AS persona_b, type(f) AS vinculo,
       sa.fecha AS fecha_a, sb.fecha AS fecha_b,
       la.nombre AS lugar_a, lb.nombre AS lugar_b
ORDER BY fecha_a
LIMIT 60;

// 19) ¿Dónde hubo partos en cautiverio, y qué se sabe de esas madres?
MATCH (m:Persona)-[p:PARIO_EN]->(c:Lugar)
OPTIONAL MATCH (m)-[:MADRE_DE]->(h:Persona)
RETURN c.nombre  AS lugar_del_parto,
       c.zona    AS zona_militar,
       p.fecha   AS fecha_aprox,
       p.precision_fecha AS precision,
       m.nombre  AS madre,
       collect(DISTINCT h.nombre) AS hijes_registrades
ORDER BY lugar_del_parto, fecha_aprox;

// 20) ¿Cómo viene la búsqueda de nietes: cuántes siguen sin aparecer y a qué
//     ritmo se produjeron las restituciones?
MATCH (n:Nietx)
RETURN n.estado AS estado,
       count(*) AS casos,
       count(CASE WHEN n.ADN <> 'DESCONOCIDA' THEN 1 END) AS con_fecha_de_adn
ORDER BY casos DESC;

// 20b) Restituciones por década (año extraído del texto del campo ADN)
MATCH (n:Nietx)
WHERE n.ADN IS NOT NULL AND n.ADN <> 'DESCONOCIDA'
WITH toInteger(right(n.ADN, 4)) AS anio, n
WHERE anio IS NOT NULL
RETURN (anio / 10) * 10 AS decada, count(*) AS restituciones
ORDER BY decada;

// 21) ¿A quiénes nombran los testimonios sólo por su apodo o nombre de
//     guerra? (837 alias cargados; insumo directo para identificación)
MATCH (a:AliasPersona)-[:IDENTIFICA_A]->(p:Persona)
OPTIONAL MATCH (p)-[:PRESENTE_EN]->(c:Lugar {tipoGeopolitico:'CCD'})
RETURN p.nombre  AS persona,
       a.alias   AS alias,
       a.fuente  AS fuente_del_alias,
       collect(DISTINCT c.nombre) AS ccds
ORDER BY persona
LIMIT 50;

// 22) ¿Qué fichas de distintas fuentes podrían ser la misma persona?
//     (homónimos exactos entre fuentes: cola de trabajo para resolución de
//     identidades, complemento de las aristas CANDIDATO_MERGE ya existentes)
MATCH (p:Persona)
WITH toUpper(p.nombre) AS nombre, collect(p) AS fichas
WHERE size(fichas) > 1
  AND size(apoc.coll.toSet([f IN fichas | f.fuente])) > 1
RETURN nombre,
       size(fichas) AS fichas_en_el_grafo,
       [f IN fichas | f.fuente] AS fuentes,
       [f IN fichas | coalesce(f.fecha_secuestro, f.edad, '(sin dato)')] AS pistas
ORDER BY fichas_en_el_grafo DESC, nombre
LIMIT 50;

// 23) ¿Qué pares ya marcó el pipeline como probable misma persona, y con qué
//     confianza? (aristas CANDIDATO_MERGE)
MATCH (a:Persona)-[r:CANDIDATO_MERGE]->(b:Persona)
RETURN a.nombre AS ficha_a, a.fuente AS fuente_a,
       b.nombre AS ficha_b, b.fuente AS fuente_b,
       r.metodo AS metodo, r.score_nombre AS score, r.confianza AS confianza
ORDER BY score DESC;

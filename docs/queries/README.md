# Neo4j: carga del grafo y potencial analitico

Este directorio documenta el modelo grafo de ZONA4 y provee consultas Cypher para validacion y analitica.

## Objetivo

El pipeline unifica fuentes heterogeneas de personas, lugares, CCDs, organizaciones y casos de nietxs en un grafo consultable. El foco es:

- trazabilidad de hechos por persona (los hechos son relaciones fechadas, no nodos)
- normalizacion geografica jerarquica
- integracion de CCDs dentro de la misma taxonomia de lugar
- preservacion de direcciones especificas sin contaminar la capa de toponimos

## Flujo general de carga

El pipeline principal esta en src/zona4_graph_loader/pipeline/load_graph.py.

1. Lee las fuentes JSON/CSV (detalles_personas, nietxs, ccds y las de
   `data/sources/`: archivo_memoria, minjus victimas/imputados/sentencias/ccds,
   juicios_condenados, eaaf_lugares).
2. Construye entidades y relaciones por capas (un builder por fuente) sobre un
   modelo canonico comun (CDM).
3. Normaliza lugares con reglas + georef + fallbacks contextuales.
4. Integra CCDs como Lugar con `tipoGeopolitico='CCD'` y los ancla
   jerarquicamente al Lugar geografico cuando es posible.
5. Extrae `DirecciónCCD` cuando hay direccion puntual del centro.
6. Resuelve identidades y propone aristas CANDIDATO_MERGE.
7. Escribe nodos/relaciones en Neo4j por lotes.
8. Ejecuta QA final de cobertura y consistencia.

## Comando tipico de carga limpia

Ejemplo local:

```bash
PYTHONPATH=src \
NEO4J_URI=bolt://localhost:17687 \
NEO4J_USER=neo4j \
NEO4J_PASSWORD=zona4local \
NEO4J_DATABASE=neo4j \
.venv/bin/python -m zona4_graph_loader.cli --clean-project
```

Notas:

- --clean-project limpia nodos del proyecto y recarga.
- --clean-all limpia toda la base.
- El pipeline crea constraints e indices si no existen.

## APOC y GDS

Para entorno local con Docker, este repo habilita ambos plugins en `docker-compose.yml`:

- APOC
- Graph Data Science (GDS)

Verificacion rapida en Neo4j Browser:

```cypher
RETURN apoc.version() AS apoc_version;
RETURN gds.version() AS gds_version;
```

Si falla por plugin ausente:

1. Reiniciar contenedor con recreacion: `docker compose up -d --force-recreate`.
2. Revisar logs: `docker logs neo4j-zona4 | grep -Ei "apoc|gds|plugin"`.

Nota sobre Aura:

- AuraDB no permite instalar plugins arbitrarios.
- APOC Core suele estar disponible de forma parcial.
- GDS requiere AuraDS o una instancia autogestionada de Neo4j con plugin GDS.

## Esquema conceptual resumido

Verificado en vivo contra `bolt://localhost:17687` (2026-09-11): 21.426 nodos
y 42.068 relaciones. El modelo NO tiene nodo de evento: los hechos se
representan como relaciones fechadas entre Persona y Lugar / EntidadContexto.

### Nodos principales

| Label | Nodos | Notas |
| ----- | ----- | ----- |
| `Persona` | 14.691 | clave `persona_key`; se subtipifica con `:Victima` (12.508), `:Represor` (1.691), `:Complice` (197, siempre tambien `:Represor`) y `:Nietx` (392) |
| `Lugar` | 1.345 | clave `lugar_key`; `tipoGeopolitico` in PAIS / PROVINCIA / DEPARTAMENTO / CIUDAD / CCD / CEMENTERIO / ENTERRAMIENTO / INDETERMINADO |
| `AliasLugar` | 1.782 | clave `alias_key` |
| `EntidadContexto` | 3.217 | clave `entidad_key`; se subtipifica con `:Institución` (1.596), `:AliasPersona` (837) y `:Org` (784, de las cuales 42 con `tipoOrg='FUERZA'`) |
| `DirecciónCCD` | 391 | clave `direccion_ccd_key`; `direccionExacta`, `tipo_direccion`, `coordenadas` |

Los cinco labels con constraint de unicidad son `Persona`, `Lugar`,
`AliasLugar`, `EntidadContexto` y `DirecciónCCD`.

### Relaciones principales

Hechos sobre la persona (todas llevan `origen` y `fecha`):

- `(Persona)-[:SECUESTRADO_EN]->(Lugar)` — 7.133
- `(Persona)-[:PRESENTE_EN]->(Lugar {tipoGeopolitico:'CCD'})` — 3.512
- `(Persona)-[:ASESINADO_EN]->(Lugar)` — 1.667
- `(Persona)-[:NACIO_EN]->(Lugar)` — 2.158
- `(Persona)-[:PARIO_EN]->(Lugar)` — 39

Responsabilidad penal (ademas de `origen`/`fecha`, llevan `delitos` y
`fecha_sentencia`):

- `(Persona:Represor)-[:TORTURO_A]->(Persona)` — 11.511, solo cuando la
  sentencia imputa tormentos a ese par imputado-victima
- `(Persona:Represor)-[:IMPUTADO_POR]->(Persona)` — 3.347, el resto de los
  cargos (homicidio, sustraccion de menor, privacion ilegitima, etc.)

Contexto y pertenencia:

- `(Persona)-[:PARTE_DE]->(EntidadContexto)` — 3.040 (militancia o fuerza)
- `(Persona)-[:TRABAJO_EN]->(Institución)` — 1.327
- `(Persona)-[:ESTUDIO_EN]->(Institución)` — 610
- `(AliasPersona)-[:IDENTIFICA_A]->(Persona)` — 837

Vinculos entre personas: `PAREJA_DE` (1.558), `HERMANX_DE` (805),
`MADRE_DE` (420), `PADRE_DE` (357), `CUÑADX_DE` (178), `HIJE_DE` (109),
`SUEGRX_DE` (20), `YERNX_NUERX_DE` (20), `ABUELX_DE` (3) y
`CANDIDATO_MERGE` (4, propuestas de resolucion de identidades).

Geografia: `(Lugar)-[:PARTE_DE]->(Lugar)` (1.240), `(AliasLugar)-[:ALIAS_DE]->(Lugar)`
(1.782) y `(DirecciónCCD)-[:UBICADA_EN]->(Lugar)` (391).

### Fechas: advertencias

- Las fechas viajan como STRING en las relaciones (`fecha`, `fecha_fin`,
  `fecha_sentencia`) y admiten el centinela `'DESCONOCIDA'`. Filtrar con
  `size(r.fecha) = 10` antes de hacer `date(r.fecha)`.
- `PRESENTE_EN.fecha` es la fecha del caso (el secuestro), no la fecha de
  ingreso a cada CCD: se repite identica en todos los centros de una misma
  persona. El grafo dice por donde paso cada quien, **no** en que orden; hoy
  no permite ordenar cronologicamente un recorrido de cautiverio.
  Las 204 aristas provenientes de `ccds_json` son la excepcion parcial:
  traen `fecha_fin` y `precision_fecha` (YEAR / MONTH / DAY).
- La fecha del secuestro esta en dos lugares segun la fuente: en
  `SECUESTRADO_EN.fecha` para detalles_personas, y en
  `Persona.fecha_secuestro` para minjus_victimas y archivo_memoria.
- `Persona.edad` tambien es STRING: usar `toInteger()`.
- `Persona.genero` y `Persona.edad` solo tienen valor real en
  detalles_personas; el resto de las fuentes traen `'INDETERMINADO'` o null.

## Lugares, jerarquia y CCDs

La normalizacion de lugares combina:

- limpieza textual y reglas de dominio
- resolver georef con scoring y control de ambiguedad
- equivalencias (por ejemplo CABA/CAPITAL FEDERAL)
- fallback provincia por defecto (controlado) para casos sin pista provincial
- segmentacion "localidad + contexto administrativo" para mejorar desambiguacion

Los CCDs se cargan como `Lugar` con `tipoGeopolitico = 'CCD'` y se conectan por PARTE_DE al lugar geografico cuando hay evidencia (coordenadas o texto de ubicacion/denominacion). Esto permite analizar los CCD dentro de la misma taxonomia territorial. Ademas llevan `zona`, `subzona`, `area` y `emplazamiento_propiedad` (la fuerza a cargo) cuando la fuente los declara.

## Direcciones especificas

La capa `DirecciónCCD` captura la direccion puntual de cada CCD.

- Evita perder granularidad operativa.
- Clave unica `direccion_ccd_key`; guarda `direccionExacta`, `tipo_direccion` y
  `coordenadas`.
- Se ancla con `(DirecciónCCD)-[:UBICADA_EN]->(Lugar)`: 391 aristas, de las
  cuales 123 apuntan al propio nodo CCD y el resto a la localidad, provincia o
  departamento correspondiente.
- No reemplaza al Lugar: lo complementa.

## Consultas incluidas

- queries_preguntas_de_interes.cypher
  - 23 consultas de investigacion, cada una encabezada por la pregunta en
    lenguaje natural que responde: circuitos de CCD, Zona 4, red de
    represores, ritmo de las sentencias, brecha de impunidad, perfil etario
    y de genero, militancia, complicidad empresarial, secuestros familiares,
    partos en cautiverio, nietxs y resolucion de identidades.
  - Verificadas en vivo contra el grafo; incluyen las notas de modelo
    necesarias (fechas como STRING con centinela DESCONOCIDA, edad STRING,
    fecha de secuestro en dos lugares segun la fuente).
- queries_analitica_avanzada.cypher
  - piezas de analisis reutilizables sobre el modelo actual: roll-ups
    territoriales y por zona militar, series mensuales, ventanas de actividad
    de cada CCD, rezago entre hecho y sentencia, listas de aristas para
    exportar a Gephi/QGIS y bloques de GDS (proyeccion, Louvain, PageRank y
    WCC de nucleos familiares).
  - Reescrita el 2026-09-11: las 26 sentencias corren sin error contra el
    grafo vivo.
- queries_validacion.cypher
  - 37 chequeos agrupados en inventario, claves/labels/roles, responsabilidad
    penal, fechas, geografia/CCD/direcciones, alias, cobertura por entidad y
    resolucion de identidades. Cada bloque declara si es invariante dura
    ("DEBE DAR 0") o metrica de cobertura, y anota el valor de la corrida del
    2026-09-11 para comparar despues de cada recarga.
  - Reescrita el 2026-09-11. Dos invariantes fallan hoy y estan documentadas
    en el propio archivo: una auto-relacion `HIJE_DE` (bloque 2.5) y el nodo
    "CIUDAD AUTONOMA DE BUENOS AIRES" sin tilde, huerfano y con 2.386 hechos
    encima, duplicado del nodo tildado (bloques 5.2 y 5.3). Ese duplicado hace
    que todo roll-up por provincia subcuente CABA.

## Potencial de analisis

Con el modelo actual se puede:

- mapear concentracion de hechos por jerarquia territorial y zona militar
- reconstruir circuitos de CCD por victimas compartidas
- cruzar responsabilidad penal (represores, fuerzas, delitos, sentencias) con
  las victimas y los centros por los que pasaron
- distinguir lugar general y direccion puntual de un mismo CCD
- auditar calidad de normalizacion y cobertura de datos

## Buenas practicas de uso

- Ejecutar queries_validacion.cypher despues de cada recarga y comparar contra
  los valores anotados en cada bloque.
- Revisar aliases de bajo soporte (frecuencia 1) para mejora incremental de reglas.
- Mantener trazabilidad: no borrar alias_raw ni descripcion_raw.
- Cuando se agreguen reglas nuevas de normalizacion, volver a correr carga limpia y comparar metricas antes/despues.

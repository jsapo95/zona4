# MinJus GBA — Derechos Humanos, Ministerio de Justicia de la Provincia de Buenos Aires

## Origen

*   **URL**: https://derechoshumanos.mjus.gba.gob.ar/consulta-interactiva/
*   **Archivos en `data/raw/`**:
    *   `derechos_humanos_minjus_gba_centros_clandestinos.json` (87 registros).
    *   `derechos_humanos_minjus_gba_imputados.json` (454 registros).
    *   `derechos_humanos_minjus_gba_victimas.json` (3257 registros).
    *   `derechos_humanos_minjus_gba_sentencias.json` (113 registros).
*   **Builders**:
    *   `src/zona4_graph_loader/builders/minjus_ccds.py::build_minjus_ccds_rows`.
    *   `src/zona4_graph_loader/builders/minjus_imputados.py::build_minjus_imputados_rows`.
    *   `src/zona4_graph_loader/builders/minjus_victimas.py::build_minjus_victimas_rows`.
    *   `src/zona4_graph_loader/builders/minjus_sentencias.py::build_sentencias_index` (no produce filas de CDM: ver más abajo).

Es la fuente más grande incorporada en esta iteración y la que más pendientes
deja documentados, porque es la única con datos narrativos de dirección y con
un vocabulario de estado biográfico que el modelo todavía no aloja.

## Esquema y mapeo al CDM

### Centros clandestinos (`_centros_clandestinos.json`)

| Campo origen | Destino CDM |
| --- | --- |
| `titulo` | `:Lugar.nombre`, tipo `CCD`. |
| `metadatos.Dependencia` | `:Lugar.jurisdiccion`. |
| `metadatos.Domicilio` | `:Lugar.ubicacion` y `:DireccionCCD.direccionExacta` (sin coordenadas: `coordenadas = "DESCONOCIDAS"`). |
| `source_url` | slug único (`slug_ccd`), usado para deduplicar contra RUVTE y como clave de unión con víctimas/imputados. |

**Dedup contra RUVTE**: de los 87 centros, **19** matchean contra un CCD ya
cargado desde el listado RUVTE (`ccds.json`, `build_ccd_rows`) y reutilizan su
`lugar_key` en vez de crear un nodo nuevo; los otros **68** son nodos `:Lugar`
nuevos. El matching (`_match_existente` en `builders/minjus_ccds.py`) combina
comparación directa de nombre sin acentos con `name_similarity_score`
(umbral 0.93). Tuvo que agregarse un guardia adicional sobre los dígitos
crudos del nombre (`_numeros_distintos`) porque `name_similarity_score`
descarta tokens de un solo carácter como ruido, lo que incluye números de un
dígito: sin el guardia, "Comisaría 8ª de La Plata" y "Comisaría 5ª de La
Plata" —dos centros distintos— puntuaban 1.000 de similitud y se fusionaban
en un único nodo.

### Imputados (`_imputados.json`) — 454 represores

| Campo origen | Destino CDM |
| --- | --- |
| `nombre` | `:Persona.nombre`, `roles: ["REPRESOR"]`. |
| `datos_personales.fecha_de_nacimiento` | `:Persona.fecha_nacimiento`. |
| `datos_personales.fuerza` | `:Org` + arista `PARTE_DE`. |
| `datos_personales.apodo` | `:AliasPersona` + arista `IDENTIFICA_A`. |
| `sentencias_y_victimas[].victimas_asociadas[]` | Arista `TORTURO_A` hacia `minjus_victima:{slug}`. |
| `condenas_recibidas` (426 de 454) | **No mapeado.** |
| `datos_personales.fallecido` (388 de 454) | **No mapeado.** |

### Víctimas (`_victimas.json`) — 3257 registros

| Campo origen | Destino CDM |
| --- | --- |
| `nombre` | `:Persona.nombre`, `roles: ["VICTIMA"]`. |
| `datos_personales.fecha_de_secuestro` | `:Persona.fecha_secuestro`. |
| `datos_personales.militancia` | `:Org` + arista `PARTE_DE`. |
| `datos_personales.lugar_de_trabajo` | `:Institucion` + arista `TRABAJO_EN`. |
| `datos_personales.dónde_estudió` | `:Institucion` + arista `ESTUDIO_EN`. |
| `datos_personales.apodo` | `:AliasPersona` + arista `IDENTIFICA_A`. |
| `centros_clandestinos[].url` | Arista `PRESENTE_EN` hacia el `:Lugar` resuelto por `minjus_ccds` (3308 aristas en total). |
| `datos_personales.lugar_de_secuestro` (2785 de 3257) | **No mapeado** (ver pendiente 1). |
| `datos_personales.situación_actual` | **No mapeado** (ver pendiente 2). |

MinJus usa el guión largo "–" (y a veces un "." suelto) como placeholder de
"sin dato" en varios campos de `datos_personales`. Ninguno de los dos está en
el conjunto de centinelas compartido de `clean_text`, así que los builders de
víctimas e imputados chequean el slug del valor (no sólo si el campo está
vacío) antes de crear una entidad de contexto — sin ese chequeo, docenas de
víctimas terminarían compartiendo una "organización" o un "oficio" que nunca
existió.

### Sentencias (`_sentencias.json`) — no genera nodos

`build_sentencias_index` construye un índice `slug -> {titulo, tribunal,
fecha, origen}` en memoria. **No produce entidades ni aristas propias**: el
modelo V1.2 no tiene nodo `:Sentencia` ni `:Causa`. Sus 113 registros (112
slugs distintos — dos sentencias comparten identificador) sólo alimentan las
propiedades `origen` y `fecha` de las aristas `TORTURO_A` que generan los
builders de imputados y víctimas. Cuando un bloque de sentencia referencia un
slug ausente de este índice, el `origen` se deriva del propio slug
(`minjus_sentencias:{slug}`) en vez de perderse; si no hay slug en absoluto, se
usa el sentinel compartido `minjus_sentencias:desconocida`.

---

## Pendientes

### 1. `lugar_de_secuestro` no se parsea — sin aristas `SECUESTRADO_EN`

2785 de las 3257 víctimas traen `lugar_de_secuestro`, pero es texto narrativo
libre con saltos de línea embebidos en 107 de esos casos (p. ej. mezcla de
dirección, aclaraciones entre paréntesis y referencias a otros lugares en el
mismo campo). Parsear esto de forma confiable quedó fuera de alcance de esta
iteración, así que **no se generan aristas `SECUESTRADO_EN` para esta
fuente**.

Para no perder el dato mientras tanto, la fecha correspondiente sí se
persiste: `:Persona.fecha_secuestro` queda poblado en 2937 víctimas (más que
las 2785 con lugar, porque algunas traen fecha sin lugar). Esto permite
reconstruir las aristas `SECUESTRADO_EN` en una iteración futura —una vez que
exista un parser para el texto narrativo— sin tener que re-scrapear la fuente.

### 2. `situación_actual` se descarta — insumo natural para `ASESINADO_EN`/`LIBERADO_EN`

El campo trae, sobre las 3257 víctimas:

| Valor | Registros |
| --- | --- |
| Persona liberada | 1608 |
| Persona desaparecida | 1237 |
| Persona asesinada | 326 |
| Persona restituida | 43 |
| (otros valores residuales: fallecido, fugado, vacío) | 43 |

Hoy se descarta por completo: el modelo no tiene dónde alojar un estado
biográfico de este tipo en `:Persona`, y el CDM tampoco tiene un campo para
eso en `eventos_espaciales`. Es el insumo natural para generar aristas
`ASESINADO_EN` y `LIBERADO_EN` (ambas ya declaradas en el catálogo de
relaciones del modelo, sección 3.3 de `NEO4J_DATA_MODEL.md`) el día que se
retome el parseo de `lugar_de_secuestro`: la situación decide qué arista
generar y el lugar parseado decide su destino.

### 3. 785 aristas `TORTURO_A` se descartan porque el imputado no existe como nodo

Los bloques `sentencias[].imputados[]` de las víctimas referencian imputados
por `imputado_url`; cuando ese slug no corresponde a ningún imputado presente
en `_imputados.json`, la arista queda con un `source_key` que el Cypher de
carga no puede resolver (`MATCH (s:Persona {persona_key: ...})` no encuentra
nada, y la fila se descarta en silencio). Pasa en 785 aristas sobre 26 slugs
de imputado distintos:

*   **777 aristas (18 slugs)** son hueco real de la fuente: el imputado
    referenciado no aparece en absoluto en `_imputados.json`.
*   **8 aristas (8 slugs)** son deriva de id: el mismo imputado está en el
    archivo de imputados bajo un número distinto al que usa el bloque de
    sentencia de la víctima — por ejemplo, `473-videla-jorge-rafael` (el slug
    que cita la víctima) contra `446-videla-jorge-rafael` (el slug real bajo
    el que existe el nodo). El nombre coincide exactamente; sólo cambia el
    prefijo numérico.

No hay builder ni normalización que hoy compense ninguno de los dos casos.

### 4. 32 nodos `:Persona` huérfanos, creados por `MERGE` desde las aristas de imputados

Cuando una arista `TORTURO_A` generada por el builder de imputados apunta a
una `minjus_victima:{slug}` que no está en la lista de víctimas cargadas (la
inversa del pendiente 3), el Cypher de aristas (`CYPHER_UPSERT_REL_PERSONA` en
`db/cypher.py`) hace `MERGE (t:Persona {persona_key: ...})` sobre el destino.
Esto crea el nodo `:Persona`, pero:

*   no recibe el label de rol `:Victima` (eso lo asigna un paso Cypher
    separado, `CYPHER_UPSERT_PROTAGONISTAS`/`CYPHER_UPSERT_PERSONAS`, que sólo
    corre sobre las filas de `personas` del CDM);
*   no tiene `fecha_secuestro`;
*   queda invisible a `domain/roles.py::normalize_roles` (nunca pasó por ahí)
    y a la reconciliación de identidades (`domain/identity_resolution.py`
    trabaja sobre `dataset["personas"]`, no sobre nodos ya escritos en Neo4j).

Esto ocurre en 32 casos. El efecto práctico es que cualquier conteo de
`victimas_total` basado en el label `:Victima` subcuenta en 32 respecto del
total real de nodos `:Persona` que MinJus GBA terminó creando.

### 5. `condenas_recibidas` y `fallecido` no se leen

`condenas_recibidas` (presente en 426 de los 454 imputados, con sentencia,
sanción y URL por condena) y `fallecido` (388 de 454) no tienen destino en el
modelo V1.2: no hay nodo `:Condena` ni propiedad de fallecimiento en
`:Persona`. Ambos campos se ignoran por completo en
`build_minjus_imputados_rows`.

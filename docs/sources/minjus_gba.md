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
| `datos_personales.fecha_de_nacimiento` | `:Persona.fecha_nacimiento` (347 de 454) — validada (V1.3, hallazgo I6): un valor fuera de rango se descarta a `"DESCONOCIDA"` en vez de persistirse. Ningún imputado real cae hoy fuera de rango en este archivo (el caso de fecha imposible de esta iteración, "Massera, Emilio Eduardo" → `"08/11/2010"`, viene de `juicios_lesa_humanidad_condenados.json`, no de éste; el guardia se agregó igual, por consistencia). |
| `datos_personales.fuerza` | `Persona.fuerza` (435 de 454 lo traen) **+** `:Org` + arista `PARTE_DE` — salvo que el valor sea un centinela (V1.3, hallazgo I3d): `SIN ESPECIFICAR`/`CIVIL`/`POLICIA (SIN ESPECIFICAR)`/`NO ESPECIFICADO`/`NO DETERMINADO`/`DESCONOCIDA`/`DESCONOCIDO`. **57 de los 435** son uno de estos centinelas: antes de este fix fabricaban una organización falsa (109 represores de esta fuente + `juicios_condenados` compartían membresía en un `:Org "SIN ESPECIFICAR"` que no es una organización, es la ausencia del dato); ahora el valor crudo queda sólo en `Persona.fuerza`, sin arista. 17 organizaciones reales resultan de los 454 imputados (antes, con los centinelas materializados, habría sido más). |
| `datos_personales.apodo` | `:AliasPersona` + arista `IDENTIFICA_A` (24 alias). |
| `sentencias_y_victimas[].victimas_asociadas[].delitos` | Clasifica la arista hacia `minjus_victima:{slug}` (V1.3, hallazgo C1/Fix A): `TORTURO_A` si `delitos` incluye la familia de tormentos (`"Tormentos"` / `"Tormentos seguidos de muerte"`) para ese par en particular, `IMPUTADO_POR` en caso contrario. Ambos tipos de arista llevan la lista completa de `delitos` tal como la da la fuente. Antes de este fix se emitía `TORTURO_A` para el 100 % de los pares sin mirar `delitos`: acusaba de tormentos a personas cuya sentencia las condena por otra cosa (sustracción de menor, homicidio, privación ilegítima de la libertad...). Medido sobre el archivo real (2026-08-30, corriendo el builder actual): de los 14.826 pares imputado-víctima de este archivo, **11.494 son `TORTURO_A`** y **3.332 son `IMPUTADO_POR`**. El vocabulario completo de `delitos` en esta fuente (imputados + víctimas combinados) trae 30 variantes distintas; sólo dos ("Tormentos", "Tormentos seguidos de muerte") clasifican como tortura — el resto incluye Privación Ilegítima de la libertad (14.273 apariciones), Violencia y amenazas (4.412), Homicidio (2.980), Desaparición Forzada (765), Sustracción de menor (185), Abuso sexual (222), entre otras. |
| `condenas_recibidas` (426 de 454) | **No mapeado.** |
| `datos_personales.fallecido` (388 de 454) | **No mapeado.** |

### Víctimas (`_victimas.json`) — 3257 registros

| Campo origen | Destino CDM |
| --- | --- |
| `nombre` | `:Persona.nombre`, `roles: ["VICTIMA"]`. |
| `datos_personales.fecha_de_secuestro` | `:Persona.fecha_secuestro` — validada (V1.3, hallazgo I6): un valor fuera de `[1966, 1990]` se descarta a `"DESCONOCIDA"`. Queda poblado en **2925** víctimas (era ~2937 antes de este fix; 12 registros reales traían fechas entre 1997 y 2077 — p.ej. `Cuatrocchio, Daniel Ernesto` = `"2077-05-26"` — y ya no se persisten). |
| `datos_personales.militancia` | `:Org` + arista `PARTE_DE`, salvo centinela (V1.3, hallazgo I3d, cerrado en el commit `91b55f9` tras un hallazgo de verificación en vivo posterior al resto del fix: la primera carga completa mostró `orgs_sentinel_total: 3` porque `militancia` no había recibido el mismo guardia que `fuerza`/`lugar_de_trabajo`/`dónde_estudió` — 4 registros reales, `Álvarez Carrera`, `Bietti`, `Botazzi`, `Gildengers`, traen `"No determinado"`/`"Desconocida"`/`"No especificado"` como militancia). A diferencia de `fuerza`, no se agregó un `Persona.militancia` de respaldo: es una decisión de modelado separada, no forzada por este fix. |
| `datos_personales.lugar_de_trabajo` | `:Institucion` + arista `TRABAJO_EN`, salvo centinela (`NO DETERMINADO`/`NO ESPECIFICADO`/`NO ESPECIFICA`/`DESCONOCIDO`/`DESCONOCIDA`, V1.3, hallazgo I3d). |
| `datos_personales.dónde_estudió` | `:Institucion` + arista `ESTUDIO_EN`, mismo guardia de centinela. |
| `datos_personales.apodo` | `:AliasPersona` + arista `IDENTIFICA_A` (813 alias). |
| `centros_clandestinos[].url` | Arista `PRESENTE_EN` hacia el `:Lugar` resuelto por `minjus_ccds` (3308 aristas, sin cambios de esta rama). |
| `datos_personales.lugar_de_secuestro` (2785 de 3257) | **No mapeado** (ver pendiente 1). |
| `datos_personales.situación_actual` | **No mapeado** (ver pendiente 2). |

Medido sobre el archivo real de víctimas (2026-08-30): de los 15.374 pares
imputado-víctima que aporta este lado de la fuente, **11.797 clasifican como
`TORTURO_A`** y **3.577 como `IMPUTADO_POR`** (mismo criterio de `delitos` que
en imputados, arriba; los dos archivos describen parcialmente los mismos
hechos desde puntos de vista distintos — imputado y víctima — así que sus
conteos crudos no coinciden entre sí ni con el total final del grafo, que
además filtra los pares cuyo imputado o víctima no tiene nodo propio, ver
pendiente 3). Sobre víctimas también se generan **742** entidades `:Org`
(militancia), **1596** `:Institución` (lugar de trabajo + estudios) y **813**
`:AliasPersona`.

MinJus usa el guión largo "–" (y a veces un "." suelto) como placeholder de
"sin dato" en varios campos de `datos_personales`. Ninguno de los dos está en
el conjunto de centinelas compartido de `clean_text`, así que los builders de
víctimas e imputados chequean el slug del valor (no sólo si el campo está
vacío) antes de crear una entidad de contexto. Desde V1.3 (hallazgo I3d) se
suma un segundo guardia, por coincidencia EXACTA con un vocabulario de
centinelas conocidos (`SENTINEL_ORG_VALUES`/`SENTINEL_INSTITUCION_VALUES` en
`constants.py`) para los valores que sí llegan a tener contenido pero ese
contenido es "no hay dato" en otras palabras (`"SIN ESPECIFICAR"`, `"NO
DETERMINADO"`, etc.) — sin este segundo guardia, docenas de víctimas o
imputados terminarían compartiendo una "organización" o un "oficio" que nunca
existió, sólo el hecho compartido de que la fuente no supo qué poner.

### Sentencias (`_sentencias.json`) — no genera nodos

`build_sentencias_index` construye un índice `slug -> {titulo, tribunal,
fecha_sentencia, origen}` en memoria. **No produce entidades ni aristas
propias**: el modelo no tiene nodo `:Sentencia` ni `:Causa`. Sus 113 registros
(112 slugs distintos — dos sentencias comparten identificador) alimentan las
propiedades `origen` y `fecha_sentencia` de las aristas `TORTURO_A`/
`IMPUTADO_POR` que generan los builders de imputados y víctimas, y desde
V1.3 también deciden — vía el campo `delitos` de cada bloque
`victimas_asociadas`/`sentencias`, no vía este índice — cuál de las dos
aristas corresponde (ver arriba). Cuando un bloque de sentencia referencia un
slug ausente de este índice, el `origen` se deriva del propio slug
(`minjus_sentencias:{slug}`) en vez de perderse; si no hay slug en absoluto, se
usa el sentinel compartido `minjus_sentencias:desconocida`. La propiedad
`fecha` de ambas aristas es siempre `"DESCONOCIDA"`: la fuente no registra
cuándo ocurrió el hecho, sólo cuándo se dictó la sentencia que lo documenta
(`fecha_sentencia`) — inferir la fecha del hecho a partir de la del fallo
sería inventar el dato central que esta fuente existe para preservar.

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
persiste: `:Persona.fecha_secuestro` queda poblado en 2925 víctimas (más que
las 2785 con lugar, porque algunas traen fecha sin lugar; era ~2937 antes de
la validación de rango de V1.3 — hallazgo I6 — que descarta a `"DESCONOCIDA"`
los 12 valores reales fuera de `[1966, 1990]`, ver arriba). Esto permite
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

### 3. 785 aristas `TORTURO_A`/`IMPUTADO_POR` se descartan porque el imputado no existe como nodo

Los bloques `sentencias[].imputados[]` de las víctimas referencian imputados
por `imputado_url`; cuando ese slug no corresponde a ningún imputado presente
en `_imputados.json`, la arista queda con un `source_key` que el Cypher de
carga no puede resolver (`MATCH (s:Persona {persona_key: ...})` no encuentra
nada, y la fila se descarta en silencio). Sigue pasando en **785 aristas sobre
26 slugs de imputado distintos** — el conteo agregado no cambió con el fix de
delitos (V1.3, hallazgo C1): la clasificación `TORTURO_A`/`IMPUTADO_POR` no
afecta si el `source_key` resuelve o no, sólo cambia el `tipo` de la fila que
se pierde. Re-medido sobre el código actual (2026-08-30, comparando
directamente las claves de persona de ambos builders, sin necesidad de correr
la reconciliación de identidades completa: ninguna otra fuente puede producir
una clave `minjus_imputado:{slug}`, así que el hueco es interno a MinJus y no
lo tapa ningún merge entre fuentes): de las 785, **546 habrían sido
`TORTURO_A`** y **239 `IMPUTADO_POR`**.

*   **777 aristas (18 slugs; 540 `TORTURO_A` + 237 `IMPUTADO_POR`)** son hueco
    real de la fuente: el imputado referenciado no aparece en absoluto en
    `_imputados.json`.
*   **8 aristas (8 slugs; 6 `TORTURO_A` + 2 `IMPUTADO_POR`)** son deriva de
    id: el mismo imputado está en el archivo de imputados bajo un número
    distinto al que usa el bloque de sentencia de la víctima — por ejemplo,
    `473-videla-jorge-rafael` (el slug que cita la víctima) contra
    `446-videla-jorge-rafael` (el slug real bajo el que existe el nodo). El
    nombre coincide exactamente; sólo cambia el prefijo numérico.

No hay builder ni normalización que hoy compense ninguno de los dos casos.

### 4. 32 nodos `:Persona` huérfanos, creados por `MERGE` desde las aristas de imputados

Cuando una arista generada por el builder de imputados (`TORTURO_A` o
`IMPUTADO_POR`, según sus `delitos`) apunta a una `minjus_victima:{slug}` que
no está en la lista de víctimas cargadas (la inversa del pendiente 3), el
Cypher de aristas (`CYPHER_UPSERT_REL_PERSONA` en `db/cypher.py`) hace
`MERGE (t:Persona {persona_key: ...})` sobre el destino. Esto crea el nodo
`:Persona`, pero:

*   no recibe el label de rol `:Victima` (eso lo asigna un paso Cypher
    separado, `CYPHER_UPSERT_PROTAGONISTAS`/`CYPHER_UPSERT_PERSONAS`, que sólo
    corre sobre las filas de `personas` del CDM);
*   no tiene `fecha_secuestro`;
*   queda invisible a `domain/roles.py::normalize_roles` (nunca pasó por ahí)
    y a la reconciliación de identidades (`domain/identity_resolution.py`
    trabaja sobre `dataset["personas"]`, no sobre nodos ya escritos en Neo4j).

Esto sigue ocurriendo en **32 nodos distintos** (re-medido 2026-08-30, sin
cambios respecto de antes del fix de delitos), alcanzados por **238 aristas**
(**230 `TORTURO_A` + 8 `IMPUTADO_POR`**, ya que un mismo `:Persona` huérfano
puede recibir más de una arista). El efecto práctico es que cualquier conteo
de `victimas_total` basado en el label `:Victima` subcuenta en 32 respecto del
total real de nodos `:Persona` que MinJus GBA terminó creando.

### 5. `condenas_recibidas` y `fallecido` no se leen

`condenas_recibidas` (presente en 426 de los 454 imputados, con sentencia,
sanción y URL por condena) y `fallecido` (388 de 454) no tienen destino en el
modelo (V1.3, sigue sin cambios en esto): no hay nodo `:Condena` ni propiedad
de fallecimiento en `:Persona`. Ambos campos se ignoran por completo en
`build_minjus_imputados_rows`.

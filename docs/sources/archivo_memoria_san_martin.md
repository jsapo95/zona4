# Archivo de la Memoria de San Martín

## Origen

*   **URL**: https://sitiosale.cdn.prismic.io/sitiosale/Z9luiTiBA97GimGK_M_ArchivodeMemoria-1-.pdf
*   **Archivo en `data/raw/`**: `archivo_memoria_san_martin.json` (303 registros).
*   **Builder**: `src/zona4_graph_loader/builders/archivo_memoria.py::build_archivo_memoria_rows`.

Esta fuente es la única del proyecto centrada específicamente en el partido de
San Martín (Zona IV), lo que la vuelve especialmente sensible a cómo se resuelve
su propia geografía local (ver pendiente 1, abajo).

## Esquema y mapeo al CDM

| Campo origen | Destino CDM |
| --- | --- |
| `nombre` | `:Persona.nombre` (obligatorio; si falta, la fila se descarta). |
| `fecha_nacimiento` | `:Persona.fecha_nacimiento`. |
| `fecha_desaparicion_normalizada` | `:Persona.fecha_secuestro` y `fecha` de la arista `SECUESTRADO_EN`. |
| `lugar` | Resuelto con `domain/place_norm.py::resolve_place` (topónimo corto, p. ej. "Billinghurst") → nodo `:Lugar` + arista `SECUESTRADO_EN`. |
| `estudiante_universitario` | Arista `ESTUDIO_EN` hacia un nodo `:Institucion` genérico (`institucion:universidad_sin_especificar`), porque la fuente no nombra la universidad. |
| `estudiante`, `descripcion`, `edad_al_desaparecer` | No mapeados: no tienen destino en el CDM actual. |

Todas las personas se cargan con `roles: ["VICTIMA"]` y `genero: "INDETERMINADO"`
(la fuente no discrimina género).

---

## Pendientes

### 1. La geografía de San Martín queda fragmentada en dos subárboles

Distribución actual, medida sobre los 303 registros (corregida tras el fix de
`9d3b657`, ver abajo):

| Destino | Registros |
| --- | --- |
| `lugar:DEPARTAMENTO:general_san_martin` (vía Georef directo) | 124 |
| `lugar:PROVINCIA:buenos_aires` directo (sin departamento) | 179 |
| Otra provincia | 0 |

Los 124 son Villa Ballester, Villa Lynch, Villa Maipú, Billinghurst y Villa
Libertad, resueltos por el gazetteer de Georef y correctamente anidados bajo
el departamento. Los otros 179 se crean como `:Lugar` tipo `CIUDAD` colgando
**directamente** de `lugar:PROVINCIA:buenos_aires`, sin pasar por
`DEPARTAMENTO:general_san_martin`.

**Corrección de un defecto más grave, ya resuelta.** Hasta el commit
`9d3b657` ("fix: mapear topónimos de San Martín mal georresueltos a Buenos
Aires"), 60 de esos 179 no llegaban ni siquiera a Buenos Aires: el fallback
`_resolve_segmented_place` de `domain/place_norm.py` los mandaba a una
provincia distinta, real pero equivocada — "José León Suárez" (34 registros)
resolvía a Jujuy (Dr. Manuel Belgrano), y "San Andrés" (13) y "Villa
Concepción" (13) resolvían a Tucumán (Cruz Alta y Chicligasta
respectivamente). Las tres son localidades reales del partido de General San
Martín; el fallback las tomó por localidades homónimas de otras provincias.
`EQUIV_CITIES` ya tenía una entrada `"JOSE LEON SUAREZ SAN MARTIN"` desde
antes de esta fuente, pero nunca se disparaba para estos 34 registros: el
valor crudo de `archivo_memoria_san_martin.json` es literalmente
`"José León Suárez"`, sin el sufijo `"SAN MARTIN"` que esa clave exige para
matchear. Esa entrada previa no era un precedente que ya cubriera el caso;
simplemente no aplicaba a esta fuente. El fix agregó tres entradas aditivas
nuevas y distintas a `EQUIV_CITIES` en `src/zona4_graph_loader/constants.py`
— `"JOSE LEON SUAREZ"`, `"SAN ANDRES"`, `"VILLA CONCEPCION"`, ancladas a
`PROVINCIA:BUENOS AIRES` — que se consultan antes que el gazetteer de Georef
y cortocircuitan el fallback segmentado antes de que llegue a proponer Jujuy
o Tucumán. Queda cubierto por `tests/domain/test_place_norm_san_martin.py`.
Se documenta acá para que quien audite esta fuente no "redescubra" el
defecto ni revierta el fix creyendo que las entradas nuevas son redundantes.

**Pendiente que persiste.** El fix elimina el error de provincia, pero no la
fragmentación: los 60 registros corregidos se suman a los 119 que ya estaban
bajo `PROVINCIA:buenos_aires` sin departamento (119 + 60 = 179), así que la
geografía del partido de San Martín — el objeto mismo de esta fuente — sigue
representada en dos subárboles del grafo. Buscar "todo lo que pasó en el
partido de San Martín" recorriendo `PARTE_DE` desde `general_san_martin` sigue
sin encontrar a estas 179 personas.

La razón es estructural, no un descuido de datos: la rama
`if alias_norm in EQUIV_CITIES` de `resolve_place` (`domain/place_norm.py`)
envuelve el tercer elemento de la tupla siempre como
`make_lugar_key("PROVINCIA", parent_name, "lugar:PAIS:argentina")` — no hay
forma de que una entrada de `EQUIV_CITIES` produzca un `parent_key` de tres
niveles (`CIUDAD` → `DEPARTAMENTO` → `PROVINCIA`). Por diseño, esa tabla sólo
puede anclar un lugar directamente bajo una provincia. Consolidar estos 179
registros bajo `general_san_martin` requiere entonces un cambio de algoritmo
(permitir que `EQUIV_CITIES`, o un mecanismo equivalente, exprese un padre a
nivel `DEPARTAMENTO`), no otra entrada aditiva en la tabla — que es
exactamente lo que dejó fuera de alcance el fix de `9d3b657`.

### 2. Las `persona_key` dependen de la posición en el archivo, no del contenido

El builder genera `persona_key` como `archivo_memoria:{índice}`, tomando el
índice de la fila en la lista JSON, porque el archivo no trae ningún ID propio
por registro. `data/processed/identity_merges.json` persiste decisiones de
reconciliación de identidades usando esas claves como referencia estable.

Si el archivo de origen se vuelve a scrapear y el orden de las filas cambia
(reordenamiento, inserciones, filas eliminadas), las claves `archivo_memoria:N`
pasarían a apuntar a otras personas, y los merges ya auditados en
`identity_merges.json` quedarían apuntando a una fila distinta de la que
confirmaron originalmente.

**Mitigante**: esta fuente no tiene extractor propio en el repo (el JSON en
`data/raw/` se produjo fuera del pipeline versionado), así que el riesgo de
reordenamiento espontáneo entre corridas del loader es bajo hoy. **Remedio**:
derivar la clave de un hash del contenido (p. ej. nombre + fecha de
desaparición normalizada) en vez de la posición, para que sea estable ante un
re-scrapeo futuro.

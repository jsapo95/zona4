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

De los 303 registros con `lugar`, **184 (61%)** resuelven contra el catálogo
Georef y terminan anidados bajo `lugar:DEPARTAMENTO:general_san_martin` junto
con Billinghurst, Villa Ballester, Villa Lynch, Villa Maipú y Villa Libertad.

Los otros **119 (39%)** no matchean contra Georef y caen en el fallback
`_can_assume_buenos_aires` de `domain/place_norm.py`: se crean como `:Lugar`
tipo `CIUDAD` colgando **directamente** de `lugar:PROVINCIA:buenos_aires`, sin
pasar por el departamento. Se reparten en:

| Topónimo | Registros |
| --- | --- |
| San Martín | 103 |
| Tropezón | 10 |
| Villa Zagala | 6 |

Es decir, la única fuente del proyecto centrada en Zona IV termina
representando el mismo territorio real en dos subárboles distintos y
desconectados del grafo: buscar "todo lo que pasó en el partido de San Martín"
recorriendo `PARTE_DE` desde `general_san_martin` no encuentra a estas 119
personas.

**Remedio acotado**: agregar estos tres topónimos a `EQUIV_CITIES` en
`src/zona4_graph_loader/constants.py`, mapeándolos bajo
`general_san_martin` — el mismo mecanismo que el repo ya usa para resolver
`"JOSE LEON SUAREZ SAN MARTIN"` y `"LIBERTADOR GENERAL SAN MARTIN"`. No
requiere tocar `place_norm.py` ni el builder.

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

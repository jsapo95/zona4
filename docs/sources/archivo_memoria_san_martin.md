# Archivo de la Memoria de San Martín

## Origen

*   **URL**: https://sitiosale.cdn.prismic.io/sitiosale/Z9luiTiBA97GimGK_M_ArchivodeMemoria-1-.pdf
*   **Archivo en `data/raw/`**: `archivo_memoria_san_martin.json` (303 registros).
*   **Builder**: `src/zona4_graph_loader/builders/archivo_memoria.py::build_archivo_memoria_rows`.

Esta fuente es la única del proyecto centrada específicamente en el partido de
San Martín (Zona IV). Desde V1.3 ya no aporta ninguna capa geográfica propia
al grafo (ver "V1.3: se eliminó la capa geográfica de esta fuente", abajo).

## Esquema y mapeo al CDM

| Campo origen | Destino CDM |
| --- | --- |
| `nombre` | `:Persona.nombre` (obligatorio; si falta, la fila se descarta). |
| `fecha_nacimiento` | `:Persona.fecha_nacimiento`. |
| `fecha_desaparicion_normalizada` | `:Persona.fecha_secuestro` (303 de 303 registros la traen). **Ya NO genera la arista `SECUESTRADO_EN`** — ver "V1.3: se eliminó la capa geográfica de esta fuente", abajo. |
| `lugar` | **Ya no se mapea a ningún nodo ni arista** (V1.3, hallazgo C2). Antes se resolvía con `domain/place_norm.py::resolve_place` hacia un nodo `:Lugar` + arista `SECUESTRADO_EN`; ver el porqué abajo. |
| `estudiante_universitario` | `Persona.estudiante_universitario` (booleano; V1.3, hallazgo I4). Antes generaba una arista `ESTUDIO_EN` hacia un nodo `:Institucion` fijo (`institucion:universidad_sin_especificar`) — ver abajo. |
| `estudiante`, `descripcion`, `edad_al_desaparecer` | No mapeados: no tienen destino en el CDM actual. |

Todas las personas se cargan con `roles: ["VICTIMA"]` y `genero: "INDETERMINADO"`
(la fuente no discrimina género).

---

## V1.3: se eliminó la capa geográfica de esta fuente (hallazgo C2)

**Esta fuente pasó de 303 aristas `SECUESTRADO_EN` a 0.** Es el cambio más
importante de esta ficha, y afecta precisamente al foco declarado de esta
fuente en el proyecto: el partido de San Martín (Zona IV).

**Qué es realmente el campo `lugar`.** Toma sólo 11 valores distintos en los
303 registros — San Martín, Villa Ballester, José León Suárez, Villa Lynch,
Villa Maipú, San Andrés, Villa Concepción, Billinghurst, Tropezón, Villa
Zagala, Villa Libertad — los 11 barrios en los que el Archivo de la Memoria de
San Martín organiza sus fichas para sus propios fines (homenajes, placas
locales). No es un dato extraído del hecho del secuestro: es la categoría
curatorial bajo la que el archivo municipal clasificó a la víctima.

**Por qué asertarlo como lugar del secuestro era incorrecto.** En **159 de
303 registros (52 %)** la propia `descripcion` de la fuente nombra
explícitamente *otro* lugar para el secuestro — a veces en otra jurisdicción
por completo (Barrancas de Belgrano en CABA, Vicente López, Boulogne/San
Isidro, Bella Vista/San Miguel). Ejemplo real: `Bellantuono Herrero, Jorge`
tiene `lugar:"Billinghurst"`, pero su `descripcion` dice *"secuestrado el 13
de julio de 1976 en la vía pública, en Barrancas de Belgrano"* — Capital
Federal, no Billinghurst ni siquiera el partido de San Martín. En **64 de 303
(21 %)** el valor de `lugar` ni siquiera aparece en ningún lugar del texto de
`descripcion` (ni como domicilio, ni como lugar de trabajo, ni como
residencia familiar): en más de un quinto de los casos ni "barrio de
residencia" es una descripción consistente. El grafo estaba ubicando el
secuestro de cientos de personas en un lugar que la fuente que provee ese
mismo dato contradice.

**Qué se decidió y por qué no una re-tipificación.** Se eliminó la arista por
completo en vez de re-tiparla (p. ej. a `PRESENTE_EN` o a un vínculo de
residencia): `PRESENTE_EN` no tiene una fecha propia que anclar aquí (no hay
evidencia de *cuándo* la persona estuvo en ese barrio, si es que estuvo), y
la fuente no da lo necesario para reconstruir el lugar real del hecho sin
parsing narrativo adicional sobre `descripcion` (fuera de alcance de este
fix). `Persona.fecha_secuestro` se conserva sin cambios en los 303 registros:
lo único que se pierde es la ubicación asociada a esa fecha, no la fecha en
sí.

**Qué pierde el proyecto.** El foco geográfico específico de esta fuente
(reconstruir la geografía del secuestro dentro del partido de San Martín)
queda sin datos: hoy esta fuente no aporta ningún nodo `:Lugar` ni arista
geográfica al grafo. Si en el futuro se retoma el parsing de `descripcion`
para extraer el lugar real del hecho, la fecha ya está preservada en
`Persona.fecha_secuestro` para reconstruir la arista sin re-scrapear la
fuente.

## Estudiante universitario ya no fabrica una institución (hallazgo I4)

`estudiante_universitario` es un booleano en la fuente (`true` en 56 de 303
registros; **ausente**, nunca `false`, en el resto). Antes de este fix se
materializaba como una arista `ESTUDIO_EN` hacia un único nodo fijo
`:Institución "UNIVERSIDAD SIN ESPECIFICAR"`, afirmando una institución que
la fuente nunca nombra y relacionando falsamente entre sí a las 56 personas a
través de ese nodo compartido. Ejemplo real: `Bellantuono Herrero, Jorge`
quedaba conectado a "UNIVERSIDAD SIN ESPECIFICAR" cuando su propia
`descripcion`, en la misma fuente, dice *"Estudiaba Ciencias Económicas en la
Universidad de Buenos Aires (U.B.A)"*. Ahora el booleano se persiste
directamente como `Persona.estudiante_universitario`; la ausencia del campo
no se interpreta como `false` (no es evidencia de que la persona no haya sido
estudiante universitaria).

---

## Pendientes

### 1. Las `persona_key` dependen de la posición en el archivo, no del contenido

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

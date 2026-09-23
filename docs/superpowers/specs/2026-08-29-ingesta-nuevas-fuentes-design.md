# Diseño: ingesta de nuevas fuentes al grafo (V1.2)

- **Fecha:** 2026-08-29
- **Branch:** `feature/ingesta-nuevas-fuentes`
- **Estado:** aprobado, pendiente de plan de implementación

## 1. Problema

De los 13 archivos en `data/raw/`, ninguno llega al grafo. El loader consume
únicamente `data/sources/` (`io/files.py:6-12`) más el catálogo Georef, así que
sólo tres fuentes están efectivamente cargadas: Parque de la Memoria, Nietas y
Nietos, y CCDs (RUVTE). La tabla del README marca varias fuentes como
"Procesado" cuando lo que existe es la extracción a `data/raw/`, no la carga.

Este diseño incorpora las fuentes viables y levanta los bloqueos estructurales
que hoy lo impiden.

## 2. Alcance

### Entran

| Fuente | Archivo | Registros |
|---|---|---|
| Archivo de la Memoria de San Martín | `archivo_memoria_san_martin.json` | 303 |
| EAAF — sitios de hallazgo | `eaaf_lugares.csv` | 91 |
| MinJus GBA — víctimas | `derechos_humanos_minjus_gba_victimas.json` | 3257 |
| MinJus GBA — CCDs | `derechos_humanos_minjus_gba_centros_clandestinos.json` | 87 |
| MinJus GBA — imputados | `derechos_humanos_minjus_gba_imputados.json` | 454 |
| MinJus GBA — sentencias | `derechos_humanos_minjus_gba_sentencias.json` | 113 |
| Juicios Lesa Humanidad — condenados | `juicios_lesa_humanidad_condenados.json` | 1237 |

Volumen resultante: ~5.100 `:Persona` nuevas y ~180 lugares nuevos.

`sentencias` no genera nodos: no existe `:Sentencia` ni `:Causa` en el modelo.
Se usa como índice de metadatos (`tribunal`, `fecha`) para poblar `origen` y
`fecha` en las aristas `TORTURO_A`, según exige la regla 1.2 del modelo.

### Quedan fuera

| Archivo | Motivo |
|---|---|
| `eaaf_identificados.csv` | Sin columna de nombre: 877 casos anonimizados. `:Persona.nombre` es obligatorio y el modelo prohíbe inventar entidades intermedias. Además el archivo está dañado: 357 caracteres U+FFFD y cero acentos válidos. Los agregados por sitio que aportaría ya vienen en `eaaf_lugares.csv`. |
| `juicios_lesa_humanidad_argentina.json` | 369 causas judiciales con métricas procesales. No hay nodo de causa en el modelo. |
| `juicios_lesa_humanidad_exterior.json` | Ídem, y además incompleto: `metadata.totalItems` declara 64, el archivo trae 41. |
| `leyes_dictadura.xlsx`, semblanzas | Fuera del pedido de esta ronda. |

### Diferido explícitamente

El parsing de `lugar_de_secuestro` de MinJus víctimas: 2785 direcciones
narrativas con saltos de línea embebidos (`"Su domicilio sito en la\ncalle 9 de
Julio N° 830 de la localidad de Del Viso, partido de Pilar..."`). En esta ronda
**no se generan aristas `SECUESTRADO_EN` para esa fuente**. La capa espacial de
MinJus víctimas se conserva vía `PRESENTE_EN` a CCDs (2436 víctimas, resolución
determinista por URL, sin texto libre).

Para que el diferimiento no pierda información, `fecha_de_secuestro` (2937
registros) se persiste como propiedad `fecha_secuestro` en `:Persona`. Cuando se
retome el parsing, la arista se construye desde esa propiedad sin re-scrapear.

**No están diferidos** dos casos que superficialmente se parecen:
- El campo `lugar` de San Martín es un topónimo corto ("Billinghurst") que
  `resolve_place` resuelve bien.
- El `Domicilio` de los CCDs de MinJus se guarda crudo en
  `:DirecciónCCD.direccionExacta`, sin parsear — el mismo patrón que ya usa
  `builders/ccds.py:168` para RUVTE.

## 3. Bloqueos estructurales que se levantan

**B1 — Todas las personas se etiquetan `:Victima`.** `CYPHER_UPSERT_PERSONAS`
termina en `SET p:Victima` incondicional (`db/cypher.py:36`) y el CDM sólo acepta
`es_nietx`. No hay forma de expresar `:Represor` ni `:Complice`, lo que bloquea
por completo imputados y condenados.

**B2 — Las fuentes JSON directas no acceden a la normalización toponímica.**
`resolve_place()` y el gazetteer Georef sólo corren dentro de
`build_lugar_layer_rows`. Un JSON directo debe traer los `lugar_key` ya
resueltos, y `CYPHER_LINK_PERSONA_LUGAR_DYNAMIC` hace `MATCH` sobre
`:Lugar {lugar_key}`: si no existe, **descarta la fila en silencio**. Por eso
todas las fuentes nuevas van por builder Python (Paso B de
`docs/operations/ingesta_fuentes.md`), no por JSON directo.

**B3 — Media docena de tipos del modelo no están implementados.**
`:AliasPersona`, `:Profesión`, `:Cargo`, `:Org` e `:Institución` están
declarados en `NEO4J_DATA_MODEL.md` pero no tienen Cypher en el writer.

## 4. Extensión del CDM

`ALLOWED_SOURCE_KEYS` pasa de 5 a 7 claves:

```python
personas               # + roles, complice_tipo, fecha_nacimiento,
                       #   fecha_secuestro, claves_alt
lugares
relaciones_interpersonales
eventos_espaciales
jerarquias
entidades_contexto     # NUEVA
relaciones_contexto    # NUEVA
```

### 4.1 `personas` — campos nuevos

- `roles: List[str]` ⊂ `{VICTIMA, REPRESOR, COMPLICE, NIETX}`. Reemplaza a
  `es_nietx`.
- `complice_tipo: str` ∈ `{CIVIL, CLERICAL, EMPRESARIAL}`. Obligatorio si
  `COMPLICE` ∈ `roles` (el DDL ya lo exige).
- `fecha_nacimiento: str` (ISO), opcional.
- `fecha_secuestro: str` (ISO), opcional.
- `claves_alt: List[str]`, poblado por la reconciliación.

**Retrocompatibilidad:** `es_nietx: true` se mapea a `roles: ["NIETX"]`. Una fila
sin `roles` ni `es_nietx` recibe `["VICTIMA"]`, que es el comportamiento actual.
`builders/personas.py` y las fuentes JSON existentes siguen funcionando sin
cambios.

### 4.2 `entidades_contexto` (nueva)

- `entidad_key` (obligatorio), namespaceado por tipo para evitar colisiones entre
  labels distintas: `org:ejercito_argentino`, `institucion:uba`,
  `alias_persona:el_armenio`
- `tipo_entidad` ∈ `{Org, Institucion, Profesion, Cargo, AliasPersona}`
- `nombre` / `descripcion` / `titulo` / `alias` según tipo
- `tipoOrg` (sólo `Org`), `fuente`

### 4.3 `relaciones_contexto` (nueva)

- `persona_key`, `entidad_key` (obligatorios)
- `tipo_relacion` ∈ `{PARTE_DE, FUNDO, EJERCIO, ESTUDIO_EN, TRABAJO_EN, IDENTIFICA_A}`
- `fecha` (opcional), `origen` (obligatorio)

`IDENTIFICA_A` se escribe invertida: la arista va de `:AliasPersona` a
`:Persona`, no al revés.

### 4.4 Bump del modelo a V1.2

`NEO4J_DATA_MODEL.md` se declara "arquitectura exacta e inmutable". Este diseño
agrega tres propiedades a `:Persona` — `fecha_nacimiento`, `fecha_secuestro` y
`claves_alt` — que no están en V1.1.1. Se documentan explícitamente en un bump a
V1.2, no se introducen de contrabando. Justificación: las dos fechas son
necesarias para el matching determinista de la sección 6 y, sin lugar asociado,
no tienen ninguna arista donde vivir; `claves_alt` da trazabilidad del merge.

## 5. Cambios en el writer

1. **Labels dinámicas.** Quitar el `SET p:Victima` de `CYPHER_UPSERT_PERSONAS` y
   reemplazarlo por `apoc.create.addLabels(p, row.roles)`. Setear
   `p.tipo = row.complice_tipo` cuando corresponda. Este es el cambio que
   desbloquea imputados y condenados.
2. **Cinco upserts nuevos** para `:Org`, `:Institución`, `:Profesión`, `:Cargo`
   y `:AliasPersona`, con constraint de unicidad sobre `entidad_key`. Más
   `CYPHER_LINK_PERSONA_ENTIDAD` (dinámico vía APOC) y `CYPHER_LINK_ALIAS_PERSONA`
   para `IDENTIFICA_A`.
   `CYPHER_CLEAN_PROJECT` ya incluye estos cinco labels en su `DETACH DELETE`: no
   requiere cambios.
3. **Idempotencia.** Las aristas dinámicas usan `apoc.create.relationship`, que
   duplica en cada corrida sin `--clean-project`. Con decenas de miles de aristas
   nuevas eso deja de ser tolerable: migrar a `apoc.merge.relationship`.
   *Es un cambio de comportamiento sobre código existente.*
4. **Aristas huérfanas.** `CYPHER_LINK_PERSONA_LUGAR_DYNAMIC` descarta filas en
   silencio cuando el `lugar_key` no existe. Agregar contabilización de
   no-resueltos al reporte QA (`db/qa.py`).

## 6. Reconciliación de identidades

Módulo nuevo `domain/identity_resolution.py`, ejecutado sobre el CDM en memoria
antes de abrir la sesión de Neo4j (paso 3.5 de `pipeline/load_graph.py`).

**Política elegida: merge determinista + candidatos.**

1. **Bloqueo** por `slugify_name(nombre)`, para evitar comparación O(n²). Mismo
   patrón que ya usa `builders/candidatos.py`.
2. **Merge** sólo con evidencia fuerte: nombre normalizado idéntico **y**
   coincidencia exacta (ISO) de `fecha_nacimiento` o `fecha_secuestro`. Se
   reescriben todas las referencias en `relaciones_interpersonales`,
   `eventos_espaciales` y `relaciones_contexto`, y se acumulan `claves_alt` y
   `fuente` concatenada.

   La clave canónica se elige por una lista de prioridad de fuente declarada como
   constante, con este orden por defecto (de mayor a menor): `detalles_personas`
   (Parque de la Memoria) → `nietxs_relacion` → `archivo_memoria` →
   `minjus_victimas` → `minjus_imputados` → `juicios_condenados`. El criterio es
   preferir la fuente que ya está cargada y tiene claves estables, para que los
   merges no reescriban las claves preexistentes del grafo. Ante empate dentro de
   la misma prioridad, gana la clave menor en orden lexicográfico (determinismo
   reproducible entre corridas).
3. **Regla de seguridad:** nunca fusionar dos personas de la misma fuente. Si el
   origen ya las distingue, son distintas.
4. **Sin evidencia fuerte** → arista `CANDIDATO_MERGE`, que ya existe en el
   writer con `score` / `metodo` / `confianza`:
   - nombre idéntico sin fecha confirmatoria → confianza media
   - fuzzy ≥ 0.96 vía `name_similarity_score` → confianza baja
5. **Auditoría:** volcado a `data/processed/identity_merges.json`. Flag
   `--skip-identity-resolution`.

Rechazado: merge por similitud de nombre sin fecha confirmatoria (riesgo alto de
conflacionar homónimos, inaceptable en un dataset de derechos humanos), y no
mergear nada (dejaría ~5k duplicados e inflaría todo conteo).

## 7. Builders

Siete builders en `builders/`, siguiendo el Paso B de `ingesta_fuentes.md`
(adaptador Python para fuentes que requieren Georef o parsing fino). Leen de
`data/raw/`.

| Builder | Complejidad | Aporte principal |
|---|---|---|
| `eaaf_lugares.py` | Baja | 91 sitios de hallazgo, 100% con lat/long. 3 filas de Uruguay → `pais_code`. Capa nueva: sitios de exhumación |
| `archivo_memoria.py` | Baja | 303 víctimas de Zona IV / San Martín; fechas ya ISO, topónimos cortos |
| `juicios_condenados.py` | Baja | 1237 represores. CIVILES (197) → `:Complice {tipo:"CIVIL"}`; `Fuerza` → `:Org` |
| `minjus_sentencias.py` | Baja | No emite nodos: índice `sentencia_url → {tribunal, fecha}` que consumen víctimas e imputados |
| `minjus_ccds.py` | Media | 87 CCDs; requiere dedup contra `ccds.json` (RUVTE) reusando la similitud toponímica existente |
| `minjus_imputados.py` | Media | 454 represores; `fuerza` → `:Org`; delitos → `TORTURO_A` |
| `minjus_victimas.py` | Media | 3257 víctimas, `PRESENTE_EN` a CCDs, `TORTURO_A`, contexto (militancia 1627, trabajo 1346, apodo 831, estudios 644) |

Flag nuevo `--dump-cdm <path>`: vuelca el CDM consolidado a JSON. Da
auditabilidad del intermedio sin versionar archivos gigantes.

### Nota sobre género

Ninguna de las fuentes nuevas trae sexo. Las ~5.100 personas entran como
`INDETERMINADO`. No se infiere género a partir del nombre.

## 8. Testing

El repositorio no tiene tests, ni `pyproject.toml`, ni `requirements.txt`; el
README asume un `.venv` no versionado. Dado el volumen de lógica nueva se agrega
andamiaje mínimo:

- `requirements.txt` con las dependencias hoy implícitas (`neo4j`, `requests`).
- `pytest` con tests unitarios sobre lo que no necesita Neo4j:
  - normalización de fechas y lugares por fuente
  - mapeo de roles y retrocompatibilidad de `es_nietx`
  - **el módulo de reconciliación**, con casos adversarios tomados de los datos
    reales: homónimos, `"Abadía Crespo, Dominga"` vs `"Abadía Crespo, Felicidad"`
    (dos personas distintas en MinJus con nombres muy similares), y personas
    repetidas entre MinJus y Parque de la Memoria
  - builders, con fixtures recortados de los raw

## 9. Riesgos

- **`apoc.merge.relationship`** cambia el comportamiento de la carga actual.
- **Escala:** pasar de 3 fuentes a ~5.100 personas puede mover los tiempos del
  paso de candidatos. Medir antes y después.
- **Dedup de CCDs:** MinJus (87) contra RUVTE (`ccds.json`) es la decisión de
  calidad más delicada que queda en el alcance.
- **Deuda de modelo:** `:Cargo` y `:Profesión` quedan implementados en el writer
  pero casi sin datos que los pueblen en esta ronda.
- **Documentación desactualizada:** el README describe el loader como consumidor
  exclusivo de `data/sources/`. Con builders leyendo `data/raw/` eso deja de ser
  exacto (sigue siendo estrictamente offline) y hay que corregirlo, junto con la
  columna "Estado" de la tabla de fuentes, que hoy confunde extracción con carga.

## 10. Orden de implementación

1. Andamiaje de tests (`requirements.txt`, `pytest`)
2. Writer: labels dinámicas, entidades de contexto, idempotencia (sección 5)
3. CDM: claves nuevas y retrocompatibilidad (sección 4)
4. Reconciliación de identidades (sección 6)
5. Builders de menor a mayor riesgo: `eaaf_lugares` → `archivo_memoria` →
   `juicios_condenados` → `minjus_sentencias` → `minjus_ccds` →
   `minjus_imputados` → `minjus_victimas`
6. Documentación: bump de `NEO4J_DATA_MODEL.md` a V1.2, `ingesta_fuentes.md`,
   README (estado de fuentes), `docs/sources/` para las fuentes descartadas y
   para el pendiente de direcciones en texto libre

## 11. Pendientes registrados (fuera de esta ronda)

- Parsing de `lugar_de_secuestro` de MinJus víctimas → aristas `SECUESTRADO_EN`
  (2785 direcciones). `place_norm.extract_specific_address()` ya contempla
  prefijos narrativos tipo `"SU DOMICILIO"`, así que hay base sobre la cual
  construir; falta medir la tasa de resolución real.
- `web_scraper_eaaf.py` corrompe `eaaf_identificados.csv` al forzar `latin1`.
- Paginación incompleta en el crawler de juicios (exterior: 41 de 64).
- `leyes_dictadura.xlsx` no tiene extractor ni consumidor, pero figura como
  "Procesado" en el README.

# Modelo de grafo Neo4j (v3)

Este documento propone una primera version del modelo para integrar:
- `data/detalles_personas.json`
- `data/nietxs_relacion.json`

Objetivo: tener una base consistente para consultas genealogicas y de contexto historico, con reglas de normalizacion explicitas y trazables.

## Hallazgos de perfilado

- `detalles_personas.json`: 8948 registros.
- `nietxs_relacion.json`: 392 casos (`id_nietx`).
- Relaciones en `nietxs_relacion`:
  - `Madre`: 390
  - `Padre`: 358
  - `Abuela materna`: 111
  - `Abuela paterna`: 105
  - `Hermanx`: 92
- Relaciones con `id_persona` en `nietxs_relacion`: 680 de 1056.
- Cobertura referencial `id_persona` -> `registro` de `detalles_personas`: 100% (644 ids unicos, todos existen).

## Entidades

### `(:Persona)`
Nodo canonico para personas provenientes de cualquiera de las fuentes.

Propiedades recomendadas:
- `persona_key` (string, unique): clave tecnica global.
- `registro` (int, opcional): id de Parque de la Memoria.
- `nombre_completo` (string)
- `nombre` (string, opcional)
- `apellido` (string, opcional)
- `sexo` (string, opcional)
- `estado_desaparicion` (string, opcional)
- `fecha_nacimiento` (date, opcional)
- `fecha_secuestro` (date, opcional)
- `fecha_asesinato` (date, opcional)
- `lugar_nacimiento` (string, opcional)
- `lugar_secuestro` (string, opcional)
- `es_placeholder` (bool, default false): true para personas sin id estable (solo nombre texto).
- `fuentes` (list<string>): por ejemplo `['detalles_personas']`, `['nietxs_relacion']`, o ambas.

### `(:CasoNietx)`
Nodo para el caso del buscador de Abuelas.

Propiedades recomendadas:
- `id_nietx` (int, unique)
- `nombre_caso` (string)
- `estado` (string)
- `imagen_url` (string)
- `conoce_la_historia_url` (string)
- `resumen_data` (string)
- `detalle_data` (string)
- `fecha_adn` (date, opcional)
- `fecha_restitucion` (date, opcional)

### `(:Evento)`
Nodo para hechos historicos y de trazabilidad del proceso de restitucion.

Propiedades recomendadas:
- `evento_key` (string, unique)
- `tipo` (string): `SECUESTRO`, `ASESINATO`, `ADN`, `RESTITUCION`, `SECUESTRO_CCD`, `PARTO_CAUTIVERIO_CCD`, `EVENTO_CCD`
- `fecha` (date/string ISO, opcional)
- `fecha_inicio` (date/string ISO, opcional): inicio de rango cuando la fuente no tiene dia exacto
- `fecha_fin` (date/string ISO, opcional): fin de rango cuando la fuente informa rango
- `fecha_precision` (string, opcional): `DAY`, `MONTH`, `YEAR` o `RANGE`
- `anio` (int, opcional): anio efectivo para agregaciones rapidas
- `anio_inicio` (int, opcional): anio del inicio de rango
- `anio_fin` (int, opcional): anio del fin de rango
- `lugar` (string, opcional)
- `descripcion_raw` (string, opcional)
- `fuente` (string)
- `id_ccd` (string, opcional)
- `ccd_relacion` (string, opcional)
- `ccd_certeza` (string, opcional)
- `ccd_denominacion` (string, opcional)

### `(:PaginaListado)`
Representa una pagina del index de Parque de la Memoria (`listado_paginas.json`).

Propiedades recomendadas:
- `pagina_key` (string, unique): `listado:pagina:{n}`
- `pagina` (int)
- `url` (string)
- `registros_count` (int)
- `fuente` (string)

## Relaciones

### Entre caso y protagonista
- `(:CasoNietx)-[:TIENE_PROTAGONISTA]->(:Persona)`

La persona protagonista usa `persona_key = 'nietx:' + id_nietx` para evitar colisiones.

### Relaciones familiares del caso
- `(:Persona)-[:VINCULO_FAMILIAR {tipo, tipo_raw, fuente}]->(:Persona)`

`fuente='nietxs_relacion'`, `tipo` normalizado.

### Relaciones entre personas en base general
- `(:Persona)-[:VINCULO_PERSONA {tipo, tipo_raw, fuente}]->(:Persona)`
- `(:Persona)-[:VICTIMA_SIMULTANEA {fuente}]->(:Persona)`

`fuente='detalles_personas'`.

### Relaciones con eventos
- `(:Persona)-[:PARTICIPO_EN {rol, fuente}]->(:Evento)`
- `(:CasoNietx)-[:REGISTRA_EVENTO {fuente}]->(:Evento)`

Reglas v2:
- Desde `detalles_personas`, se crea evento `SECUESTRO` y/o `ASESINATO` por persona cuando hay fecha y/o lugar.
- Desde `nietxs_relacion`, se crea evento `ADN` y/o `RESTITUCION` cuando hay fecha en `restituido`.

Reglas v2.1 (ccds):
- Desde `parque_de_la_memoria.json.ccds`, se crea un evento por referencia CCD (`SECUESTRO_CCD` o `PARTO_CAUTIVERIO_CCD`).
- Si `fecha` tiene una sola marca parcial (por ejemplo `1976`, `1976/08`), se materializa como rango (`fecha_inicio`, `fecha_fin`) y `fecha` toma el inicio del rango para mantener consultas cronologicas simples.
- Si `fecha` trae dos valores, se interpreta como rango y se guarda en `fecha_inicio`/`fecha_fin` con `fecha_precision='RANGE'`.
- `certeza` de la fuente se conserva en `Evento.ccd_certeza`.

Reglas de lugar para CCD:
- Se crea `(:Lugar {tipo:'CCD'})` por cada `id_ccd` presente en `ccds.json`.
- Se preservan coordenadas `lat`/`lon` del CCD en el nodo `Lugar` y se enlaza el evento con `(:Evento)-[:OCURRIO_EN]->(:Lugar)` usando el `id_ccd` de la referencia.
- Se intenta resolver por coordenadas a un `Lugar` geografico ya existente para reutilizar nodos y evitar fragmentacion de ubicaciones.
- Cuando hay match, el `Lugar` CCD se conserva como entidad de sitio y se conecta por jerarquia (`PARTE_DE`) al lugar geografico reutilizado.

## Criterios de escalabilidad analitica

Para soportar analitica de relacion entre personas, hotspots de eventos y conciliacion:
- Mantener eventos como hechos atomicos (`:Evento`) y nunca incrustar listas historicas en `:Persona`.
- Usar fechas en dos niveles: `fecha` (punto) + `fecha_inicio/fecha_fin` (rango) + columnas derivadas (`anio*`) para agregaciones masivas.
- Reutilizar `:Lugar` por identidad canonica y coordinar CCD como capa semantica encima del lugar geografico.
- Preservar trazabilidad en relaciones (`fuente`, `campo_fuente`, `ccd_certeza`, `id_ccd`) para auditar conciliaciones.
- Priorizar conciliacion asistida para personas/lugares ambiguos y merges automaticos solo en casos seguros.

### Reconciliacion asistida (v3)
- `(:Persona {es_placeholder:true})-[:CANDIDATO_MERGE {metodo, score, confianza, slug, fuente}]->(:Persona {registro IS NOT NULL})`

Reglas v3 actuales:
- Se proponen candidatos por `slug_exacto` de nombre normalizado.
- No se ejecuta `MERGE` de nodos automaticamente; solo se generan sugerencias para revision humana.

### Integracion de listado paginado
- `(:Persona)-[:LISTADA_EN {fuente, detail_url, estado_raw, edad, anio, embarazo_estado, embarazo_meses}]->(:PaginaListado)`

Uso:
- Trazabilidad del scraping por pagina.
- No crea nuevas personas; solo conecta por `registro` a `:Persona` existente.

## Reglas de normalizacion

## 1) Identidad y llaves

Prioridad para `persona_key`:
1. Si existe `registro`: `registro:{id}`
2. Si es protagonista de nietx: `nietx:{id_nietx}`
3. Si no hay id, pero hay nombre: `nombre:{slug_nombre}`

`slug_nombre`:
- lowercase
- quitar tildes/diacriticos
- reemplazar multiples espacios por uno
- quitar puntuacion

Nota: `nombre:{slug}` puede producir homonimos; marcar `es_placeholder=true` y luego resolver en una iteracion v2.

## 2) Normalizacion de tipos de relacion

Mapa inicial sugerido:
- `madre` -> `MADRE`
- `padre` -> `PADRE`
- `hermanx`, `hermano`, `hermana` -> `HERMANO`
- `abuela materna` -> `ABUELA_MATERNA`
- `abuela paterna` -> `ABUELA_PATERNA`
- `esposo`, `esposa`, `conyuge`, `pareja`, `ex esposo`, `ex esposa` -> `PAREJA`
- `hijo`, `hija` -> `HIJO`
- `companero`, `companera`, `novio`, `novia` -> `PAREJA`
- Otros -> `OTRA`

Guardar SIEMPRE `tipo_raw` para trazabilidad.

## 3) Fechas

Soportar dos formatos de entrada:
- `dd/mm/yyyy` (ejemplo: `26/12/1976`)
- `d de <mes>, yyyy` (ejemplo: `4 de julio, 2025`)

Convertir a `date` ISO (`yyyy-mm-dd`) cuando sea parseable.
Si no, guardar en propiedad raw (`fecha_*_raw`) y dejar la fecha normalizada en null.

## 4) Valores vacios y ruido

Tratar como null:
- `""`
- `"No hay informacion."`
- `"-"`

No descartar filas por campos faltantes; crear nodo minimo y registrar `es_placeholder` cuando corresponda.

## 5) Dedupe incremental (v2)

Regla inicial segura:
- fusionar automatico solo por `registro`.

Regla manual/asistida posterior:
- candidatos por `slug_nombre` + cercania semantica + contexto de relaciones.
- confirmar antes de merge definitivo.

## 6) Normalizacion de lugares (v4 operativo)

Para `Lugar/AliasLugar` se aplica una normalizacion de identidad conservadora antes de generar `lugar_key`:
- abreviaturas frecuentes: `CDAD` -> `CIUDAD`, `CAP FED` -> `CAPITAL FEDERAL`, `STA` -> `SANTA`.
- typo frecuente: `SECUETRADO` -> `SECUESTRADO`.
- variantes de genero/numero: `SECUESTRADA/SECUESTRADOS/SECUESTRADAS` -> `SECUESTRADO`.
- ruido narrativo recurrente: se eliminan frases `DE SU DOMICILIO` y `EN SU DOMICILIO`.

Objetivo:
- mantener idempotencia por scope (`alias_norm`, `tipo`, `parent_key`).
- reducir fragmentacion de nodos `INDETERMINADO` causada por texto narrativo, sin forzar merges agresivos.

### 6.1 Resolucion jerarquica con Georef (v5)

Se agrega una etapa opcional (activa por default si existe `data/georef_catalog.json`) para desambiguar `Lugar` con jerarquia geografica:
- orden de evidencia: `provincia -> departamento -> municipio -> localidad`.
- se priorizan coincidencias de mayor especificidad y mayor longitud de n-grama.
- si no hay provincia explicita, se usa un prior debil por ranking poblacional de provincia como desempate.
- si la diferencia entre primer y segundo candidato es menor al delta de ambiguedad, no se fuerza resolucion y cae en `INDETERMINADO`.

Comando para generar el catalogo local:

```bash
PYTHONPATH=src .venv/bin/python scripts/download_georef_catalog.py --output data/georef_catalog.json
```

Flags del loader relacionadas:
- `--disable-georef-resolver`
- `--georef-catalog-path`
- `--georef-min-score`
- `--georef-ambiguity-delta`

## Constraints e indices

```cypher
CREATE CONSTRAINT persona_key_unique IF NOT EXISTS
FOR (p:Persona) REQUIRE p.persona_key IS UNIQUE;

CREATE CONSTRAINT caso_nietx_id_unique IF NOT EXISTS
FOR (c:CasoNietx) REQUIRE c.id_nietx IS UNIQUE;

CREATE CONSTRAINT evento_key_unique IF NOT EXISTS
FOR (e:Evento) REQUIRE e.evento_key IS UNIQUE;

CREATE INDEX persona_registro_idx IF NOT EXISTS
FOR (p:Persona) ON (p.registro);

CREATE INDEX persona_nombre_idx IF NOT EXISTS
FOR (p:Persona) ON (p.nombre_completo);

CREATE INDEX evento_tipo_idx IF NOT EXISTS
FOR (e:Evento) ON (e.tipo);

CREATE INDEX evento_fecha_idx IF NOT EXISTS
FOR (e:Evento) ON (e.fecha);

CREATE CONSTRAINT pagina_listado_key_unique IF NOT EXISTS
FOR (pg:PaginaListado) REQUIRE pg.pagina_key IS UNIQUE;

CREATE INDEX pagina_listado_num_idx IF NOT EXISTS
FOR (pg:PaginaListado) ON (pg.pagina);
```

## Queries de validacion

```cypher
// 1) Cobertura de familiares con id estable
MATCH (:Persona:Nietx)-[r:VINCULO_FAMILIAR {fuente:'nietxs_relacion'}]->(f:Persona)
RETURN count(r) AS total_rel,
       count(CASE WHEN f.registro IS NOT NULL THEN 1 END) AS rel_con_registro;

// 2) Personas placeholder para priorizar reconciliacion
MATCH (p:Persona {es_placeholder:true})
RETURN count(p) AS placeholders;

// 3) Top tipos de relaciones familiares
MATCH (:Persona:Nietx)-[r:VINCULO_FAMILIAR {fuente:'nietxs_relacion'}]->(:Persona)
RETURN r.tipo AS tipo, count(*) AS c
ORDER BY c DESC;

// 4) Distribucion de eventos
MATCH (e:Evento)
RETURN e.tipo AS tipo, count(*) AS c
ORDER BY c DESC;
```

## Iteracion recomendada

- v1: `Persona` + `CasoNietx` + relaciones familiares y de victimas relacionadas.
- v2: nodos `Evento` (`Secuestro`, `Asesinato`, `ADN`, `Restitucion`) y relaciones caso/persona-evento.
- v3 (actual): reconciliacion asistida de placeholders con relaciones `CANDIDATO_MERGE`.

## Merges seguros de lugares (opcional)

El loader permite una etapa opcional de consolidacion automatica conservadora:
- flag: `--apply-safe-place-merges`
- alcance: solo `Lugar.tipo = 'CIUDAD'`
- criterio: variantes tipograficas de un solo token dentro del mismo scope (`tipo + parent_key`), sin diferencias de direccion (`ESTE/OESTE/NORTE/SUR`) ni numeros.

Objetivo:
- reducir fragmentacion por typos sin aplicar merges agresivos.
- mantener casos ambiguos (`INDETERMINADO`, diferencias estructurales) para revision manual.

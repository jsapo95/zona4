# Ingesta unificada de nuevas fuentes

Este documento define las directrices para incorporar nuevas fuentes de datos históricas al pipeline de **ZONA4** sin alterar la estabilidad del código principal, basándose en la arquitectura del **Modelo de Datos Canónico (CDM) Simplificado**.

---

## 1. Arquitectura de Ingesta y Directorios

El pipeline de ingesta trata de forma homogénea a todos los datasets estructurados, almacenándolos en la misma ubicación:
```
data/
  └── sources/
      ├── ccds.json                # CCDs base
      ├── nietos_y_nietas.json     # Nietxs base
      ├── parque_de_la_memoria.json# Personas base
      └── nuevas_sentencias.json   # Nueva fuente añadida
```

### Tipos de Fuentes Soportadas:
1.  **Fuente con Adaptador (Builder en Python)**: Para archivos crudos que requieren lógica de negocio compleja, normalización toponímica interactiva con Georef, o parsing textual fino.
2.  **Fuente de Carga Directa (JSON)**: Para aportes de información descentralizados rápidos que ya están estructurados en el formato del CDM y no requieren un script intermedio.

**Corrección:** el loader no lee exclusivamente `data/sources/`. Los builders de
las fuentes incorporadas en esta iteración (EAAF, Archivo de la Memoria de San
Martín, MinJus GBA, Juicios de Lesa Humanidad) leen sus archivos crudos desde
`data/raw/` a través de `io/raw_files.py`, y se invocan explícitamente desde
`pipeline/load_graph.py::run_load` (bloque `if not args.skip_nuevas_fuentes`).
`data/sources/` sigue siendo el mecanismo de carga directa en formato CDM de la
sección 2. Ambos caminos son estrictamente locales y offline: ninguno hace
peticiones de red durante la carga.

---

## 2. El Modelo de Datos Canónico (CDM) Simplificado

Todas las fuentes consolidan sus registros en un contenedor unificado en memoria (`CanonicalDataset`) con **7 categorías semánticas esenciales**. Todas las colecciones son opcionales, permitiendo que una fuente simple solo aporte una o dos categorías:

```python
class CanonicalDataset(TypedDict, total=False):
    personas: List[Dict[str, Any]]
    lugares: List[Dict[str, Any]]
    relaciones_interpersonales: List[Dict[str, Any]]
    eventos_espaciales: List[Dict[str, Any]]
    jerarquias: List[Dict[str, Any]]
    entidades_contexto: List[Dict[str, Any]]
    relaciones_contexto: List[Dict[str, Any]]
```

### 2.1 `personas`
Define nodos `:Persona` y sus roles asociados.
*   `persona_key` (str, obligatorio, e.g., `"registro:123"`, `"sentencia:84"`).
*   `nombre` (str, obligatorio).
*   `genero` (str, obligatorio: `"MASCULINO"`, `"FEMENINO"`, `"INDETERMINADO"`).
*   `fuente` (str, obligatorio).
*   `roles` (List[str], opcional: subconjunto de `"VICTIMA"`, `"REPRESOR"`,
    `"COMPLICE"`, `"NIETX"`). El loader los normaliza con
    `domain/roles.py::normalize_roles` y los aplica como labels dinámicas vía
    `apoc.create.addLabels` (reemplaza el `SET p:Victima` incondicional
    anterior). Una fila sin `roles` cae en `es_nietx` y, si tampoco está, en
    `["VICTIMA"]` (retrocompatibilidad).
*   `complice_tipo` (str, obligatorio si `"COMPLICE"` está en `roles`:
    `"CIVIL"`, `"CLERICAL"`, `"EMPRESARIAL"`).
*   `es_nietx` (bool, opcional, retrocompatible: si es `True` y no hay `roles`,
    se le asignará el rol `:Nietx`).
*   `fecha_nacimiento` / `fecha_secuestro` (str ISO, opcionales, V1.2). La
    segunda se persiste en el nodo cuando la fuente no permite construir la
    arista `SECUESTRADO_EN` (ver `docs/sources/minjus_gba.md`).
*   `claves_alt` (List[str], opcional, V1.2): claves de otras fuentes
    absorbidas por la reconciliación de identidades (paso 3.5, más abajo).

### 2.2 `lugares`
Define nodos geográficos, CCDs, aliases o direcciones.
*   `lugar_key` / `alias_key` / `direccion_ccd_key` (str, obligatorio).
*   `tipo_entidad` (str, obligatorio: `"Lugar"`, `"AliasLugar"`, `"DireccionCCD"`).
*   *Para Lugar*: `nombre`, `tipoGeopolitico` (`"CCD"`, `"CIUDAD"`, `"PROVINCIA"`, etc.), `pais_code`, `fuente`.
*   *Para AliasLugar*: `alias_norm`, `alias_raw`, `parent_key`, `lugar_key`, `tipo`.
*   *Para DireccionCCD*: `coordenadas`, `direccionExacta`, `lugar_key`.

### 2.3 `relaciones_interpersonales`
Define aristas genealógicas, de co-militancia, represivas o de avistamiento.
*   `source_key` (str, obligatorio).
*   `target_key` (str, obligatorio).
*   `tipo` (str, obligatorio, e.g., `"HIJE_DE"`, `"PAREJA_DE"`, `"TORTURO_A"`, `"VIO_A"`).
*   `fuente` (str, obligatorio).
*   `fecha` (str, opcional).

### 2.4 `eventos_espaciales`
Define aristas de eventos directos espacio-temporales entre Persona y Lugar.
*   `persona_key` (str, obligatorio).
*   `lugar_key` (str, obligatorio).
*   `tipo_relacion` (str, obligatorio: `"SECUESTRADO_EN"`, `"PRESENTE_EN"`, `"NACIO_EN"`, `"ASESINADO_EN"`).
*   `fecha` (str, opcional).
*   `origen` (str, obligatorio).

### 2.5 `jerarquias`
Define aristas estructurales de la capa geopolítica.
*   `tipo_relacion` (str, obligatorio: `"PARTE_DE"`, `"UBICADA_EN"`).
*   *Para PARTE_DE*: `child_key`, `parent_key`.
*   *Para UBICADA_EN*: `direccion_ccd_key`, `lugar_key`.

### 2.6 `entidades_contexto`
Define nodos de contexto biográfico.
*   `entidad_key` (str, obligatorio, namespaceado: `"org:ejercito_argentino"`).
*   `tipo_entidad` (str, obligatorio: `"Org"`, `"Institucion"`, `"Profesion"`, `"Cargo"`, `"AliasPersona"`).
*   Según tipo: `nombre` (Org, Institucion), `descripcion` (Profesion), `titulo` (Cargo), `alias` (AliasPersona).
*   `tipoOrg` (str, opcional, sólo para Org).
*   `fuente` (str, obligatorio).

### 2.7 `relaciones_contexto`
Define aristas Persona -> entidad de contexto.
*   `persona_key` (str, obligatorio).
*   `entidad_key` (str, obligatorio).
*   `tipo_relacion` (str, obligatorio: `"PARTE_DE"`, `"FUNDO"`, `"EJERCIO"`, `"ESTUDIO_EN"`, `"TRABAJO_EN"`, `"IDENTIFICA_A"`).
*   `origen` (str, obligatorio), `fecha` (str, opcional).

`IDENTIFICA_A` se escribe invertida: la arista nace en el `:AliasPersona` y
apunta a la `:Persona`.

Los cinco tipos (`Org`, `Institucion`, `Profesion`, `Cargo`, `AliasPersona`)
comparten una label técnica común, `:EntidadContexto`, que es donde vive la
única constraint de unicidad sobre `entidad_key`
(`entidad_contexto_key_unique` en `db/cypher.py`), compartida entre los cinco.

### 2.8 Reconciliación de identidades (paso 3.5 del pipeline)

Antes de escribir nada en Neo4j, `domain/identity_resolution.py::resolve_identities`
recorre `personas` agrupando por nombre normalizado y fusiona un grupo sólo si
forma un **clique completo** de fechas confirmadas: para cada par del grupo,
`fecha_nacimiento` o `fecha_secuestro` deben coincidir cuando ambos registros
traen el campo, y si un par trae fechas contradictorias el merge completo se
veta (no se hace un merge parcial del subconjunto que sí coincide). Los grupos
que fallan ese criterio, pero son sospechosos por nombre o similitud fuzzy,
quedan como aristas `CANDIDATO_MERGE` para revisión humana en vez de perderse.
Cada merge registra su procedencia (`persona_key` absorbida, campo de fecha que
lo confirmó) en `data/processed/identity_merges.json`, para que la decisión sea
auditable y, si se demuestra errónea, reversible sin reprocesar las fuentes.

---

## 3. Flujo para Sumar una Nueva Fuente

### Paso A: Si es una Fuente Directa (JSON CDM)
1.  Formatear el JSON según el modelo de 7 claves. Ver plantilla: `data/sources/_template_source.json`.
2.  Guardarlo en `data/sources/nombre_fuente.json`.
3.  El módulo `sources_ingestor.py` lo cargará automáticamente en la siguiente ingesta.

### Paso B: Si requiere un Builder
1.  Crear el script de transformación en `src/zona4_graph_loader/builders/nombre_fuente.py`.
2.  Implementar la clase que retorne un objeto `CanonicalDataset`.
3.  Registrar el builder en [load_graph.py](file:///Users/a4649783/Documents/UNSAM/zona4/src/zona4_graph_loader/pipeline/load_graph.py) y mezclar su salida en el dataset `consolidated` mediante `_merge_datasets`.

Si la fuente cruda no viene ya estructurada en JSON/CSV en `data/sources/`,
guardarla en `data/raw/` y leerla desde el builder con `io/raw_files.py`
(`read_raw_csv` / `read_raw_json`); ver la sección 1 para la corrección sobre
qué directorio lee cada mecanismo.

---

## 4. Comandos de Operación y Validación

Validar la correctitud de las fuentes directas de JSON sin inyectar datos en Neo4j:
```bash
PYTHONPATH=src .venv/bin/python -m zona4_graph_loader.cli --validate-sources-only
```

Ejecutar la ingesta local con limpieza previa del proyecto:
```bash
PYTHONPATH=src \
NEO4J_URI=bolt://localhost:17687 \
NEO4J_USERNAME=neo4j \
NEO4J_PASSWORD=zona4local \
NEO4J_DATABASE=neo4j \
.venv/bin/python -m zona4_graph_loader.cli --clean-project --apply-safe-place-merges
```

Flags útiles para el manejo de fuentes:
*   `--sources-dir`: Indica la ruta a la carpeta de fuentes (por defecto `data/sources`).
*   `--skip-direct-sources`: Desactiva la lectura automática de archivos JSON directos en disco.
*   `--skip-nuevas-fuentes`: No integra los builders que leen de `data/raw/`
    (EAAF, Archivo de la Memoria de San Martín, MinJus GBA, condenados de
    Juicios de Lesa Humanidad).
*   `--skip-identity-resolution`: No corre la reconciliación de identidades del
    paso 3.5 (sección 2.8); las fuentes quedan sin deduplicar entre sí.
*   `--dump-cdm <path>`: Vuelca el `CanonicalDataset` consolidado (ya con roles
    normalizados e identidades reconciliadas) a un JSON en `<path>`, para
    auditoría sin necesidad de una base Neo4j corriendo.

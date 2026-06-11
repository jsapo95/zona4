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

---

## 2. El Modelo de Datos Canónico (CDM) Simplificado

Todas las fuentes consolidan sus registros en un contenedor unificado de en memoria (`CanonicalDataset`) con **5 categorías semánticas esenciales**. Todas las colecciones son opcionales, permitiendo que una fuente simple solo aporte una o dos categorías:

```python
class CanonicalDataset(TypedDict, total=False):
    personas: List[Dict[str, Any]]
    lugares: List[Dict[str, Any]]
    relaciones_interpersonales: List[Dict[str, Any]]
    eventos_espaciales: List[Dict[str, Any]]
    jerarquias: List[Dict[str, Any]]
```

### 2.1 `personas`
Define nodos `:Persona` y sus roles asociados.
*   `persona_key` (str, obligatorio, e.g., `"registro:123"`, `"sentencia:84"`).
*   `nombre` (str, obligatorio).
*   `genero` (str, obligatorio: `"MASCULINO"`, `"FEMENINO"`, `"INDETERMINADO"`).
*   `fuente` (str, obligatorio).
*   `es_nietx` (bool, opcional, si es `True` se le asignará el rol `:Nietx`).

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

---

## 3. Flujo para Sumar una Nueva Fuente

### Paso A: Si es una Fuente Directa (JSON CDM)
1.  Formatear el JSON según el modelo de 5 claves. Ver plantilla: `data/sources/_template_source.json`.
2.  Guardarlo en `data/sources/nombre_fuente.json`.
3.  El módulo `sources_ingestor.py` lo cargará automáticamente en la siguiente ingesta.

### Paso B: Si requiere un Builder
1.  Crear el script de transformación en `src/zona4_graph_loader/builders/nombre_fuente.py`.
2.  Implementar la clase que retorne un objeto `CanonicalDataset`.
3.  Registrar el builder en [load_graph.py](file:///Users/a4649783/Documents/UNSAM/zona4/src/zona4_graph_loader/pipeline/load_graph.py) y mezclar su salida en el dataset `consolidated` mediante `_merge_datasets`.

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

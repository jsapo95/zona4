# Guía del Repositorio ZONA4 para Modelos de Lenguaje (LLMs)

Esta guía documenta la arquitectura global del proyecto **ZONA4**, detallando el modelo de datos en grafos (Neo4j), el pipeline de carga, normalización, validación, extensibilidad y comandos técnicos. El objetivo es proporcionar un contexto completo y estructurado para que cualquier LLM o desarrollador pueda operar con este repositorio con la máxima precisión técnica y semántica.

---

## 1. Visión General del Proyecto y Objetivos
El proyecto **ZONA4** (Universidad Nacional de General San Martín - UNSAM) tiene como objetivo la reconstrucción histórica, de memoria y derechos humanos vinculados a los crímenes de lesa humanidad perpetrados durante la última dictadura cívico-militar en Argentina, enfocándose territorialmente en la **Zona de Defensa IV** (con centro operativo en Campo de Mayo) y extendiéndose a todo el territorio nacional.

### Objetivos Principales:
1. **Ingeniería de Datos**: Extracción, limpieza y normalización de registros provenientes de múltiples fuentes heterogéneas (bases de datos públicas, sentencias, archivos desclasificados, libros).
2. **Base de Datos en Grafos (Neo4j)**: Estructuración de la información en un Knowledge Graph (Grafo de Conocimiento) para analizar redes interpersonales, CCDs, eventos de secuestro, nacimientos en cautiverio, etc.
3. **Reconciliación de Identidades**: Resolución probabilística de identidades (merge asistido por IA) de personas cuyas identidades son parciales o descritas por testigos.
4. **Visualización y Tableros**: Dashboard analítico e interfaz de consulta Graph-RAG (futura integración).

---

## 2. Arquitectura del Repositorio
A continuación se detalla la estructura física del proyecto con enlaces de referencia directa:

* **Archivos Raíz**:
  * [README.md](file:///Users/a4649783/Documents/UNSAM/zona4/README.md): Documento principal con la introducción del proyecto y los objetivos de la Comisión.
  * [docker-compose.yml](file:///Users/a4649783/Documents/UNSAM/zona4/docker-compose.yml): Configuración de Docker para desplegar Neo4j local con plugins habilitados (`apoc` y `graph-data-science`).
  * [LICENSE](file:///Users/a4649783/Documents/UNSAM/zona4/LICENSE): Licencia de uso del código.
* **Directorio de Datos (`data/`)**:
  * `raw/`: Contiene los archivos y documentos origen crudos descargados (ej. PDFs, XLSX, TXT).
  * `processed/`:
    * [georef_catalog.json](file:///Users/a4649783/Documents/UNSAM/zona4/data/processed/georef_catalog.json): Catálogo geográfico consolidado para georreferenciación y desambiguación jerárquica de localidades de Argentina.
  * `sources/`: Contiene los archivos procesados origen de las cargas base y los JSONs de aporte directo. Incluye [ccds.json](file:///Users/a4649783/Documents/UNSAM/zona4/data/sources/ccds.json), [nietos_y_nietas.json](file:///Users/a4649783/Documents/UNSAM/zona4/data/sources/nietos_y_nietas.json), [parque_de_la_memoria.json](file:///Users/a4649783/Documents/UNSAM/zona4/data/sources/parque_de_la_memoria.json) y la plantilla [_template_source.json](file:///Users/a4649783/Documents/UNSAM/zona4/data/sources/_template_source.json).
* **Documentación Técnica (`docs/`)**:
  * [ingesta_fuentes.md](file:///Users/a4649783/Documents/UNSAM/zona4/docs/operations/ingesta_fuentes.md): Contrato y checklist para la ingesta de nuevas fuentes usando el formato del CDM.
  * [README.md de Sources](file:///Users/a4649783/Documents/UNSAM/zona4/docs/sources/README.md): Detalle explicativo de los orígenes de datos procesados.
  * [README.md de Neo4j / Queries](file:///Users/a4649783/Documents/UNSAM/zona4/docs/queries/README.md): Resumen de carga del grafo, uso de plugins y consultas Cypher.
  * [README.md de Arquitectura](file:///Users/a4649783/Documents/UNSAM/zona4/docs/architecture/README.md): Explicación simple y visual del flujo de componentes y arquitectura del cargador.
* **Código Fuente del Extractor (`src/zona4_extractor/`)**:
  * [__init__.py](file:///Users/a4649783/Documents/UNSAM/zona4/src/zona4_extractor/__init__.py): Archivo de inicialización del paquete del extractor.
  * [download_georef_catalog.py](file:///Users/a4649783/Documents/UNSAM/zona4/src/zona4_extractor/download_georef_catalog.py): Script para descargar y armar el catálogo Georef local.
  * [abuelas_scraper_placeholder.py](file:///Users/a4649783/Documents/UNSAM/zona4/src/zona4_extractor/abuelas_scraper_placeholder.py): Scraper de la base de datos de Nietas y Nietos (Placeholder).
  * [parque_memoria_parser_placeholder.py](file:///Users/a4649783/Documents/UNSAM/zona4/src/zona4_extractor/parque_memoria_parser_placeholder.py): Parser e integrador de registros de Parque de la Memoria (Placeholder).
  * [georef_client_placeholder.py](file:///Users/a4649783/Documents/UNSAM/zona4/src/zona4_extractor/georef_client_placeholder.py): Cliente de API en línea del servicio Georef (Placeholder).
* **Código Fuente del Loader (`src/zona4_graph_loader/`)**:
  * [NEO4J_DATA_MODEL.md](file:///Users/a4649783/Documents/UNSAM/zona4/src/zona4_graph_loader/NEO4J_DATA_MODEL.md): Modelo de datos formal, inmutable y especificaciones de integridad DDL.
  * [cli.py](file:///Users/a4649783/Documents/UNSAM/zona4/src/zona4_graph_loader/cli.py): Interfaz de línea de comandos para orquestar la ingesta en Neo4j.
  * [config.py](file:///Users/a4649783/Documents/UNSAM/zona4/src/zona4_graph_loader/config.py): Gestión de variables de entorno y conexión a la base de datos.
  * [constants.py](file:///Users/a4649783/Documents/UNSAM/zona4/src/zona4_graph_loader/constants.py): Constantes de negocio, mapeos de relaciones familiares (`REL_MAP`), provincias, abreviaturas y prioridades.
  * **Capa DB (`src/zona4_graph_loader/db/`)**:
    * [cypher.py](file:///Users/a4649783/Documents/UNSAM/zona4/src/zona4_graph_loader/db/cypher.py): Definición de constraints de unicidad y todas las sentencias Cypher parametrizadas para la carga.
    * [qa.py](file:///Users/a4649783/Documents/UNSAM/zona4/src/zona4_graph_loader/db/qa.py): Consultas de auditoría e impresión del reporte QA post-carga.
  * **Capa de Normalización (`src/zona4_graph_loader/domain/`)**:
    * [place_norm.py](file:///Users/a4649783/Documents/UNSAM/zona4/src/zona4_graph_loader/domain/place_norm.py): Motor de desambiguación geográfica basado en Georef.
    * [name_similarity.py](file:///Users/a4649783/Documents/UNSAM/zona4/src/zona4_graph_loader/domain/name_similarity.py): Lógica de emparejamiento de nombres para candidatos a fusionar.
    * [date_norm.py](file:///Users/a4649783/Documents/UNSAM/zona4/src/zona4_graph_loader/domain/date_norm.py): Normalización de fechas y rangos textuales en español.
  * **Capa Pipeline (`src/zona4_graph_loader/pipeline/`)**:
    * [load_graph.py](file:///Users/a4649783/Documents/UNSAM/zona4/src/zona4_graph_loader/pipeline/load_graph.py): Orquestador secuencial que lee archivos, invoca constructores (builders), inicializa restricciones y corre inserciones por lotes.

---

## 3. Modelo de Datos del Grafo (Neo4j V1.1 / V1.1.1)
El grafo de ZONA4 se estructura sobre principios estrictos de multi-etiquetado y auditoría explícita en las aristas.

### 3.1 Nodos y sus Propiedades Clave
1. **`:Persona` (Nodo base obligatorio)**:
   * `persona_key` [String, ÚNICO]: Llave técnica para merges estables.
   * `nombre` [String] (Obligatorio).
   * `genero` [String] (Obligatorio, ej: "MASCULINO", "FEMENINO", "INDETERMINADO").
   * `fuente` [String] (Obligatorio).
   * *Roles Secundarios* (etiquetas en el mismo nodo físico):
     * `:Victima`
     * `:Represor`
     * `:Complice` (con propiedad `tipo` obligatoria restringida a: "CIVIL", "CLERICAL", "EMPRESARIAL")
     * `:Nietx` (con propiedades `caso` y `ADN` obligatorias)
2. **`:Lugar`**:
   * `lugar_key` [String, ÚNICO].
   * `nombre` [String] (Obligatorio).
   * `tipoGeopolitico` [String] (Obligatorio, valores: `PAIS`, `PROVINCIA`, `CIUDAD`, `BARRIO`, `CCD`).
   * `pais_code` [String].
   * `geo_point` [Point (Neo4j spatial)]: Coordenadas geográficas.
3. **`:DirecciónCCD`**:
   * `direccion_ccd_key` [String, ÚNICO].
   * `coordenadas` [String] (ej: "lat,lon" o "DESCONOCIDAS").
   * `direccionExacta` [String].
4. **`:AliasLugar`**:
   * `alias_key` [String, ÚNICO].
   * `nombreAlternativo` [String] (el toponímico crudo o alternativo).
   * `parent_key` [String].
5. **`:AliasPersona`** -> `alias` [String].
6. **`:Profesión`** -> `descripcion` [String].
7. **`:Cargo`** -> `titulo` [String].
8. **`:Org`** -> `nombre` [String], `tipoOrg` [String].
9. **`:Institución`** -> `nombre` [String].

### 3.2 Relaciones Clave (Todas con propiedades `fecha` y `origen` obligatorias)
* **Genealógicas e Interpersonales**:
  * `(:Persona)-[:HIJE_DE]->(:Persona)` (hijo/a)
  * `(:Persona)-[:PADRE_DE]->(:Persona)` (padre)
  * `(:Persona)-[:MADRE_DE]->(:Persona)` (madre)
  * `(:Persona)-[:NIETX_DE]->(:Persona)` (nieto/a)
  * `(:Persona)-[:ABUELX_DE]->(:Persona)` (abuelo/a)
  * `(:Persona)-[:HERMANX_DE]->(:Persona)` (hermano/a - unifica hermano/hermana/hermanx)
  * `(:Persona)-[:PAREJA_DE]->(:Persona)` (pareja - unifica esposo/a, novio/a, cónyuge, compañero/a)
  * `(:Persona)-[:CUÑADX_DE]->(:Persona)` (cuñado/a)
  * `(:Persona)-[:SUEGRX_DE]->(:Persona)` (suegro/a)
  * `(:Persona)-[:YERNX_NUERX_DE]->(:Persona)` (yerno o nuera)
  * `(:Persona)-[:TORTURO_A]->(:Persona)` (represor a víctima)
  * `(:Persona)-[:VIO_A]->(:Persona)` (avistamiento por testigo)
  * `(:Persona)-[:MILITO_CON]->(:Persona)` (co-militancia)
* **Espaciales y Hechos Históricos**:
  * `(:Persona)-[:NACIO_EN]->(:Lugar)`
  * `(:Persona)-[:SECUESTRADO_EN]->(:Lugar)`
  * `(:Persona)-[:ASESINADO_EN]->(:Lugar)`
  * `(:Persona)-[:PRESENTE_EN]->(:Lugar)` (detención en un CCD)
  * `(:Persona)-[:PARIO_EN]->(:Lugar)` (parto en cautiverio)
  * `(:Persona)-[:MURIO_EN]->(:Lugar)`
  * `(:Persona)-[:LIBERADO_EN]->(:Lugar)`
* **Estructura y Topología**:
  * `(:DirecciónCCD)-[:UBICADA_EN]->(:Lugar)`
  * `(:Lugar)-[:PARTE_DE]->(:Lugar)` (jerarquía anidada recursiva)
  * `(:AliasLugar)-[:ALIAS_DE]->(:Lugar)`
  * `(:Persona)-[:CANDIDATO_MERGE {metodo, score, confianza}]->(:Persona)`

---

## 4. Normalización Geográfica y de Identidades

### 4.1 Resolución de Lugares
El módulo [place_norm.py](file:///Users/a4649783/Documents/UNSAM/zona4/src/zona4_graph_loader/domain/place_norm.py) implementa un motor que:
1. Extrae direcciones específicas (ej. "Av. Santa Fe 1234") del texto y crea nodos `:Direccion` separados para no contaminar la capa geopolítica.
2. Consulta el catálogo [georef_catalog.json](file:///Users/a4649783/Documents/UNSAM/zona4/data/processed/georef_catalog.json) evaluando coincidencias aproximadas con un score umbral configurable (`--georef-min-score` por defecto `0.76`).
3. Mantiene una diferencia mínima de ambigüedad (`--georef-ambiguity-delta` de `0.02`) para evitar merges falsos de toponimia común (ej: "San Martín").
4. Genera relaciones recursivas `:PARTE_DE` que escalan de Localidad -> Partido/Departamento -> Provincia -> País.

### 4.2 Resolución de Identidades (Candidatos Merge)
El pipeline utiliza lógica fuzzy ([name_similarity.py](file:///Users/a4649783/Documents/UNSAM/zona4/src/zona4_graph_loader/domain/name_similarity.py)) para encontrar candidatos de merge cuando existen placeholders o víctimas parciales (mencionadas con alias, nombre parcial, etc.) comparadas con perfiles conocidos. Esto escribe aristas `:CANDIDATO_MERGE` en el grafo para validación interactiva o reportes.

---

## 5. Operaciones Técnicas y Comandos del Pipeline
El entorno local se levanta con Docker. El contenedor de Neo4j expone el puerto Bolt en `17687` para no colisionar con instalaciones previas.

### 5.1 Levantar Neo4j Local
```bash
# Iniciar contenedor
docker compose up -d

# Validar plugins APOC y GDS en el Neo4j Browser (http://localhost:7474)
# Ejecutar:
#   RETURN apoc.version() AS apoc_version;
#   RETURN gds.version() AS gds_version;
```

### 5.2 Comando de Carga Completa / Limpia
La ingesta requiere definir `PYTHONPATH=src` y apuntar a las variables de entorno de Neo4j local:
```bash
PYTHONPATH=src \
NEO4J_URI=bolt://localhost:17687 \
NEO4J_USERNAME=neo4j \
NEO4J_PASSWORD=zona4local \
NEO4J_DATABASE=neo4j \
.venv/bin/python -m zona4_graph_loader.cli --clean-project --apply-safe-place-merges
```

### 5.3 Modos de Limpieza, Validación y Flags Útiles
* `--clean-project`: Limpia solo los nodos correspondientes al dominio del proyecto (`:Persona`, `:Lugar`, `:AliasLugar`, `:DirecciónCCD`, `:Profesión`, `:Cargo`, `:Org`, `:Institución`, `:AliasPersona`) antes de realizar la inserción, respetando el resto del grafo.
* `--clean-all`: Borra absolutamente todo el grafo físico de Neo4j.
* `--apply-safe-place-merges`: Aplica fusiones automáticas seguras en nodos `:Lugar` de tipo `CIUDAD` con alta coincidencia de toponimia y parentesco jerárquico.
* `--skip-direct-sources`: Deshabilita la ingesta de fuentes JSON directas ubicadas en `data/sources/`.
* `--skip-qa-report`: Evita calcular e imprimir las métricas de control al terminar la ingesta.

### 5.4 Comportamiento de Constraints e Integridad en Entornos de Comunidad
Las restricciones de existencia en propiedades (`REQUIRE prop IS NOT NULL`) son una característica exclusiva de **Neo4j Enterprise Edition**. Dado que el entorno local típicamente corre sobre **Neo4j Community Edition**, el loader captura silenciosamente los errores de creación de restricciones de existencia, reporta una advertencia (`Warning`), crea de todos modos las restricciones de unicidad e índices de performance que sí están disponibles en Community, y continúa con la ingesta.

### 5.5 Creación de Nodos Placeholder
Al insertar relaciones familiares, si una persona objetivo (`target_key`) no existe previamente en la base de datos de personas procesadas, el cargador genera automáticamente un nodo `:Persona` placeholder con género `INDETERMINADO` y los datos mínimos conocidos de la relación. Esto asegura la consistencia e integridad referencial del grafo.

---

## 6. Ingesta de Nuevas Fuentes (Fuentes Directas)
Para agregar nuevos datos sin interferir en los scripts principales del pipeline, se utiliza la ingesta directa por JSON descrita en [ingesta_fuentes.md](file:///Users/a4649783/Documents/UNSAM/zona4/docs/operations/ingesta_fuentes.md).

1. **Crear archivo JSON**: Guardar en `data/sources/tu_fuente.json`.
2. **Estructura del JSON**: Debe ajustarse al esquema especificado en [_template_source.json](file:///Users/a4649783/Documents/UNSAM/zona4/data/sources/_template_source.json). Permite aportar directamente filas estructuradas de acuerdo a las 5 llaves esenciales del CDM:
   * `personas`, `lugares`, `relaciones_interpersonales`, `eventos_espaciales`, `jerarquias`.
3. **Validar Contrato antes de Cargar**:
   ```bash
   PYTHONPATH=src .venv/bin/python -m zona4_graph_loader.cli --validate-sources-only --sources-dir data/sources
   ```

---

## 7. Consultas Cypher Comunes
Los scripts Cypher de referencia se encuentran en:
* [queries_validacion.cypher](file:///Users/a4649783/Documents/UNSAM/zona4/docs/queries/queries_validacion.cypher): Control de calidad de la base (chequeos de orfandad, alias en conflicto, CCDs sin anclaje).
* [queries_analitica_avanzada.cypher](file:///Users/a4649783/Documents/UNSAM/zona4/docs/queries/queries_analitica_avanzada.cypher): Consultas analíticas (trayectorias de víctimas, hotspots de secuestros, redes de parentesco, actividad temporal de CCDs).

### Ejemplo de Consulta: Cobertura de Normalización de Lugares
```cypher
MATCH (p:Persona:Victima)
OPTIONAL MATCH (p)-[r:SECUESTRADO_EN]->(l:Lugar)
RETURN 
  count(p) as total_victimas,
  count(l) as victimas_con_secuestro_georreferenciado,
  (toFloat(count(l)) / count(p)) * 100 as porcentaje_cobertura
```

### Ejemplo de Consulta: Secuencias de Hechos por Víctima (Trayectorias)
```cypher
MATCH (p:Persona)-[r:SECUESTRADO_EN|ASESINADO_EN|PRESENTE_EN]->(l:Lugar)
WHERE p:Victima
RETURN p.nombre, type(r) as tipo_hecho, r.fecha as fecha, l.nombre as lugar
ORDER BY p.persona_key, r.fecha ASC
```

---
Este archivo sirve como el punto de anclaje de conocimiento para cualquier asistente de IA que necesite entender las reglas de negocio, los constraints de integridad, las transformaciones de datos y las ejecuciones operativas del repositorio **ZONA4**.

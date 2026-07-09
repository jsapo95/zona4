# Comisión de Ciencia de Datos

## Objetivos

| Objetivo | Descripción | Estado |
| -------- | ----------- | ------ |
| Ingeniería de datos | Recopilación, limpieza, procesamiento y normalización de datos sobre la dictadura. Para esto utilizamos bases de datos públicas y también extracción de datos a partir de documentación pública digitalizada. | En proceso |
| Creación de bases de datos | Crear bases de datos tabulares y de grafos de conocimiento para poder realizar distintos tipos de análisis e investigaciones. | En proceso |
| Disponibilización pública de información | Disponibilizar las bases de datos que hagamos en conjunto con desarrollos de técnicas, procesos y programas propios que permitan mejorar la investigación en estos temas. | Pendiente |
| Chatbot Graph-RAG | Desarrollo de herramientas de búsqueda de información sobre la dictadura y sobre nuestras bases de datos, usando inteligencia artificial. | Pendiente |
| Resolución de identidades | Investigación y desarrollo de modelos analíticos predictivos que ayuden en la resolución de identidades. Esto es: tratar de determinar probabilísticamente si descripciones parciales de personas corresponden a una misma persona. Por ejemplo, si hay sobrevivientes que vieron a otrx secuestrado pero no saben quién fue, queremos ver si encontramos la forma de analizar las descripciones y saber quien era esa persona. Es algo que tenemos que investigar por un pedido que nos hicieron desde Abuelas. | Pendiente |
| Transcripción de archivos desclasificados | Desarrollo de técnicas para la transcripción de archivos desclasificados de EEUU durante la dictadura que fueron digitalizados. | Pendiente |
| Dashboard sobre la dictadura | Realización de dashboard con métricas y gráficos utilizando nuestras bases de datos. | Pendiente |


## Recopilación y análisis inicial de documentación

Los datos con los que trabajamos son de origen público, obtenidos de distintas fuentes y en formatos variados. Se trabaja únicamente con información digitalizada que puede ser texto plano, tablas e imágenes. Estos datos pueden provenir de:

* Libros
* Sentencias judiciales
* Bases de datos
* Testimonios

La obtención fue realizada descargando la información a través de la web o mediante _web scraping_ o _web crawling_ con programas hechos en lenguaje python.

Dicha información se encuentra de forma estructurada (tablas), semi-estructurada (.json) y no-estructurada (texto, imágenes). A su vez, se identificaron algunos tipos de redacción distintos:

* Lenguaje técnico: proveniente mayormente de archivos judiciales.
* Lenguaje académico: proveniente mayormente de libros.
* Lenguaje coloquial: puede estar en varios tipos de documentos.

La veracidad de la información utilizada se encuentra ligada mayormente al contexto de la época en que se sucedieron los hechos. La dictadura militar se ocupó de erradicar cualquier información y prueba de sus crímenes cometidos; por ende, los datos trabajados provienen de testimonios de personas secuestradas, algunos testimonios de militares, investigaciones, documentación recuperada, etc.

### Fuentes de datos

| Nombre | Estado | Url | Glosario |
| ------ | ------ | --- | -------- |
| Archivo de la Memoria de San Martín | Procesado | https://sitiosale.cdn.prismic.io/sitiosale/Z9luiTiBA97GimGK_M_ArchivodeMemoria-1-.pdf | |
| Base de datos - Parque de la memoria | Procesado | https://basededatos.parquedelamemoria.org.ar/registros/ | [Ver glosario](/docs/base_de_datos/parque_de_la_memoria.md) |
| Niños desaparecidos. Jóvenes localizados 1975 - 2015 | Pendiente | https://www.unq.edu.ar/wp-content/uploads/migracion/documentos/5594327fb5347.pdf | |
| Nietas y nietos - Abuelas de Plaza de Mayo | Procesado | https://www.abuelas.org.ar/nietas-y-nietos/buscador | [Ver glosario](/docs/base_de_datos/nietos_y_nietas.md) |
| Centros clandestinos de detención | Pendiente | https://es.wikipedia.org/wiki/Centro_clandestino_de_detenci%C3%B3n_(Argentina) | |
| Listado de Centros Clandestinos de Detención | Procesado | https://www.argentina.gob.ar/sites/default/files/6._anexo_v_listado_de_ccd-investigacion_ruvte-ilid.pdf | [Ver glosario](/docs/base_de_datos/ccds.md) |
| Listado de casos sin denuncia formal | Pendiente | https://www.argentina.gob.ar/sites/default/files/3._anexo_ii_listado_de_casos_sin_dcia_formal-investigacion_ruvte-ilid.pdf | |
| Registro Unificado de Víctimas del Terrorismo de Estado (RUVTE) | Pendiente | https://www.argentina.gob.ar/derechoshumanos/ANM/ruvte/2015 | |
| Centros Clandestinos de Detención durante la dictadura cívico-militar entre 1976 y 1982 | Pendiente | https://observatorioconurbano.ungs.edu.ar/?p=5392 | |
| Paquete R - presentes | Procesado | https://diegokoz.github.io/presentes/ | [Ver glosario](/docs/base_de_datos/paquete_r_presentes.md) |
| Documentos desclasificados EE.UU. | Pendiente |https://desclasificados.org.ar/ | |
| Datos de represores y victimas | Pendiente | https://derechoshumanos.mjus.gba.gob.ar/imputado/33-balmaceda-roberto-armando/ | |
| Imputados | Pendiente | https://www.mpf.gob.ar/plan-condor/imputados/zona-iv-santiago-omar-riveros/ | |
| Archivo provincial de la memoria | Pendiente | https://apm.gov.ar/presentes/detalle/2716 | |
| Semblanza de las dictaduras civico-militares del 55' al 83' | Pendiente | https://robertobaschetti.com/ | |
| Leyes de la dictadura | Reprocesar | https://www.lasleyesdeladictadura.com.ar/index.php?a=PublicView&name=LeyesPublic | |
| Condor Atlanta | Pendiente | https://condor-atlanta.org/ | |
| Juicios de Lesa Humanidad | Pendiente | http://www.juiciosdelesahumanidad.ar/ | |
| Nizkor | Pendiente | https://www.derechos.org/nizkor/arg/ | |
| Fiscales juicios | Pendiente | https://www.fiscales.gob.ar/lesa-humanidad/?tipo-entrada=agenda | |
| Webinar IA y DDHH | Pendiente | https://www.cipdh.gob.ar/inteligencia-artificial-y-derechos-humanos/ | |
| Juicios | Pendiente | https://www.mpf.gob.ar/lesa/jurisprudencia/ | |
| Juicios PBA | Pendiente | https://derechoshumanos.mjus.gba.gob.ar/lesa-humanidad/ | |


## Procesamiento de los datos y Arquitectura Decoplada

Para garantizar la estabilidad y evitar dependencias de red durante la carga del grafo, el repositorio se divide arquitectónicamente en dos subsistemas principales:

1. **Extractor de Datos (`src/zona4_extractor/`)**:
   - **Propósito**: Ejecutar de manera previa y/o independiente la lógica de scraping, consulta de APIs en línea, parseo de archivos no estructurados (PDFs, HTML, etc.) y reverse-geocoding online.
   - **Salida**: Genera datasets intermedios estructurados y homogéneos de personas, relaciones, y catalogaciones geopolíticas que se almacenan de forma local en `data/sources/`.
   - **Archivos de referencia (Placeholders)**:
     - [download_georef_catalog.py](file:///Users/a4649783/Documents/UNSAM/zona4/src/zona4_extractor/download_georef_catalog.py): Script para descargar y consolidar el catálogo local offline de Georef.
     - [abuelas_scraper_placeholder.py](file:///Users/a4649783/Documents/UNSAM/zona4/src/zona4_extractor/abuelas_scraper_placeholder.py): Scraper web del buscador de Abuelas de Plaza de Mayo (Placeholder).
     - [parque_memoria_parser_placeholder.py](file:///Users/a4649783/Documents/UNSAM/zona4/src/zona4_extractor/parque_memoria_parser_placeholder.py): Parseador de registros procedentes del Parque de la Memoria (Placeholder).
     - [georef_client_placeholder.py](file:///Users/a4649783/Documents/UNSAM/zona4/src/zona4_extractor/georef_client_placeholder.py): Cliente de consulta dinámico de la API oficial de Georef Argentina (Placeholder).

2. **Cargador del Grafo (`src/zona4_graph_loader/`)**:
   - **Propósito**: Consumir de manera estrictamente local, determinista y *offline* los datasets ubicados en `data/sources/` e inyectarlos de forma masiva en la base de datos de grafos de Neo4j.
   - **Ventaja**: El loader está totalmente libre de acoplamiento de red; no realiza peticiones externas y está optimizado únicamente para el ordenamiento geopolítico e interpersonal del Knowledge Graph.

Con esta normalización y desacoplamiento, la base de datos se mantiene en un estado sólido de control de calidad y auditoría, siendo escalable para la integración futura de nuevas fuentes mediante el sistema de fuentes manuales en `data/sources/` o nuevos módulos de extracción en `src/zona4_extractor/`.

## Operación técnica del loader y Modelo de Datos (V1.1.1)

El pipeline de ingesta del proyecto se ha actualizado a la **Versión 1.1.1** del modelo de datos en grafos. 

### Cambios Clave en el Modelo de Datos:
1. **Simplificación Topológica**: Se eliminaron los nodos intermediarios `:Evento` y `:CasoNietx`. Ahora los hechos históricos se mapean como relaciones temporales directas desde los nodos `:Persona` hacia los nodos `:Lugar` (ej: `-[:SECUESTRADO_EN]->`, `-[:PRESENTE_EN]->`, `-[:ASESINADO_EN]->`), reduciendo la redundancia de datos.
2. **Nuevas Relaciones Interpersonales y Familiares**: Se incorporó soporte nativo y unificado para:
   - Parejas (`PAREJA_DE`), unificando cónyuge, novio/a y compañero/a.
   - Hermanos (`HERMANX_DE`).
   - Parientes políticos de alta frecuencia: Cuñados (`CUÑADX_DE`), Suegros (`SUEGRX_DE`), y Yernos/Nueras (`YERNX_NUERX_DE`).
3. **Consistencia Referencial (Placeholder Merges)**: Al procesar relaciones familiares, si un actor no se encuentra formalmente declarado como persona base, el cargador genera un nodo `:Persona` temporal tipo placeholder para no perder la arista genealógica.

Para documentación técnica detallada:
- Ver [ingesta_fuentes.md](file:///Users/a4649783/Documents/UNSAM/zona4/docs/operations/ingesta_fuentes.md) para extender la carga con nuevas fuentes.
- Ver [README.md de Arquitectura](file:///Users/a4649783/Documents/UNSAM/zona4/docs/architecture/README.md) para comprender de forma visual y simple el flujo y los componentes del cargador.
- Ver [README.md de Queries](file:///Users/a4649783/Documents/UNSAM/zona4/docs/queries/README.md) para el modelo de grafo, DDL e integridad, y consultas Cypher.
- Ver [GEMINI.md](file:///Users/a4649783/Documents/UNSAM/zona4/GEMINI.md) para la guía completa del repositorio optimizada para LLMs.

### Carga Base Completa y Limpia

Para ejecutar la ingesta local apuntando al puerto Neo4j configurado (`17687`), utilice las siguientes variables de entorno:

```bash
PYTHONPATH=src \
NEO4J_URI=bolt://localhost:17687 \
NEO4J_USERNAME=neo4j \
NEO4J_PASSWORD=zona4local \
NEO4J_DATABASE=neo4j \
.venv/bin/python -m zona4_graph_loader.cli --clean-project --apply-safe-place-merges
```

*Nota para Neo4j Community Edition:* Las restricciones de existencia (`IS NOT NULL`) de las labels son exclusivas de la versión Enterprise de Neo4j. El loader detectará de forma automática si la base de datos es Community Edition, omitirá amigablemente la creación de estas restricciones arrojando un `Warning` y continuará con la inserción de los datos.

### Flags útiles en `cli.py`:
- `--clean-project`: Limpia todos los nodos y relaciones correspondientes al proyecto (conservando otros dominios si existieran) antes de cargar.
- `--clean-all`: Borra absolutamente todo el grafo físico de Neo4j.
- `--apply-safe-place-merges`: Aplica fusiones automáticas conservadoras sobre nodos `:Lugar` de tipo `CIUDAD` con alta similitud toponímica y coherencia jerárquica.
- `--skip-direct-sources`: Deshabilita la ingesta de fuentes directas en formato JSON ubicadas en `data/sources/`.
- `--validate-sources-only`: Valida la correctitud de las fuentes directas en `data/sources/` y sale sin inyectar datos en Neo4j.
- `--skip-qa-report`: Evita calcular e imprimir el reporte QA de cierre al terminar la carga.

### Configuración del Entorno Local (Docker):
- El archivo `docker-compose.yml` en la raíz define e inicializa el contenedor local de Neo4j con los plugins `apoc` y `graph-data-science` (GDS) habilitados por defecto.
- Expone el puerto Bolt en `17687` para evitar colisionar con otras instancias activas en el puerto default `7687`.
- Puede verificar que la inicialización fue correcta ingresando a la consola (Browser) y corriendo:
  ```cypher
  RETURN apoc.version() AS apoc_version;
  RETURN gds.version() AS gds_version;
  ```


## Análisis y visualización de datos

Realización de tableros con:

* Gráficos
* Grafos
* Métricas


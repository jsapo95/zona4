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

`Extraído` indica que el dato fue efectivamente descargado/parseado a
`data/raw/` o `data/sources/`. `En grafo` indica que existe un builder
registrado en `pipeline/load_graph.py` que lo escribe en Neo4j. Antes de esta
iteración ambas columnas eran una sola (`Estado: Procesado/Pendiente`), y
"Procesado" se usaba para lo primero aunque nunca llegara al grafo — la
verdad de cada fila fue verificada contra el código, no copiada del estado
anterior.

| Nombre | Extraído | En grafo | Url | Glosario |
| ------ | -------- | -------- | --- | -------- |
| Archivo de la Memoria de San Martín | Sí | Sí (303 víctimas, 0 aristas geográficas⁷) | https://sitiosale.cdn.prismic.io/sitiosale/Z9luiTiBA97GimGK_M_ArchivodeMemoria-1-.pdf | [Ver ficha](/docs/sources/archivo_memoria_san_martin.md) |
| Base de datos - Parque de la memoria | Sí | Sí | https://basededatos.parquedelamemoria.org.ar/registros/ | [Ver glosario](/docs/sources/parque_de_la_memoria.md) |
| Niños desaparecidos. Jóvenes localizados 1975 - 2015 | No | No | https://www.unq.edu.ar/wp-content/uploads/migracion/documentos/5594327fb5347.pdf | |
| Nietas y nietos - Abuelas de Plaza de Mayo | Sí | Sí | https://www.abuelas.org.ar/nietas-y-nietos/buscador | [Ver glosario](/docs/sources/nietos_y_nietas.md) |
| Centros clandestinos de detención | No | No | https://es.wikipedia.org/wiki/Centro_clandestino_de_detenci%C3%B3n_(Argentina) | |
| Listado de Centros Clandestinos de Detención (RUVTE) | Sí | Sí | https://www.argentina.gob.ar/sites/default/files/6._anexo_v_listado_de_ccd-investigacion_ruvte-ilid.pdf | [Ver glosario](/docs/sources/ccds.md) |
| Listado de casos sin denuncia formal | No | No | https://www.argentina.gob.ar/sites/default/files/3._anexo_ii_listado_de_casos_sin_dcia_formal-investigacion_ruvte-ilid.pdf | |
| Registro Unificado de Víctimas del Terrorismo de Estado (RUVTE) | No | No | https://www.argentina.gob.ar/derechoshumanos/ANM/ruvte/2015 | |
| Centros Clandestinos de Detención durante la dictadura cívico-militar entre 1976 y 1982 | No | No | https://observatorioconurbano.ungs.edu.ar/?p=5392 | |
| Paquete R - presentes | No¹ | No | https://diegokoz.github.io/presentes/ | |
| Documentos desclasificados EE.UU. | No | No | https://desclasificados.org.ar/ | |
| MinJus GBA - centros clandestinos | Sí | Sí (87: 19 dedup. contra RUVTE, 68 nuevos) | https://derechoshumanos.mjus.gba.gob.ar/consulta-interactiva/ | [Ver ficha](/docs/sources/minjus_gba.md) |
| MinJus GBA - imputados | Sí | Sí (454 represores)⁸ | https://derechoshumanos.mjus.gba.gob.ar/consulta-interactiva/ | [Ver ficha](/docs/sources/minjus_gba.md) |
| MinJus GBA - víctimas | Sí | Sí (3257)⁸ | https://derechoshumanos.mjus.gba.gob.ar/consulta-interactiva/ | [Ver ficha](/docs/sources/minjus_gba.md) |
| MinJus GBA - sentencias | Sí | Sí² (113 registros, 112 slugs, sin nodos propios) | https://derechoshumanos.mjus.gba.gob.ar/consulta-interactiva/ | [Ver ficha](/docs/sources/minjus_gba.md) |
| Imputados (Plan Cóndor) | No | No | https://www.mpf.gob.ar/plan-condor/imputados/zona-iv-santiago-omar-riveros/ | |
| Archivo provincial de la memoria | No | No | https://apm.gov.ar/presentes/detalle/2716 | |
| Semblanza de las dictaduras civico-militares del 55' al 83' | Sí³ | No | https://robertobaschetti.com/ | |
| Leyes de la dictadura | Sí⁴ | No | https://www.lasleyesdeladictadura.com.ar/index.php?a=PublicView&name=LeyesPublic | |
| Condor Atlanta | No | No | https://condor-atlanta.org/ | |
| Juicios de Lesa Humanidad - condenados | Sí | Sí (1237 represores, 197 cómplices civiles)⁹ | http://www.juiciosdelesahumanidad.ar/ | [Ver ficha](/docs/sources/juicios_lesa_humanidad.md) |
| Juicios de Lesa Humanidad - causas (Argentina/exterior) | Sí⁵ | No | http://www.juiciosdelesahumanidad.ar/ | [Ver ficha](/docs/sources/juicios_lesa_humanidad.md) |
| Nizkor | No | No | https://www.derechos.org/nizkor/arg/ | |
| Fiscales juicios | No | No | https://www.fiscales.gob.ar/lesa-humanidad/?tipo-entrada=agenda | |
| Webinar IA y DDHH | No | No | https://www.cipdh.gob.ar/inteligencia-artificial-y-derechos-humanos/ | |
| Juicios | No | No | https://www.mpf.gob.ar/lesa/jurisprudencia/ | |
| Juicios PBA | No | No | https://derechoshumanos.mjus.gba.gob.ar/lesa-humanidad/ | |
| EAAF - sitios de hallazgo | Sí | Sí (91 lugares; 90 con coordenadas válidas, 1 rechazado)¹⁰ | https://labusqueda.eaaf.org.ar/ | [Ver ficha](/docs/sources/eaaf.md) |
| EAAF - identificados | Sí (877 filas, encoding dañado) | No⁶ | https://labusqueda.eaaf.org.ar/ | [Ver ficha](/docs/sources/eaaf.md) |

¹ No se encontró archivo de datos ni builder para esta fuente en el repositorio, pese a estar documentada con un glosario en versiones previas del README.
² No genera nodos propios (el modelo no tiene `:Sentencia` ni `:Causa`); sus metadatos (`origen`, `fecha`, y desde V1.3 también `delitos`) se usan sólo para las aristas `TORTURO_A`/`IMPUTADO_POR` que aportan los builders de imputados y víctimas (ver nota ⁸).
³ Existe el PDF original y una versión de texto ya limpiada (`data/raw/semblanza_limpio.txt`), pero no hay builder que la consuma.
⁴ El archivo `data/raw/leyes_dictadura.xlsx` existe, pero no tiene extractor ni consumidor rastreable en `src/` (ninguna referencia a "leyes" en el código).
⁵ `juicios_lesa_humanidad_argentina.json` (369 causas) está completo; `juicios_lesa_humanidad_exterior.json` está incompleto: su propio `metadata.totalItems` declara 64 y el archivo trae 41. Ninguno de los dos entra al grafo: el modelo no tiene nodo `:Causa`. Ver `docs/sources/juicios_lesa_humanidad.md`.
⁶ Descartado: no tiene columna de nombre (casos anonimizados) y `:Persona.nombre` es obligatorio en el modelo. Ver `docs/sources/eaaf.md`.
⁷ Hasta el commit `01d41a7` (auditoría semántica V1.3, hallazgo C2) esta fuente generaba una arista `SECUESTRADO_EN` por víctima a partir de su campo `lugar`. Se investigó y `lugar` no es el lugar del secuestro: toma sólo 11 valores (los 11 barrios del Partido de General San Martín) y en 159 de 303 registros (52 %) contradice directamente el lugar que la propia `descripcion` de la fuente nombra para el hecho — a veces en otra jurisdicción (Barrancas de Belgrano/CABA, Vicente López, Boulogne/San Isidro). Es la categoría barrial bajo la que el archivo municipal organiza cada ficha, no un dato verificable del hecho. La arista se eliminó por completo en vez de re-tiparla: hoy esta fuente no aporta ningún nodo `:Lugar` ni arista geográfica al grafo (0, era 303); la fecha de desaparición se conserva en `Persona.fecha_secuestro`. Ver `docs/sources/archivo_memoria_san_martin.md`.
⁸ Medido en vivo contra `bolt://localhost:17687` el 2026-08-30: `rel_torturo_a_total = 11511`, `rel_imputado_por_total = 3347` (mismo total de 14.858 pares que antes de la auditoría semántica V1.3, hallazgo C1; ese total ya existía y no cambió — lo que cambió es que antes los 14.858 se emitían todos como `TORTURO_A` sin excepción). Ahora `TORTURO_A` sólo se emite cuando la sentencia imputa tormentos a ese par imputado-víctima en particular (campo `delitos`); el resto —homicidio, sustracción de menor, privación ilegítima de la libertad y otros cargos que no son tormentos— recibe `IMPUTADO_POR`. Ambos tipos de arista llevan la lista completa de `delitos`. Ver `docs/sources/minjus_gba.md`.
⁹ `Persona.fuerza` conserva el valor crudo del campo `Fuerza` de la fuente, incluidos los centinelas ("SIN ESPECIFICAR", "CIVIL", "POLICIA (SIN ESPECIFICAR)"); desde V1.3 (hallazgo I3d) esos centinelas ya no generan un nodo `:Org` ni la arista `PARTE_DE` (109 + 87 + 46 aristas fabricadas hacia 3 organizaciones falsas antes del fix, sumando esta fuente y MinJus imputados). Ver `docs/sources/juicios_lesa_humanidad.md`.
¹⁰ El sitio "Cementerio San Antonio de Padua, San Miguel" trae coordenadas corruptas (`Lat=-3453760000000000.0`, `Long=-5.8739e+16`); el loader las rechaza en vez de crear un `:DirecciónCCD` con una ubicación imposible. El nodo `:Lugar` del sitio se crea igual, sin coordenadas. Ver `docs/sources/eaaf.md`.


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

## Operación técnica del loader y Modelo de Datos (V1.3)

El pipeline de ingesta del proyecto usa actualmente la **Versión 1.3** del modelo
de datos en grafos (`src/zona4_graph_loader/NEO4J_DATA_MODEL.md`). Es la versión
vigente al cierre de esta rama (`feature/ingesta-nuevas-fuentes`); las secciones
de abajo describen los cambios acumulados desde V1.1.1.

### Novedades de V1.3 (auditoría semántica, 2026-08-29/30)

Una auditoría contra el grafo cargado encontró 15 casos (5 críticos) de una
misma clase de defecto: **una propiedad que afirma algo que la fuente no
dice**. Los fixes redujeron deliberadamente lo que el grafo afirma — no
agregaron dato nuevo, sacaron afirmaciones que no estaban respaldadas. Los más
importantes:

- `TORTURO_A` ya no se emite para todo par imputado-víctima de MinJus: sólo
  cuando la sentencia imputa tormentos a ese par en particular. El resto recibe
  la nueva relación `IMPUTADO_POR`, con la misma lista de `delitos` en ambos
  casos (antes: 14.858 pares, todos `TORTURO_A`, sin mirar qué delito
  imputaba realmente la sentencia).
- El Archivo de la Memoria de San Martín deja de generar aristas
  `SECUESTRADO_EN`: su campo `lugar` es una categoría barrial curatorial del
  archivo municipal, no el lugar del hecho (contradecía la propia descripción
  de la fuente en más de la mitad de los casos). Pasa de 303 aristas
  geográficas a 0.
- El resolver de topónimos ya no inventa una ciudad de Buenos Aires para texto
  que no puede resolver, ni reubica personas en la provincia equivocada — un
  defecto preexistente que esta rama expuso a mayor escala, no algo que
  introdujera.
- `Nietx.ADN` ya no se completa con `"SÍ"` cuando la fuente no trae fecha de
  confirmación: quedaba afirmando una identificación genética falsa para 275
  nietxs que la propia fuente clasifica como en búsqueda, no nacidxs o
  asesinadxs — otro defecto preexistente, no nuevo de esta rama.
- Valores centinela de las fuentes (`"SIN ESPECIFICAR"`, `"–"`, `"NO
  DETERMINADO"`, etc.) ya no generan nodos `:Org`/`:Institución` reales.

Detalle completo, conteos y lo que queda deliberadamente sin arreglar:
`.superpowers/sdd/2026-08-29-ingesta-nuevas-fuentes/semantic-audit-report.md` y
`semantic-fixes-report.md`.

### Cambios Clave introducidos en V1.1.1 (histórico):
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
- `--skip-nuevas-fuentes`: No integra los builders que leen de `data/raw/` (EAAF, Archivo de la Memoria de San Martín, MinJus GBA, condenados de Juicios de Lesa Humanidad).
- `--skip-identity-resolution`: No reconcilia identidades entre fuentes antes de cargar (ver sección 2.8 de [ingesta_fuentes.md](/docs/operations/ingesta_fuentes.md)).
- `--dump-cdm <path>`: Vuelca el CDM consolidado a un JSON en `<path>`, para auditoría sin necesidad de una base Neo4j corriendo.

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


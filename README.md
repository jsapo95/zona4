# Comisión de Ciencia de Datos

## Objetivos

| Objetivo | Descripción | Estado |
| -------- | ----------- | ------ |
| Ingeniería de datos | Recopilación, limpieza, procesamiento y normalización de datos sobre la dictadura. Para esto utilizamos bases de datos públicas y también extracción de datos a partir de documentación pública digitalizada. | En proceso |
|Creación de bases de datos | Crear bases de datos tabulares y de grafos de conomiento para poder realizar distintos tipos de análisis e investigaciones. | En proceso |
| Disponibilización pública de información | Disponibilizar las bases de datos que hagamos en conjunto con desarrollos de técnicas, procesos y programas propios que permitan mejorar la investigación en estos temas. | Pendiente |
| Chatbot Graph-RAG | Desarrollo de herramientas de búsqueda de información sobre la dictadura y sobre nuestras bases de datos, usando inteligencia artificial. | Pendiente |
| Resolución de identidades | Investigación y desarrollo de modelos analíticos predictivos que ayuden en la resolución de identidades. Esto es: tratar de determinar probabilísticamente si descripciones parciales de personas corresponden a una misma persona. Por ejemplo, si hay sobrevivientes que vieron a otrx secuestrado pero no saben quién fue, queremos ver si encontramos la forma de analizar las descripciones y saber quien era esa persona. Es algo que tenemos que investigar por un pedido que nos hicieron desde Abuelas. |
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
| Archivo de la Memoria de San Martín | Pendiente | https://sitiosale.cdn.prismic.io/sitiosale/Z9luiTiBA97GimGK_M_ArchivodeMemoria-1-.pdf | |
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


## Procesamiento de los datos

Para poder analizar y crear modelos analíticos, se necesita procesar los datos obtenidos para normalizarlos. En ese sentido se utilizan técnicas de automatización cuando es posible o procesamiento manual en varios casos.

Con esta normalización se pretende crear una base de datos que pueda ser accedida públicamente con datos que están en constante actualización.

## Operacion tecnica del loader

Para documentacion tecnica de ingesta y extension de nuevas fuentes:

- Ver `docs/ingesta_extensible.md`.
- Ver `docs/neo4j/README.md` para modelo de grafo y consultas Cypher.

Carga base (con extensiones habilitadas por default):

```bash
PYTHONPATH=src .venv/bin/python -m zona4_graph_loader.cli --clean-project
```

Flags utiles:

- `--extensions-dir data/extensions`
- `--skip-extensions`

Neo4j local con plugins:

- `docker-compose.yml` ya incluye instalacion automatica de APOC y GDS para entorno local.
- Esta instancia publica Bolt en `localhost:17687` para evitar conflictos con otros Neo4j en `7687`.
- Reiniciar con `docker compose up -d --force-recreate` cuando se cambie la configuracion de Neo4j.
- Verificar en Browser:
	- `RETURN apoc.version() AS apoc_version;`
	- `RETURN gds.version() AS gds_version;`


## Análisis y visualización de datos

Realización de tableros con:

* Gráficos
* Grafos
* Métricas


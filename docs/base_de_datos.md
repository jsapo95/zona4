# Comisión de Ciencia de Datos

## Objetivos

* Recopilar datos públicos de distintas fuentes y en distintos formatos.
* Limpiar, procesar, normalizar y estructurar los datos recopilados.
* Poder vincular documentación parecida y duplicada.
* Integrar modelos de lenguaje (LLMs) en los sistemas para ingeniería de datos y búsqueda de información.
* Realizar modelos de aprendizaje automático para automatizar la clasificación de entidades y relaciones en textos.
* Analizar y visualizar los datos obtenidos.
* Crear documentación de cada proceso para que puedan ser replicados y mejorados.


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

* [Archivo de la Memoria de San Martín](https://sitiosale.cdn.prismic.io/sitiosale/Z9luiTiBA97GimGK_M_ArchivodeMemoria-1-.pdf)
* [Base de datos - Parque de la memoria](https://basededatos.parquedelamemoria.org.ar/registros/)
* [Niños desaparecidos. Jóvenes localizados 1975 - 2015](https://www.unq.edu.ar/wp-content/uploads/migracion/documentos/5594327fb5347.pdf)
* [Nietas y nietos - Abuelas de Plaza de Mayo](https://www.abuelas.org.ar/nietas-y-nietos/buscador)
* [Centros clandestinos de detención](https://es.wikipedia.org/wiki/Centro_clandestino_de_detenci%C3%B3n_(Argentina))
* [Listado de Centros Clandestinos de Detención](https://www.argentina.gob.ar/sites/default/files/6._anexo_v_listado_de_ccd-investigacion_ruvte-ilid.pdf)
* [Listado de casos sin denuncia formal](https://www.argentina.gob.ar/sites/default/files/3._anexo_ii_listado_de_casos_sin_dcia_formal-investigacion_ruvte-ilid.pdf)
* [Registro Unificado de Víctimas del Terrorismo de Estado (RUVTE)](https://www.argentina.gob.ar/derechoshumanos/ANM/ruvte/2015)
* [Centros Clandestinos de Detención durante la dictadura cívico-militar entre 1976 y 1982](https://observatorioconurbano.ungs.edu.ar/?p=5392)
* [Paquete R - presentes](https://diegokoz.github.io/presentes/)
* [Documentos desclasificados EE.UU.](https://desclasificados.org.ar/)
* [Datos de represores y victimas](https://derechoshumanos.mjus.gba.gob.ar/imputado/33-balmaceda-roberto-armando/)
* [Imputados](https://www.mpf.gob.ar/plan-condor/imputados/zona-iv-santiago-omar-riveros/)
* [Archivo provincial de la memoria](https://apm.gov.ar/presentes/detalle/2716)
* [Semblanza de las dictaduras civico-militares del 55' al 83'](https://robertobaschetti.com/)
* [Leyes de la dictadura](https://www.lasleyesdeladictadura.com.ar/index.php?a=PublicView&name=LeyesPublic)
* [Condor Atlanta](https://condor-atlanta.org/)
* [Juicios de Lesa Humanidad](http://www.juiciosdelesahumanidad.ar/)
* [Nizkor](https://www.derechos.org/nizkor/arg/)
* [Fiscales juicios](https://www.fiscales.gob.ar/lesa-humanidad/?tipo-entrada=agenda)
* [Webinar IA y DDHH](https://www.cipdh.gob.ar/inteligencia-artificial-y-derechos-humanos/)
* [Juicios](https://www.mpf.gob.ar/lesa/jurisprudencia/)


## Procesamiento de los datos

Para poder analizar y crear modelos analíticos, se necesita procesar los datos obtenidos para normalizarlos. En ese sentido se utilizan técnicas de automatización cuando es posible o procesamiento manual en varios casos.

Con esta normalización se pretende crear una base de datos que pueda ser accedida públicamente con datos que están en constante actualización.


## Análisis y visualización de datos

Realización de tableros con:

* Gráficos
* Grafos
* Métricas








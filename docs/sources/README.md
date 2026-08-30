# Documentación de Fuentes de Datos (ZONA4)

Este directorio contiene las especificaciones, glosarios y metodologías aplicadas a cada una de las fuentes de información utilizadas en el proyecto **ZONA4**.

El objetivo es documentar el origen de los datos, el mapeo hacia las entidades y relaciones del grafo de Neo4j, y garantizar la trazabilidad socio-histórica de la información utilizada en la reconstrucción de memoria y derechos humanos.

---

## 1. Fuentes de Datos Procesadas y Glosarios

A continuación se listan las fuentes de información actualmente activas y normalizadas en el cargador, con enlaces a su documentación detallada:

*   **Centros Clandestinos de Detención (CCD)**:
    *   *Descripción*: Información de centros de detención procedentes del listado oficial unificado del RUVTE.
    *   *Documentación*: [ccds.md](file:///Users/a4649783/Documents/UNSAM/zona4/docs/sources/ccds.md)
*   **Buscador de Nietas y Nietos (Abuelas de Plaza de Mayo)**:
    *   *Descripción*: Registros de casos y relaciones de parentesco procedentes de Abuelas de Plaza de Mayo.
    *   *Documentación*: [nietos_y_nietas.md](file:///Users/a4649783/Documents/UNSAM/zona4/docs/sources/nietos_y_nietas.md)
*   **Base de Datos del Parque de la Memoria**:
    *   *Descripción*: Registros de víctimas y fichas personales detalladas procedentes del Parque de la Memoria.
    *   *Documentación*: [parque_de_la_memoria.md](file:///Users/a4649783/Documents/UNSAM/zona4/docs/sources/parque_de_la_memoria.md)
*   **Paquete R - Presentes**:
    *   *Descripción*: Datos consolidados de militancia, detenciones y trayectorias del paquete analítico "Presentes".
    *   *Documentación*: [paquete_r_presentes.md](file:///Users/a4649783/Documents/UNSAM/zona4/docs/sources/paquete_r_presentes.md)
*   **Archivo de la Memoria de San Martín**:
    *   *Descripción*: Víctimas del partido de San Martín (Zona IV), con lugar de secuestro y fecha normalizada.
    *   *Documentación*: [archivo_memoria_san_martin.md](file:///Users/a4649783/Documents/UNSAM/zona4/docs/sources/archivo_memoria_san_martin.md)
*   **EAAF — La Búsqueda**:
    *   *Descripción*: Sitios de hallazgo de restos del Equipo Argentino de Antropología Forense; el CSV de identificados de la misma fuente queda fuera del grafo (ver ficha).
    *   *Documentación*: [eaaf.md](file:///Users/a4649783/Documents/UNSAM/zona4/docs/sources/eaaf.md)
*   **MinJus GBA**:
    *   *Descripción*: Centros clandestinos, imputados, víctimas y sentencias de la consulta interactiva de Derechos Humanos de la Provincia de Buenos Aires.
    *   *Documentación*: [minjus_gba.md](file:///Users/a4649783/Documents/UNSAM/zona4/docs/sources/minjus_gba.md)
*   **Juicios de Lesa Humanidad**:
    *   *Descripción*: Condenados por lesa humanidad; las causas de Argentina y del exterior quedan fuera del grafo (ver ficha).
    *   *Documentación*: [juicios_lesa_humanidad.md](file:///Users/a4649783/Documents/UNSAM/zona4/docs/sources/juicios_lesa_humanidad.md)

---

## 2. Contenido de los Documentos de Fuente

Para mantener la consistencia, cada archivo de documentación técnica en esta carpeta define:
1.  **Origen y Licencia**: De dónde se obtuvieron los datos y sus licencias públicas.
2.  **Esquema de Campos Originales**: Listado de campos que provee la fuente original (CSV/JSON).
3.  **Procesamiento y Mapeo**: Reglas de normalización aplicadas (e.g. limpieza de texto y mapeo de género) y cómo se traducen a nodos (ej. `:Persona:Victima`, `:Lugar:CCD`) y aristas (ej. `-[:SECUESTRADO_EN]->`, `-[:HIJE_DE]->`) en Neo4j.
4.  **Trazabilidad**: Llaves estables de origen (e.g. `id_nietx`, `registro`) para garantizar la auditabilidad.

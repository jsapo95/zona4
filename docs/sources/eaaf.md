# Equipo Argentino de Antropología Forense (EAAF) — La Búsqueda

## Origen

*   **URL**: https://labusqueda.eaaf.org.ar/
*   **Extractor**: `src/zona4_extractor/web_scraper_eaaf.py` descarga dos CSV
    distintos del mismo micrositio a `data/raw/`:
    *   `eaaf_lugares.csv` (desde `consolidadoLugaresFix.csv`).
    *   `eaaf_identificados.csv` (desde `get-csv-cors.php?file=Consolidado_Micrositio_EAAFIdentificados_DATASET.csv`).

Las dos fuentes tienen destinos completamente distintos en el grafo: una está
adentro, la otra afuera.

---

## `eaaf_lugares.csv` — EN GRAFO

*   **Builder**: `src/zona4_graph_loader/builders/eaaf_lugares.py::build_eaaf_lugares_rows`.
*   **Registros**: 91 filas, 100% con coordenadas (`Lat`/`Long`).
*   **Formato**: CSV con delimitador `;`. Columnas: `PROVINCIA`, `LOCALIDAD`,
    `CEM - CCD - EP`, `LUGAR DE HALLAZGO`, `HOJA DE REFERENCIA`, `Lat`, `Long`,
    y cuatro columnas de conteo (`Suma de CASOS`, `Suma de EXHUMADOS`,
    `Suma de ID CON CUERPO`, `Suma de ID SIN CUERPO`, `Suma de ID`,
    `Suma de NO ID`) que no se mapean al CDM: son agregados que ya vienen
    resumidos por sitio y no aportan una entidad o arista propia del modelo.

### Mapeo al CDM

| Campo origen | Destino CDM |
| --- | --- |
| `PROVINCIA` | jerarquía `:Lugar` PAIS/PROVINCIA (o sólo PAIS si la provincia es en realidad un país extranjero — ver abajo). |
| `LOCALIDAD` | `:Lugar` tipo `CIUDAD`, colgado del contenedor anterior. |
| `CEM - CCD - EP` | `tipoGeopolitico` del sitio: `CEMENTERIO`, `CCD` o `ENTERRAMIENTO` (fallback `SITIO_HALLAZGO` si el código no matchea). |
| `LUGAR DE HALLAZGO` | `nombre` del `:Lugar` hoja. |
| `Lat` / `Long` | `:DireccionCCD.coordenadas`, enlazada al lugar hoja vía `UBICADA_EN`. |
| `HOJA DE REFERENCIA` | `:Lugar.ubicacion` (texto libre, no estructurado). |

Tres filas traen `PROVINCIA = URUGUAY` (además hay códigos para BOLIVIA, BRASIL,
CHILE y PARAGUAY, sin filas reales en el dataset actual). Para esas filas la
jerarquía no arma PROVINCIA argentina: el país mismo pasa a ser el contenedor
directo y usa su propio `pais_code` (`UY`, no `AR`), vía la tabla
`PAISES_EXTRANJEROS` del builder.

Las claves de lugar (`sitio_key`) se derivan de nombre + contenedor, no sólo
del nombre: el dataset real trae más de un sitio homónimo (p. ej. varios
"Cementerio Norte" en provincias distintas) que colisionarían si la clave
saliera únicamente del nombre en mayúsculas.

---

## `eaaf_identificados.csv` — DESCARTADO, fuera del grafo

*   **Registros**: 877 filas.
*   **Sin builder**: no hay ningún módulo en `src/zona4_graph_loader/builders/`
    que lo consuma.

### Por qué queda afuera

1.  **No tiene columna de nombre.** Son casos anonimizados: las columnas son
    `provincia`, `lugar de hallazgo`, `sexo`, `fecha desaparición`, `id por`,
    `causa de muerte`, `año de id`, `cuerpo`, `edad` — ninguna identifica a la
    persona. `:Persona.nombre` es un campo obligatorio en el modelo (V1.2), así
    que no hay forma de crear un nodo `:Persona` válido por fila.
2.  **El archivo está dañado por un problema de encoding.** El texto contiene
    357 caracteres U+FFFD (el carácter de reemplazo Unicode) y **cero**
    caracteres acentuados válidos en todo el archivo — ni una sola "ñ" o
    vocal con tilde sobrevivió. Los propios nombres de columna están rotos
    (`fecha desaparici�n`, `a�o de id`).

    La causa está en `src/zona4_extractor/web_scraper_eaaf.py`, función
    `descargar_archivo_csv`:

    ```python
    if response.encoding is None or response.encoding.lower() == 'iso-8859-1':
        response.encoding = 'latin1'
    ```

    Cuando el servidor declara el charset como `ISO-8859-1` (o no lo declara),
    el script fuerza la decodificación a `latin1` y vuelve a escribir el
    resultado como UTF-8. El archivo resultante en disco es el que hoy tiene
    357 reemplazos y ningún acento recuperable: el bug está en el *extractor*,
    no en el loader, así que corregirlo requiere re-descargar el CSV con el
    encoding correcto, no un fix en el pipeline de carga.

Los agregados por sitio que este archivo aportaría (cantidad de identificados,
exhumados, con/sin cuerpo) ya están disponibles — y sin el problema de
encoding — en `eaaf_lugares.csv`, que sí entró al grafo (ver arriba).

### Remedio

Corregir `descargar_archivo_csv` para que respete el encoding real declarado
por el servidor (o lo autodetecte de forma confiable, p. ej. con `chardet`
antes de forzar `latin1`) y volver a descargar el archivo. Aun corregido el
encoding, seguiría faltando una columna de nombre: esta fuente seguiría sin
poder generar nodos `:Persona` propios, aunque sí podría aportar en el futuro
si el modelo incorporara un nodo de "caso anonimizado" distinto de `:Persona`.

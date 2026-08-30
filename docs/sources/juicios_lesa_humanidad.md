# Juicios de Lesa Humanidad en Argentina

## Origen

*   **URL**: http://www.juiciosdelesahumanidad.ar/
*   **Archivos en `data/raw/`**:
    *   `juicios_lesa_humanidad_condenados.json` (1237 registros).
    *   `juicios_lesa_humanidad_argentina.json` (369 causas).
    *   `juicios_lesa_humanidad_exterior.json` (causas juzgadas fuera de
        Argentina, incompleto — ver pendiente).
*   **Builder**: `src/zona4_graph_loader/builders/juicios_condenados.py::build_juicios_condenados_rows`,
    que sólo consume el archivo de condenados. Los dos archivos de causas no
    tienen builder.

## `condenados` — EN GRAFO (1237 represores, 197 cómplices civiles)

| Campo origen | Destino CDM |
| --- | --- |
| `condenados.impu_id` | Componente de `persona_key` (`juicios_condenado:{impu_id}`). |
| `condenados.apellido_nombre` | `:Persona.nombre`. |
| `condenados.Categoria` | Si es `"CIVILES"`, agrega el rol `COMPLICE` con `complice_tipo: "CIVIL"` además de `REPRESOR`; para `"FUERZAS ARMADAS"`/`"FUERZAS DE SEGURIDAD"` sólo `REPRESOR`. |
| `condenados.Nacimiento` | `:Persona.fecha_nacimiento`. El campo viene como `DD-MM-YYYY` (con guiones, a diferencia del `DD/MM/YYYY` de MinJus); en condenados fallecidos trae `"DD-MM-YYYY/DD-MM-YYYY"` (nacimiento/fallecimiento) y sólo se toma el primer componente. |
| `condenados.Fuerza` | `:Org` (`tipoOrg: "FUERZA"`) + arista `PARTE_DE`. |

De los 1237 condenados, **197** están categorizados como `CIVILES` y entran
como `:Persona:Represor:Complice {tipo: "CIVIL"}`.

---

## Pendientes

### Las causas quedan fuera del grafo — no existe nodo `:Causa`

Ni `juicios_lesa_humanidad_argentina.json` (369 causas) ni
`juicios_lesa_humanidad_exterior.json` tienen builder ni destino en el CDM: el
modelo V1.2 no define un nodo `:Causa` (ni `:Sentencia`, la misma carencia
documentada en `docs/sources/minjus_gba.md` para las sentencias de MinJus).
Cada causa trae, entre otros campos, nombre, lugar, relato y cantidad de
imputados — información que hoy no tiene dónde aterrizar sin ese nodo.

Adicionalmente, **el archivo de causas del exterior está incompleto**: su
propio `metadata` declara

```json
{"paginaActual": 1, "paginas": 1, "RegistrosPorPagina": 41, "totalItems": 64, ...}
```

es decir, la fuente misma admite que existen 64 causas juzgadas fuera de
Argentina, pero el archivo descargado sólo trae 41 — un 36% faltante, sin que
haya paginación real que lo explique (`paginas: 1`). El archivo de causas
argentinas, en cambio, sí está completo: `RegistrosPorPagina` y `totalItems`
coinciden en 369.

**Remedio**: para cargar estas causas hace falta (a) sumar un nodo `:Causa` al
modelo V1.2, con su propio builder y aristas hacia `:Persona` (imputados/
condenados) y `:Lugar`; y (b) re-descargar `juicios_lesa_humanidad_exterior.json`
forzando la paginación real de la fuente para recuperar las 23 causas
faltantes antes de darlo por completo.

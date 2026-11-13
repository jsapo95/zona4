# Recorridos: del secuestro al hallazgo

Mapa animado de Argentina. Cada punto es una víctima y, al reproducir, pasa por
cuatro etapas abstractas (no son fechas):

| Etapa | Fuente | En el grafo |
| ----- | ------ | ----------- |
| 0 · Secuestro | Parque de la Memoria, `descripcion_lugar_de_secuestro` | `SECUESTRADO_EN` |
| 1 · Centro clandestino | RUVTE (`ccds.json`) y MinJus GBA | `PRESENTE_EN` |
| 2 · Asesinato | Parque de la Memoria, `Lugar de asesinato` | `ASESINADO_EN` |
| 3 · Hallazgo de restos | Parque de la Memoria, `descripcion_datos_de_identificacion`, cruzado con `eaaf_lugares.csv` | no está |

Hay dos versiones, que se eligen arriba del panel:

- **Sabemos dónde terminaron** (740 personas): tienen registrado el hallazgo de
  sus restos. En 690 se pudo ubicar el lugar.
- **No sabemos dónde terminaron** (8.156 personas): desaparecidas o asesinadas
  sin hallazgo de restos registrado. En la etapa final cada punto se apaga en
  el último lugar donde las fuentes la ubican.

Las personas liberadas, fugadas o restituidas según MinJus (1.662) quedan
afuera de las dos versiones.

## Cómo abrirla

Abrir `recorridos.html` en el navegador (doble clic alcanza; no hace falta
servidor). Necesita internet: Leaflet viene de cdnjs y el mapa base es
[Argenmap](https://www.ign.gob.ar/AreaServicios/Argenmap/Introduccion), del IGN.

- **Reproducir** (o barra espaciadora): recorre las cuatro etapas.
- Los números 0–3 debajo de la barra, o las flechas, saltan a una etapa.
- **Clic en un punto**: muestra el recorrido de esa persona, con la precisión de
  cada lugar y el link a su ficha en la fuente. También se la puede buscar por
  nombre.
- Capas: mapa de calor, personas y trayectos (arcos entre etapas).

## Cómo regenerar los datos

```bash
# 1. Una sola vez: centroides de Georef (el catálogo del loader no trae coordenadas)
.venv/Scripts/python visualizaciones/recorridos/descargar_centroides.py

# 2. Datos de la visualización (≈1,5 min)
.venv/Scripts/python visualizaciones/recorridos/construir_datos.py
```

`construir_datos.py` corre el pipeline del loader en memoria hasta el CDM
(`cdm.py`), sin Neo4j, así que usa las mismas personas, lugares y fusiones de
identidad que el grafo. Dos ajustes, ninguno cambia el CDM: se saltea el Paso 2
de `resolve_identities` (candidatos fuzzy, que sólo agrega `CANDIDATO_MERGE` y
hace que la carga tarde más de media hora) y corre en un directorio temporal
para no reescribir `data/processed/identity_merges.json`.

Al final imprime un resumen con cuántos lugares se ubicaron en cada etapa y por
qué no se ubicaron los demás. Medido el 2026-11-12:

| Etapa | Registrados | Ubicados | No ubicados |
| ----- | ----------- | -------- | ----------- |
| Secuestro | 7.133 | 6.749 | 262 sólo provincia, 88 sin centroide, 34 en el exterior |
| Centro clandestino | 3.472 | 3.428 (1.255 por la localidad de su dirección) | 44 sin coordenadas ni dirección |
| Asesinato | 1.667 | 1.549 | 90 sólo provincia, 15 sin centroide, 13 en el exterior |
| Hallazgo de restos | 745 | 690 | 55 textos sin lugar ("Identificado por el EAAF en 2009") |

Los tests de las reglas de ubicación están en
`tests/visualizaciones/test_recorridos_ubicacion.py`.

## Cómo se ubica cada lugar

- **CCD y sitios del EAAF**: coordenadas propias de la fuente. Los CCD de MinJus
  que no las tienen se ubican por la localidad de su dirección.
- **Localidades y barrios**: centroide de Georef (localidad, municipio o
  asentamiento, en ese orden). Los puntos que comparten centroide se dispersan
  un poco para que se vean; la dispersión es fija entre recargas.
- **"Capital Federal" sin barrio** (1.801 secuestros): centro de CABA, con una
  dispersión mayor.
- **Sólo la provincia**: no se dibuja. El centroide de Buenos Aires cae en medio
  de la pampa, lejos de cualquier hecho.
- **Hallazgo de restos**: primero se busca en el texto un sitio del EAAF
  ("Cementerio de Avellaneda", "Pozo de Vargas"). Si no hay, se lee el texto por
  segmentos, descartando calles, números, intersecciones y cuerpos de agua, y se
  usa el resolver de lugares del grafo. Ante la duda no se ubica: "Río de la
  Plata" no es La Plata y "Perito Moreno y Dellepiane" no es Moreno.

## Lo que el mapa no dice

- **El orden entre CCD no se conoce.** Quien pasó por tres aparece en los tres a
  la vez, con un tercio de peso en cada uno.
- **La etapa de CCD está sesgada hacia la provincia de Buenos Aires**: MinJus GBA
  es la fuente con más pasos por CCD y sólo cubre esa provincia.
- **MinJus no tiene lugar de secuestro procesado** (es texto narrativo, pendiente
  en el grafo). Esas personas aparecen recién en la etapa 1.
- **Las fichas que el grafo no fusionó son dos personas.** Por ejemplo, Juan
  Carlos Abachian está en el Parque (secuestro en La Plata, 26/12/1976) y en
  MinJus (tres CCD, secuestro el 20/01/1977). Como las fechas se contradicen, el
  grafo no las une y el mapa muestra dos recorridos incompletos.
- **Un punto apagado indica que la fuente no registra esa etapa**, no que la
  persona no haya pasado por ella.

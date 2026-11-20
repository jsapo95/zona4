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

- **Restos hallados** (738 personas): tienen registrado el hallazgo de sus
  restos. En 691 se pudo ubicar el lugar.
- **Sin hallazgo de restos registrado** (7.738 personas): desaparecidas o
  asesinadas sin hallazgo de restos registrado (1.435 figuran como asesinadas).
  En la etapa final cada punto se apaga en el último lugar donde las fuentes
  ubican a esa persona.

Las personas liberadas, fugadas o restituidas según MinJus (1.662; en 3 el
Parque dice desaparecida, así que las fuentes se contradicen) quedan
afuera de las dos versiones. También las 29 que sólo están en MinJus como
"Persona fallecido" o sin estado: varios relatos cuentan que fueron liberadas y
murieron después, así que no se sabe si siguen desaparecidas.

## Cómo abrirla

Abrir `recorridos.html` en el navegador (doble clic alcanza; no hace falta
servidor). Necesita internet: Leaflet viene de cdnjs y el mapa base es
[Argenmap](https://www.ign.gob.ar/AreaServicios/Argenmap/Introduccion), del IGN.
Si el servidor del IGN no responde en 6 segundos, el mapa queda sin fondo (los
datos se ven igual) con un aviso y un botón para reintentar. No hay mapa de
respaldo a propósito: los otros mapas base públicos (OpenStreetMap, por
ejemplo) rotulan las Islas Malvinas como "Falkland Islands", y ese rótulo
viene dibujado en la imagen, así que no se puede corregir desde la página.

- **Reproducir** (o barra espaciadora): recorre las cuatro etapas.
- Los números 0–3 debajo de la barra, o las flechas, saltan a una etapa.
- **Seguir a quienes pasaron por un centro clandestino**: escribir un CCD (por
  ejemplo "ESMA") deja en el mapa sólo a esas personas, en todas las etapas, para
  ver de dónde venían y adónde fueron. Se elige sola la versión con más personas
  de ese CCD.
- **Clic en un punto**: muestra el recorrido de esa persona, con la precisión de
  cada lugar y el link a su ficha en la fuente. También se la puede buscar por
  nombre.
- Capas: mapa de calor, personas y trayectos (arcos entre etapas).

## Recorridos frecuentes (`flujos.html`)

Segunda vista con los mismos datos: un mapa de flujos con los tramos entre
etapas. Cada flecha une un lugar con el siguiente del recorrido de una persona y
su grosor es la cantidad de personas; el color dice hacia qué etapa va (CCD,
asesinato o hallazgo de restos).

- **Recorridos similares** son los que pasan por los mismos lugares en las mismas
  etapas. Para que se puedan comparar, secuestro, asesinato y hallazgo se
  agrupan por partido o departamento de Georef (Villa Ballester y San Andrés
  son General San Martín; todos los barrios de CABA son la Ciudad de Buenos
  Aires). Los CCD y los sitios del EAAF quedan como sitios propios.
- Se filtra por versión, por **año de secuestro** (con un botón que recorre los
  años) y por un lugar escrito (partido, CCD o cementerio). La lista de
  recorridos más repetidos deja ver a las personas de cada uno.
- Tres casillas en la leyenda prenden o apagan cada tipo de tramo: hacia el
  CCD, hacia el lugar de asesinato y hacia el hallazgo de restos.
- **Zonas y sitios**: un punto con borde punteado y relleno tenue es una zona
  (la fuente sólo dice el partido, la localidad, el barrio o "Capital
  Federal"): es el centro de esa zona, no una dirección. Un punto relleno es un
  sitio específico (CCD o sitio del EAAF con coordenadas propias); con borde
  punteado, un CCD sin coordenadas propias, ubicado en el centro de su
  localidad. Con zoom se siguen viendo todos los tramos, y desde el zoom 10 el
  rótulo de abajo a la izquierda lista las zonas que se ven con cuántos
  secuestros, pasos por CCD, asesinatos y hallazgos sin dirección exacta tiene
  cada una. Las etapas sin registro (sin CCD, sin asesinato, etc.) se cuentan
  en el panel.
- Sólo entran las 1.178 personas con dos etapas o más ubicadas. Las más
  repetidas: Tucumán (capital) → Pozo de Vargas (44), CABA → El Vesubio (33),
  General Pueyrredón → Base Naval Mar del Plata (23).
- El año es el del secuestro (arista del Parque o ficha de MinJus); 78 de esas
  1.178 no lo tienen y sólo aparecen con "Todos los años".

`mapa_base.js` tiene el mapa base (Argenmap, sin respaldo) que usan las dos
páginas.
`estilo.css` tiene el estilo común de la interfaz, inspirado en la web de
Abuelas de Plaza de Mayo (Inter, violeta y naranja), sin su logo ni su nombre.
Los colores de los datos siguen siendo la paleta validada para daltonismo.

## Cómo regenerar los datos

Los datos ya generados están en el repo (`datos/recorridos.js`): para ver los
mapas no hace falta regenerarlos. Hay que hacerlo cuando cambian las fuentes,
el loader o las reglas de ubicación:

```bash
# Datos de la visualización (≈1,5 min; necesita el venv del loader)
.venv/Scripts/python visualizaciones/recorridos/construir_datos.py

# Sólo para actualizar los centroides de Georef (ya están en datos/centroides_georef.json)
.venv/Scripts/python visualizaciones/recorridos/descargar_centroides.py
```

`construir_datos.py` corre el pipeline del loader en memoria hasta el CDM
(`cdm.py`), sin Neo4j, así que usa las mismas personas, lugares y fusiones de
identidad que el grafo. Dos ajustes, ninguno cambia el CDM: se saltea el Paso 2
de `resolve_identities` (candidatos fuzzy, que sólo agrega `CANDIDATO_MERGE` y
hace que la carga tarde más de media hora) y corre en un directorio temporal
para no reescribir `data/processed/identity_merges.json`.

Al final imprime un resumen con cuántos lugares se ubicaron en cada etapa y por
qué no se ubicaron los demás. Medido el 2026-11-18:

| Etapa | Registrados | Ubicados | No ubicados |
| ----- | ----------- | -------- | ----------- |
| Secuestro | 7.133 | 6.457 | 479 sólo provincia, 89 sin centroide, 34 en el exterior, 74 errores conocidos del grafo |
| Centro clandestino o lugar de detención | 3.472 | 3.428 (1.191 por la localidad de su dirección, 51 con coordenadas de RUVTE corregidas) | 44 sin coordenadas ni dirección |
| Asesinato | 1.667 | 1.400 | 212 sólo provincia, 15 sin centroide, 13 en el exterior, 27 errores conocidos del grafo |
| Hallazgo de restos | 745 | 691 | 54 que no se pudieron ubicar: algunos textos no nombran un lugar ("Identificado por el EAAF en 2009"), otros nombran uno que el lector no reconoce o un río |

**Errores conocidos del grafo**: aristas que el loader ubica mal y cuyo arreglo
todavía no está en `main` no se dibujan (`ERRORES_CONOCIDOS_DEL_GRAFO` y
`TEXTOS_EN_LA_CAPITAL_POR_ERROR`). Son 101: el país Uruguay resuelto en Entre
Ríos (PR #7), textos "LOCALIDAD. PROVINCIA" mandados a la capital ("METAN.
SALTA" y "PALOMITAS. SALTA" en Salta capital, "ROSARIO. SANTA FE (…)" en la
ciudad de Santa Fe; PR #9), Cruz Alta (Tucumán) en San Juan, Puente Saavedra en
el partido de Saavedra, y ocho casos sueltos ("BUENOS AIRES (Pasteur…)" que es
CABA, "V. Crespo … CAPITAL FEDERAL" en Crespo, Entre Ríos, etc.). Cuando cada
arreglo llegue a `main`, su entrada se borra y los datos se regeneran.

13 fichas del Parque traen en el lugar de secuestro el del asesinato
("asesinado 29/09/76 ROSARIO. SANTA FE"): ese lugar se dibuja en la etapa de
asesinato y la fecha no se usa como fecha de secuestro.

Los tests de las reglas de ubicación están en
`tests/visualizaciones/test_recorridos_ubicacion.py`.

## Cómo se ubica cada lugar

- **Sitios del EAAF y CCD de RUVTE**: coordenadas propias de la fuente, salvo 7
  CCD de RUVTE cuyas coordenadas contradicen su propia dirección o son las de
  otro CCD cercano (el Olimpo tiene las de Coordinación Federal;
  `COORDENADAS_RUVTE_ERRONEAS`, revisados uno por uno). Un sitio del EAAF
  nombrado con otra provincia no se usa: "Cementerio de la Piedad, Oberá,
  Misiones" no es La Piedad de Rosario.
- **CCD de MinJus sin coordenadas** (un tercio de los pasos por CCD): la
  localidad de su dirección o de su nombre, con la provincia como pista (sin
  ella, "SAN NICOLAS" caía en el barrio porteño). Si sólo se encuentra el
  partido, el punto va al partido. El Banco usa las coordenadas del sitio del
  EAAF.
- **"Bs. As." puede ser CABA**: un barrio porteño con "Bs. As." o "Buenos
  Aires" ("Palermo, Bs. As.") es ese barrio si no hay un lugar bonaerense con
  el mismo nombre. Si lo hay, vale la provincia en el texto libre; en una clave
  del grafo sin partido ("Saavedra" en la provincia) no se dibuja, porque no se
  sabe cuál de los dos es. "SAN NICOLAS. BS. AS." es San Nicolás de los Arroyos:
  el Parque escribe el barrio porteño como "CAPITAL FEDERAL (San Nicolas (…))"
  (`LOCALIDAD_DE_GEOREF`).
- **Localidades y barrios**: centroide de Georef (localidad, municipio o
  asentamiento, en ese orden). Las personas de un mismo lugar son un mismo
  punto, sin dispersión: el punto lista quiénes son y, en el hallazgo, la
  dirección que da el texto de cada una ("Dorrego y F. Alcorta (Palermo)").
- **"Capital Federal" sin barrio** (1.799 secuestros) y lugares que sólo dan el
  partido: centro de CABA o del partido. Con zoom de ciudad (10 o más, la vista AMBA) se
  ocultan, porque su punto parecería una dirección.
- **Nombres que en Georef son otro lugar**: "Guadalupe" (Santa Fe) no se ubica,
  porque el único candidato es Guadalupe Norte, a 300 km; "Fronterita"
  (Tucumán) va a Famaillá, donde está el ingenio (`PARTIDO_DE_LOCALIDAD`).
- **Cementerios con sectores**: si el texto dice "Cementerio de Avellaneda" sin
  sector, se nombra así, sin inventar el "Sector 134" del EAAF.
- **Sólo la provincia**: no se dibuja. El centroide de Buenos Aires cae en medio
  de la pampa, lejos de cualquier hecho. Un nombre de provincia a secas en
  secuestro o asesinato ("CORDOBA", "San Juan") es la provincia, no su capital:
  la fuente escribe la ciudad como "CORDOBA CAPITAL" (decisión del equipo; el
  grafo la aplica con el PR #10).
- **Hallazgo de restos**: primero se busca en el texto un sitio del EAAF
  ("Cementerio de Avellaneda", "Pozo de Vargas"). Si no hay, se lee el texto por
  segmentos, descartando calles, números, intersecciones y cuerpos de agua, y se
  usa el resolver de lugares del grafo. Ante la duda no se ubica: "Río de la
  Plata" no es La Plata y "Perito Moreno y Dellepiane" no es Moreno. "Cementerio
  de General Villegas" es el de Villegas, en La Matanza: el Parque lo llama así
  ("Cementerio de General Villegas, La Matanza, Bs As") y el EAAF no tiene
  sitios en General Villegas.

## Lo que el mapa no dice

La lista completa de huecos de datos, con cifras de referencia y fuentes,
está en [`../HUECOS_DE_DATOS.md`](../HUECOS_DE_DATOS.md).

- **El orden entre CCD no se conoce.** Quien pasó por tres aparece en los tres a
  la vez, con un tercio de peso en cada uno.
- **La etapa 1 incluye cárceles.** Las fuentes registran como lugar de
  detención unidades penales (la 9 de La Plata, Devoto, la 3 de San Nicolás):
  358 de los 3.472 pasos. Por eso la etapa se llama "Centro clandestino o lugar
  de detención".
- **La etapa de CCD está sesgada hacia la provincia de Buenos Aires**: MinJus GBA
  es la fuente con más pasos por CCD y sólo cubre esa provincia.
- **Los grandes CCD de CABA casi no aparecen.** Las fichas del Parque de la
  Memoria no tienen un campo de CCD, así que los pasos por CCD salen sólo de
  MinJus GBA (3.308) y del campo `ccds` de 148 fichas del Parque (206). La ESMA,
  por ejemplo, tiene 117 personas con `PRESENTE_EN` en el grafo (127 aristas: 97
  de MinJus y 30 del Parque, 10 personas en las dos); 46 son liberadas o
  restituidas y quedan afuera, y en el mapa se ven 71 (70 sin hallazgo de restos
  registrado, 1 con restos hallados).
- **MinJus no tiene lugar de secuestro procesado** (es texto narrativo, pendiente
  en el grafo). Esas personas aparecen recién en la etapa 1.
- **Las fichas que el grafo no fusionó son dos personas.** Por ejemplo, Juan
  Carlos Abachian está en el Parque (secuestro en La Plata, 26/12/1976) y en
  MinJus (tres CCD, secuestro el 20/01/1977). Como las fechas se contradicen, el
  grafo no las une y el mapa muestra dos recorridos incompletos.
- **Un punto apagado indica que la fuente no registra esa etapa**, no que la
  persona no haya pasado por ella.
- **Los trayectos son arcos, no rutas.** Un arco dice "de acá a allá", que es lo
  que registran las fuentes; no dice por dónde. Ver la nota de abajo.

## Nota: ¿se puede dibujar la ruta más probable entre etapas?

Se discutió y por ahora no. Lo que habría que resolver antes:

- **No hay una red vial digital de 1976–1983.** El ruteo disponible
  (OpenStreetMap, con OSRM o similares) usa las rutas de hoy: la autopista
  Buenos Aires–La Plata, por ejemplo, es de los años noventa. Hay mapas
  históricos escaneados (del IGN, del Automóvil Club Argentino), pero pasarlos a
  una red vial utilizable es un proyecto en sí mismo.
- **Muchos traslados no fueron por tierra**, como los vuelos de la muerte desde
  la ESMA o Campo de Mayo, y las fuentes casi nunca dicen cómo se hizo un
  traslado: sólo que la persona estuvo en un lugar y después en otro.
- **Una "ruta más probable" sería una suposición dibujada como si fuera un
  dato**, lo contrario del criterio del grafo de afirmar menos antes que
  inventar.

Lo que sí se podría hacer sin ese problema: mostrar como dato aparte la
distancia por ruta entre etapas, aclarando que es una estimación con la red de
hoy; o averiguar qué cartografía vial de la época existe digitalizada antes de
decidir.

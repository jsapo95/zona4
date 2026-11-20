# Huecos de datos que muestran las visualizaciones

Lo que falta en el grafo, medido al dibujar los recorridos
(`visualizaciones/recorridos/`) y en una revisión adversarial del 2026-11-18.
Cada hueco dice si **falta en la fuente** (F) o si **está en la fuente pero no
se cargó** (NC), y qué fuente lo cubriría.

Cómo se midió: personas distintas con `PRESENTE_EN` o `PARIO_EN` por CCD en el
CDM completo del loader (`recorridos/cdm.py`, incluye liberadas y
sobrevivientes, porque las cifras de referencia también las incluyen). En el
mapa las cifras son más bajas porque las sobrevivientes quedan afuera (ESMA:
117 en el grafo, 71 en el mapa).

Las cifras externas tienen link. Las marcadas con \* salen de
`data/raw/juicios_lesa_humanidad_argentina.json` (portal
juiciosdelesahumanidad.ar, campo `cant_victimas`) y no se contrastaron una por
una con la web.

## Resumen

- **El universo de víctimas está casi completo.** El Parque de la Memoria tiene
  8.948 fichas; el RUVTE reconoce 8.571 víctimas (7.010 desaparecidas y 1.561
  asesinadas)
  ([Unidiversidad](https://www.unidiversidad.com.ar/el-gobierno-reconocio-mas-de-8-mil-victimas-de-la-dictadura)).
- **Lo que falta son las etapas**, sobre todo el paso por centros
  clandestinos fuera del AMBA. Los pasos por CCD salen sólo de MinJus GBA
  (3.308) y del campo `ccds` de 148 fichas del Parque.
- Donde MinJus tiene página del CCD, el grafo llega más o menos a las víctimas
  de los juicios. Donde no la tiene (todo el interior y los grandes CCD de
  CABA), la cobertura está entre 0 y 2 %.
- 714 de los 808 CCD del RUVTE (88 %) no tienen ninguna persona.

## 1. Por centro clandestino

Ordenado por tamaño del hueco.

| CCD | En el grafo | Referencia | Cobertura | Causa | Fuente que lo cubriría |
| --- | --- | --- | --- | --- | --- |
| ESMA | 117 | "fueron desaparecidas alrededor de cinco mil personas" ([argentina.gob.ar](https://www.argentina.gob.ar/node/285364)); juicio ESMA III: 789 víctimas ([Amnistía](https://www.es.amnesty.org/en-que-estamos/noticias/noticia/articulo/argentina-esma-y-vuelos-de-la-muerte/)) | 2 % (15 % del juicio) | F: el Parque no tiene campo de CCD. NC: 17 relatos de MinJus la nombran sin tenerla en su lista | Sentencias ESMA III, IV y V |
| Escuelita de Famaillá | 5 | "alrededor de 3.000 personas" ([argentina.gob.ar](https://www.argentina.gob.ar/node/300214)) | 0,2 % | F: MinJus no cubre Tucumán | Sentencias Operativo Independencia I y II (269 y 335 víctimas\*) |
| La Perla | 8 | "entre 2200 y 2500 personas" ([argentina.gob.ar](https://www.argentina.gob.ar/node/285364)); megacausa: 716 víctimas ([La Izquierda Diario](https://www.laizquierdadiario.com/Megacausa-La-Perla-716-victimas-y-solo-43-acusados)) | 0,4 % (1 % del juicio) | F: no hay fuente de Córdoba. NC: 11 relatos de MinJus | Sentencia Menéndez III; Archivo Provincial de la Memoria de Córdoba |
| Servicio de Informaciones de Rosario | 0 (no hay nodo; RUVTE id 256) | "más de 2000 detenidos" ([La Capital](https://www.lacapital.com.ar/suscriptores/24-marzo-un-recorrido-el-interior-la-memoria-colectiva-n10011289.html)); Feced III y IV: 188 víctimas ([La Capital](https://www.lacapital.com.ar/politica/condenan-prision-perpetua-marcote-y-lofiego-delitos-lesa-humanidad-rosario-n2584280.html)) | 0 % | F: no hay fuente de Santa Fe | Sentencias Feced I–IV y Guerrieri; "Memoria urgente" (Santa Fe, 2023) |
| Club Atlético | 9 | "habría alojado a más de MIL QUINIENTAS (1500) personas" ([Decreto 1762/2014](https://www.argentina.gob.ar/normativa/nacional/decreto-1762-2014-236117/texto)) | 0,6 % | NC: unos 40 relatos de MinJus lo nombran | Sentencias ABO; relatos de MinJus |
| Olimpo | 7 | "aproximadamente QUINIENTAS (500) personas" (mismo decreto) | 1,4 % | NC: unos 45 relatos de MinJus | Ídem |
| D2 de Mendoza | 0 (RUVTE id 230) | megacausa D2: "más de 300 personas" ([argentina.gob.ar](https://www.argentina.gob.ar/node/391330)) | 0 % | F | Sentencia D2 (329 víctimas\*) |
| Jefatura de Policía de Tucumán | 2 | Jefatura III: 237 casos ([La Izquierda Diario](https://www.izquierdadiario.es/Megacausa-Jefatura-III-17-condenas-y-7-absoluciones-a-ex-militares-y-ex-policias-por-crimenes-de)) | 0,8 % | F | Sentencias Jefatura II y III |
| Automotores Orletti | 15 | "unos DOSCIENTOS (200) detenidos" (Decreto 1762/2014) | 7,5 % | F. NC: 7 relatos | Sentencia Orletti (65 víctimas\*) |
| Campo de Mayo | 374 | "entre 2000 y 5000 personas" ([Tiempo Argentino](https://www.tiempoar.com.ar/ta_article/el-centro-clandestino-campo-de-mayo-por-dentro-en-realidad-virtual/amp/), prensa); megacausa: "más de 350 víctimas" ([gba.gob.ar](https://gba.gob.ar/derechoshumanos/juicios_lesa_humanidad/megacausa_campo_de_mayo_perpetua_para_diez_imputados_y_penas)) | 7–19 % (todo el juicio) | Está lo que juzgó MinJus; el resto no está en ninguna fuente cargada | Listas de Memoria Abierta y del ANM |
| El Vesubio | 364 | Vesubio III: 370 víctimas ([argentina.gob.ar](https://www.argentina.gob.ar/node/219112)) | casi todo el juicio | Ídem | Listas del sitio de memoria |
| Mansión Seré | 69 | "al menos 150" ([Tiempo Argentino](https://www.tiempoar.com.ar/ta_article/donde-hubo-terror-ahora-brota-vida-25-anos-de-la-mansion-sere-como-espacio-de-resistencia/), prensa) | ≤ 46 % | — | Mansión Seré V (133\*) |
| Pozo de Banfield | 225 | "cerca de 350 personas" ([argentina.gob.ar](https://www.argentina.gob.ar/node/398624)) | 64 % | Bastante cubierto por MinJus | Sentencia "Las Brigadas" (442\*) |
| Pozo de Quilmes | 159 | "alrededor de 250 personas" ([Ley 14.895](https://normas.gba.gob.ar/documentos/V9LqgH3B.html)) | 64 % | Ídem | — |
| La Cacha | 146 | "más de 250 personas" ([gba.gob.ar](https://www.gba.gob.ar/derechoshumanos/noticias/se_inaugur%C3%B3_el_espacio_para_la_memoria_donde_funcion%C3%B3_la_cacha)) | < 58 % | Ídem | — |

CCD con 0 personas o casi, que MinJus nombra en sus relatos: Coordinación
Federal (4 personas, unos 50 relatos), Brigada de Lanús "El Infierno" (0, unos
40), Garage Azopardo (0, 13). Sin nadie y sin relatos: Campo de la Ribera (0),
D2 de Córdoba (1).

Los conteos de relatos salen de buscar el nombre del CCD en `relato_hechos`;
hay que revisarlos uno por uno antes de cargarlos.

## 2. Por provincia

Personas distintas en el CDM.

| Provincia | Secuestro | CCD | Asesinato | CCD del RUVTE sin ninguna persona |
| --- | --- | --- | --- | --- |
| Buenos Aires | 3.169 | 2.396 | 690 | 188 de 260 |
| CABA | 1.890 | 250 | 216 | 53 de 60 |
| Tucumán | 649 | 6 | 112 | 57 de 62 |
| Córdoba | 556 | 9 | 231 | 45 de 49 |
| Santa Fe | 294 | 6 | 228 | 53 de 57 |
| Mendoza | 135 | 0 | 21 | 40 de 40 |

- **El desbalance de Rosario se repite:** en Córdoba, Santa Fe y Tucumán hay
  cientos de asesinadas y menos de diez personas con un CCD registrado.
- 19 provincias tienen 0 personas en todos sus CCD.
- No se encontró un desglose oficial de las víctimas del RUVTE por provincia.

## 3. Hallazgo de restos

El hallazgo no está en el grafo: sale del texto de identificación del Parque
(745 fichas). El EAAF tiene 860 identificados en 91 sitios
(`eaaf_lugares.csv`) y el mapa ubica 589 personas en sitios del EAAF (68 %).

| Sitio | Identificados por el EAAF | En el mapa |
| --- | --- | --- |
| Cementerio de la Chacarita | 41 | 6 |
| Cementerio La Piedad (Rosario) | 51 | 25 |
| Pozo de Vargas | 121 | 103 |
| Cementerio de Villegas | 34 | 16 |
| Cementerio de Avellaneda | 136 | 123 |
| Cementerio de San Martín | 37 | 24 |
| Ex CCD La Perla | 16 | 3 |
| Cementerio de La Plata | 45 | 33 |
| Cementerio Santa Fe de la Vera Cruz | 13 | 5 |
| Cementerio de Benavídez | 6 | 0 |

Causa (F): `eaaf_identificados.csv` no trae nombres. Lo cubriría el listado
nominal de identificados por sitio, pedido al EAAF.

## 4. Datos que están en las fuentes y no se cargaron

- **CCD nombrados en los relatos de MinJus** que no están en su lista
  `centros_clandestinos`: unos 330 vínculos (ver la sección 1).
- **45 pares persona–CCD descartados** en
  `src/zona4_graph_loader/builders/minjus_victimas.py` (`if not lugar_key:
  continue`), cuando el CCD no tiene página propia en MinJus: ESIM (27),
  Comisaría 1ª de Moreno (14), Brigada Aérea VIII (2), Destacamento Jorge
  Newbery (1), Escuela Agrícola N° 2 (1). La fuente cruda tiene 3.353 pares y
  el grafo 3.308.
- **MinJus no tiene lugar de secuestro procesado**: está en texto narrativo.
  617 desaparecidas y 235 asesinadas que están sólo en MinJus no tienen
  secuestro ni asesinato ubicados.
- **Archivo de la Memoria de San Martín**: 261 personas sin ninguna arista
  geográfica.

## 5. Errores del grafo que reparten o esconden datos

- **El mismo CCD en varios nodos**: Puente 12 tiene 134 personas en el nodo de
  MinJus y 9 en el del RUVTE; La Perla, Arsenal Miguel de Azcuénaga, El Banco y
  Puesto Vasco tienen además un nodo del EAAF separado.
- **Fichas del Parque y de MinJus sin fusionar**: 188 pares con el mismo
  nombre (80 con fechas a 7 días o menos, 69 con una fecha faltante). 25
  personas aparecen a la vez como "restos hallados" y "sin hallazgo".
- **Localidades que caen en la capital de su provincia**: "METAN. SALTA",
  "ORAN. SALTA", "GOYA. CORRIENTES", "ROSARIO. SANTA FE" con prefijo, etc. (62
  aristas). En Salta capital, 30 de 78 casos son otras localidades.

## 6. Por año

Sólo 15 de las 326 personas secuestradas en 1975 tienen un CCD (4,6 %), justo
el período del Operativo Independencia. En 1976 es el 13 % y en 1977 el 19 %.

## Qué agregaría más cobertura

1. **Cargar las listas de víctimas de las sentencias**, con un nodo `:Causa`:
   ESMA III y IV, Menéndez III (La Perla, Campo de la Ribera), ABO, Feced y
   Guerrieri (Rosario), Jefatura y Operativo Independencia (Tucumán), D2 de
   Mendoza. Es la única fuente que llena el interior y los grandes CCD de CABA.
2. **Extraer de `relato_hechos` de MinJus los CCD que nombra**, contra el
   catálogo del RUVTE, revisando el contexto de cada mención.
3. **No descartar los 45 pares** (crear los CCD sin página) y **unificar los
   nodos duplicados** de RUVTE, MinJus y EAAF.
4. **Fuentes provinciales**: Archivo Provincial de la Memoria de Córdoba,
   "Memoria urgente" de Santa Fe, Espacio de Famaillá, la lista de Mendoza de
   CONICET. Preguntar al RUVTE o al ANM (Ley 27.275) si tienen la relación
   víctima–CCD.
5. **Pedir al EAAF el listado nominal** de identificados por sitio, empezando
   por Chacarita, La Piedad, Villegas y La Perla.

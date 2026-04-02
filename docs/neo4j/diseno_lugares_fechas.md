# Diseno KG para nodos comunes (lugares, fechas, estudio, embarazo)

Este diseno propone una capa transversal para responder consultas por nodos comunes del grafo.

Contexto observado en datos reales:
- Variantes de ciudad/capital recurrentes:
  - "CAPITAL FEDERAL"
  - "Ciudad De Bs. As."
  - "Ciudad de Bs. As."
  - "BUENOS AIRES" (ambigua entre provincia y ciudad)
  - "CORDOBA CAPITAL" / "CORDOBA"
  - "SAN MIGUEL DE TUCUMAN" / "TUCUMAN"
- Campos de lugar en fuentes actuales:
  - `detalle.descripcion_lugar_de_secuestro`
  - `detalle["Lugar de nacimiento"]`
  - texto de `Estudios`
- Embarazo con formatos heterogeneos:
  - `"Sí"`, `"8 Meses"`, `"2 A 3 Meses"`, `"2 meses y medio"`, `"embarazada"`, etc.

## 1) Modelo recomendado

## 1.1 Lugar
- `(:Lugar {lugar_key, nombre_canonico, tipo, pais_code})`
- `(:AliasLugar {alias_key, alias_norm, alias_raw, fuente, campo_fuente})`

Relaciones:
- `(:AliasLugar)-[:ALIAS_DE]->(:Lugar)`
- `(:Lugar)-[:PARTE_DE]->(:Lugar)`

Tipos sugeridos para `Lugar.tipo`:
- `PAIS`
- `PROVINCIA`
- `CIUDAD`
- `BARRIO`
- `SEDE` (institucion/sitio especifico)

## 1.2 Fecha
- `(:Fecha {fecha_iso})`
- `(:Anio {anio})`

Relaciones:
- `(:Evento)-[:EN_FECHA]->(:Fecha)`
- `(:Evento)-[:EN_ANIO]->(:Anio)`

Nota: si una fecha viene incompleta (solo anio), no inventar dia/mes; conectar solo a `:Anio`.

## 1.3 Estudio
- `(:Institucion {institucion_key, nombre_canonico, sigla})`
- `(:Carrera {carrera_key, nombre_canonico})`

Relaciones:
- `(:Persona)-[:CURSO {nivel, estado_raw, fuente}]->(:Carrera)`
- `(:Carrera)-[:DICTADA_EN]->(:Institucion)`
- `(:Institucion)-[:UBICADA_EN]->(:Lugar)`

## 1.4 Embarazo
- `(:CondicionEmbarazo {embarazo_key, estado, meses_min, meses_max, texto_raw, fuente})`

Relaciones:
- `(:Persona)-[:CURSABA_EMBARAZO]->(:CondicionEmbarazo)`
- Opcional (si aplica temporalmente): `(:Evento)-[:ASOCIADO_A_EMBARAZO]->(:CondicionEmbarazo)`

`estado` sugerido:
- `NO_INFO`, `SI`, `MESES`, `RANGO_MESES`, `OTRO`

## 2) Reglas de identidad para "mismo lugar"

## 2.1 Normalizacion base (obligatoria)
Aplicar antes de resolver identidad:
1. uppercase
2. quitar tildes
3. reemplazar puntuacion por espacios (`. , ; - /`)
4. colapsar espacios
5. normalizar abreviaturas:
   - `BS AS` -> `BUENOS AIRES`
   - `CAP FED` -> `CAPITAL FEDERAL`
6. remover prefijos de ruido (`SE DESCONOCE`, `NO HAY INFORMACION`) como null

## 2.2 Diccionario canonico (deterministico)
Resolver primero por tabla de equivalencias curada:
- `CAPITAL FEDERAL`, `CABA`, `CIUDAD DE BS AS`, `CIUDAD DE BUENOS AIRES` ->
  `Lugar(CIUDAD, CIUDAD AUTONOMA DE BUENOS AIRES)`
- `CORDOBA CAPITAL` -> `Lugar(CIUDAD, CORDOBA)` + `PARTE_DE` provincia Cordoba
- `SAN MIGUEL DE TUCUMAN` -> `Lugar(CIUDAD, SAN MIGUEL DE TUCUMAN)`

## 2.3 Regla parent-aware (evita falsos positivos)
Si no hay diccionario:
- dos lugares son el mismo solo si coinciden:
  - `nombre_norm`
  - `tipo`
  - `parent_key` (provincia/pais), cuando exista

Ejemplo:
- `SAN MARTIN` en Buenos Aires != `SAN MARTIN` en Mendoza

## 2.4 Regla de ambiguedad
Si falta parent y el nombre es comun (`SAN MARTIN`, `BELGRANO`, `CENTRO`):
- no merge automatico
- crear `:AliasLugar` y marcar para revision

## 2.5 Fuzzy matching (solo candidato)
Para casos no deterministas:
- generar candidatos con similitud textual (umbral alto, por ejemplo >= 0.93)
- nunca merge automatico con fuzzy
- guardar como sugerencia (`CANDIDATO_MERGE_LUGAR` o tabla externa)

## 3) Reglas de parseo de embarazo

Entrada `embarazada` -> salida canonica:
- vacio -> `NO_INFO`
- `SI`, `EMBARAZADA` -> `SI`
- `8 MESES` -> `MESES`, `meses_min=8`, `meses_max=8`
- `2 A 3 MESES`, `4 O 5 MESES`, `ENTRE 2 Y 4 MESES` -> `RANGO_MESES`, min/max
- `2 MESES Y MEDIO` -> `RANGO_MESES`, min=2, max=3

## 4) Estrategia de integracion incremental

1. Crear nodos `Lugar` y `AliasLugar` desde campos ya limpios (`lugar_nacimiento`, `lugar_secuestro`, `LISTADA_EN.estado_raw` no aplica a lugar).
2. Conectar `Evento` existentes con `:OCURRIO_EN -> :Lugar`.
3. Conectar `Institucion`/`Carrera` a partir de `Estudios` con parser conservador.
4. Mantener merges automaticos solo por reglas deterministicas (diccionario + parent-aware).
5. Todo lo ambiguo pasa a cola de revision.

## 5) Consultas clave que habilita

- Personas secuestradas en la misma ciudad/barrio.
- Casos conectados por misma institucion educativa.
- Eventos por anio y por lugar.
- Casos con embarazo al momento del secuestro (cuando se pueda asociar temporalmente).

## 6) Riesgos y mitigacion

- `BUENOS AIRES` ambiguo (ciudad/provincia):
  - mitigar con diccionario + tipo explicito.
- barrios homonimos:
  - exigir parent (`PARTE_DE`) para merge.
- errores OCR/scraping:
  - fuzzy solo como candidato, nunca merge automatico.

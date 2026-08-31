# ESPECIFICACIÓN FORMAL DE MODELO DE DATOS EN GRAFOS (NEO4J)
## Dominio: Reconstrucción Histórica, Memoria y Derechos Humanos
## Versión: 1.3 — Rigor de Producción para Agentes de IA

### Novedades V1.3 (auditoría semántica 2026-08-29, Fix A)
- Se declara `(:Persona)-[:IMPUTADO_POR]->(:Persona)` (§3.2): la sentencia
  imputa a esta persona un delito contra la otra, sin que ese delito sea
  necesariamente tormentos. Antes de este fix, todo par imputado-víctima de
  MinJus recibía `TORTURO_A` sin mirar el campo `delitos` de la fuente, que
  trae el listado exacto de cargos por par (22,5 % de los pares no tenían
  ningún cargo de tormentos — ver auditoría, hallazgo C1). `TORTURO_A` queda
  restringido a los pares donde `delitos` incluye la familia de tormentos.
  Ambos tipos de arista llevan `delitos [List[String]]` como propiedad, con
  el texto de la fuente preservado, para que la clasificación sea auditable.
- La resolución de topónimos (`domain/place_norm.py`) ya no fabrica una
  ciudad de Buenos Aires a partir de cualquier cadena corta sin resolver, ni
  reubica personas en la provincia equivocada cuando la fuente trae el
  patrón "LOCALIDAD. PROVINCIA" (hallazgos C3 y C4). Prefiere no resolver
  (evento huérfano, reportado por los contadores existentes) antes que
  inventar o desplazar un lugar. No agrega labels, nodos ni propiedades
  nuevas al modelo; se documenta acá porque cambia qué cuenta como un
  `:Lugar` real en los conteos existentes de `qa_report`.
- `:Nietx.ADN` deja de completarse con el literal `"SÍ"` cuando la fuente no
  trae fecha de confirmación genética (hallazgo C5): queda `"DESCONOCIDA"`,
  el mismo sentinel que ya usan `fecha_sentencia` y `TORTURO_A.fecha` para
  "la fuente no lo dice". Se agrega `estado [String] (Obligatorio)` a
  `:Nietx` -antes no se persistía- porque es el campo que distingue un
  nietx restituido de uno que sigue en búsqueda; sin él, `ADN: "DESCONOCIDA"`
  no permite saber si el motivo es "todavía no identificadx" o
  "identificadx pero sin fecha de ADN registrada en esta fuente". Ver §2 y
  §4 para el detalle.
- Fix E (mismos auditoría y bump): `PARIO_EN` deja de emitirse sobre
  registros de género masculino (hallazgo I1); `PRESENTE_EN`/`PARIO_EN` de
  `ccds_json` agregan `fecha_fin`/`precision_fecha` en vez de fabricar
  precisión de día (I2); `estudiante_universitario` pasa de una arista
  `ESTUDIO_EN` fabricada a un atributo booleano de `:Persona` (I4); valores
  sentinel de `Fuerza`/`lugar_de_trabajo`/`dónde_estudió` ("SIN
  ESPECIFICAR", "CIVIL", "NO DETERMINADO"...) dejan de generar
  `:Org`/`:Institución` falsos, y `Persona.fuerza` conserva el dato crudo
  (I3d); `:DirecciónCCD` declara `tipo_direccion` ("CCD" /
  "HECHO_NARRATIVO" / "CEMENTERIO"/"ENTERRAMIENTO"/"SITIO_HALLAZGO") para
  distinguir un centro clandestino real de un domicilio o un cementerio
  (I5); fechas de nacimiento/secuestro/asesinato fuera de un rango
  históricamente plausible (verificado contra los datos reales, ver
  `domain/date_norm.py`) se descartan a `"DESCONOCIDA"` en vez de
  persistirse, y se agrega `Persona.edad` para que las contradicciones
  entre edad y fecha sean auditables (I6); `CANDIDATO_MERGE` ya no se
  propone entre roles mutuamente excluyentes (víctima/nietx vs.
  represor/cómplice) sin ninguna fecha que lo respalde, y su propiedad
  `score` se renombra a `score_nombre` (I7); `fecha_sentencia` deja de
  filtrarse a las 2.710 aristas de parentesco que no tienen nada que ver
  con una sentencia judicial (M1). Ver `semantic-fixes-report.md` para el
  detalle completo, los conteos y lo que queda deliberadamente sin arreglar
  (I3a, I3b, I3c).

Este documento define la arquitectura exacta e inmutable del grafo en Neo4j. Cualquier proceso de extracción, estructuración o ingesta automática de datos ejecutado por un LLM debe adherirse estrictamente a las reglas, etiquetas, relaciones y propiedades declaradas a continuación. Está prohibido inventar o inferir entidades intermedias.

---

### 1. REGLAS CORE DE LA ARQUITECTURA

1.1 MULTI-LABELING PARA INDIVIDUOS: Toda entidad humana en el grafo se inicializa con el nodo base obligatorio `:Persona`. Los roles específicos no se guardan como propiedades, sino como labels semánticas adicionales agregadas al mismo nodo físico (ej. un nodo puede ser simultáneamente `:Persona:Victima:Nietx`).
1.2 AUDITORÍA OBLIGATORIA EN ARISTAS: Absolutamente TODAS las relaciones del grafo, sin excepción, deben contener estas dos propiedades específicas:
    - fecha: String (Valor puntual o rango temporal descriptivo).
    - origen: String (Fuente documental, testimonio o registro judicial que valida el vínculo).
1.3 DIRECCIONALIDAD RÍGIDA: Todas las relaciones poseen un sentido explícito que define la semántica operacional del grafo.
1.4 ROLES COMO LABELS DINÁMICAS: El cargador asigna las labels de rol a partir
del campo `roles` del CDM. Una fila sin `roles` recibe `["VICTIMA"]`.

---

### 2. DICCIONARIO DE NODOS (LABELS) Y PROPIEDADES

- :Persona (Nodo Base)
  * nombre [String] (Obligatorio)
  * genero [String] (Obligatorio)
  * fuente [String] (Obligatorio)
  * fecha_nacimiento [String ISO] (Opcional, V1.2) — validada (V1.3, Fix E,
    hallazgo I6): cualquier valor parseado posterior al 31/12/1983 se
    descarta en el builder (nunca llega a persistirse) en vez de afirmar un
    nacimiento imposible. No se corrige el dato -la fuente puede tener una
    errata real, como Massera, Emilio Eduardo (represor, fuente:
    "08/11/2010", probablemente confundido con su fecha de fallecimiento
    real; nació en 1925)- se descarta.
  * fecha_secuestro [String ISO] (Opcional, V1.2) — se persiste en el nodo cuando
    no hay lugar asociado que permita construir la arista :SECUESTRADO_EN.
    Validada (V1.3, Fix E, hallazgo I6): cualquier valor fuera de
    [1966, 1990] se descarta antes de persistirse (12 registros reales
    tenían fechas entre 1997 y 2077).
  * edad [String] (Opcional, V1.3, Fix E, hallazgo I6) — sólo la puebla
    `detalles_personas` (Parque de la Memoria, presente en sus 8.948
    registros). Se persiste tal como la da la fuente, sin validar contra
    ninguna fecha: existe específicamente para que una contradicción entre
    edad y fecha de nacimiento/secuestro (que antes de este fix era
    invisible porque `Edad` no se cargaba) sea auditable desde el grafo.
  * claves_alt [List[String]] (Opcional, V1.2) — claves de otras fuentes
    absorbidas por la reconciliación de identidades.
  * estudiante_universitario [Boolean] (Opcional, V1.3, Fix E, hallazgo I4) —
    sólo la puebla `archivo_memoria`. La fuente trae un booleano
    (`true` en 56 de 303 registros; ausente, no `false`, en el resto). Antes
    de este fix se materializaba como una arista `ESTUDIO_EN` hacia un nodo
    fijo `:Institución "UNIVERSIDAD SIN ESPECIFICAR"`, afirmando una
    institución que la fuente nunca nombra. Nunca se escribe `false`: la
    ausencia del campo no es evidencia de que la persona no haya sido
    estudiante universitaria.
  * fuerza [String] (Opcional, V1.3, Fix E, hallazgo I3d) — sólo la
    puebla `juicios_condenados`/`minjus_imputados` (`Fuerza`/`fuerza`).
    Se persiste el valor crudo tal como lo da la fuente, incluidos los
    sentinels ("SIN ESPECIFICAR", "CIVIL", "POLICIA (SIN ESPECIFICAR)",
    "NO ESPECIFICADO", "NO DETERMINADO", "DESCONOCIDO/A"): esos valores NO
    generan `:Org`/`PARTE_DE` (ver más abajo), así que este atributo es la
    única forma en que el dato ("no se sabe la fuerza" / "era civil") queda
    en el grafo.
- :Victima (Label de Rol secundario conectado a :Persona)
- :Represor (Label de Rol secundario conectado a :Persona)
- :Complice (Label de Rol secundario conectado a :Persona)
  * tipo [String] (Obligatorio, restringido estrictamente a: "CIVIL", "CLERICAL", "EMPRESARIAL")
- :Nietx (Label de Rol secundario conectado a :Persona)
  * caso [String] (Obligatorio) — el identificador de expediente/caso (p.ej.
    apellidos de ambos progenitores separados por guión, "Metz - Romero"),
    NO necesariamente el nombre de una persona. El builder deriva `nombre` y
    `caso` del mismo campo fuente (`nombre_completo`), así que `nombre ==
    caso` para los 392 nodos `:Nietx` sin excepción (verificado en vivo,
    2026-08-30) — la corrección importante no es esa igualdad sino que, de
    esos 392, **235** tienen el patrón "Apellido1 - Apellido2" propio de un
    identificador de expediente en vez del nombre real de una persona (213 de
    los 252 "Búsqueda", los 19 "No nacidx", y 3 de los 117 "Restituido/a";
    verificado en vivo por patrón `CONTAINS ' - '` sobre `Nietx.nombre`,
    V1.3, hallazgo C5), porque la fuente en sí no tiene otro nombre que dar
    -no es una omisión del cargador, es lo único que provee Abuelas de Plaza
    de Mayo para esos expedientes. No se debe inferir ni inventar un nombre
    de persona para esos casos.
  * ADN [String] (Obligatorio) — la fecha de confirmación genética cuando la
    fuente la trae; `"DESCONOCIDA"` en caso contrario (V1.3, Fix D, hallazgo
    C5). Antes de este fix se completaba con el literal `"SÍ"`, afirmando
    una identificación de ADN falsa para 310 de 392 nietxs (los que la
    fuente marca como en búsqueda, no nacidxs, asesinadxs, o restituidxs sin
    fecha de ADN registrada). NUNCA inferir `"SÍ"` de la ausencia de dato.
  * estado [String] (Obligatorio, V1.3, Fix D) — tal como lo da la fuente,
    sin normalizar a un vocabulario nuevo. Valores observados en la fuente
    actual (`nietos_y_nietas.json`, 392 registros): `"Búsqueda"` (252),
    `"Restituido/a"` (117, de los cuales 82 con fecha de ADN real y 35 sin
    ella), `"No nacidx"` (19), `"Asesinadx"` (4). Es el campo que distingue
    estos casos entre sí -sin él, `ADN: "DESCONOCIDA"` no alcanza para saber
    por qué.
- :EntidadContexto (Label técnica compartida por los cinco tipos de contexto
  de abajo; sostiene el índice único de `entidad_key`, la clave con la que
  todo upsert de contexto hace MERGE. No se usa sola: siempre coexiste con
  una de las labels semánticas siguientes en el mismo nodo físico, igual que
  `:Persona` coexiste con sus labels de rol.)
  * entidad_key [String] (Obligatorio, único)
- :AliasPersona (+ :EntidadContexto) -> alias [String], fuente [String]
- :Profesión (+ :EntidadContexto) -> descripcion [String], fuente [String]
  (V1.2: el upsert existe pero ningún builder emite esta entidad todavía.)
- :Cargo (+ :EntidadContexto) -> titulo [String], fuente [String]
  (V1.2: el upsert existe pero ningún builder emite esta entidad todavía.)
- :Org (+ :EntidadContexto) -> nombre [String], tipoOrg [String], fuente [String]
- :Institución (+ :EntidadContexto) -> nombre [String], fuente [String]
- :DirecciónCCD (Punto geográfico preciso) -> coordenadas [String], direccionExacta [String]
  * tipo_direccion [String] (Obligatorio, V1.3, Fix E, hallazgo I5) —
    `"CCD"` (centro clandestino real; 123 de 391 nodos, medido en vivo contra
    `bolt://localhost:17687` el 2026-08-30) | `"CEMENTERIO"` /
    `"ENTERRAMIENTO"` / `"SITIO_HALLAZGO"` (fuente EAAF; 82 de 391: 76
    CEMENTERIO + 6 ENTERRAMIENTO + 0 SITIO_HALLAZGO en la carga actual) |
    `"HECHO_NARRATIVO"` (domicilio, vía pública o lugar de trabajo extraído
    del texto libre de secuestro/nacimiento/asesinato de una víctima; 186 de
    391 — dos menos que la estimación pre-Fix-C de `semantic-fixes-report.md`,
    consistente con que el resolver de lugares (Fix C) ahora rechaza dos
    cadenas que antes alcanzaban a producir una dirección narrativa). La
    label no distinguía estos tres casos: un domicilio o un
    cementerio llevaban la misma label `:DirecciónCCD` que un centro
    clandestino real, sin ninguna marca. No se renombró la label -afecta la
    constraint única y toda consulta existente sobre `:DirecciónCCD`, un
    cambio estructural mayor- pero ahora `tipo_direccion` distingue los tres
    honestamente.
- :Lugar (Entidad geopolítica abstracta anidada) -> nombre [String], tipoGeopolitico [String]
- :AliasLugar -> nombreAlternativo [String]

---

### 3. CATÁLOGO TAXONÓMICO DE RELACIONES (CON DIRECCIÓN)

#### 3.1 Persona -> Entidades de Contexto
- (:Persona)-[:EJERCIO]->(:Profesión)
- (:Persona)-[:EJERCIO]->(:Cargo)
- (:Persona)-[:PARTE_DE]->(:Org)   // Relación de pertenencia o militancia activa. NUNCA se emite cuando `Fuerza` es un sentinel (V1.3, Fix E, hallazgo I3d): "SIN ESPECIFICAR"/"CIVIL"/"POLICIA (SIN ESPECIFICAR)"/"NO ESPECIFICADO"/"NO DETERMINADO"/"DESCONOCIDO(A)" no son organizaciones, son la ausencia del dato -materializarlos agrupaba falsamente a cientos de represores bajo una membresía compartida inexistente (109 casos reales de "SIN ESPECIFICAR", 87 de "CIVIL"). El valor crudo se persiste en `Persona.fuerza` en su lugar.
- (:Persona)-[:FUNDO]->(:Org)      // Acto explícito de fundación (verbo fundar).
- (:Persona)-[:ESTUDIO_EN]->(:Institución)  // NUNCA se emite cuando el valor de la fuente es un sentinel puro ("NO DETERMINADO"/"NO ESPECIFICADO"/"NO ESPECIFICA"/"DESCONOCIDO(A)", V1.3, Fix E, hallazgo I3d).
- (:Persona)-[:TRABAJO_EN]->(:Institución)  // Misma regla que ESTUDIO_EN.
- (:AliasPersona)-[:IDENTIFICA_A]->(:Persona) // El alias apunta a la entidad real de la persona.

#### 3.2 Relaciones Interpersonales (Persona -> Persona)
*Todas asumen la misma dirección operativa (Origen -> Destino) en el almacenamiento físico.*
- (:Persona)-[:HIJE_DE]->(:Persona)
- (:Persona)-[:PADRE_DE]->(:Persona)
- (:Persona)-[:MADRE_DE]->(:Persona)
- (:Persona)-[:NIETX_DE]->(:Persona)
- (:Persona)-[:ABUELX_DE]->(:Persona)
- (:Persona)-[:HERMANX_DE]->(:Persona)
- (:Persona)-[:PAREJA_DE]->(:Persona)
- (:Persona)-[:CUÑADX_DE]->(:Persona)
- (:Persona)-[:SUEGRX_DE]->(:Persona)
- (:Persona)-[:YERNX_NUERX_DE]->(:Persona)
- (:Persona)-[:TORTURO_A]->(:Persona) // Semántica restrictiva: (:Represor)-[:TORTURO_A]->(:Victima). Emitida SOLO cuando `delitos` (ver abajo) incluye la familia de tormentos ("Tormentos" / "Tormentos seguidos de muerte") para ese par específico (V1.3, Fix A/C1).
  * fecha [String] — la fuente MinJus no registra cuándo ocurrió la tortura
    (el hecho); queda en "DESCONOCIDA" en vez de asumir la fecha del fallo
    judicial (V1.2, Fix 9: inferirla sería inventar el hecho central que este
    dataset existe para preservar).
  * fecha_sentencia [String] (Opcional, V1.2) — fecha en que el tribunal dictó
    la sentencia que documenta el hecho. Es procedencia, no el hecho (regla
    1.2: `fecha` describe la relación, `origen` identifica la fuente que la
    valida); se conserva como propiedad propia en vez de perderse.
  * delitos [List[String]] (V1.3) — el listado completo de cargos que la
    sentencia imputa a esta persona respecto de esta víctima en particular,
    tal como los nombra la fuente (incluye "Tormentos" y puede incluir otros:
    Homicidio, Privación Ilegítima de la libertad, etc.).
- (:Persona)-[:IMPUTADO_POR]->(:Persona) // V1.3, Fix A/C1. Misma dirección y misma fuente (MinJus GBA) que TORTURO_A: la sentencia imputa a esta persona un delito contra la otra, SIN que la familia de tormentos esté entre los cargos de ese par (p.ej. sólo Sustracción de menor, o sólo Homicidio). Se emite exactamente cuando TORTURO_A no aplica, nunca junto con TORTURO_A para el mismo par.
  * fecha [String] — igual semántica que en TORTURO_A: "DESCONOCIDA", la fuente no registra la fecha del hecho.
  * fecha_sentencia [String] (Opcional) — igual semántica que en TORTURO_A.
  * delitos [List[String]] — igual semántica que en TORTURO_A; nunca contiene un cargo de la familia de tormentos (si lo contuviera, el par habría recibido TORTURO_A en su lugar).
- (:Persona)-[:VIO_A]->(:Persona)     // Verbo VER. Avistamiento o constatación visual de la presencia del destino por el origen.
- (:Persona)-[:MILITO_CON]->(:Persona)// Relación de co-militancia orientada desde la perspectiva del registro.

#### 3.3 Persona -> Espacio Geopolítico
- (:Persona)-[:NACIO_EN]->(:Lugar) // `fecha` validada (V1.3, Fix E, hallazgo I6): un valor posterior al 31/12/1983 se descarta a "DESCONOCIDA" en vez de afirmar un nacimiento imposible (7 registros reales tenían fechas entre 2021 y 2052).
- (:Persona)-[:SECUESTRADO_EN]->(:Lugar) // `fecha` validada (V1.3, Fix E, hallazgo I6): un valor fuera de [1966, 1990] se descarta a "DESCONOCIDA".
- (:Persona)-[:ASESINADO_EN]->(:Lugar) // `fecha` validada (V1.3, Fix E, hallazgo I6): mismo rango que SECUESTRADO_EN.
- (:Persona)-[:PRESENTE_EN]->(:Lugar) // `fecha` proveniente de `fecha_secuestro` (minjus_victimas) validada (V1.3, Fix E, hallazgo I6): un valor fuera de [1966, 1990] se descarta a "DESCONOCIDA" antes de propagarse a esta arista.
  * fecha_fin [String ISO] (Opcional, V1.3, Fix E, hallazgo I2) — sólo la
    puebla `ccds_json` (`builders/ccds.py`). La fuente trae la fecha de CCD
    en formato `AAAA/MM` (245 de 278 valores) o `AAAA` (23 de 278); sólo 10
    son `AAAA/MM/DD`. Antes de este fix, `fecha` se completaba con el primer
    día del mes/año (`"1977/06"` -> `"1977-06-01"`), fabricando una
    precisión que la fuente no tiene, y cuando la fuente traía más de un
    valor (`["1978/01","1978/02"]`) se descartaba el segundo mes por
    completo. Ahora `fecha` sigue siendo el inicio más temprano (para no
    romper el formato ISO que ya consumía el resto del grafo), pero
    `fecha_fin` conserva el fin más tardío de TODOS los valores de la fuente
    (para ese ejemplo: `fecha:"1978-01-01"`, `fecha_fin:"1978-02-28"`), y
    `precision_fecha` declara la granularidad real.
  * precision_fecha [String] (Opcional, V1.3, Fix E, hallazgo I2) —
    `"DAY"` | `"MONTH"` | `"YEAR"`, la granularidad real del valor que dio
    `fecha`. Sólo poblada por `ccds_json`.
- (:Persona)-[:PARIO_EN]->(:Lugar) // Restrictiva: sólo se emite cuando `Persona.genero <> "MASCULINO"` (V1.3, Fix E, hallazgo I1). La fuente (`ccds_json`, relación `pario_en`) la usaba de forma laxa para "el parto de su hije ocurrió aquí" y la aplicaba por igual al padre; un registro masculino con esa relación se emite como PRESENTE_EN.
  * fecha_fin [String ISO] / precision_fecha [String] (Opcional, V1.3, Fix E,
    hallazgo I2) — misma semántica que en `PRESENTE_EN` arriba.
- (:Persona)-[:MURIO_EN]->(:Lugar)
- (:Persona)-[:LIBERADO_EN]->(:Lugar)

#### 3.4 Estructura Organizacional, Infraestructura y Topología
- (:Cargo)-[:PERTENECE_A]->(:Org)
- (:Institución)-[:FORMA_PARTE_DE]->(:Org)
- (:Institución)-[:UBICADA_EN]->(:Lugar)
- (:DirecciónCCD)-[:UBICADA_EN]->(:Lugar) // Punto geográfico específico contenido dentro de un contenedor geopolítico mayor.
- (:AliasLugar)-[:ALIAS_DE]->(:Lugar)
- (:Lugar)-[:PARTE_DE]->(:Lugar)       // RELACIÓN RECURSIVA CRÍTICA. Modela la jerarquía anidada. Va del contenedor menor al contenedor de orden político superior (Ej: Localidad -> Partido -> Provincia).

#### 3.5 Candidatos de reconciliación de identidad (V1.3, Fix E, hallazgo I7)
- (:Persona)-[:CANDIDATO_MERGE]->(:Persona) // NO es una fusión: es una SUGERENCIA para revisión humana entre dos nodos :Persona que podrían ser la misma persona y que la reconciliación automática (identity_resolution.py) no fusionó -o porque no hay fecha que lo confirme, o porque los roles son mutuamente excluyentes. La dirección del par es arbitraria (orden alfabético de las claves), no semántica.
  * fecha [String] — siempre `"PROBABILÍSTICA"` (no es un hecho fechado).
  * origen [String] — siempre `"name_similarity"`.
  * metodo [String] — cómo se generó el candidato: `"nombre_exacto_sin_fecha"` (mismo nombre exacto, ninguna fecha compartida confirma ni contradice), `"nombre_exacto_fecha_contradictoria"` (mismo nombre, fechas que se contradicen), `"nombre_exacto_clique_incompleto"` (fecha confirma pero un tercer registro rompe el clique), `"nombre_exacto_roles_incompatibles"` (fecha confirma pero los roles son víctima/nietx vs. represor/cómplice — el bloqueo de merge más fuerte, pero con evidencia real detrás), `"set_dice_typo_v1"` (similitud de cadena entre nombres distintos, sin coincidencia exacta), `"slug_exacto"` (V3, reconciliación asistida contra placeholders sin resolver).
  * score_nombre [Float] — similitud de cadena entre los nombres normalizados (0 a 1). **No es una confianza de identidad**: dos nombres distintos con errata típica pueden dar `score_nombre` 1.0 con `confianza` "baja" (antes de V1.3 esta propiedad se llamaba `score`, invitando a leerla como certeza).
  * confianza [String] — `"alta"` | `"media"` | `"baja"`, la lectura que sí hay que usar para priorizar revisión.
  * slug [String] — el nombre normalizado que originó el candidato.
  * fuente [String] — `"reconciliacion_cross_fuente"` (Paso 1/2 de `identity_resolution.py`) o `"v3_reconciliacion_asistida"` (`builders/candidatos.py`).

  **Nunca se propone un candidato entre roles mutuamente excluyentes
  (víctima/nietx vs. represor/cómplice) si no hay ninguna fecha que lo
  respalde** (hallazgo I7): proponer que una víctima y un represor son la
  misma persona, sin ninguna evidencia más que una coincidencia o similitud
  de nombre, es la peor hipótesis de este dominio con la menor evidencia
  posible. Cuando SÍ hay una fecha que confirma la coincidencia, el
  candidato se sigue proponiendo (con `metodo:
  "nombre_exacto_roles_incompatibles"`, `confianza: "alta"`) para que un
  humano lo revise -ahí hay evidencia real detrás, aunque el merge nunca se
  ejecute automáticamente.

---

### 4. DDL DE INTEGRIDAD (NEO4J CYPHER)

Ejecutar obligatoriamente al inicializar la base de datos para garantizar la consistencia de tipos:

```cypher
// Restricciones técnicas de unicidad (verificado contra db/cypher.py::CONSTRAINTS,
// ausentes de esta sección en versiones previas del documento — discrepancia
// encontrada y corregida en el pase de documentación del 2026-08-30, no
// relacionada con la auditoría semántica de V1.3).
CREATE CONSTRAINT persona_key_unique IF NOT EXISTS FOR (p:Persona) REQUIRE p.persona_key IS UNIQUE;
CREATE CONSTRAINT lugar_key_unique IF NOT EXISTS FOR (l:Lugar) REQUIRE l.lugar_key IS UNIQUE;
CREATE CONSTRAINT alias_lugar_key_unique IF NOT EXISTS FOR (a:AliasLugar) REQUIRE a.alias_key IS UNIQUE;
CREATE CONSTRAINT direccion_ccd_key_unique IF NOT EXISTS FOR (d:DirecciónCCD) REQUIRE d.direccion_ccd_key IS UNIQUE;

// Restricciones de Existencia Base
CREATE CONSTRAINT persona_nombre_exist IF NOT EXISTS FOR (p:Persona) REQUIRE p.nombre IS NOT NULL;
CREATE CONSTRAINT persona_genero_exist IF NOT EXISTS FOR (p:Persona) REQUIRE p.genero IS NOT NULL;
CREATE CONSTRAINT persona_fuente_exist IF NOT EXISTS FOR (p:Persona) REQUIRE p.fuente IS NOT NULL;

// Restricciones de Existencia para el Rol Nietx
CREATE CONSTRAINT nietx_caso_exist IF NOT EXISTS FOR (n:Nietx) REQUIRE n.caso IS NOT NULL;
CREATE CONSTRAINT nietx_adn_exist IF NOT EXISTS FOR (n:Nietx) REQUIRE n.ADN IS NOT NULL;
CREATE CONSTRAINT nietx_estado_exist IF NOT EXISTS FOR (n:Nietx) REQUIRE n.estado IS NOT NULL; // V1.3, Fix D

// Restricciones de Existencia para el Rol Cómplice
CREATE CONSTRAINT complice_tipo_exist IF NOT EXISTS FOR (c:Complice) REQUIRE c.tipo IS NOT NULL;

// Restricción técnica única para las entidades de contexto (V1.2): todo
// upsert de :Org, :Institución, :Profesión, :Cargo y :AliasPersona hace
// MERGE sobre la label técnica compartida :EntidadContexto, no sobre su
// label semántica.
CREATE CONSTRAINT entidad_contexto_key_unique IF NOT EXISTS FOR (e:EntidadContexto) REQUIRE e.entidad_key IS UNIQUE;
```
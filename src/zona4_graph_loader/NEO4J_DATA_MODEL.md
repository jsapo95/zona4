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
  * fecha_nacimiento [String ISO] (Opcional, V1.2)
  * fecha_secuestro [String ISO] (Opcional, V1.2) — se persiste en el nodo cuando
    no hay lugar asociado que permita construir la arista :SECUESTRADO_EN.
  * claves_alt [List[String]] (Opcional, V1.2) — claves de otras fuentes
    absorbidas por la reconciliación de identidades.
- :Victima (Label de Rol secundario conectado a :Persona)
- :Represor (Label de Rol secundario conectado a :Persona)
- :Complice (Label de Rol secundario conectado a :Persona)
  * tipo [String] (Obligatorio, restringido estrictamente a: "CIVIL", "CLERICAL", "EMPRESARIAL")
- :Nietx (Label de Rol secundario conectado a :Persona)
  * caso [String] (Obligatorio) — el identificador de expediente/caso (p.ej.
    apellidos de ambos progenitores separados por guión, "Metz - Romero"),
    NO necesariamente el nombre de una persona. Cuando la fuente no da un
    nombre propio restituido, `nombre` también queda igual a `caso` (235 de
    392 casos, V1.3, hallazgo C5) porque la fuente en sí no tiene otro
    nombre que dar -no es una omisión del cargador, es lo único que provee
    Abuelas de Plaza de Mayo para esos expedientes. No se debe inferir ni
    inventar un nombre de persona para esos casos.
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
- :DirecciónCCD (Punto geográfico preciso / Centro Clandestino de Detención) -> coordenadas [String], direccionExacta [String]
- :Lugar (Entidad geopolítica abstracta anidada) -> nombre [String], tipoGeopolitico [String]
- :AliasLugar -> nombreAlternativo [String]

---

### 3. CATÁLOGO TAXONÓMICO DE RELACIONES (CON DIRECCIÓN)

#### 3.1 Persona -> Entidades de Contexto
- (:Persona)-[:EJERCIO]->(:Profesión)
- (:Persona)-[:EJERCIO]->(:Cargo)
- (:Persona)-[:PARTE_DE]->(:Org)   // Relación de pertenencia o militancia activa.
- (:Persona)-[:FUNDO]->(:Org)      // Acto explícito de fundación (verbo fundar).
- (:Persona)-[:ESTUDIO_EN]->(:Institución)
- (:Persona)-[:TRABAJO_EN]->(:Institución)
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
- (:Persona)-[:NACIO_EN]->(:Lugar)
- (:Persona)-[:SECUESTRADO_EN]->(:Lugar)
- (:Persona)-[:ASESINADO_EN]->(:Lugar)
- (:Persona)-[:PRESENTE_EN]->(:Lugar)
- (:Persona)-[:PARIO_EN]->(:Lugar)
- (:Persona)-[:MURIO_EN]->(:Lugar)
- (:Persona)-[:LIBERADO_EN]->(:Lugar)

#### 3.4 Estructura Organizacional, Infraestructura y Topología
- (:Cargo)-[:PERTENECE_A]->(:Org)
- (:Institución)-[:FORMA_PARTE_DE]->(:Org)
- (:Institución)-[:UBICADA_EN]->(:Lugar)
- (:DirecciónCCD)-[:UBICADA_EN]->(:Lugar) // Punto geográfico específico contenido dentro de un contenedor geopolítico mayor.
- (:AliasLugar)-[:ALIAS_DE]->(:Lugar)
- (:Lugar)-[:PARTE_DE]->(:Lugar)       // RELACIÓN RECURSIVA CRÍTICA. Modela la jerarquía anidada. Va del contenedor menor al contenedor de orden político superior (Ej: Localidad -> Partido -> Provincia).

---

### 4. DDL DE INTEGRIDAD (NEO4J CYPHER)

Ejecutar obligatoriamente al inicializar la base de datos para garantizar la consistencia de tipos:

```cypher
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
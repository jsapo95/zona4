# ESPECIFICACIÓN FORMAL DE MODELO DE DATOS EN GRAFOS (NEO4J)
## Dominio: Reconstrucción Histórica, Memoria y Derechos Humanos
## Versión: 1.1 — Rigor de Producción para Agentes de IA

Este documento define la arquitectura exacta e inmutable del grafo en Neo4j. Cualquier proceso de extracción, estructuración o ingesta automática de datos ejecutado por un LLM debe adherirse estrictamente a las reglas, etiquetas, relaciones y propiedades declaradas a continuación. Está prohibido inventar o inferir entidades intermedias.

---

### 1. REGLAS CORE DE LA ARQUITECTURA

1.1 MULTI-LABELING PARA INDIVIDUOS: Toda entidad humana en el grafo se inicializa con el nodo base obligatorio `:Persona`. Los roles específicos no se guardan como propiedades, sino como labels semánticas adicionales agregadas al mismo nodo físico (ej. un nodo puede ser simultáneamente `:Persona:Victima:Nietx`).
1.2 AUDITORÍA OBLIGATORIA EN ARISTAS: Absolutamente TODAS las relaciones del grafo, sin excepción, deben contener estas dos propiedades específicas:
    - fecha: String (Valor puntual o rango temporal descriptivo).
    - origen: String (Fuente documental, testimonio o registro judicial que valida el vínculo).
1.3 DIRECCIONALIDAD RÍGIDA: Todas las relaciones poseen un sentido explícito que define la semántica operacional del grafo.

---

### 2. DICCIONARIO DE NODOS (LABELS) Y PROPIEDADES

- :Persona (Nodo Base)
  * nombre [String] (Obligatorio)
  * genero [String] (Obligatorio)
  * fuente [String] (Obligatorio)
- :Victima (Label de Rol secundario conectado a :Persona)
- :Represor (Label de Rol secundario conectado a :Persona)
- :Complice (Label de Rol secundario conectado a :Persona)
  * tipo [String] (Obligatorio, restringido estrictamente a: "CIVIL", "CLERICAL", "EMPRESARIAL")
- :Nietx (Label de Rol secundario conectado a :Persona)
  * caso [String] (Obligatorio)
  * ADN [String] (Obligatorio)
- :AliasPersona -> alias [String]
- :Profesión -> descripcion [String]
- :Cargo -> titulo [String]
- :Org -> nombre [String], tipoOrg [String]
- :Institución -> nombre [String]
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
- (:Persona)-[:TORTURO_A]->(:Persona) // Semántica restrictiva: (:Represor)-[:TORTURO_A]->(:Victima)
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

// Restricciones de Existencia para el Rol Cómplice
CREATE CONSTRAINT complice_tipo_exist IF NOT EXISTS FOR (c:Complice) REQUIRE c.tipo IS NOT NULL;
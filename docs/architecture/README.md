# Arquitectura del Repositorio ZONA4

Este documento describe la estructura y el flujo de datos del proyecto **ZONA4** de forma simple y visual, ayudando a desarrolladores y analistas a entender cómo interactúan los distintos componentes de software.

---

## 1. Los Dos Pilares de la Arquitectura

Para evitar dependencias de red inestables durante la carga y garantizar la reproducibilidad offline, el repositorio se divide en dos subsistemas desacoplados:

```
                  ONLINE (Scraping/APIs)                    OFFLINE (Carga local)
             ┌──────────────────────────────┐          ┌─────────────────────────────┐
             │                              │          │                             │
             │     1. Extractor de Datos    ├─────────►│    2. Cargador del Grafo    │
             │     (src/zona4_extractor/)   │  JSONs   │  (src/zona4_graph_loader/)  │
             │                              │          │                             │
             └──────────────────────────────┘          └─────────────────────────────┘
```

1.  **Extractor de Datos (`src/zona4_extractor/`)**: Corre procesos de scraping (e.g. Abuelas) y descargas externas para generar datasets locales limpios y pre-procesados.
2.  **Cargador del Grafo (`src/zona4_graph_loader/`)**: Lee los datasets locales e inyecta la información en la base de datos de grafos de Neo4j. Funciona de manera 100% offline y determinista.

---

## 2. Flujo de Datos del Cargador (Pipeline)

El cargador está estructurado en base a un **Modelo de Datos Canónico (CDM) Simplificado** en memoria, lo que permite acoplar fuentes con lógicas muy distintas de forma homogénea.

### Diagrama del Pipeline de Carga
```mermaid
flowchart TD
    subgraph Directorio de Fuentes (data/sources/)
        F1[(ccds.json)]
        F2[(nietos_y_nietas.json)]
        F3[(parque_de_la_memoria.json)]
        F4[(fuentes_directas.json)]
    end

    subgraph Capa de Adaptadores (Builders)
        B1[ccds.py]
        B2[relaciones.py / personas.py]
        B3[lugares.py / personas.py]
        B4[sources_ingestor.py]
    end

    subgraph Servicios Comunes (src/zona4_graph_loader/domain/)
        N1[date_norm.py]
        N2[place_norm.py]
        N3[name_similarity.py]
    end

    subgraph Contenedor Unificado (CanonicalDataset)
        CDM_Obj{{"Modelo Canónico (5 llaves)\n- personas\n- lugares\n- relaciones_interpersonales\n- eventos_espaciales\n- jerarquias"}}
    end

    subgraph Orquestador y Base de Datos
        ORQ[load_graph.py]
        CYP[cypher.py]
        DB[(Neo4j local)]
    end

    F1 --> B1
    F2 --> B2
    F3 --> B3
    F4 --> B4

    B1 & B3 -.-> N2
    B2 -.-> N1

    B1 & B2 & B3 & B4 --> CDM_Obj
    CDM_Obj --> ORQ
    ORQ --> CYP
    CYP --> DB
```

---

## 3. Componentes Clave del Loader

El código del loader (`src/zona4_graph_loader/`) se divide en las siguientes capas de responsabilidad única:

*   **Orquestador ([load_graph.py](file:///Users/a4649783/Documents/UNSAM/zona4/src/zona4_graph_loader/pipeline/load_graph.py))**: Es el punto de entrada del pipeline. Inicializa el cargador, ejecuta secuencialmente los adaptadores (builders) y las fuentes en disco, consolida el dataset y gestiona la escritura en Neo4j por lotes.
*   **Adaptadores (Builders)**: Clases y funciones en `src/zona4_graph_loader/builders/` que leen una fuente de datos particular y traducen sus campos al formato del CDM.
*   **Ingestor Directo ([sources_ingestor.py](file:///Users/a4649783/Documents/UNSAM/zona4/src/zona4_graph_loader/io/sources_ingestor.py))**: Lee y valida archivos JSON que ya cumplen con el formato del CDM de forma nativa sin requerir código de transformación en Python.
*   **Servicios de Dominio (`src/zona4_graph_loader/domain/`)**: Contiene algoritmos puros de normalización espacial (Georef en `place_norm.py`), parseo de fechas en español (`date_norm.py`) y emparejamiento fuzzy de nombres de candidatos a fusionar (`name_similarity.py`).
*   **Escritura DB ([cypher.py](file:///Users/a4649783/Documents/UNSAM/zona4/src/zona4_graph_loader/db/cypher.py))**: Define las restricciones, índices y consultas Cypher parametrizadas para Neo4j.

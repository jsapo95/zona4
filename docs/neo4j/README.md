# Neo4j: carga del grafo y potencial analitico

Este directorio documenta el modelo grafo de ZONA4 y provee consultas Cypher para validacion y analitica.

## Objetivo

El pipeline unifica fuentes heterogeneas de personas, eventos, lugares, CCDs y casos de nietxs en un grafo consultable. El foco es:

- trazabilidad de hechos por persona y evento
- normalizacion geografica jerarquica
- integracion de CCDs dentro de la misma taxonomia de lugar
- preservacion de direcciones especificas sin contaminar la capa de toponimos

## Flujo general de carga

El pipeline principal esta en src/zona4_graph_loader/pipeline/load_graph.py.

1. Lee fuentes JSON (detalles_personas, nietxs, ccds y listado_paginas).
2. Construye entidades y relaciones por capas (builders).
3. Normaliza lugares con reglas + georef + fallbacks contextuales.
4. Integra CCDs como Lugar tipo CCD y los ancla jerarquicamente a Lugar geografico cuando es posible.
5. Extrae Direccion cuando el texto corresponde a direccion especifica.
6. Escribe nodos/relaciones en Neo4j por lotes.
7. Ejecuta QA final de cobertura y consistencia.

## Comando tipico de carga limpia

Ejemplo local:

```bash
PYTHONPATH=src \
NEO4J_URI=bolt://localhost:7687 \
NEO4J_USER=neo4j \
NEO4J_PASSWORD=zona4local \
NEO4J_DATABASE=neo4j \
.venv/bin/python -m zona4_graph_loader.cli --clean-project
```

Notas:

- --clean-project limpia nodos del proyecto y recarga.
- --clean-all limpia toda la base.
- El pipeline crea constraints e indices si no existen.

## Esquema conceptual resumido

### Nodos principales

- Persona
- Evento
- Lugar
- Direccion
- AliasLugar
- CasoNietx
- PaginaListado

### Relaciones principales

- (Persona)-[:PARTICIPO_EN]->(Evento)
- (Evento)-[:OCURRIO_EN]->(Lugar)
- (Evento)-[:OCURRIO_EN_DIRECCION]->(Direccion)
- (Direccion)-[:UBICADA_EN]->(Lugar)
- (AliasLugar)-[:ALIAS_DE]->(Lugar)
- (Lugar)-[:PARTE_DE]->(Lugar)
- (CasoNietx)-[:REGISTRA_EVENTO]->(Evento)

## Lugares, jerarquia y CCDs

La normalizacion de lugares combina:

- limpieza textual y reglas de dominio
- resolver georef con scoring y control de ambiguedad
- equivalencias (por ejemplo CABA/CAPITAL FEDERAL)
- fallback provincia por defecto (controlado) para casos sin pista provincial
- segmentacion "localidad + contexto administrativo" para mejorar desambiguacion

Los CCDs se cargan como Lugar.tipo = CCD y se conectan por PARTE_DE al lugar geografico cuando hay evidencia (coordenadas o texto de ubicacion/denominacion). Esto permite analizar eventos CCD en la misma taxonomia territorial.

## Direcciones especificas

La capa Direccion captura domicilios/esquinas/calles detectadas en texto narrativo.

- Evita perder granularidad operativa.
- Se deduplica de forma estricta por (direccion_norm, lugar_key).
- No reemplaza al Lugar: lo complementa.

## Consultas incluidas

- queries_analitica_avanzada.cypher
  - hotspots, series temporales, trayectorias, cobertura de direcciones, actividad CCD
- queries_validacion.cypher
  - chequeos de consistencia, colisiones de alias, orfandad de direccion, cobertura de anclaje CCD
- constraints_lugares_fechas.cypher
  - utilidades de constraints/indices complementarias

## Potencial de analisis

Con el modelo actual se puede:

- mapear concentracion de eventos por jerarquia territorial
- analizar secuencias temporales de eventos por persona
- distinguir lugar general y direccion puntual de un mismo hecho
- estudiar actividad y relaciones de CCDs dentro del territorio
- auditar calidad de normalizacion y cobertura de datos

## Buenas practicas de uso

- Ejecutar primero queries_validacion.cypher despues de cada recarga.
- Revisar aliases de bajo soporte (frecuencia 1) para mejora incremental de reglas.
- Mantener trazabilidad: no borrar alias_raw ni descripcion_raw.
- Cuando se agreguen reglas nuevas de normalizacion, volver a correr carga limpia y comparar metricas antes/despues.

# Ingesta extensible para nuevas fuentes

Este documento define como mantener el proyecto ordenado y como sumar nuevas fuentes sin tocar el pipeline principal.

## Objetivos de arquitectura

- Orden: separar extraccion, normalizacion y carga.
- Trazabilidad: cada fila debe indicar fuente y llave estable.
- Extensibilidad: agregar una nueva fuente via paquete JSON canonico.
- Seguridad operativa: validar y cargar en batch sin romper el resto.

## Estructura recomendada

- `data/`: datos de entrada base.
- `data/extensions/`: paquetes opcionales de fuentes nuevas.
- `scripts/`: scripts de descarga y preprocesamiento.
- `src/zona4_graph_loader/builders/`: mapeos desde fuentes base a filas canonicas.
- `src/zona4_graph_loader/pipeline/load_graph.py`: orquestacion y escritura.

## Nuevo mecanismo de extension

El loader ahora acepta paquetes JSON en `data/extensions/*.json`.
Cada paquete puede aportar filas canonicas para las colecciones intermedias del pipeline.

Campos permitidos:

- `personas_detalles`
- `casos_nietx`
- `protagonistas`
- `rel_familiares`
- `rel_personas`
- `rel_simult`
- `eventos`
- `paginas_listado`
- `links_listado`
- `lugares`
- `aliases`
- `direcciones`
- `parents`
- `persona_links`
- `evento_links`
- `evento_direccion_links`

Campos opcionales de metadata por archivo:

- `source_id`
- `description`
- `version`

Ver plantilla: `data/extensions/_template_extension.json`.

## Flujo recomendado para sumar una fuente nueva

1. Crear script de extraccion en `scripts/` (si aplica).
2. Transformar la fuente al contrato canonico del paquete de extension.
3. Guardar el JSON en `data/extensions/`.
4. Ejecutar carga:

```bash
PYTHONPATH=src .venv/bin/python -m zona4_graph_loader.cli --clean-project
```

Validacion previa opcional del paquete:

```bash
PYTHONPATH=src .venv/bin/python scripts/validate_extension_bundle.py --extensions-dir data/extensions
```

5. Correr validaciones de Neo4j:

- `docs/neo4j/queries_validacion.cypher`
- `docs/neo4j/queries_analitica_avanzada.cypher`

## Flags utiles

- `--extensions-dir data/extensions`: directorio de paquetes.
- `--skip-extensions`: desactiva esta capa.

## Convenciones para mantener calidad

- Usar llaves estables (`persona_key`, `evento_key`, `lugar_key`).
- Mantener `fuente` en nodos y relaciones cuando corresponda.
- Evitar merges agresivos de lugar sin reglas verificadas.
- Incluir checks de cobertura y colisiones tras cada alta de fuente.

## Checklist de alta de fuente

- [ ] Contrato de filas canonicas respetado.
- [ ] Keys unicas y estables.
- [ ] Fechas normalizadas.
- [ ] Lugares y direcciones con formato consistente.
- [ ] Carga limpia ejecutada.
- [ ] Queries de validacion sin alertas criticas.

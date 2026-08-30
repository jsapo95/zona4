from __future__ import annotations

from zona4_graph_loader.pipeline.load_graph import contar_relaciones_source_huerfanas


def test_relacion_con_source_existente_no_es_huerfana():
    rows = [{"source_key": "registro:1", "target_key": "registro:2", "tipo": "TORTURO_A"}]
    assert contar_relaciones_source_huerfanas(rows, {"registro:1", "registro:2"}) == []


def test_relacion_sin_nodo_persona_para_source_es_huerfana():
    """CYPHER_UPSERT_REL_PERSONA hace MATCH (no MERGE) sobre source_key: si el
    perpetrador no tiene nodo :Persona propio, la fila entera -y su arista
    TORTURO_A- se descarta en silencio. Debe reportarse en vez de perderse.
    """
    rows = [{"source_key": "juicios_condenado:9", "target_key": "registro:2", "tipo": "TORTURO_A"}]
    huerfanas = contar_relaciones_source_huerfanas(rows, {"registro:2"})
    assert len(huerfanas) == 1
    assert huerfanas[0]["source_key"] == "juicios_condenado:9"


def test_solo_source_importa_target_ausente_no_cuenta():
    # CYPHER_UPSERT_REL_PERSONA hace MERGE sobre target_key (crea el nodo si
    # falta); solo el MATCH sobre source_key descarta la fila.
    rows = [{"source_key": "registro:1", "target_key": "inexistente:1", "tipo": "TORTURO_A"}]
    assert contar_relaciones_source_huerfanas(rows, {"registro:1"}) == []

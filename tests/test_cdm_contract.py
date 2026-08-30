from __future__ import annotations

from zona4_graph_loader.builders.archivo_memoria import build_archivo_memoria_rows
from zona4_graph_loader.builders.base import TIPOS_ENTIDAD_CONTEXTO
from zona4_graph_loader.builders.juicios_condenados import build_juicios_condenados_rows
from zona4_graph_loader.builders.minjus_imputados import build_minjus_imputados_rows
from zona4_graph_loader.builders.minjus_sentencias import build_sentencias_index
from zona4_graph_loader.builders.minjus_victimas import build_minjus_victimas_rows
from zona4_graph_loader.io.raw_files import read_raw_json
from zona4_graph_loader.io.sources_ingestor import (
    ALLOWED_SOURCE_KEYS,
    empty_canonical_dataset,
)


def test_cdm_tiene_siete_colecciones():
    assert ALLOWED_SOURCE_KEYS == {
        "personas",
        "lugares",
        "relaciones_interpersonales",
        "eventos_espaciales",
        "jerarquias",
        "entidades_contexto",
        "relaciones_contexto",
    }


def test_dataset_vacio_tiene_todas_las_claves():
    dataset = empty_canonical_dataset()
    assert set(dataset) == ALLOWED_SOURCE_KEYS
    assert all(value == [] for value in dataset.values())


def test_todo_tipo_entidad_emitido_por_los_builders_esta_particionado():
    """pipeline.load_graph.run_load particiona `entidades_contexto` en
    orgs/instituciones/profesiones/cargos/alias_personas comparando
    `tipo_entidad` contra literales exactos. Una entidad cuyo tipo_entidad no
    calce ninguno de los cinco cae fuera de toda partición y no se escribe,
    sin ningún aviso (Fix 8). Este contrato corre los builders reales que hoy
    emiten `entidades_contexto` sobre los datos reales y verifica que ninguno
    emita un tipo_entidad fuera de TIPOS_ENTIDAD_CONTEXTO.
    """
    sentencias_index = build_sentencias_index(
        read_raw_json("derechos_humanos_minjus_gba_sentencias.json")
    )
    datasets = [
        build_archivo_memoria_rows(read_raw_json("archivo_memoria_san_martin.json")),
        build_juicios_condenados_rows(read_raw_json("juicios_lesa_humanidad_condenados.json")),
        build_minjus_imputados_rows(
            read_raw_json("derechos_humanos_minjus_gba_imputados.json"),
            sentencias_index=sentencias_index,
        ),
        build_minjus_victimas_rows(
            read_raw_json("derechos_humanos_minjus_gba_victimas.json"),
            ccd_key_by_slug={},
            sentencias_index=sentencias_index,
        ),
    ]

    tipos_emitidos = {
        entidad.get("tipo_entidad")
        for dataset in datasets
        for entidad in dataset.get("entidades_contexto", [])
    }
    assert tipos_emitidos, "ningún builder emitió entidades_contexto: revisar los datos de prueba"
    assert tipos_emitidos <= TIPOS_ENTIDAD_CONTEXTO

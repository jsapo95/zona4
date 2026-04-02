from __future__ import annotations

import argparse
from typing import LiteralString, cast

from neo4j import GraphDatabase, Query

from zona4_graph_loader.builders.candidatos import build_v3_candidate_rows
from zona4_graph_loader.builders.casos import build_nietx_rows
from zona4_graph_loader.builders.eventos import build_detalles_event_rows, build_nietx_event_rows
from zona4_graph_loader.builders.listado import build_listado_links_rows, build_listado_paginas_rows
from zona4_graph_loader.builders.lugares import build_lugar_layer_rows, build_safe_place_merge_rows
from zona4_graph_loader.builders.personas import build_detalles_rows, build_nietx_protagonistas
from zona4_graph_loader.builders.relaciones import build_detalles_rel_rows, build_detalles_simult_rows, build_nietx_rel_rows
from zona4_graph_loader.config import get_config
from zona4_graph_loader.constants import BATCH_SIZE
from zona4_graph_loader.db.cypher import (
    CONSTRAINTS,
    CYPHER_APPLY_SAFE_PLACE_MERGES,
    CYPHER_CLEAN_ALL,
    CYPHER_CLEAN_PROJECT,
    CYPHER_LINK_CASO_EVENTO,
    CYPHER_LINK_EVENTO_LUGAR,
    CYPHER_LINK_LUGAR_PARENT,
    CYPHER_LINK_PERSONA_EVENTO,
    CYPHER_LINK_PERSONA_LUGAR,
    CYPHER_LINK_PERSONA_PAGINA,
    CYPHER_UPSERT_ALIAS_LUGAR,
    CYPHER_UPSERT_CANDIDATO_MERGE,
    CYPHER_UPSERT_CASOS,
    CYPHER_UPSERT_EVENTOS,
    CYPHER_UPSERT_LUGARES,
    CYPHER_UPSERT_PAGINAS_LISTADO,
    CYPHER_UPSERT_PERSONAS,
    CYPHER_UPSERT_PROTAGONISTAS,
    CYPHER_UPSERT_REL_FAMILIAR,
    CYPHER_UPSERT_REL_PERSONA,
    CYPHER_UPSERT_SIMULT,
)
from zona4_graph_loader.db.qa import run_qa_report
from zona4_graph_loader.db.writer import run_batches
from zona4_graph_loader.io.files import DETALLES_PATH, LISTADO_PAGINAS_PATH, NIETXS_PATH, read_json


def run_load(args: argparse.Namespace) -> None:
    detalles = read_json(DETALLES_PATH)
    nietxs = read_json(NIETXS_PATH)
    listado_paginas = read_json(LISTADO_PAGINAS_PATH) if not args.skip_listado_paginas else []

    detalles_personas = build_detalles_rows(detalles)
    casos_nietx = build_nietx_rows(nietxs)
    protagonistas = build_nietx_protagonistas(nietxs)
    rel_familiares = build_nietx_rel_rows(nietxs)
    rel_personas = build_detalles_rel_rows(detalles)
    rel_simult = build_detalles_simult_rows(detalles)
    eventos_detalles = build_detalles_event_rows(detalles)
    eventos_nietx = build_nietx_event_rows(nietxs)
    eventos = eventos_detalles + eventos_nietx
    paginas_listado = build_listado_paginas_rows(listado_paginas)
    links_listado = build_listado_links_rows(listado_paginas)
    lugar_layer = (
        build_lugar_layer_rows(detalles)
        if not args.skip_lugares
        else {
            "lugares": [],
            "aliases": [],
            "parents": [],
            "persona_links": [],
            "evento_links": [],
        }
    )
    safe_place_merges = (
        build_safe_place_merge_rows(lugar_layer)
        if (not args.skip_lugares and args.apply_safe_place_merges)
        else []
    )
    v3_candidates = build_v3_candidate_rows(detalles_personas, rel_familiares, rel_personas, rel_simult)

    cfg = get_config()
    driver = GraphDatabase.driver(cfg.uri, auth=(cfg.username, cfg.password))

    with driver.session(database=cfg.database) as session:
        if args.clean_all:
            session.run(Query(cast(LiteralString, CYPHER_CLEAN_ALL))).consume()
            print("clean_all: ok")
        elif args.clean_project:
            session.run(Query(cast(LiteralString, CYPHER_CLEAN_PROJECT))).consume()
            print("clean_project: ok")

        for statement in CONSTRAINTS:
            session.run(Query(cast(LiteralString, statement))).consume()

        run_batches(session, CYPHER_UPSERT_PERSONAS, detalles_personas, "personas_detalles", BATCH_SIZE)
        run_batches(session, CYPHER_UPSERT_CASOS, casos_nietx, "casos_nietx", BATCH_SIZE)
        run_batches(session, CYPHER_UPSERT_PROTAGONISTAS, protagonistas, "protagonistas_nietx", BATCH_SIZE)
        run_batches(session, CYPHER_UPSERT_REL_FAMILIAR, rel_familiares, "relaciones_familiares_nietx", BATCH_SIZE)
        run_batches(session, CYPHER_UPSERT_REL_PERSONA, rel_personas, "relaciones_detalles", BATCH_SIZE)
        run_batches(session, CYPHER_UPSERT_SIMULT, rel_simult, "victimas_simultaneas", BATCH_SIZE)
        run_batches(session, CYPHER_UPSERT_EVENTOS, eventos, "eventos", BATCH_SIZE)
        run_batches(session, CYPHER_LINK_PERSONA_EVENTO, eventos, "persona_evento", BATCH_SIZE)
        run_batches(
            session,
            CYPHER_LINK_CASO_EVENTO,
            [e for e in eventos if e.get("id_nietx") is not None],
            "caso_evento",
            BATCH_SIZE,
        )

        if not args.skip_lugares:
            run_batches(session, CYPHER_UPSERT_LUGARES, lugar_layer["lugares"], "lugares", BATCH_SIZE)
            run_batches(session, CYPHER_LINK_LUGAR_PARENT, lugar_layer["parents"], "lugar_parte_de", BATCH_SIZE)
            run_batches(session, CYPHER_UPSERT_ALIAS_LUGAR, lugar_layer["aliases"], "alias_lugar", BATCH_SIZE)
            run_batches(session, CYPHER_LINK_PERSONA_LUGAR, lugar_layer["persona_links"], "persona_lugar", BATCH_SIZE)
            run_batches(session, CYPHER_LINK_EVENTO_LUGAR, lugar_layer["evento_links"], "evento_lugar", BATCH_SIZE)
            if args.apply_safe_place_merges:
                run_batches(
                    session,
                    CYPHER_APPLY_SAFE_PLACE_MERGES,
                    safe_place_merges,
                    "safe_place_merges_aplicados",
                    BATCH_SIZE,
                )

        if not args.skip_listado_paginas:
            run_batches(session, CYPHER_UPSERT_PAGINAS_LISTADO, paginas_listado, "paginas_listado", BATCH_SIZE)
            run_batches(session, CYPHER_LINK_PERSONA_PAGINA, links_listado, "persona_listada_en", BATCH_SIZE)

        if not args.skip_v3_candidates:
            run_batches(session, CYPHER_UPSERT_CANDIDATO_MERGE, v3_candidates, "v3_candidatos_merge", BATCH_SIZE)

        if not args.skip_qa_report:
            run_qa_report(session, include_candidates=not args.skip_v3_candidates)

    driver.close()

from __future__ import annotations

from typing import Dict, LiteralString, cast

from neo4j import Query

QA_QUERIES = {
    "personas_total": "MATCH (p:Persona) RETURN count(p) AS value",
    "casos_total": "MATCH (c:CasoNietx) RETURN count(c) AS value",
    "eventos_total": "MATCH (e:Evento) RETURN count(e) AS value",
    "placeholders_total": "MATCH (p:Persona {es_placeholder:true}) RETURN count(p) AS value",
    "rel_familiares_total": "MATCH ()-[r:VINCULO_FAMILIAR]->() RETURN count(r) AS value",
    "rel_persona_total": "MATCH ()-[r:VINCULO_PERSONA]->() RETURN count(r) AS value",
    "rel_simult_total": "MATCH ()-[r:VICTIMA_SIMULTANEA]->() RETURN count(r) AS value",
    "rel_evento_total": "MATCH ()-[r:PARTICIPO_EN]->() RETURN count(r) AS value",
    "rel_caso_evento_total": "MATCH ()-[r:REGISTRA_EVENTO]->() RETURN count(r) AS value",
    "candidatos_merge_total": "MATCH ()-[r:CANDIDATO_MERGE]->() RETURN count(r) AS value",
    "paginas_listado_total": "MATCH (pg:PaginaListado) RETURN count(pg) AS value",
    "rel_listada_en_total": "MATCH ()-[r:LISTADA_EN]->() RETURN count(r) AS value",
    "lugares_total": "MATCH (l:Lugar) RETURN count(l) AS value",
    "alias_lugar_total": "MATCH (a:AliasLugar) RETURN count(a) AS value",
    "rel_persona_lugar_total": "MATCH ()-[r:LUGAR_REFERENCIA]->() RETURN count(r) AS value",
    "rel_evento_lugar_total": "MATCH ()-[r:OCURRIO_EN]->() RETURN count(r) AS value",
}


def run_qa_report(session, include_candidates: bool = True) -> None:
    report: Dict[str, int] = {}
    for key, query in QA_QUERIES.items():
        if key == "candidatos_merge_total" and not include_candidates:
            continue
        rec = session.run(Query(cast(LiteralString, query))).single()
        report[key] = int(rec["value"]) if rec and rec["value"] is not None else 0

    print("qa_report:")
    for key in sorted(report.keys()):
        print(f"  {key}: {report[key]}")

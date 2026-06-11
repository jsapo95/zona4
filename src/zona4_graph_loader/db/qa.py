from __future__ import annotations

from typing import Dict, LiteralString, cast

from neo4j import Query

QA_QUERIES = {
    "personas_total": "MATCH (p:Persona) RETURN count(p) AS value",
    "victimas_total": "MATCH (p:Persona:Victima) RETURN count(p) AS value",
    "nietxs_total": "MATCH (p:Persona:Nietx) RETURN count(p) AS value",
    "complices_total": "MATCH (p:Persona:Complice) RETURN count(p) AS value",
    "represores_total": "MATCH (p:Persona:Represor) RETURN count(p) AS value",
    "direcciones_ccd_total": "MATCH (d:DirecciónCCD) RETURN count(d) AS value",
    "lugares_total": "MATCH (l:Lugar) RETURN count(l) AS value",
    "alias_lugar_total": "MATCH (a:AliasLugar) RETURN count(a) AS value",
    "rel_familiares_total": "MATCH ()-[r:HIJE_DE|PADRE_DE|MADRE_DE|NIETX_DE|ABUELX_DE|HERMANX_DE|PAREJA_DE|CUÑADX_DE|SUEGRX_DE|YERNX_NUERX_DE]->() RETURN count(r) AS value",
    "rel_secuestrado_en_total": "MATCH ()-[r:SECUESTRADO_EN]->() RETURN count(r) AS value",
    "rel_asesinado_en_total": "MATCH ()-[r:ASESINADO_EN]->() RETURN count(r) AS value",
    "rel_presente_en_total": "MATCH ()-[r:PRESENTE_EN]->() RETURN count(r) AS value",
    "rel_pario_en_total": "MATCH ()-[r:PARIO_EN]->() RETURN count(r) AS value",
    "rel_murio_en_total": "MATCH ()-[r:MURIO_EN]->() RETURN count(r) AS value",
    "rel_liberado_en_total": "MATCH ()-[r:LIBERADO_EN]->() RETURN count(r) AS value",
    "candidatos_merge_total": "MATCH ()-[r:CANDIDATO_MERGE]->() RETURN count(r) AS value",
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

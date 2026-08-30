from __future__ import annotations

from typing import Dict, LiteralString, cast

from neo4j import Query

QA_QUERIES = {
    "personas_total": "MATCH (p:Persona) RETURN count(p) AS value",
    "victimas_total": "MATCH (p:Persona:Victima) RETURN count(p) AS value",
    "nietxs_total": "MATCH (p:Persona:Nietx) RETURN count(p) AS value",
    # Fix D (V1.3, hallazgo C5): ADN ya no se completa con "SÍ" cuando la
    # fuente no trae fecha de confirmación -queda "DESCONOCIDA". Este
    # contador hace auditable en cada corrida cuántos nietxs tienen una
    # fecha de ADN real vs. cuántos no.
    "nietxs_adn_confirmado_total": "MATCH (p:Persona:Nietx) WHERE p.ADN <> 'DESCONOCIDA' RETURN count(p) AS value",
    "nietxs_estado_busqueda_total": "MATCH (p:Persona:Nietx) WHERE p.estado = 'Búsqueda' RETURN count(p) AS value",
    "complices_total": "MATCH (p:Persona:Complice) RETURN count(p) AS value",
    "represores_total": "MATCH (p:Persona:Represor) RETURN count(p) AS value",
    "direcciones_ccd_total": "MATCH (d:DirecciónCCD) RETURN count(d) AS value",
    "lugares_total": "MATCH (l:Lugar) RETURN count(l) AS value",
    "alias_lugar_total": "MATCH (a:AliasLugar) RETURN count(a) AS value",
    "rel_familiares_total": "MATCH ()-[r:HIJE_DE|PADRE_DE|MADRE_DE|NIETX_DE|ABUELX_DE|HERMANX_DE|PAREJA_DE|CUÑADX_DE|SUEGRX_DE|YERNX_NUERX_DE]->() RETURN count(r) AS value",
    # Fix C1/A (V1.3): TORTURO_A queda restringido a los pares imputado-víctima
    # cuya sentencia condena por tormentos; el resto de los pares de MinJus
    # recibe IMPUTADO_POR. Contadores separados para que la restricción sea
    # auditable en cada corrida.
    "rel_torturo_a_total": "MATCH ()-[r:TORTURO_A]->() RETURN count(r) AS value",
    "rel_imputado_por_total": "MATCH ()-[r:IMPUTADO_POR]->() RETURN count(r) AS value",
    "rel_secuestrado_en_total": "MATCH ()-[r:SECUESTRADO_EN]->() RETURN count(r) AS value",
    "rel_asesinado_en_total": "MATCH ()-[r:ASESINADO_EN]->() RETURN count(r) AS value",
    "rel_presente_en_total": "MATCH ()-[r:PRESENTE_EN]->() RETURN count(r) AS value",
    "rel_pario_en_total": "MATCH ()-[r:PARIO_EN]->() RETURN count(r) AS value",
    "rel_murio_en_total": "MATCH ()-[r:MURIO_EN]->() RETURN count(r) AS value",
    "rel_liberado_en_total": "MATCH ()-[r:LIBERADO_EN]->() RETURN count(r) AS value",
    "candidatos_merge_total": "MATCH ()-[r:CANDIDATO_MERGE]->() RETURN count(r) AS value",
    # Fix E (V1.3, hallazgo I7): ya no se proponen candidatos víctima-represor
    # sin ninguna fecha que los respalde. Los que persisten (si los hay)
    # deberían venir todos con `metodo:"nombre_exacto_roles_incompatibles"`
    # -evidencia real detrás, revisión humana pendiente- nunca de
    # "nombre_exacto_sin_fecha" ni "set_dice_typo_v1".
    "candidatos_merge_victima_represor_total": (
        "MATCH (a:Persona)-[r:CANDIDATO_MERGE]->(b:Persona) "
        "WHERE (a:Victima AND b:Represor) OR (a:Represor AND b:Victima) "
        "RETURN count(r) AS value"
    ),
    "orgs_total": "MATCH (e:Org) RETURN count(e) AS value",
    "instituciones_total": "MATCH (e:Institución) RETURN count(e) AS value",
    "profesiones_total": "MATCH (e:Profesión) RETURN count(e) AS value",
    "cargos_total": "MATCH (e:Cargo) RETURN count(e) AS value",
    "alias_personas_total": "MATCH (e:AliasPersona) RETURN count(e) AS value",
    "rel_parte_de_org_total": "MATCH (:Persona)-[r:PARTE_DE]->(:Org) RETURN count(r) AS value",
    "rel_identifica_a_total": "MATCH ()-[r:IDENTIFICA_A]->() RETURN count(r) AS value",
    # Fix E (V1.3, hallazgo I6): fechas imposibles (nacimientos en el futuro,
    # secuestros/asesinatos fuera del período histórico real de esta fuente)
    # ya no se persisten -deberían dar 0 en toda carga futura. Si alguno de
    # estos contadores no es 0, algún builder nuevo o modificado dejó pasar
    # una fecha imposible sin pasar por `validar_fecha_de_hecho`/
    # `validar_fecha_de_nacimiento`.
    "personas_fecha_nacimiento_imposible_total": (
        "MATCH (p:Persona) WHERE p.fecha_nacimiento IS NOT NULL "
        "AND p.fecha_nacimiento <> 'DESCONOCIDA' AND p.fecha_nacimiento > '1983-12-31' "
        "RETURN count(p) AS value"
    ),
    "rel_nacio_en_fecha_imposible_total": (
        "MATCH ()-[r:NACIO_EN]->() WHERE r.fecha <> 'DESCONOCIDA' AND r.fecha > '1983-12-31' "
        "RETURN count(r) AS value"
    ),
    "rel_secuestrado_en_fecha_fuera_de_rango_total": (
        "MATCH ()-[r:SECUESTRADO_EN]->() "
        "WHERE r.fecha <> 'DESCONOCIDA' AND (r.fecha < '1966-01-01' OR r.fecha > '1990-12-31') "
        "RETURN count(r) AS value"
    ),
    "rel_asesinado_en_fecha_fuera_de_rango_total": (
        "MATCH ()-[r:ASESINADO_EN]->() "
        "WHERE r.fecha <> 'DESCONOCIDA' AND (r.fecha < '1966-01-01' OR r.fecha > '1990-12-31') "
        "RETURN count(r) AS value"
    ),
    # Fix E (V1.3, hallazgo I3d): "SIN ESPECIFICAR"/"CIVIL"/etc. ya no deben
    # generar :Org ni :Institución con aristas -deberían dar 0 en toda carga
    # futura.
    "orgs_sentinel_total": (
        "MATCH (e:Org) WHERE e.nombre IN "
        "['SIN ESPECIFICAR', 'POLICIA (SIN ESPECIFICAR)', 'CIVIL', "
        "'NO ESPECIFICADO', 'NO DETERMINADO', 'DESCONOCIDA', 'DESCONOCIDO'] "
        "RETURN count(e) AS value"
    ),
    "instituciones_sentinel_total": (
        "MATCH (e:Institución) WHERE e.nombre IN "
        "['NO DETERMINADO', 'NO ESPECIFICADO', 'NO ESPECIFICA', 'DESCONOCIDO', 'DESCONOCIDA'] "
        "RETURN count(e) AS value"
    ),
    # Fix E (V1.3, hallazgo I5): distribución de tipo_direccion sobre
    # :DirecciónCCD -antes indistinguible entre CCD real, domicilio/vía
    # pública y cementerio bajo la misma label.
    "direcciones_ccd_tipo_ccd_total": "MATCH (d:DirecciónCCD {tipo_direccion: 'CCD'}) RETURN count(d) AS value",
    "direcciones_ccd_tipo_hecho_narrativo_total": (
        "MATCH (d:DirecciónCCD {tipo_direccion: 'HECHO_NARRATIVO'}) RETURN count(d) AS value"
    ),
    "direcciones_ccd_sin_tipo_direccion_total": (
        "MATCH (d:DirecciónCCD) WHERE d.tipo_direccion IS NULL RETURN count(d) AS value"
    ),
}


def run_qa_report(session, include_candidates: bool = True) -> None:
    report: Dict[str, int] = {}
    for key, query in QA_QUERIES.items():
        if key in {"candidatos_merge_total", "candidatos_merge_victima_represor_total"} and not include_candidates:
            continue
        rec = session.run(Query(cast(LiteralString, query))).single()
        report[key] = int(rec["value"]) if rec and rec["value"] is not None else 0

    print("qa_report:")
    for key in sorted(report.keys()):
        print(f"  {key}: {report[key]}")

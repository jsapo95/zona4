#!/usr/bin/env python3
"""Carga datos de JSON a Neo4j Aura.

Uso:
  export NEO4J_URI='neo4j+s://<tu-aura>.databases.neo4j.io'
  export NEO4J_USERNAME='neo4j'
  export NEO4J_PASSWORD='***'
  export NEO4J_DATABASE='neo4j'
  python scripts/load_neo4j_aura.py
    python scripts/load_neo4j_aura.py --clean-project
    python scripts/load_neo4j_aura.py --clean-all
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, List, LiteralString, Optional, cast

from neo4j import GraphDatabase, Query

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
NIETXS_PATH = DATA_DIR / "nietxs_relacion.json"
DETALLES_PATH = DATA_DIR / "detalles_personas.json"
LISTADO_PAGINAS_PATH = DATA_DIR / "listado_paginas.json"
BATCH_SIZE = 500
ALIAS_ROOT_PARENT_KEY = "__ROOT__"

SPANISH_MONTHS = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}

REL_MAP = {
    "madre": "MADRE",
    "padre": "PADRE",
    "hermanx": "HERMANO",
    "hermano": "HERMANO",
    "hermana": "HERMANO",
    "abuela materna": "ABUELA_MATERNA",
    "abuela paterna": "ABUELA_PATERNA",
    "esposo": "PAREJA",
    "esposa": "PAREJA",
    "conyuge": "PAREJA",
    "pareja": "PAREJA",
    "ex esposo": "PAREJA",
    "ex esposa": "PAREJA",
    "companero": "PAREJA",
    "companera": "PAREJA",
    "novio": "PAREJA",
    "novia": "PAREJA",
    "hijo": "HIJO",
    "hija": "HIJO",
}

UNKNOWN_PLACE_VALUES = {
    "SE DESCONOCE",
    "NO HAY INFORMACION",
    "SIN DATOS",
    "DESCONOCIDO",
}

EQUIV_CITIES = {
    "CAPITAL FEDERAL": ("CIUDAD", "CIUDAD AUTONOMA DE BUENOS AIRES", None),
    "CABA": ("CIUDAD", "CIUDAD AUTONOMA DE BUENOS AIRES", None),
    "CIUDAD DE BS AS": ("CIUDAD", "CIUDAD AUTONOMA DE BUENOS AIRES", None),
    "CIUDAD DE BUENOS AIRES": ("CIUDAD", "CIUDAD AUTONOMA DE BUENOS AIRES", None),
    "CIUDAD DE BS AS": ("CIUDAD", "CIUDAD AUTONOMA DE BUENOS AIRES", None),
    "CORDOBA CAPITAL": ("CIUDAD", "CORDOBA", "CORDOBA"),
    "MENDOZA CAPITAL": ("CIUDAD", "MENDOZA", "MENDOZA"),
    "SAN MIGUEL DE TUCUMAN": ("CIUDAD", "SAN MIGUEL DE TUCUMAN", "TUCUMAN"),
}

PROVINCE_ABBR = {
    "BS AS": "BUENOS AIRES",
    "BUENOS AIRES": "BUENOS AIRES",
    "BSA": "BUENOS AIRES",
    "SANTA FE": "SANTA FE",
    "TUCUMAN": "TUCUMAN",
    "CORDOBA": "CORDOBA",
    "MENDOZA": "MENDOZA",
}

DIRECTIONAL_TOKENS = {
    "ESTE",
    "OESTE",
    "NORTE",
    "SUR",
}


@dataclass
class Config:
    uri: str
    username: str
    password: str
    database: str


def _norm_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def strip_accents(value: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", value) if not unicodedata.combining(c))


def slugify_name(value: str) -> str:
    text = strip_accents(value.lower())
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = _norm_space(text)
    return text.replace(" ", "_")


def clean_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    value = _norm_space(value)
    if value in {"", "-", "No hay informacion."}:
        return None
    return value


def parse_ddmmyyyy(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    match = re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", value.strip())
    if not match:
        return None
    day, month, year = map(int, match.groups())
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def parse_spanish_long_date(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    text = strip_accents(value.lower().strip())
    match = re.fullmatch(r"(\d{1,2})\s+de\s+([a-z]+),\s*(\d{4})", text)
    if not match:
        return None
    day = int(match.group(1))
    month_name = match.group(2)
    year = int(match.group(3))
    month = SPANISH_MONTHS.get(month_name)
    if not month:
        return None
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def normalize_relation(value: Optional[str]) -> str:
    if not value:
        return "OTRA"
    text = strip_accents(value.lower())
    text = _norm_space(re.sub(r"[\.,;:_\-]+", " ", text))
    return REL_MAP.get(text, "OTRA")


def persona_key_from_name(name: str) -> str:
    return f"nombre:{slugify_name(name)}"


def chunked(items: List[Dict[str, Any]], size: int) -> Iterable[List[Dict[str, Any]]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_detalles_rows(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for item in data:
        detalle = item.get("detalle", {})
        registro = item.get("registro")
        if registro is None:
            continue
        rows.append(
            {
                "persona_key": f"registro:{registro}",
                "registro": registro,
                "nombre_completo": clean_text(item.get("nombre_completo")) or clean_text(detalle.get("descripcion_nombre")),
                "nombre": clean_text(item.get("nombre")),
                "apellido": clean_text(item.get("apellido")),
                "sexo": clean_text(detalle.get("Sexo")),
                "estado_desaparicion": clean_text(detalle.get("descripcion_estado")),
                "fecha_nacimiento": parse_ddmmyyyy(clean_text(detalle.get("descripcion_fecha_nacimiento"))),
                "fecha_secuestro": parse_ddmmyyyy(clean_text(detalle.get("descripcion_fecha_de_secuestro"))),
                "fecha_asesinato": parse_ddmmyyyy(clean_text(detalle.get("descripcion_fecha_de_asesinato"))),
                "lugar_nacimiento": clean_text(detalle.get("Lugar de nacimiento")),
                "lugar_secuestro": clean_text(detalle.get("descripcion_lugar_de_secuestro")),
                "fuentes": ["detalles_personas"],
            }
        )
    return rows


def build_nietx_rows(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for item in data:
        id_nietx = item.get("id_nietx")
        if id_nietx is None:
            continue
        restituido = item.get("restituido", {}) or {}
        rows.append(
            {
                "id_nietx": id_nietx,
                "nombre_caso": clean_text(item.get("nombre_completo")),
                "estado": clean_text(item.get("estado")),
                "imagen_url": clean_text(item.get("imagen_url")),
                "conoce_la_historia_url": clean_text(item.get("conoce_la_historia")),
                "resumen_data": clean_text(item.get("resumen_data")),
                "detalle_data": clean_text(item.get("detalle_data")),
                "fecha_adn": parse_spanish_long_date(clean_text(restituido.get("ADN"))),
                "fecha_restitucion": parse_spanish_long_date(clean_text(restituido.get("Restitucion")) or clean_text(restituido.get("Restitución"))),
            }
        )
    return rows


def build_nietx_protagonistas(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for item in data:
        id_nietx = item.get("id_nietx")
        if id_nietx is None:
            continue
        rows.append(
            {
                "id_nietx": id_nietx,
                "persona_key": f"nietx:{id_nietx}",
                "nombre_completo": clean_text(item.get("nombre_completo")),
                "fuentes": ["nietxs_relacion"],
            }
        )
    return rows


def build_nietx_rel_rows(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for item in data:
        id_nietx = item.get("id_nietx")
        if id_nietx is None:
            continue
        source_key = f"nietx:{id_nietx}"
        for rel in item.get("relaciones", []) or []:
            rel_name = clean_text(rel.get("nombre_completo_relacion"))
            if not rel_name:
                continue
            rel_id = rel.get("id_persona")
            target_key = f"registro:{rel_id}" if rel_id is not None else persona_key_from_name(rel_name)
            rows.append(
                {
                    "source_key": source_key,
                    "target_key": target_key,
                    "target_registro": rel_id,
                    "target_nombre": rel_name,
                    "target_placeholder": rel_id is None,
                    "tipo_raw": clean_text(rel.get("relacion")),
                    "tipo": normalize_relation(clean_text(rel.get("relacion"))),
                    "fuente": "nietxs_relacion",
                }
            )
    return rows


def build_detalles_rel_rows(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for item in data:
        registro = item.get("registro")
        if registro is None:
            continue
        source_key = f"registro:{registro}"
        detalle = item.get("detalle", {})
        for rel in detalle.get("victimas_relacionadas_red", []) or []:
            rel_name = clean_text(rel.get("nombre_completo"))
            if not rel_name:
                continue
            rel_id = rel.get("registro")
            target_key = f"registro:{rel_id}" if rel_id is not None else persona_key_from_name(rel_name)
            rows.append(
                {
                    "source_key": source_key,
                    "target_key": target_key,
                    "target_registro": rel_id,
                    "target_nombre": rel_name,
                    "target_placeholder": rel_id is None,
                    "tipo_raw": clean_text(rel.get("relacion")),
                    "tipo": normalize_relation(clean_text(rel.get("relacion"))),
                    "fuente": "detalles_personas",
                }
            )
    return rows


def build_detalles_simult_rows(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for item in data:
        registro = item.get("registro")
        if registro is None:
            continue
        source_key = f"registro:{registro}"
        detalle = item.get("detalle", {})
        for rel in detalle.get("victimas_simultaneas_red", []) or []:
            rel_name = clean_text(rel.get("nombre_completo"))
            if not rel_name:
                continue
            rel_id = rel.get("registro")
            target_key = f"registro:{rel_id}" if rel_id is not None else persona_key_from_name(rel_name)
            rows.append(
                {
                    "source_key": source_key,
                    "target_key": target_key,
                    "target_registro": rel_id,
                    "target_nombre": rel_name,
                    "target_placeholder": rel_id is None,
                    "fuente": "detalles_personas",
                }
            )
    return rows


CONSTRAINTS = [
    "CREATE CONSTRAINT persona_key_unique IF NOT EXISTS FOR (p:Persona) REQUIRE p.persona_key IS UNIQUE",
    "CREATE CONSTRAINT caso_nietx_id_unique IF NOT EXISTS FOR (c:CasoNietx) REQUIRE c.id_nietx IS UNIQUE",
    "CREATE CONSTRAINT evento_key_unique IF NOT EXISTS FOR (e:Evento) REQUIRE e.evento_key IS UNIQUE",
    "CREATE CONSTRAINT pagina_listado_key_unique IF NOT EXISTS FOR (pg:PaginaListado) REQUIRE pg.pagina_key IS UNIQUE",
    "CREATE CONSTRAINT lugar_key_unique IF NOT EXISTS FOR (l:Lugar) REQUIRE l.lugar_key IS UNIQUE",
    "CREATE CONSTRAINT alias_lugar_key_unique IF NOT EXISTS FOR (a:AliasLugar) REQUIRE a.alias_key IS UNIQUE",
    "CREATE CONSTRAINT alias_lugar_scope_unique IF NOT EXISTS FOR (a:AliasLugar) REQUIRE (a.alias_norm, a.tipo, a.parent_key) IS UNIQUE",
    "CREATE INDEX persona_registro_idx IF NOT EXISTS FOR (p:Persona) ON (p.registro)",
    "CREATE INDEX persona_nombre_idx IF NOT EXISTS FOR (p:Persona) ON (p.nombre_completo)",
    "CREATE INDEX evento_tipo_idx IF NOT EXISTS FOR (e:Evento) ON (e.tipo)",
    "CREATE INDEX evento_fecha_idx IF NOT EXISTS FOR (e:Evento) ON (e.fecha)",
    "CREATE INDEX pagina_listado_num_idx IF NOT EXISTS FOR (pg:PaginaListado) ON (pg.pagina)",
    "CREATE INDEX lugar_nombre_tipo_idx IF NOT EXISTS FOR (l:Lugar) ON (l.nombre_canonico, l.tipo)",
    "CREATE INDEX alias_lugar_norm_idx IF NOT EXISTS FOR (a:AliasLugar) ON (a.alias_norm)",
]

CYPHER_UPSERT_PERSONAS = """
UNWIND $rows AS row
MERGE (p:Persona {persona_key: row.persona_key})
SET p.registro = coalesce(row.registro, p.registro),
    p.nombre_completo = coalesce(row.nombre_completo, p.nombre_completo),
    p.nombre = coalesce(row.nombre, p.nombre),
    p.apellido = coalesce(row.apellido, p.apellido),
    p.sexo = coalesce(row.sexo, p.sexo),
    p.estado_desaparicion = coalesce(row.estado_desaparicion, p.estado_desaparicion),
    p.fecha_nacimiento = coalesce(row.fecha_nacimiento, p.fecha_nacimiento),
    p.fecha_secuestro = coalesce(row.fecha_secuestro, p.fecha_secuestro),
    p.fecha_asesinato = coalesce(row.fecha_asesinato, p.fecha_asesinato),
    p.lugar_nacimiento = coalesce(row.lugar_nacimiento, p.lugar_nacimiento),
    p.lugar_secuestro = coalesce(row.lugar_secuestro, p.lugar_secuestro),
    p.es_placeholder = coalesce(p.es_placeholder, false),
    p.fuentes = CASE
      WHEN p.fuentes IS NULL THEN row.fuentes
      ELSE reduce(acc = p.fuentes, f IN row.fuentes |
        CASE WHEN f IN acc THEN acc ELSE acc + f END)
    END
"""

CYPHER_UPSERT_CASOS = """
UNWIND $rows AS row
MERGE (c:CasoNietx {id_nietx: row.id_nietx})
SET c.nombre_caso = row.nombre_caso,
    c.estado = row.estado,
    c.imagen_url = row.imagen_url,
    c.conoce_la_historia_url = row.conoce_la_historia_url,
    c.resumen_data = row.resumen_data,
    c.detalle_data = row.detalle_data,
    c.fecha_adn = row.fecha_adn,
    c.fecha_restitucion = row.fecha_restitucion
"""

CYPHER_UPSERT_PROTAGONISTAS = """
UNWIND $rows AS row
MERGE (p:Persona {persona_key: row.persona_key})
SET p.nombre_completo = coalesce(row.nombre_completo, p.nombre_completo),
    p.es_placeholder = false,
    p.fuentes = CASE
      WHEN p.fuentes IS NULL THEN row.fuentes
      ELSE reduce(acc = p.fuentes, f IN row.fuentes |
        CASE WHEN f IN acc THEN acc ELSE acc + f END)
    END
SET p:Nietx
WITH p, row
MATCH (c:CasoNietx {id_nietx: row.id_nietx})
MERGE (c)-[:TIENE_PROTAGONISTA]->(p)
"""

CYPHER_UPSERT_REL_FAMILIAR = """
UNWIND $rows AS row
MATCH (s:Persona {persona_key: row.source_key})
MERGE (t:Persona {persona_key: row.target_key})
SET t.registro = coalesce(row.target_registro, t.registro),
    t.nombre_completo = coalesce(row.target_nombre, t.nombre_completo),
    t.es_placeholder = coalesce(row.target_placeholder, t.es_placeholder, false),
    t.fuentes = CASE
      WHEN t.fuentes IS NULL THEN [row.fuente]
      WHEN row.fuente IN t.fuentes THEN t.fuentes
      ELSE t.fuentes + row.fuente
    END
MERGE (s)-[r:VINCULO_FAMILIAR {tipo: row.tipo, fuente: row.fuente}]->(t)
SET r.tipo_raw = row.tipo_raw
"""

CYPHER_UPSERT_REL_PERSONA = """
UNWIND $rows AS row
MATCH (s:Persona {persona_key: row.source_key})
MERGE (t:Persona {persona_key: row.target_key})
SET t.registro = coalesce(row.target_registro, t.registro),
    t.nombre_completo = coalesce(row.target_nombre, t.nombre_completo),
    t.es_placeholder = coalesce(row.target_placeholder, t.es_placeholder, false),
    t.fuentes = CASE
      WHEN t.fuentes IS NULL THEN [row.fuente]
      WHEN row.fuente IN t.fuentes THEN t.fuentes
      ELSE t.fuentes + row.fuente
    END
MERGE (s)-[r:VINCULO_PERSONA {tipo: row.tipo, fuente: row.fuente}]->(t)
SET r.tipo_raw = row.tipo_raw
"""

CYPHER_UPSERT_SIMULT = """
UNWIND $rows AS row
MATCH (s:Persona {persona_key: row.source_key})
MERGE (t:Persona {persona_key: row.target_key})
SET t.registro = coalesce(row.target_registro, t.registro),
    t.nombre_completo = coalesce(row.target_nombre, t.nombre_completo),
    t.es_placeholder = coalesce(row.target_placeholder, t.es_placeholder, false),
    t.fuentes = CASE
      WHEN t.fuentes IS NULL THEN [row.fuente]
      WHEN row.fuente IN t.fuentes THEN t.fuentes
      ELSE t.fuentes + row.fuente
    END
MERGE (s)-[:VICTIMA_SIMULTANEA {fuente: row.fuente}]->(t)
"""

CYPHER_UPSERT_EVENTOS = """
UNWIND $rows AS row
MERGE (e:Evento {evento_key: row.evento_key})
SET e.tipo = row.tipo,
    e.fecha = coalesce(row.fecha, e.fecha),
    e.lugar = coalesce(row.lugar, e.lugar),
    e.descripcion_raw = coalesce(row.descripcion_raw, e.descripcion_raw),
    e.fuente = row.fuente
"""

CYPHER_LINK_PERSONA_EVENTO = """
UNWIND $rows AS row
MATCH (p:Persona {persona_key: row.persona_key})
MATCH (e:Evento {evento_key: row.evento_key})
MERGE (p)-[r:PARTICIPO_EN {rol: row.rol, fuente: row.fuente}]->(e)
SET r.descripcion_raw = row.descripcion_raw
"""

CYPHER_LINK_CASO_EVENTO = """
UNWIND $rows AS row
MATCH (c:CasoNietx {id_nietx: row.id_nietx})
MATCH (e:Evento {evento_key: row.evento_key})
MERGE (c)-[:REGISTRA_EVENTO {fuente: row.fuente}]->(e)
"""

CYPHER_UPSERT_PAGINAS_LISTADO = """
UNWIND $rows AS row
MERGE (pg:PaginaListado {pagina_key: row.pagina_key})
SET pg.pagina = row.pagina,
    pg.url = row.url,
    pg.fuente = row.fuente,
    pg.registros_count = row.registros_count
"""

CYPHER_LINK_PERSONA_PAGINA = """
UNWIND $rows AS row
MATCH (p:Persona {registro: row.registro})
MATCH (pg:PaginaListado {pagina_key: row.pagina_key})
MERGE (p)-[r:LISTADA_EN {fuente: row.fuente}]->(pg)
SET r.detail_url = row.detail_url,
    r.estado_raw = row.estado_raw,
    r.edad = row.edad,
    r.anio = row.anio,
    r.embarazo_estado = row.embarazo_estado,
    r.embarazo_meses = row.embarazo_meses
"""

CYPHER_CLEAN_PROJECT = """
MATCH (n)
WHERE n:Persona OR n:CasoNietx OR n:Evento OR n:PaginaListado OR n:Lugar OR n:AliasLugar
DETACH DELETE n
"""

CYPHER_CLEAN_ALL = """
MATCH (n)
DETACH DELETE n
"""

CYPHER_UPSERT_CANDIDATO_MERGE = """
UNWIND $rows AS row
MATCH (p:Persona {persona_key: row.placeholder_key})
MATCH (c:Persona {persona_key: row.candidate_key})
MERGE (p)-[r:CANDIDATO_MERGE {metodo: row.metodo}]->(c)
SET r.score = row.score,
    r.slug = row.slug,
    r.confianza = row.confianza,
    r.fuente = row.fuente
"""

CYPHER_UPSERT_LUGARES = """
UNWIND $rows AS row
MERGE (l:Lugar {lugar_key: row.lugar_key})
SET l.nombre_canonico = row.nombre_canonico,
    l.tipo = row.tipo,
    l.pais_code = row.pais_code,
    l.fuente = row.fuente
"""

CYPHER_LINK_LUGAR_PARENT = """
UNWIND $rows AS row
MATCH (child:Lugar {lugar_key: row.child_key})
MATCH (parent:Lugar {lugar_key: row.parent_key})
MERGE (child)-[:PARTE_DE]->(parent)
"""

CYPHER_UPSERT_ALIAS_LUGAR = """
UNWIND $rows AS row
MERGE (a:AliasLugar {alias_norm: row.alias_norm, tipo: row.tipo, parent_key: row.parent_key})
ON CREATE SET a.alias_key = row.alias_key,
              a.alias_raw = row.alias_raw,
              a.fuente = row.fuente,
              a.campo_fuente = row.campo_fuente
SET a.alias_norm = row.alias_norm,
    a.alias_raw = row.alias_raw,
    a.fuente = row.fuente,
    a.campo_fuente = row.campo_fuente,
    a.tipo = row.tipo,
    a.parent_key = row.parent_key
WITH a, row
MATCH (l:Lugar {lugar_key: row.lugar_key})
MERGE (a)-[:ALIAS_DE]->(l)
"""

CYPHER_LINK_PERSONA_LUGAR = """
UNWIND $rows AS row
MATCH (p:Persona {registro: row.registro})
MATCH (l:Lugar {lugar_key: row.lugar_key})
MERGE (p)-[r:LUGAR_REFERENCIA {campo: row.campo, fuente: row.fuente}]->(l)
SET r.alias_raw = row.alias_raw
"""

CYPHER_LINK_EVENTO_LUGAR = """
UNWIND $rows AS row
MATCH (e:Evento {evento_key: row.evento_key})
MATCH (l:Lugar {lugar_key: row.lugar_key})
MERGE (e)-[r:OCURRIO_EN {fuente: row.fuente, campo_fuente: row.campo_fuente}]->(l)
SET r.alias_raw = row.alias_raw
"""

CYPHER_APPLY_SAFE_PLACE_MERGES = """
UNWIND $rows AS row
MATCH (src:Lugar {lugar_key: row.source_key})
MATCH (dst:Lugar {lugar_key: row.target_key})
WHERE src <> dst
WITH src, dst, row
OPTIONAL MATCH (a:AliasLugar)-[ad:ALIAS_DE]->(src)
FOREACH (_ IN CASE WHEN ad IS NULL THEN [] ELSE [1] END |
    MERGE (a)-[:ALIAS_DE]->(dst)
    DELETE ad
)
WITH src, dst, row
OPTIONAL MATCH (p:Persona)-[rp:LUGAR_REFERENCIA]->(src)
FOREACH (_ IN CASE WHEN rp IS NULL THEN [] ELSE [1] END |
    MERGE (p)-[rp2:LUGAR_REFERENCIA {campo: rp.campo, fuente: rp.fuente}]->(dst)
    SET rp2.alias_raw = coalesce(rp2.alias_raw, rp.alias_raw)
    DELETE rp
)
WITH src, dst, row
OPTIONAL MATCH (e:Evento)-[re:OCURRIO_EN]->(src)
FOREACH (_ IN CASE WHEN re IS NULL THEN [] ELSE [1] END |
    MERGE (e)-[re2:OCURRIO_EN {fuente: re.fuente, campo_fuente: re.campo_fuente}]->(dst)
    SET re2.alias_raw = coalesce(re2.alias_raw, re.alias_raw)
    DELETE re
)
WITH src, dst, row
OPTIONAL MATCH (src)-[r1:PARTE_DE]->(parent:Lugar)
FOREACH (_ IN CASE WHEN r1 IS NULL THEN [] ELSE [1] END |
    MERGE (dst)-[:PARTE_DE]->(parent)
    DELETE r1
)
WITH src, dst, row
OPTIONAL MATCH (child:Lugar)-[r2:PARTE_DE]->(src)
FOREACH (_ IN CASE WHEN r2 IS NULL THEN [] ELSE [1] END |
    MERGE (child)-[:PARTE_DE]->(dst)
    DELETE r2
)
WITH src, row
SET src.merged_into = row.target_key,
        src.merge_reason = row.reason,
        src.merge_score = row.score
DETACH DELETE src
"""

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


def parse_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    text = clean_text(value)
    if text is None:
        return None
    match = re.search(r"\d+", text)
    return int(match.group(0)) if match else None


def normalize_embarazo(value: Optional[str]) -> tuple[str, Optional[int]]:
    text = clean_text(value)
    if text is None:
        return ("NO_INFO", None)
    text_norm = strip_accents(text.lower())
    if text_norm in {"si", "sí"}:
        return ("SI", None)
    months = parse_int(text)
    if months is not None:
        return ("MESES", months)
    return ("OTRO", None)


def normalize_place_text(value: str) -> str:
    text = strip_accents(value.upper())
    text = re.sub(r"[^A-Z0-9\s]", " ", text)
    text = _norm_space(text)
    return text


def normalize_place_identity(value: str) -> str:
    text = value
    # Unifica variantes frecuentes de abreviaturas y errores tipograficos.
    text = re.sub(r"\bCDAD\b", "CIUDAD", text)
    text = re.sub(r"\bCAP\s+FED\b", "CAPITAL FEDERAL", text)
    text = re.sub(r"\bSTA\b", "SANTA", text)
    text = re.sub(r"\bSECUETRADO\b", "SECUESTRADO", text)
    text = re.sub(r"\bSECUESTRAD[OA]S?\b", "SECUESTRADO", text)
    text = re.sub(r"\bFUE\s+SECUESTRADO\b", "SECUESTRADO", text)

    # Reduce ruido narrativo para favorecer identidad de lugar.
    text = re.sub(r"\bDE\s+SU\s+DOMICILIO\b", "", text)
    text = re.sub(r"\bEN\s+SU\s+DOMICILIO\b", "", text)

    return _norm_space(text)


def make_lugar_key(tipo: str, nombre: str, parent_key: Optional[str]) -> str:
    base = f"lugar:{tipo}:{slugify_name(nombre)}"
    return f"{base}|{parent_key}" if parent_key else base


def resolve_place(raw: Optional[str]) -> Optional[Dict[str, Any]]:
    text = clean_text(raw)
    if text is None:
        return None

    alias_norm = normalize_place_identity(normalize_place_text(text))
    if not alias_norm or alias_norm in UNKNOWN_PLACE_VALUES:
        return None

    if alias_norm in EQUIV_CITIES:
        tipo, nombre, parent_name = EQUIV_CITIES[alias_norm]
        parent_key = None
        if parent_name:
            parent_key = make_lugar_key("PROVINCIA", parent_name, "lugar:PAIS:argentina")
        lugar_key = make_lugar_key(tipo, nombre, parent_key)
        return {
            "alias_raw": text,
            "alias_norm": alias_norm,
            "tipo": tipo,
            "nombre_canonico": nombre,
            "lugar_key": lugar_key,
            "parent_key": parent_key,
        }

    # Caso con sufijo de provincia (ej: LA PLATA BS AS)
    for suffix, prov_name in PROVINCE_ABBR.items():
        if alias_norm.endswith(f" {suffix}"):
            city_name = alias_norm[: -len(suffix)].strip()
            if city_name:
                parent_key = make_lugar_key("PROVINCIA", prov_name, "lugar:PAIS:argentina")
                lugar_key = make_lugar_key("CIUDAD", city_name, parent_key)
                return {
                    "alias_raw": text,
                    "alias_norm": alias_norm,
                    "tipo": "CIUDAD",
                    "nombre_canonico": city_name,
                    "lugar_key": lugar_key,
                    "parent_key": parent_key,
                }

    # Ambiguedad controlada: conservar nodo, no mergearlo con jerarquia forzada.
    lugar_key = make_lugar_key("INDETERMINADO", alias_norm, None)
    return {
        "alias_raw": text,
        "alias_norm": alias_norm,
        "tipo": "INDETERMINADO",
        "nombre_canonico": alias_norm,
        "lugar_key": lugar_key,
        "parent_key": None,
    }


def build_lugar_layer_rows(data: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    pais_key = "lugar:PAIS:argentina"
    lugares: Dict[str, Dict[str, Any]] = {
        pais_key: {
            "lugar_key": pais_key,
            "nombre_canonico": "ARGENTINA",
            "tipo": "PAIS",
            "pais_code": "AR",
            "fuente": "normalizacion_lugar",
        }
    }
    parents: set[tuple[str, str]] = set()
    aliases: Dict[str, Dict[str, Any]] = {}
    persona_links: list[Dict[str, Any]] = []
    evento_links: list[Dict[str, Any]] = []

    def register_place(place: Dict[str, Any], field: str, registro: int, evento_key: Optional[str], persona_campo: Optional[str]) -> None:
        nonlocal lugares, parents, aliases, persona_links, evento_links

        lugares[place["lugar_key"]] = {
            "lugar_key": place["lugar_key"],
            "nombre_canonico": place["nombre_canonico"],
            "tipo": place["tipo"],
            "pais_code": "AR",
            "fuente": "normalizacion_lugar",
        }
        if place.get("parent_key"):
            parent_key = place["parent_key"]
            parents.add((place["lugar_key"], parent_key))
            if parent_key not in lugares:
                prov_name = parent_key.split(":PROVINCIA:", 1)[1].split("|", 1)[0].replace("_", " ").upper()
                lugares[parent_key] = {
                    "lugar_key": parent_key,
                    "nombre_canonico": prov_name,
                    "tipo": "PROVINCIA",
                    "pais_code": "AR",
                    "fuente": "normalizacion_lugar",
                }
            parents.add((parent_key, pais_key))

        alias_key = f"alias:{field}:{registro}:{slugify_name(place['alias_norm'])}"
        aliases[alias_key] = {
            "alias_key": alias_key,
            "alias_norm": place["alias_norm"],
            "alias_raw": place["alias_raw"],
            "fuente": "detalles_personas",
            "campo_fuente": field,
            "tipo": place["tipo"],
            "parent_key": place.get("parent_key") or ALIAS_ROOT_PARENT_KEY,
            "lugar_key": place["lugar_key"],
        }

        if persona_campo:
            persona_links.append(
                {
                    "registro": registro,
                    "lugar_key": place["lugar_key"],
                    "campo": persona_campo,
                    "fuente": "detalles_personas",
                    "alias_raw": place["alias_raw"],
                }
            )
        if evento_key:
            evento_links.append(
                {
                    "evento_key": evento_key,
                    "lugar_key": place["lugar_key"],
                    "fuente": "detalles_personas",
                    "campo_fuente": field,
                    "alias_raw": place["alias_raw"],
                }
            )

    for item in data:
        registro = item.get("registro")
        if registro is None:
            continue
        detalle = item.get("detalle", {})

        place_sec = resolve_place(detalle.get("descripcion_lugar_de_secuestro"))
        if place_sec:
            register_place(
                place=place_sec,
                field="descripcion_lugar_de_secuestro",
                registro=registro,
                evento_key=f"evento:detalles:secuestro:{registro}",
                persona_campo="secuestro",
            )

        place_nac = resolve_place(detalle.get("Lugar de nacimiento"))
        if place_nac:
            register_place(
                place=place_nac,
                field="lugar_nacimiento",
                registro=registro,
                evento_key=None,
                persona_campo="nacimiento",
            )

        place_ase = resolve_place(detalle.get("Lugar de asesinato"))
        if place_ase:
            register_place(
                place=place_ase,
                field="lugar_asesinato",
                registro=registro,
                evento_key=f"evento:detalles:asesinato:{registro}",
                persona_campo=None,
            )

    parent_rows = [{"child_key": c, "parent_key": p} for c, p in sorted(parents)]
    return {
        "lugares": list(lugares.values()),
        "aliases": list(aliases.values()),
        "parents": parent_rows,
        "persona_links": persona_links,
        "evento_links": evento_links,
    }


def build_detalles_event_rows(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for item in data:
        registro = item.get("registro")
        if registro is None:
            continue

        detalle = item.get("detalle", {})

        fecha_sec_raw = clean_text(detalle.get("descripcion_fecha_de_secuestro"))
        lugar_sec = clean_text(detalle.get("descripcion_lugar_de_secuestro"))
        if fecha_sec_raw or lugar_sec:
            rows.append(
                {
                    "evento_key": f"evento:detalles:secuestro:{registro}",
                    "tipo": "SECUESTRO",
                    "fecha": parse_ddmmyyyy(fecha_sec_raw),
                    "lugar": lugar_sec,
                    "descripcion_raw": fecha_sec_raw,
                    "fuente": "detalles_personas",
                    "persona_key": f"registro:{registro}",
                    "rol": "victima",
                }
            )

        fecha_ase_raw = clean_text(detalle.get("descripcion_fecha_de_asesinato"))
        lugar_ase = clean_text(detalle.get("Lugar de asesinato"))
        if fecha_ase_raw or lugar_ase:
            rows.append(
                {
                    "evento_key": f"evento:detalles:asesinato:{registro}",
                    "tipo": "ASESINATO",
                    "fecha": parse_ddmmyyyy(fecha_ase_raw),
                    "lugar": lugar_ase,
                    "descripcion_raw": fecha_ase_raw,
                    "fuente": "detalles_personas",
                    "persona_key": f"registro:{registro}",
                    "rol": "victima",
                }
            )
    return rows


def build_nietx_event_rows(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for item in data:
        id_nietx = item.get("id_nietx")
        if id_nietx is None:
            continue

        restituido = item.get("restituido", {}) or {}
        fecha_adn_raw = clean_text(restituido.get("ADN"))
        fecha_rest_raw = clean_text(restituido.get("Restitucion")) or clean_text(restituido.get("Restitución"))

        if fecha_adn_raw:
            rows.append(
                {
                    "evento_key": f"evento:nietx:adn:{id_nietx}",
                    "tipo": "ADN",
                    "fecha": parse_spanish_long_date(fecha_adn_raw),
                    "lugar": None,
                    "descripcion_raw": fecha_adn_raw,
                    "fuente": "nietxs_relacion",
                    "persona_key": f"nietx:{id_nietx}",
                    "id_nietx": id_nietx,
                    "rol": "protagonista",
                }
            )

        if fecha_rest_raw:
            rows.append(
                {
                    "evento_key": f"evento:nietx:restitucion:{id_nietx}",
                    "tipo": "RESTITUCION",
                    "fecha": parse_spanish_long_date(fecha_rest_raw),
                    "lugar": None,
                    "descripcion_raw": fecha_rest_raw,
                    "fuente": "nietxs_relacion",
                    "persona_key": f"nietx:{id_nietx}",
                    "id_nietx": id_nietx,
                    "rol": "protagonista",
                }
            )

    return rows


def build_listado_paginas_rows(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for page in data:
        pagina = page.get("pagina")
        if pagina is None:
            continue
        registros = page.get("registros", []) or []
        rows.append(
            {
                "pagina_key": f"listado:pagina:{pagina}",
                "pagina": pagina,
                "url": clean_text(page.get("url")),
                "registros_count": len(registros),
                "fuente": "listado_paginas",
            }
        )
    return rows


def build_listado_links_rows(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for page in data:
        pagina = page.get("pagina")
        if pagina is None:
            continue
        pagina_key = f"listado:pagina:{pagina}"
        for reg in page.get("registros", []) or []:
            registro = reg.get("registro")
            if registro is None:
                continue
            embarazo_estado, embarazo_meses = normalize_embarazo(reg.get("embarazada"))
            rows.append(
                {
                    "registro": registro,
                    "pagina_key": pagina_key,
                    "detail_url": clean_text(reg.get("detail_url")),
                    "estado_raw": clean_text(reg.get("estado")),
                    "edad": parse_int(reg.get("edad")),
                    "anio": parse_int(reg.get("año")),
                    "embarazo_estado": embarazo_estado,
                    "embarazo_meses": embarazo_meses,
                    "fuente": "listado_paginas",
                }
            )
    return rows


def get_config() -> Config:
    uri = os.getenv("NEO4J_URI")
    username = os.getenv("NEO4J_USERNAME", "neo4j")
    password = os.getenv("NEO4J_PASSWORD")
    database = os.getenv("NEO4J_DATABASE", "neo4j")
    if not uri or not password:
        raise RuntimeError("Faltan variables de entorno: NEO4J_URI y/o NEO4J_PASSWORD")
    return Config(uri=uri, username=username, password=password, database=database)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Carga y normalizacion de datos en Neo4j Aura")
    parser.add_argument(
        "--clean-project",
        action="store_true",
        help="Limpia solo nodos y relaciones del proyecto (Persona, CasoNietx, Evento) antes de cargar.",
    )
    parser.add_argument(
        "--clean-all",
        action="store_true",
        help="Limpia todo el grafo antes de cargar.",
    )
    parser.add_argument(
        "--skip-v3-candidates",
        action="store_true",
        help="No crea relaciones CANDIDATO_MERGE de reconciliacion asistida.",
    )
    parser.add_argument(
        "--skip-qa-report",
        action="store_true",
        help="No imprime el reporte QA de cierre al finalizar la carga.",
    )
    parser.add_argument(
        "--skip-listado-paginas",
        action="store_true",
        help="No integra data/listado_paginas.json (PaginaListado y relacion LISTADA_EN).",
    )
    parser.add_argument(
        "--skip-lugares",
        action="store_true",
        help="No construye la capa de Lugar/AliasLugar ni enlaces con Persona/Evento.",
    )
    parser.add_argument(
        "--apply-safe-place-merges",
        action="store_true",
        help="Aplica merges automaticos conservadores de nodos Lugar tipo CIUDAD (solo typos/variantes seguras).",
    )

    args = parser.parse_args()
    if args.clean_project and args.clean_all:
        parser.error("No se puede usar --clean-project y --clean-all al mismo tiempo")
    return args


def run_batches(session, cypher: str, rows: List[Dict[str, Any]], label: str) -> None:
    total = 0
    for batch in chunked(rows, BATCH_SIZE):
        session.run(Query(cast(LiteralString, cypher)), rows=batch).consume()
        total += len(batch)
    print(f"{label}: {total}")


def _place_similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()


def _is_safe_city_merge_name(name_a: str, name_b: str) -> tuple[bool, float, str]:
    if not name_a or not name_b or name_a == name_b:
        return (False, 0.0, "sin_cambio")

    nums_a = set(re.findall(r"\d+", name_a))
    nums_b = set(re.findall(r"\d+", name_b))
    if nums_a != nums_b:
        return (False, 0.0, "numeros_distintos")

    tokens_a = name_a.split()
    tokens_b = name_b.split()
    dirs_a = {t for t in tokens_a if t in DIRECTIONAL_TOKENS}
    dirs_b = {t for t in tokens_b if t in DIRECTIONAL_TOKENS}
    if dirs_a != dirs_b:
        return (False, 0.0, "direccion_distinta")

    if len(tokens_a) != len(tokens_b):
        return (False, 0.0, "estructura_distinta")

    mismatches = [(a, b) for a, b in zip(tokens_a, tokens_b) if a != b]
    if len(mismatches) != 1:
        return (False, 0.0, "muchas_diferencias")

    token_score = _place_similarity(mismatches[0][0], mismatches[0][1])
    full_score = _place_similarity(name_a, name_b)
    if token_score < 0.8 or full_score < 0.9:
        return (False, full_score, "diferencia_no_tipografica")

    return (True, full_score, "typo_un_token")


def build_safe_place_merge_rows(lugar_layer: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    places = {row["lugar_key"]: row for row in lugar_layer.get("lugares", [])}
    aliases = lugar_layer.get("aliases", [])

    alias_count_by_place: Dict[str, int] = Counter(a["lugar_key"] for a in aliases)
    scope_by_place: Dict[str, tuple[str, str]] = {}
    for a in aliases:
        key = a["lugar_key"]
        if key not in scope_by_place:
            scope_by_place[key] = (a.get("tipo") or "", a.get("parent_key") or ALIAS_ROOT_PARENT_KEY)

    city_keys = [
        k
        for k, row in places.items()
        if row.get("tipo") == "CIUDAD" and k in scope_by_place and scope_by_place[k][1] != ALIAS_ROOT_PARENT_KEY
    ]
    scope_groups: Dict[tuple[str, str], List[str]] = defaultdict(list)
    for key in city_keys:
        scope_groups[scope_by_place[key]].append(key)

    parent: Dict[str, str] = {k: k for k in city_keys}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra == rb:
            return
        if ra < rb:
            parent[rb] = ra
        else:
            parent[ra] = rb

    evidence: Dict[tuple[str, str], tuple[float, str]] = {}
    for _, keys in scope_groups.items():
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                ka, kb = keys[i], keys[j]
                na = str(places[ka].get("nombre_canonico") or "")
                nb = str(places[kb].get("nombre_canonico") or "")
                ok, score, reason = _is_safe_city_merge_name(na, nb)
                if not ok:
                    continue
                union(ka, kb)
                pair = (ka, kb) if ka < kb else (kb, ka)
                evidence[pair] = (score, reason)

    clusters: Dict[str, List[str]] = defaultdict(list)
    for k in city_keys:
        clusters[find(k)].append(k)

    rows: List[Dict[str, Any]] = []
    for _, keys in clusters.items():
        if len(keys) < 2:
            continue
        target = sorted(keys, key=lambda k: (-alias_count_by_place.get(k, 0), k))[0]
        for source in keys:
            if source == target:
                continue
            pair = (source, target) if source < target else (target, source)
            score, reason = evidence.get(pair, (0.91, "typo_cluster"))
            rows.append(
                {
                    "source_key": source,
                    "target_key": target,
                    "score": round(score, 3),
                    "reason": reason,
                }
            )
    return rows


def build_v3_candidate_rows(
    detalles_personas: List[Dict[str, Any]],
    rel_familiares: List[Dict[str, Any]],
    rel_personas: List[Dict[str, Any]],
    rel_simult: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    # Placeholder keys provienen de relaciones sin id_persona/registro estable.
    placeholder_keys = {
        r["target_key"]
        for r in (rel_familiares + rel_personas + rel_simult)
        if r.get("target_placeholder") is True and str(r.get("target_key", "")).startswith("nombre:")
    }

    slug_to_candidates: Dict[str, List[str]] = {}
    for person in detalles_personas:
        key = person.get("persona_key")
        name = person.get("nombre_completo")
        if not key or not name:
            continue
        slug = slugify_name(name)
        slug_to_candidates.setdefault(slug, []).append(key)

    rows: List[Dict[str, Any]] = []
    for placeholder_key in sorted(placeholder_keys):
        slug = placeholder_key.split("nombre:", 1)[1]
        candidates = slug_to_candidates.get(slug, [])
        if not candidates:
            continue

        score = 1.0 if len(candidates) == 1 else 0.7
        confianza = "alta" if len(candidates) == 1 else "media"
        for candidate_key in candidates:
            rows.append(
                {
                    "placeholder_key": placeholder_key,
                    "candidate_key": candidate_key,
                    "metodo": "slug_exacto",
                    "score": score,
                    "slug": slug,
                    "confianza": confianza,
                    "fuente": "v3_reconciliacion_asistida",
                }
            )
    return rows


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


def main() -> None:
    args = parse_args()

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
    lugar_layer = build_lugar_layer_rows(detalles) if not args.skip_lugares else {
        "lugares": [],
        "aliases": [],
        "parents": [],
        "persona_links": [],
        "evento_links": [],
    }
    safe_place_merges = build_safe_place_merge_rows(lugar_layer) if (not args.skip_lugares and args.apply_safe_place_merges) else []
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

        run_batches(session, CYPHER_UPSERT_PERSONAS, detalles_personas, "personas_detalles")
        run_batches(session, CYPHER_UPSERT_CASOS, casos_nietx, "casos_nietx")
        run_batches(session, CYPHER_UPSERT_PROTAGONISTAS, protagonistas, "protagonistas_nietx")
        run_batches(session, CYPHER_UPSERT_REL_FAMILIAR, rel_familiares, "relaciones_familiares_nietx")
        run_batches(session, CYPHER_UPSERT_REL_PERSONA, rel_personas, "relaciones_detalles")
        run_batches(session, CYPHER_UPSERT_SIMULT, rel_simult, "victimas_simultaneas")
        run_batches(session, CYPHER_UPSERT_EVENTOS, eventos, "eventos")
        run_batches(session, CYPHER_LINK_PERSONA_EVENTO, eventos, "persona_evento")
        run_batches(session, CYPHER_LINK_CASO_EVENTO, [e for e in eventos if e.get("id_nietx") is not None], "caso_evento")

        if not args.skip_lugares:
            run_batches(session, CYPHER_UPSERT_LUGARES, lugar_layer["lugares"], "lugares")
            run_batches(session, CYPHER_LINK_LUGAR_PARENT, lugar_layer["parents"], "lugar_parte_de")
            run_batches(session, CYPHER_UPSERT_ALIAS_LUGAR, lugar_layer["aliases"], "alias_lugar")
            run_batches(session, CYPHER_LINK_PERSONA_LUGAR, lugar_layer["persona_links"], "persona_lugar")
            run_batches(session, CYPHER_LINK_EVENTO_LUGAR, lugar_layer["evento_links"], "evento_lugar")
            if args.apply_safe_place_merges:
                run_batches(session, CYPHER_APPLY_SAFE_PLACE_MERGES, safe_place_merges, "safe_place_merges_aplicados")

        if not args.skip_listado_paginas:
            run_batches(session, CYPHER_UPSERT_PAGINAS_LISTADO, paginas_listado, "paginas_listado")
            run_batches(session, CYPHER_LINK_PERSONA_PAGINA, links_listado, "persona_listada_en")

        if not args.skip_v3_candidates:
            run_batches(session, CYPHER_UPSERT_CANDIDATO_MERGE, v3_candidates, "v3_candidatos_merge")

        if not args.skip_qa_report:
            run_qa_report(session, include_candidates=not args.skip_v3_candidates)

    driver.close()


if __name__ == "__main__":
    main()

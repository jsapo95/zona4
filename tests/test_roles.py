from __future__ import annotations

from pathlib import Path

import pytest

from zona4_graph_loader.db.qa import QA_QUERIES
from zona4_graph_loader.domain.roles import (
    ROLE_LABELS,
    VALID_COMPLICE_TIPOS,
    VALID_ROLES,
    graph_labels,
    normalize_roles,
)

NEO4J_DATA_MODEL_PATH = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "zona4_graph_loader"
    / "NEO4J_DATA_MODEL.md"
)


def test_sin_roles_ni_es_nietx_default_victima():
    assert normalize_roles({"persona_key": "registro:1"}) == ["VICTIMA"]


def test_es_nietx_true_mapea_a_nietx():
    assert normalize_roles({"persona_key": "nietx:1", "es_nietx": True}) == ["NIETX"]


def test_es_nietx_false_mapea_a_victima():
    assert normalize_roles({"persona_key": "registro:1", "es_nietx": False}) == ["VICTIMA"]


def test_roles_explicitos_ganan_sobre_es_nietx():
    persona = {"persona_key": "x:1", "es_nietx": True, "roles": ["REPRESOR"]}
    assert normalize_roles(persona) == ["REPRESOR"]


def test_roles_se_ordenan_y_deduplican():
    persona = {"persona_key": "x:1", "roles": ["VICTIMA", "NIETX", "VICTIMA"]}
    assert normalize_roles(persona) == ["NIETX", "VICTIMA"]


def test_rol_desconocido_falla():
    with pytest.raises(ValueError, match="TESTIGO"):
        normalize_roles({"persona_key": "x:1", "roles": ["TESTIGO"]})


def test_complice_sin_tipo_falla():
    with pytest.raises(ValueError, match="complice_tipo"):
        normalize_roles({"persona_key": "x:1", "roles": ["COMPLICE"]})


def test_complice_con_tipo_invalido_falla():
    persona = {"persona_key": "x:1", "roles": ["COMPLICE"], "complice_tipo": "MILITAR"}
    with pytest.raises(ValueError, match="complice_tipo"):
        normalize_roles(persona)


def test_complice_con_tipo_valido_pasa():
    persona = {"persona_key": "x:1", "roles": ["COMPLICE"], "complice_tipo": "CIVIL"}
    assert normalize_roles(persona) == ["COMPLICE"]


def test_roles_vacio_falla():
    with pytest.raises(ValueError, match="vacía"):
        normalize_roles({"persona_key": "x:1", "roles": []})


def test_constantes_declaradas():
    assert VALID_ROLES == {"VICTIMA", "REPRESOR", "COMPLICE", "NIETX"}
    assert VALID_COMPLICE_TIPOS == {"CIVIL", "CLERICAL", "EMPRESARIAL"}


def test_graph_labels_traduce_a_titulo():
    assert graph_labels(["VICTIMA", "NIETX"]) == ["Victima", "Nietx"]


def test_role_labels_cubre_todos_los_roles_validos():
    assert set(ROLE_LABELS.keys()) == VALID_ROLES


def test_cada_label_de_rol_aparece_en_qa_queries_y_en_el_modelo_de_datos():
    """Contrato sin Neo4j: si un rol del CDM no tiene su label declarada en
    QA_QUERIES y en NEO4J_DATA_MODEL.md, un load puede escribir esa label y
    dejar que los contadores de QA la ignoren en silencio (el bug real de
    represores_total: 0 con :REPRESOR en mayúsculas).
    """
    modelo = NEO4J_DATA_MODEL_PATH.read_text(encoding="utf-8")
    qa_queries_text = " ".join(QA_QUERIES.values())

    for rol in VALID_ROLES:
        label = ROLE_LABELS[rol]
        assert f":{label}" in qa_queries_text, (
            f"La label '{label}' (rol {rol}) no aparece en ninguna query de QA_QUERIES"
        )
        assert f":{label}" in modelo, (
            f"La label '{label}' (rol {rol}) no está declarada en NEO4J_DATA_MODEL.md"
        )

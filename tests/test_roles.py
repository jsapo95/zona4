from __future__ import annotations

import pytest

from zona4_graph_loader.domain.roles import (
    VALID_COMPLICE_TIPOS,
    VALID_ROLES,
    normalize_roles,
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

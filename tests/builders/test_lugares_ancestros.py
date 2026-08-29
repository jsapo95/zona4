from __future__ import annotations

from zona4_graph_loader.builders.lugares import (
    expand_lugar_ancestors,
    node_from_lugar_key,
)

CIUDAD = "lugar:CIUDAD:billinghurst|lugar:PROVINCIA:buenos_aires|lugar:PAIS:argentina"


def test_node_from_lugar_key_reconstruye_nombre_y_tipo():
    nodo = node_from_lugar_key(CIUDAD)
    assert nodo["tipoGeopolitico"] == "CIUDAD"
    assert nodo["nombre"] == "BILLINGHURST"


def test_expande_toda_la_cadena():
    lugares, jerarquias = expand_lugar_ancestors(CIUDAD, "test")
    keys = [l["lugar_key"] for l in lugares]
    assert keys == [
        CIUDAD,
        "lugar:PROVINCIA:buenos_aires|lugar:PAIS:argentina",
        "lugar:PAIS:argentina",
    ]
    assert all(l["fuente"] == "test" for l in lugares)
    assert all(l["tipo_entidad"] == "Lugar" for l in lugares)


def test_genera_una_arista_por_salto():
    _, jerarquias = expand_lugar_ancestors(CIUDAD, "test")
    assert len(jerarquias) == 2
    assert jerarquias[0]["child_key"] == CIUDAD
    assert jerarquias[0]["parent_key"] == "lugar:PROVINCIA:buenos_aires|lugar:PAIS:argentina"
    assert jerarquias[1]["parent_key"] == "lugar:PAIS:argentina"


def test_clave_sin_padre_no_genera_jerarquia():
    lugares, jerarquias = expand_lugar_ancestors("lugar:PAIS:argentina", "test")
    assert len(lugares) == 1
    assert jerarquias == []

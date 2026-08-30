from __future__ import annotations

from zona4_graph_loader.pipeline.load_graph import contar_eventos_huerfanos


def test_evento_con_lugar_existente_no_es_huerfano():
    dataset = {
        "lugares": [{"lugar_key": "lugar:CCD:olimpo", "tipo_entidad": "Lugar"}],
        "eventos_espaciales": [
            {"persona_key": "p:1", "lugar_key": "lugar:CCD:olimpo",
             "tipo_relacion": "PRESENTE_EN", "origen": "test"}
        ],
    }
    assert contar_eventos_huerfanos(dataset) == []


def test_evento_sin_lugar_es_huerfano():
    dataset = {
        "lugares": [{"lugar_key": "lugar:CCD:olimpo", "tipo_entidad": "Lugar"}],
        "eventos_espaciales": [
            {"persona_key": "p:1", "lugar_key": "lugar:CCD:inexistente",
             "tipo_relacion": "PRESENTE_EN", "origen": "test"}
        ],
    }
    huerfanos = contar_eventos_huerfanos(dataset)
    assert len(huerfanos) == 1
    assert huerfanos[0]["lugar_key"] == "lugar:CCD:inexistente"


def test_skip_lugares_marca_todos_los_eventos_como_huerfanos():
    """Con --skip-lugares el batch que escribe :Lugar y el que enlaza
    eventos espaciales no corren, sin importar si el lugar_key existe en el
    CDM consolidado (los builders de nuevas fuentes lo agregan de todos
    modos). Todo evento debe reportarse como huérfano.
    """
    dataset = {
        "lugares": [{"lugar_key": "lugar:CCD:olimpo", "tipo_entidad": "Lugar"}],
        "eventos_espaciales": [
            {"persona_key": "p:1", "lugar_key": "lugar:CCD:olimpo",
             "tipo_relacion": "SECUESTRADO_EN", "origen": "test"}
        ],
    }
    # Sin el flag, el lugar existe en el CDM y el evento no es huérfano.
    assert contar_eventos_huerfanos(dataset) == []
    # Con --skip-lugares, ese mismo evento nunca se va a escribir.
    huerfanos = contar_eventos_huerfanos(dataset, lugares_se_escriben=False)
    assert len(huerfanos) == 1
    assert huerfanos[0]["lugar_key"] == "lugar:CCD:olimpo"


def test_alias_y_direcciones_no_cuentan_como_lugares():
    dataset = {
        "lugares": [
            {"alias_key": "alias:1", "tipo_entidad": "AliasLugar",
             "lugar_key": "lugar:CIUDAD:x"},
        ],
        "eventos_espaciales": [
            {"persona_key": "p:1", "lugar_key": "lugar:CIUDAD:x",
             "tipo_relacion": "PRESENTE_EN", "origen": "test"}
        ],
    }
    assert len(contar_eventos_huerfanos(dataset)) == 1

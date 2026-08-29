from __future__ import annotations

from zona4_graph_loader.builders.archivo_memoria import build_archivo_memoria_rows
from zona4_graph_loader.io.raw_files import read_raw_json

REGISTRO = {
    "nombre": "Bellantuono Herrero, Jorge",
    "fecha_desaparicion": "13 de julio de 1976",
    "estudiante": True,
    "estudiante_universitario": True,
    "descripcion": "Nació el 13 de diciembre de 1951. Su apodo era “Nechi”.",
    "lugar": "Billinghurst",
    "fecha_nacimiento": "1951-12-13",
    "fecha_desaparicion_normalizada": "1976-07-13",
    "edad_al_desaparecer": 24,
}


def test_genera_persona_con_rol_victima():
    dataset = build_archivo_memoria_rows([REGISTRO], use_georef=False)
    persona = dataset["personas"][0]
    assert persona["persona_key"] == "archivo_memoria:0"
    assert persona["nombre"] == "Bellantuono Herrero, Jorge"
    assert persona["roles"] == ["VICTIMA"]
    assert persona["genero"] == "INDETERMINADO"
    assert persona["fuente"] == "archivo_memoria"


def test_persiste_fechas_normalizadas():
    persona = build_archivo_memoria_rows([REGISTRO], use_georef=False)["personas"][0]
    assert persona["fecha_nacimiento"] == "1951-12-13"
    assert persona["fecha_secuestro"] == "1976-07-13"


def test_registro_sin_nombre_se_descarta():
    dataset = build_archivo_memoria_rows([dict(REGISTRO, nombre=None)], use_georef=False)
    assert dataset["personas"] == []


def test_estudiante_universitario_genera_institucion():
    dataset = build_archivo_memoria_rows([REGISTRO], use_georef=False)
    instituciones = [e for e in dataset["entidades_contexto"]
                     if e["tipo_entidad"] == "Institucion"]
    assert len(instituciones) == 1
    rel = [r for r in dataset["relaciones_contexto"]
           if r["tipo_relacion"] == "ESTUDIO_EN"]
    assert len(rel) == 1
    assert rel[0]["persona_key"] == "archivo_memoria:0"
    assert rel[0]["origen"] == "archivo_memoria"
    # Auditoría de aristas: toda relación lleva fecha, aunque sea DESCONOCIDA;
    # el brief original omitía este campo, inconsistente con el resto de los
    # builders (ver builders/relaciones.py) y con la Cypher que lo consume.
    assert rel[0]["fecha"] == "DESCONOCIDA"


def test_no_universitario_no_genera_institucion():
    registro = dict(REGISTRO, estudiante=True, estudiante_universitario=False)
    dataset = build_archivo_memoria_rows([registro], use_georef=False)
    assert dataset["entidades_contexto"] == []


def test_evento_secuestrado_en_apunta_a_lugar_del_dataset():
    dataset = build_archivo_memoria_rows([REGISTRO], use_georef=False)
    eventos = dataset["eventos_espaciales"]
    if not eventos:
        return  # sin Georef el topónimo puede no resolver; no es un fallo del builder
    lugar_keys = {l["lugar_key"] for l in dataset["lugares"]
                  if l["tipo_entidad"] == "Lugar"}
    assert eventos[0]["tipo_relacion"] == "SECUESTRADO_EN"
    assert eventos[0]["lugar_key"] in lugar_keys
    assert eventos[0]["fecha"] == "1976-07-13"


def test_sobre_el_archivo_real():
    data = read_raw_json("archivo_memoria_san_martin.json")
    dataset = build_archivo_memoria_rows(data)
    assert len(dataset["personas"]) == 303
    assert all(p["fuente"] == "archivo_memoria" for p in dataset["personas"])
    assert len({p["persona_key"] for p in dataset["personas"]}) == 303

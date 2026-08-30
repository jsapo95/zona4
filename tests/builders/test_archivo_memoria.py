from __future__ import annotations

from zona4_graph_loader.builders.archivo_memoria import build_archivo_memoria_rows
from zona4_graph_loader.io.raw_files import read_raw_json

REGISTRO = {
    "nombre": "Bellantuono Herrero, Jorge",
    "fecha_desaparicion": "13 de julio de 1976",
    "estudiante": True,
    "estudiante_universitario": True,
    "descripcion": (
        "Nació el 13 de diciembre de 1951. Su apodo era “Nechi”. Tenía 24 "
        "años cuando fue secuestrado el 13 de julio de 1976 en la vía "
        "pública, en Barrancas de Belgrano."
    ),
    "lugar": "Billinghurst",
    "fecha_nacimiento": "1951-12-13",
    "fecha_desaparicion_normalizada": "1976-07-13",
    "edad_al_desaparecer": 24,
}


def test_genera_persona_con_rol_victima():
    dataset = build_archivo_memoria_rows([REGISTRO])
    persona = dataset["personas"][0]
    assert persona["persona_key"] == "archivo_memoria:0"
    assert persona["nombre"] == "Bellantuono Herrero, Jorge"
    assert persona["roles"] == ["VICTIMA"]
    assert persona["genero"] == "INDETERMINADO"
    assert persona["fuente"] == "archivo_memoria"


def test_persiste_fechas_normalizadas():
    persona = build_archivo_memoria_rows([REGISTRO])["personas"][0]
    assert persona["fecha_nacimiento"] == "1951-12-13"
    assert persona["fecha_secuestro"] == "1976-07-13"


def test_registro_sin_nombre_se_descarta():
    dataset = build_archivo_memoria_rows([dict(REGISTRO, nombre=None)])
    assert dataset["personas"] == []


def test_estudiante_universitario_se_persiste_como_atributo_no_como_institucion():
    """Fix E (auditoría C5, hallazgo I4): `estudiante_universitario` es un
    booleano en la fuente, no el nombre de una institución. Antes de este
    fix, el builder materializaba un único nodo
    `:Institución "UNIVERSIDAD SIN ESPECIFICAR"` y conectaba a él a las 56
    personas con este campo en `true` -afirmando una institución que la
    fuente nunca nombra y relacionando falsamente entre sí a esas 56
    personas. Ahora es sólo un atributo de `Persona`.
    """
    dataset = build_archivo_memoria_rows([REGISTRO])
    persona = dataset["personas"][0]
    assert persona["estudiante_universitario"] is True
    assert dataset.get("entidades_contexto", []) == []
    assert dataset.get("relaciones_contexto", []) == []


def test_ausencia_del_campo_no_afirma_false():
    # La fuente nunca trae `estudiante_universitario: false` -está ausente en
    # 247 de 303 registros. No hay que inventar ese valor: el atributo debe
    # quedar ausente en la persona, no en `False`.
    registro = dict(REGISTRO)
    del registro["estudiante_universitario"]
    dataset = build_archivo_memoria_rows([registro])
    persona = dataset["personas"][0]
    assert "estudiante_universitario" not in persona


def test_no_genera_ningun_evento_espacial_ni_lugar():
    """Fix B (auditoría C2): `lugar` es la categoría barrial con la que el
    archivo municipal organiza cada ficha (11 valores para 303 registros,
    todos barrios del Partido de San Martín), no el lugar del secuestro. En
    el propio registro de ejemplo (Bellantuono), `lugar` dice "Billinghurst"
    pero `descripcion` dice explícitamente que fue secuestrado en
    "Barrancas de Belgrano" (CABA, otra jurisdicción) -contradicción real de
    la fuente, no hipotética. El builder ya no genera ninguna arista
    geográfica ni nodo :Lugar a partir de este campo.
    """
    dataset = build_archivo_memoria_rows([REGISTRO])
    assert dataset.get("eventos_espaciales", []) == []
    assert dataset.get("lugares", []) == []
    assert dataset.get("jerarquias", []) == []


def test_sobre_el_archivo_real():
    data = read_raw_json("archivo_memoria_san_martin.json")
    dataset = build_archivo_memoria_rows(data)
    assert len(dataset["personas"]) == 303
    assert all(p["fuente"] == "archivo_memoria" for p in dataset["personas"])
    assert len({p["persona_key"] for p in dataset["personas"]}) == 303
    # Fix B: cero aristas geográficas desde esta fuente (antes 303
    # SECUESTRADO_EN); la fecha de desaparición sigue viva en
    # Persona.fecha_secuestro para cada registro que la trae.
    assert dataset.get("eventos_espaciales", []) == []
    assert dataset.get("lugares", []) == []
    con_fecha = [p for p in dataset["personas"] if p["fecha_secuestro"]]
    assert len(con_fecha) == 303
    # Hallazgo I4: 56 de 303 registros reales traen `estudiante_universitario:
    # true`; ninguno debe generar entidad ni relación de contexto.
    universitarios = [p for p in dataset["personas"] if p.get("estudiante_universitario") is True]
    assert len(universitarios) == 56
    assert dataset.get("entidades_contexto", []) == []
    assert dataset.get("relaciones_contexto", []) == []

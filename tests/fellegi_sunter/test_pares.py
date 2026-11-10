from __future__ import annotations

import itertools

from zona4_graph_loader.fellegi_sunter.comparaciones import NIVELES
from zona4_graph_loader.fellegi_sunter.pares import (
    Registro,
    construir_registros,
    generar_pares,
    nombres_largos_parque,
    pasa_filtro,
    patron,
)


def _persona(key, nombre, fuente, roles=("VICTIMA",), **extra):
    return {"persona_key": key, "nombre": nombre, "fuente": fuente, "roles": list(roles), **extra}


def test_construir_registros_toma_fechas_de_aristas_y_centros():
    dataset = {
        "personas": [
            _persona("registro:1", "Pérez, Juan", "detalles_personas"),
            _persona("minjus_victima:1", "Pérez, Juan", "minjus_victimas", fecha_secuestro="1976-05-04"),
            _persona("nietx:1", "Toranzo - Palacín", "nietxs_relacion", roles=("NIETX",)),
            _persona("registro:2", "Sin Coma Juan", "detalles_personas"),
        ],
        "eventos_espaciales": [
            {"persona_key": "registro:1", "lugar_key": "lugar:x", "tipo_relacion": "SECUESTRADO_EN",
             "fecha": "1976-05-04"},
            {"persona_key": "registro:1", "lugar_key": "lugar:CCD:a", "tipo_relacion": "PRESENTE_EN",
             "fecha": "1976-05-04"},
        ],
    }
    registros = {r.clave: r for r in construir_registros(dataset)}
    assert set(registros) == {"registro:1", "minjus_victima:1"}, "sin Abuelas y sin nombres sin coma"
    assert registros["registro:1"].fecha_secuestro == registros["minjus_victima:1"].fecha_secuestro
    assert registros["registro:1"].centro == frozenset({"lugar:CCD:a"})


def _registros(filas):
    dataset = {"personas": [_persona(*fila[:3], **(fila[3] if len(fila) > 3 else {})) for fila in filas]}
    return construir_registros(dataset)


def test_generar_pares_reglas_de_exclusion():
    registros = _registros([
        ("registro:1", "Pérez, Juan", "detalles_personas"),
        ("registro:2", "Pérez, Juan", "detalles_personas"),            # misma fuente
        ("minjus_victima:1", "Pérez, Juan", "minjus_victimas"),
        ("juicios_condenado:1", "Pérez, Juan", "juicios_condenados", {"roles": ["REPRESOR"]}),
        ("archivo_memoria:1", "Gómez, Juan", "archivo_memoria"),        # apellido distinto
    ])
    claves = {tuple(sorted((a.clave, b.clave))) for a, b, _ in generar_pares(registros)}
    assert claves == {("minjus_victima:1", "registro:1"), ("minjus_victima:1", "registro:2")}


def test_generar_pares_coincide_con_recorrer_todos_los_pares():
    """El índice no pierde ni agrega pares respecto de comparar todo contra todo."""
    nombres = [
        "Castiñeira, Ana", "Castineyra, Ana", "Godoy Ruiz, Luis", "Godoy, Luis", "Ruiz, Pedro",
        "Li, Wen", "Lu, Wen", "Perez, Juan", "Peres Gomez, Juan", "Gomes, Juan", "Diaz, Rosa",
        "Dias, Rosa", "Rodriguez, Ana", "Rodrigues Paz, Ana", "Paz, Ana",
    ]
    fuentes = ["detalles_personas", "minjus_victimas", "archivo_memoria"]
    registros = _registros([
        (f"k:{i}:{f}", n, f) for i, (n, f) in enumerate(itertools.product(nombres, fuentes))
    ])
    esperado = {
        (a.clave, b.clave)
        for a, b in itertools.combinations(registros, 2)
        if a.fuente != b.fuente and pasa_filtro(a, b)
    }
    obtenido = {(a.clave, b.clave) for a, b, _ in generar_pares(registros)}
    assert obtenido == esperado
    assert len(obtenido) > 0


def test_apellido_largo_del_parque_cambia_el_nivel_pero_no_el_filtro():
    dataset = {"personas": [
        _persona("registro:1", "Abad, Ana Catalina", "detalles_personas"),
        _persona("minjus_victima:1", "Abad Scarlatta, Ana Catalina", "minjus_victimas"),
        _persona("minjus_victima:2", "Abad Coronel, Ana Catalina", "minjus_victimas"),
        _persona("archivo_memoria:1", "Scarlatta, Ana", "archivo_memoria"),
    ]}
    largos = nombres_largos_parque([
        {"registro": 1, "detalle": {"descripcion_nombre": "Ana Catalina Abad Scarlatta"}},
    ])
    registros = {r.clave: r for r in construir_registros(dataset, largos)}
    parque = registros["registro:1"]
    assert parque.apellido == frozenset({"abad", "scarlatta"})
    assert parque.apellido_base == frozenset({"abad"})
    assert registros["minjus_victima:1"].apellido_base is None, "sólo cambia quien tiene nombre largo"

    niveles = {
        (a.clave, b.clave): NIVELES["apellido"][g[0]]
        for a, b, g in generar_pares(list(registros.values()))
    }
    assert niveles[("registro:1", "minjus_victima:1")] == "exacto"   # antes: contenido
    assert niveles[("registro:1", "minjus_victima:2")] == "comparte"  # antes: contenido
    # El filtro mira el apellido base: "Scarlatta" sólo no alcanza para comparar
    # con el registro del Parque, aunque su apellido completo lo tenga.
    assert ("registro:1", "archivo_memoria:1") not in niveles


def test_patron_sigue_el_orden_de_campos():
    a = Registro("a", "detalles_personas", frozenset({"VICTIMA"}), frozenset({"perez"}),
                 frozenset({"juan"}), None, None, None)
    b = Registro("b", "minjus_victimas", frozenset({"VICTIMA"}), frozenset({"perez"}),
                 frozenset({"juan", "carlos"}), None, None, None)
    assert patron(a, b) == (0, 1, None, None, None)

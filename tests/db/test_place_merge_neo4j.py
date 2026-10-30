"""Regresión: la fusión de ciudades perdía aristas (2026-10-28).

`CYPHER_APPLY_SAFE_PLACE_MERGES` trasladaba una lista fija de tipos de arista
del `Lugar` fusionado (`src`) al que queda (`dst`) y después hacía `DETACH
DELETE src`. Todo tipo fuera de la lista se borraba en silencio: NACIO_EN
(verificado en el grafo: 2.159 nacimientos cargando sin fusionar, 2.158
fusionando), PARIO_EN, MURIO_EN, LIBERADO_EN y UBICADA_EN. Los hechos que sí
se trasladaban perdían `fecha_fin` y `precision_fecha`.

Estos tests corren la consulta real contra un Neo4j con APOC. No hay una base
en el suite por defecto, así que se saltean salvo que se defina
NEO4J_TEST_URI (y NEO4J_TEST_PASSWORD). Sólo crean y borran nodos marcados
con la propiedad `tid`, y además se niegan a correr si la base tiene
cualquier otro nodo: nunca apuntarlos al grafo del proyecto.

    docker run -d --name neo4j-zona4-test -p 27687:7687 \\
        -e NEO4J_AUTH=neo4j/zona4test \\
        -e NEO4J_dbms_security_procedures_unrestricted='apoc.*' \\
        -v zona_4_san_martin_neo4j_plugins:/plugins:ro neo4j:5
    NEO4J_TEST_URI=bolt://localhost:27687 NEO4J_TEST_PASSWORD=zona4test pytest -m neo4j
"""
from __future__ import annotations

import os
import random
from typing import Any, Dict, Iterator, List, Tuple

import pytest

from zona4_graph_loader.db.cypher import CYPHER_APPLY_SAFE_PLACE_MERGES
from zona4_graph_loader.db.writer import run_batches

neo4j = pytest.importorskip("neo4j")

pytestmark = [
    pytest.mark.neo4j,
    pytest.mark.skipif(
        not os.getenv("NEO4J_TEST_URI"),
        reason="NEO4J_TEST_URI no definida: tests de integración con Neo4j desactivados",
    ),
]

# Hechos Persona -> Lugar del modelo (NEO4J_DATA_MODEL.md §3.3).
TIPOS_PERSONA_LUGAR = [
    "NACIO_EN",
    "SECUESTRADO_EN",
    "ASESINADO_EN",
    "PRESENTE_EN",
    "PARIO_EN",
    "MURIO_EN",
    "LIBERADO_EN",
]

Arista = Tuple[str, str, Tuple[Tuple[str, Any], ...], str]


@pytest.fixture(scope="module")
def driver() -> Iterator[Any]:
    uri = os.environ["NEO4J_TEST_URI"]
    user = os.getenv("NEO4J_TEST_USERNAME", "neo4j")
    password = os.getenv("NEO4J_TEST_PASSWORD", "")
    drv = neo4j.GraphDatabase.driver(uri, auth=(user, password))
    with drv.session() as s:
        ajenos = s.run("MATCH (n) WHERE n.tid IS NULL RETURN count(n) AS c").single()["c"]
    if ajenos:
        drv.close()
        pytest.fail(
            f"La base de NEO4J_TEST_URI tiene {ajenos} nodos que no son de test: "
            "estos tests sólo corren contra una base descartable."
        )
    yield drv
    drv.close()


@pytest.fixture
def session(driver: Any) -> Iterator[Any]:
    with driver.session() as s:
        s.run("MATCH (n) WHERE n.tid IS NOT NULL DETACH DELETE n").consume()
        yield s
        s.run("MATCH (n) WHERE n.tid IS NOT NULL DETACH DELETE n").consume()


# --- helpers ---------------------------------------------------------------


def lugar(s: Any, key: str, **props: Any) -> None:
    s.run(
        "CREATE (l:Lugar {tid: $k, lugar_key: $k}) SET l += $p",
        k=key,
        p=props,
    ).consume()


def nodo(s: Any, label: str, tid: str) -> None:
    # Las labels no se parametrizan en Cypher; sólo se llama con literales del test.
    s.run(f"CREATE (:`{label}` {{tid: $t}})", t=tid).consume()


def arista(s: Any, a: str, tipo: str, b: str, **props: Any) -> None:
    s.run(
        f"MATCH (a {{tid: $a}}), (b {{tid: $b}}) CREATE (a)-[r:`{tipo}`]->(b) SET r = $p",
        a=a,
        b=b,
        p=props,
    ).consume()


def fusionar(s: Any, *pares: Tuple[str, str], batch_size: int = 500) -> None:
    rows = [
        {"source_key": src, "target_key": dst, "reason": "test", "score": 1.0}
        for src, dst in pares
    ]
    run_batches(s, CYPHER_APPLY_SAFE_PLACE_MERGES, rows, "test_fusion", batch_size)


def aristas(s: Any) -> List[Arista]:
    res = s.run(
        "MATCH (a)-[r]->(b) WHERE a.tid IS NOT NULL AND b.tid IS NOT NULL "
        "RETURN a.tid AS a, type(r) AS t, properties(r) AS p, b.tid AS b"
    )
    return sorted((x["a"], x["t"], tuple(sorted(x["p"].items())), x["b"]) for x in res)


def existe(s: Any, tid: str) -> bool:
    return s.run("MATCH (n {tid: $t}) RETURN count(n) AS c", t=tid).single()["c"] == 1


def props(**kw: Any) -> Tuple[Tuple[str, Any], ...]:
    return tuple(sorted(kw.items()))


# --- el caso reportado -----------------------------------------------------


def test_nacio_en_se_traslada_al_lugar_que_queda(session):
    lugar(session, "ciudad_a")
    lugar(session, "ciudad_b")
    nodo(session, "Persona", "p1")
    arista(session, "p1", "NACIO_EN", "ciudad_a", fecha="1950-01-01", origen="parque")

    fusionar(session, ("ciudad_a", "ciudad_b"))

    assert not existe(session, "ciudad_a")
    assert aristas(session) == [
        ("p1", "NACIO_EN", props(fecha="1950-01-01", origen="parque"), "ciudad_b")
    ]


@pytest.mark.parametrize("tipo", TIPOS_PERSONA_LUGAR)
def test_cada_hecho_persona_lugar_sobrevive_la_fusion(session, tipo):
    lugar(session, "src")
    lugar(session, "dst")
    nodo(session, "Persona", "p1")
    nodo(session, "Persona", "p2")
    arista(session, "p1", tipo, "src", fecha="1976-05-01", origen="o1")
    arista(session, "p2", tipo, "src", fecha="DESCONOCIDA", origen="o2")

    fusionar(session, ("src", "dst"))

    assert aristas(session) == [
        ("p1", tipo, props(fecha="1976-05-01", origen="o1"), "dst"),
        ("p2", tipo, props(fecha="DESCONOCIDA", origen="o2"), "dst"),
    ]


@pytest.mark.parametrize("tipo", ["PRESENTE_EN", "PARIO_EN"])
def test_se_conservan_fecha_fin_y_precision_fecha(session, tipo):
    # Antes el traslado copiaba sólo fecha y origen.
    lugar(session, "src")
    lugar(session, "dst")
    nodo(session, "Persona", "p1")
    p = dict(fecha="1978-01-01", fecha_fin="1978-02-28", precision_fecha="MONTH", origen="ccds_json")
    arista(session, "p1", tipo, "src", **p)

    fusionar(session, ("src", "dst"))

    assert aristas(session) == [("p1", tipo, props(**p), "dst")]


def test_hechos_de_varios_tipos_en_la_misma_ciudad(session):
    lugar(session, "src")
    lugar(session, "dst")
    nodo(session, "Persona", "p1")
    for i, tipo in enumerate(TIPOS_PERSONA_LUGAR):
        arista(session, "p1", tipo, "src", fecha=f"197{i}-01-01", origen="o")

    fusionar(session, ("src", "dst"))

    got = aristas(session)
    assert sorted(t for _, t, _, _ in got) == sorted(TIPOS_PERSONA_LUGAR)
    assert {b for _, _, _, b in got} == {"dst"}


# --- aristas estructurales -------------------------------------------------


@pytest.mark.parametrize("label", ["DirecciónCCD", "Institución"])
def test_ubicada_en_se_traslada(session, label):
    lugar(session, "src")
    lugar(session, "dst")
    nodo(session, label, "x1")
    arista(session, "x1", "UBICADA_EN", "src", fecha="ETERNA", origen="normalizacion_lugar")

    fusionar(session, ("src", "dst"))

    assert aristas(session) == [
        ("x1", "UBICADA_EN", props(fecha="ETERNA", origen="normalizacion_lugar"), "dst")
    ]


def test_alias_de_se_traslada(session):
    lugar(session, "src")
    lugar(session, "dst")
    nodo(session, "AliasLugar", "al1")
    arista(session, "al1", "ALIAS_DE", "src", fecha="ETERNA", origen="alias")

    fusionar(session, ("src", "dst"))

    assert aristas(session) == [("al1", "ALIAS_DE", props(fecha="ETERNA", origen="alias"), "dst")]


def test_parte_de_saliente_hacia_el_partido(session):
    lugar(session, "src")
    lugar(session, "dst")
    lugar(session, "partido")
    arista(session, "src", "PARTE_DE", "partido", fecha="ETERNA", origen="normalizacion_lugar")

    fusionar(session, ("src", "dst"))

    assert aristas(session) == [
        ("dst", "PARTE_DE", props(fecha="ETERNA", origen="normalizacion_lugar"), "partido")
    ]


def test_parte_de_entrante_desde_un_barrio(session):
    lugar(session, "src")
    lugar(session, "dst")
    lugar(session, "barrio")
    arista(session, "barrio", "PARTE_DE", "src", fecha="ETERNA", origen="normalizacion_lugar")

    fusionar(session, ("src", "dst"))

    assert aristas(session) == [
        ("barrio", "PARTE_DE", props(fecha="ETERNA", origen="normalizacion_lugar"), "dst")
    ]


def test_parte_de_que_dst_ya_tiene_no_se_duplica(session):
    # Las dos ciudades son del mismo partido: después de fusionar debe quedar
    # una sola PARTE_DE, con las propiedades de la de `src` (comportamiento
    # previo de la lista fija, que se mantiene).
    lugar(session, "src")
    lugar(session, "dst")
    lugar(session, "partido")
    arista(session, "src", "PARTE_DE", "partido", fecha="ETERNA", origen="de_src")
    arista(session, "dst", "PARTE_DE", "partido", fecha="ETERNA", origen="de_dst")

    fusionar(session, ("src", "dst"))

    assert aristas(session) == [
        ("dst", "PARTE_DE", props(fecha="ETERNA", origen="de_src"), "partido")
    ]


def test_ubicada_en_que_dst_ya_tiene_no_se_duplica(session):
    lugar(session, "src")
    lugar(session, "dst")
    nodo(session, "DirecciónCCD", "d1")
    arista(session, "d1", "UBICADA_EN", "src", fecha="ETERNA", origen="normalizacion_lugar")
    arista(session, "d1", "UBICADA_EN", "dst", fecha="ETERNA", origen="normalizacion_lugar")

    fusionar(session, ("src", "dst"))

    assert aristas(session) == [
        ("d1", "UBICADA_EN", props(fecha="ETERNA", origen="normalizacion_lugar"), "dst")
    ]


# --- identidad de los hechos -----------------------------------------------


def test_duplicado_exacto_en_dst_se_colapsa(session):
    lugar(session, "src")
    lugar(session, "dst")
    nodo(session, "Persona", "p1")
    p = dict(fecha="1950-01-01", origen="parque")
    arista(session, "p1", "NACIO_EN", "src", **p)
    arista(session, "p1", "NACIO_EN", "dst", **p)

    fusionar(session, ("src", "dst"))

    assert aristas(session) == [("p1", "NACIO_EN", props(**p), "dst")]


@pytest.mark.parametrize(
    "en_src, en_dst",
    [
        (dict(fecha="1976-05-01", origen="o"), dict(fecha="1976-06-01", origen="o")),
        (dict(fecha="1976-05-01", origen="o1"), dict(fecha="1976-05-01", origen="o2")),
        (
            dict(fecha="1978-01-01", fecha_fin="1978-02-28", origen="o"),
            dict(fecha="1978-01-01", origen="o"),
        ),
        # Al revés: el de dst tiene propiedades de más. Un MERGE matchea por
        # subconjunto y se tragaba el de src (lo encontró el test al azar).
        (
            dict(fecha="1978-01-01", origen="o"),
            dict(fecha="1978-01-01", fecha_fin="1978-02-28", origen="o"),
        ),
    ],
    ids=["distinta_fecha", "distinto_origen", "src_con_fecha_fin", "dst_con_fecha_fin"],
)
def test_hechos_que_difieren_se_conservan_los_dos(session, en_src, en_dst):
    lugar(session, "src")
    lugar(session, "dst")
    nodo(session, "Persona", "p1")
    arista(session, "p1", "SECUESTRADO_EN", "src", **en_src)
    arista(session, "p1", "SECUESTRADO_EN", "dst", **en_dst)

    fusionar(session, ("src", "dst"))

    assert aristas(session) == sorted(
        [
            ("p1", "SECUESTRADO_EN", props(**en_src), "dst"),
            ("p1", "SECUESTRADO_EN", props(**en_dst), "dst"),
        ]
    )


def test_tipo_de_arista_desconocido_tambien_se_traslada(session):
    # El traslado es genérico: un tipo nuevo no necesita tocar la consulta.
    lugar(session, "src")
    lugar(session, "dst")
    nodo(session, "Persona", "p1")
    lugar(session, "otro")
    arista(session, "p1", "TIPO_NUEVO_EN", "src", origen="futuro")
    arista(session, "src", "LIMITA_CON", "otro", origen="futuro")

    fusionar(session, ("src", "dst"))

    assert aristas(session) == [
        ("dst", "LIMITA_CON", props(origen="futuro"), "otro"),
        ("p1", "TIPO_NUEVO_EN", props(origen="futuro"), "dst"),
    ]


def test_arista_sin_propiedades(session):
    lugar(session, "src")
    lugar(session, "dst")
    nodo(session, "Persona", "p1")
    arista(session, "p1", "NACIO_EN", "src")

    fusionar(session, ("src", "dst"))

    assert aristas(session) == [("p1", "NACIO_EN", (), "dst")]


# --- bordes ----------------------------------------------------------------


def test_aristas_entre_src_y_dst_no_quedan_como_lazo(session):
    lugar(session, "src")
    lugar(session, "dst")
    arista(session, "src", "PARTE_DE", "dst", fecha="ETERNA", origen="x")
    arista(session, "dst", "LIMITA_CON", "src", origen="x")
    arista(session, "src", "LIMITA_CON", "src", origen="x")

    fusionar(session, ("src", "dst"))

    assert not existe(session, "src")
    assert aristas(session) == []


def test_propiedades_de_dst_no_cambian_y_src_desaparece(session):
    lugar(session, "src", nombre="SAN MARTIN", tipoGeopolitico="CIUDAD")
    lugar(session, "dst", nombre="GENERAL SAN MARTIN", tipoGeopolitico="CIUDAD")

    fusionar(session, ("src", "dst"))

    assert not existe(session, "src")
    p = session.run("MATCH (l {tid: 'dst'}) RETURN properties(l) AS p").single()["p"]
    assert p == {"tid": "dst", "lugar_key": "dst", "nombre": "GENERAL SAN MARTIN", "tipoGeopolitico": "CIUDAD"}


def test_fuente_inexistente_no_hace_nada(session):
    lugar(session, "dst")
    nodo(session, "Persona", "p1")
    arista(session, "p1", "NACIO_EN", "dst", origen="o")
    antes = aristas(session)

    fusionar(session, ("no_existe", "dst"))

    assert existe(session, "dst")
    assert aristas(session) == antes


def test_destino_inexistente_no_borra_la_fuente(session):
    lugar(session, "src")
    nodo(session, "Persona", "p1")
    arista(session, "p1", "NACIO_EN", "src", origen="o")
    antes = aristas(session)

    fusionar(session, ("src", "no_existe"))

    assert existe(session, "src")
    assert aristas(session) == antes


def test_fuente_igual_a_destino_no_borra_el_lugar(session):
    lugar(session, "a")
    nodo(session, "Persona", "p1")
    arista(session, "p1", "NACIO_EN", "a", origen="o")
    antes = aristas(session)

    fusionar(session, ("a", "a"))

    assert existe(session, "a")
    assert aristas(session) == antes


def test_varias_fuentes_al_mismo_destino_en_un_batch(session):
    for k in ("a", "b", "c", "dst"):
        lugar(session, k)
    nodo(session, "Persona", "p1")
    arista(session, "p1", "NACIO_EN", "a", origen="o1")
    arista(session, "p1", "SECUESTRADO_EN", "b", origen="o2")
    arista(session, "p1", "SECUESTRADO_EN", "c", origen="o2")  # duplicado exacto del de "b"

    fusionar(session, ("a", "dst"), ("b", "dst"), ("c", "dst"))

    assert not any(existe(session, k) for k in ("a", "b", "c"))
    assert aristas(session) == [
        ("p1", "NACIO_EN", props(origen="o1"), "dst"),
        ("p1", "SECUESTRADO_EN", props(origen="o2"), "dst"),
    ]


def test_volver_a_aplicar_la_fusion_no_cambia_nada(session):
    lugar(session, "src")
    lugar(session, "dst")
    nodo(session, "Persona", "p1")
    arista(session, "p1", "NACIO_EN", "src", origen="o")
    fusionar(session, ("src", "dst"))
    despues = aristas(session)

    fusionar(session, ("src", "dst"))

    assert aristas(session) == despues


def test_nodos_ajenos_no_se_tocan(session):
    lugar(session, "src")
    lugar(session, "dst")
    lugar(session, "otra")
    nodo(session, "Persona", "p1")
    arista(session, "p1", "NACIO_EN", "otra", origen="o")
    arista(session, "p1", "SECUESTRADO_EN", "src", origen="o")

    fusionar(session, ("src", "dst"))

    assert aristas(session) == [
        ("p1", "NACIO_EN", props(origen="o"), "otra"),
        ("p1", "SECUESTRADO_EN", props(origen="o"), "dst"),
    ]


# --- invariante sobre un grafo armado al azar --------------------------------


@pytest.mark.parametrize("seed", range(5))
@pytest.mark.parametrize("batch_size", [1, 500])
def test_invariante_ninguna_arista_se_pierde(session, seed, batch_size):
    """Cada arista que toca una ciudad fusionada aparece, redirigida, en el
    resultado; sólo se colapsan los duplicados exactos (y las estructurales
    repetidas, que acá llevan siempre las mismas propiedades)."""
    rng = random.Random(seed)
    ciudades = [f"c{i}" for i in range(8)]
    fusion = {"c1": "c0", "c2": "c0", "c3": "c0", "c5": "c4", "c7": "c6"}
    for c in ciudades:
        lugar(session, c)
    lugar(session, "partido")
    for c in ciudades:
        arista(session, c, "PARTE_DE", "partido", fecha="ETERNA", origen="normalizacion_lugar")

    creadas: set = set()
    personas = [f"p{i}" for i in range(15)]
    for p in personas:
        nodo(session, "Persona", p)
    for _ in range(80):
        a = rng.choice(personas)
        tipo = rng.choice(TIPOS_PERSONA_LUGAR)
        c = rng.choice(ciudades)
        pr: Dict[str, Any] = {
            "fecha": rng.choice(["1976-03-24", "1977-01-01", "DESCONOCIDA"]),
            "origen": rng.choice(["parque", "minjus", "ccds_json"]),
        }
        if rng.random() < 0.3:
            pr.update(fecha_fin="1978-02-28", precision_fecha="MONTH")
        clave = (a, tipo, tuple(sorted(pr.items())), c)
        if clave in creadas:
            continue
        creadas.add(clave)
        arista(session, a, tipo, c, **pr)
    for i in range(6):
        nodo(session, "DirecciónCCD", f"d{i}")
        arista(session, f"d{i}", "UBICADA_EN", rng.choice(ciudades), fecha="ETERNA", origen="normalizacion_lugar")
        nodo(session, "AliasLugar", f"al{i}")
        arista(session, f"al{i}", "ALIAS_DE", rng.choice(ciudades), fecha="ETERNA", origen="alias")

    antes = aristas(session)
    esperado = sorted({(fusion.get(a, a), t, p, fusion.get(b, b)) for a, t, p, b in antes})

    fusionar(session, *fusion.items(), batch_size=batch_size)

    despues = aristas(session)
    assert len(despues) == len(set(despues)), "quedaron aristas duplicadas"
    assert despues == esperado
    for c in fusion:
        assert not existe(session, c)
    for tipo in TIPOS_PERSONA_LUGAR:
        n_antes = len({(a, p, fusion.get(b, b)) for a, t, p, b in antes if t == tipo})
        n_despues = sum(1 for _, t, _, _ in despues if t == tipo)
        assert n_despues == n_antes, tipo

"""Regresión: "LOCALIDAD. PROVINCIA" no puede caer en la capital homónima.

Contexto del defecto: varias provincias tienen una capital con el mismo
nombre (Salta, Corrientes, La Rioja, Formosa, San Luis, San Juan, Santa Fe,
Santiago del Estero, Neuquén...). `PlaceGazetteer.resolve` matchea por
n-gramas contra la cadena entera, y el nombre de la provincia, que el texto
pone como pista ("METAN. SALTA"), también matcheaba como la localidad
capital. Ganaba la capital cuando la localidad nombrada no estaba en Georef
con ese nombre (Metán es "San José de Metán") o por desempate: por largo de
nombre ("GOYA" contra "CORRIENTES", mismo puntaje) o por tener más palabras
("SANTA FE" contra "ROSARIO" en "Domicilio (ROSARIO. SANTA FE)", donde el
Fix C no aplica por el prefijo). En `parque_de_la_memoria.json` eso ubicaba
en la capital hechos ocurridos en Metán, Orán, Palomitas, Goya, Chamical,
Rosario y otras localidades, a veces a cientos de kilómetros.

El mismo mecanismo llevaba a una capital las calles con nombre de provincia
("San Luis 2535 ... Mar del Plata", "Entre Ríos y La Rioja (Quilmes)"): la
calle se tomaba como pista de provincia y descartaba la ciudad que el texto
nombra.

Este archivo fija que:
- si el texto nombra otro lugar de la provincia, gana ése;
- si la localidad nombrada no está en Georef, se afirma sólo la provincia;
- una calle o esquina con nombre de provincia no le gana a la ciudad nombrada;
- los textos que sí nombran la capital no cambian.

Fuera de alcance (siguen como antes): "MANUEL ALBERTI. PILAR" (va al partido
de Alberti: Georef no tiene la localidad Manuel Alberti y empatan Alberti y
Pilar, ambos de Buenos Aires), "Entre San Juan y Córdoba" (esquina sin
ciudad), "San Luis y Pellegrini - Taller metalúrgico (Lugar de trabajo)
(Salta - Capital)" (la normalización borra todo lo que sigue a "lugar de
trabajo", incluida la provincia).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from zona4_graph_loader.domain.place_norm import resolve_place


REPO_ROOT = Path(__file__).resolve().parents[2]
GEOREF_CATALOG = REPO_ROOT / "data" / "processed" / "georef_catalog.json"

pytestmark = pytest.mark.skipif(
    not GEOREF_CATALOG.exists(), reason="falta data/processed/georef_catalog.json"
)

PAIS = "lugar:PAIS:argentina"


def _prov(provincia: str) -> str:
    return f"lugar:PROVINCIA:{provincia}|{PAIS}"


def _dep(departamento: str, provincia: str) -> str:
    return f"lugar:DEPARTAMENTO:{departamento}|{_prov(provincia)}"


def _ciudad(ciudad: str, departamento: str, provincia: str) -> str:
    return f"lugar:CIUDAD:{ciudad}|{_dep(departamento, provincia)}"


def _resolver(raw: str) -> str:
    place = resolve_place(raw, georef_catalog_path=GEOREF_CATALOG)
    assert place is not None
    return place["lugar_key"]


# Valores reales de `parque_de_la_memoria.json` (lugar de secuestro, de
# asesinato o de nacimiento) que antes de este fix caían en la capital de la
# provincia.
CASOS_OTRA_LOCALIDAD = [
    ("GOYA. CORRIENTES", _ciudad("goya", "goya", "corrientes")),
    ("Goya, Pcia. De Corrientes", _ciudad("goya", "goya", "corrientes")),
    ("MERCEDES. CORRIENTES", _ciudad("mercedes", "mercedes", "corrientes")),
    ("GOBERNADOR VIRASORO. CORRIENTES", f"lugar:CIUDAD:gobernador_virasoro|{_prov('corrientes')}"),
    ("ALVEAR. CORRIENTES", _ciudad("alvear", "general_alvear", "corrientes")),
    ("CHAMICAL. LA RIOJA", _ciudad("chamical", "chamical", "la_rioja")),
    ("Parroquia El Salvador (Chamical, La Rioja)", _ciudad("chamical", "chamical", "la_rioja")),
    ("PIRANE. FORMOSA", _ciudad("pirane", "pirane", "formosa")),
    ("LUJAN. SAN LUIS", _ciudad("lujan", "ayacucho", "san_luis")),
    ("LA TOMA. SAN LUIS", _ciudad("la_toma", "coronel_pringles", "san_luis")),
    ("RAWSON. SAN JUAN", _ciudad("rawson", "rawson", "san_juan")),
    ("LA BANDA. SANTIAGO DEL ESTERO", _ciudad("la_banda", "banda", "santiago_del_estero")),
    ("Domicilio (ROSARIO. SANTA FE)", _ciudad("rosario", "rosario", "santa_fe")),
    ("asesinado 15/12/76. ROSARIO. SANTA FE", _ciudad("rosario", "rosario", "santa_fe")),
    ("ROSARIO. SANTA FE (Rosario, Pcia de Santa Fé)", _ciudad("rosario", "rosario", "santa_fe")),
    ("Carreras, Gral. López, Santa Fe. Ruta Prov. N° 90", _ciudad("carreras", "general_lopez", "santa_fe")),
    (
        "TERCERO ARRIBA. CORDOBA (Secuestrado de la vía pública. En Barrio Velez Sarsfield)",
        _dep("tercero_arriba", "cordoba"),
    ),
    ("Tabacal, Orán, Salta", _dep("oran", "salta")),
    # "Ingenio San Juan" no es la provincia de San Juan.
    ("CRUZ ALTA. TUCUMAN (Ingenio San Juan, Cruz Alta, Tucumán)", _dep("cruz_alta", "tucuman")),
]


@pytest.mark.parametrize("raw,esperada", CASOS_OTRA_LOCALIDAD)
def test_otra_localidad_de_la_provincia_le_gana_a_la_capital(raw: str, esperada: str) -> None:
    assert _resolver(raw) == esperada


# Georef nombra estas localidades con el nombre largo.
CASOS_NOMBRE_LARGO = [
    ("METAN. SALTA", f"lugar:CIUDAD:san_jose_de_metan|{_prov('salta')}"),
    ("Metán, Salta", f"lugar:CIUDAD:san_jose_de_metan|{_prov('salta')}"),
    ("ORAN. SALTA", _ciudad("san_ramon_de_la_nueva_oran", "oran", "salta")),
    ("VILLA GDOR GALVEZ. SANTA FE (Rambla de Saladillo)", _ciudad("villa_gobernador_galvez", "rosario", "santa_fe")),
    ("VILLA GDOR. GALVEZ. SANTA FE", _ciudad("villa_gobernador_galvez", "rosario", "santa_fe")),
]


@pytest.mark.parametrize("raw,esperada", CASOS_NOMBRE_LARGO)
def test_localidad_con_otro_nombre_en_georef(raw: str, esperada: str) -> None:
    assert _resolver(raw) == esperada


# La localidad no está en Georef: se afirma sólo la provincia (o el
# departamento, si es lo único que el texto nombra) antes que inventar la
# capital.
CASOS_SOLO_PROVINCIA = [
    ("PALOMITAS. SALTA", _prov("salta")),
    ("VIRASORO. CORRIENTES", _prov("corrientes")),
    ("PARAJE PALMITOS. CORRIENTES", _prov("corrientes")),
    ("El ROCILLO. FORMOSA", _prov("formosa")),
    ("TORO POZO. SANTIAGO DEL ESTERO", _prov("santiago_del_estero")),
    ("Paso fronterizo (Provincia de Salta)", _prov("salta")),
    ("San Luis, provincia.", _prov("san_luis")),
    ("Confluencia, Neuquén", _dep("confluencia", "neuquen")),
]


@pytest.mark.parametrize("raw,esperada", CASOS_SOLO_PROVINCIA)
def test_localidad_no_encontrada_afirma_solo_la_provincia(raw: str, esperada: str) -> None:
    assert _resolver(raw) == esperada


# Calles y esquinas con nombre de provincia.
CASOS_CALLE = [
    (
        "Domicilio de sus padres (San Luis 2535) (Gral. Pueyrredón. Mar Del PLata. Bs. As.)",
        _ciudad("mar_del_plata", "general_pueyrredon", "buenos_aires"),
    ),
    ("Entre Ríos y La Rioja (Quilmes)", _ciudad("quilmes", "quilmes", "buenos_aires")),
    (
        "Santa Fé y Urquiza - Parada de colectivo (Acassuso - San isidro - Buenos Aires)",
        _ciudad("san_isidro", "san_isidro", "buenos_aires"),
    ),
    (
        "CAPITAL FEDERAL (San Nicolas (Corrientes y Callao))",
        f"lugar:CIUDAD:san_nicolas|lugar:DEPARTAMENTO:comuna_1|{_prov('ciudad_autonoma_de_buenos_aires')}",
    ),
]


@pytest.mark.parametrize("raw,esperada", CASOS_CALLE)
def test_calle_con_nombre_de_provincia_no_gana(raw: str, esperada: str) -> None:
    assert _resolver(raw) == esperada


SALTA = _ciudad("salta", "capital", "salta")
CORRIENTES = _ciudad("corrientes", "capital", "corrientes")
SANTA_FE = _ciudad("santa_fe", "la_capital", "santa_fe")
LA_RIOJA = _ciudad("la_rioja", "capital", "la_rioja")
FORMOSA = _ciudad("formosa", "formosa", "formosa")
SAN_LUIS = _ciudad("san_luis", "juan_martin_de_pueyrredon", "san_luis")
CORDOBA = _ciudad("cordoba", "capital", "cordoba")

# Textos que nombran la capital (o sólo la provincia, que Georef resuelve a la
# capital) y que este fix no debe cambiar.
CASOS_SIN_CAMBIOS = [
    ("SALTA", SALTA),
    ("SALTA. SALTA", SALTA),
    ("Salta, Salta", SALTA),
    ("SALTA CAPITAL", SALTA),
    ("CORRIENTES", CORRIENTES),
    ("CORRIENTES. CORRIENTES", CORRIENTES),
    ("CORRIENTES CAPITAL", CORRIENTES),
    ("SANTA FE", SANTA_FE),
    ("Santa Fe, Santa Fe", SANTA_FE),
    ("SANTA FE CAPITAL", SANTA_FE),
    ("LA RIOJA", LA_RIOJA),
    ("LA RIOJA CAPITAL", LA_RIOJA),
    ("FORMOSA (Barrio Villa Ketty, Formosa)", FORMOSA),
    ("Colón, Córdoba Capital", CORDOBA),
    ("Yapeyú - Corrientes Capital. Pje. Granaderos e/Colombia y México (Vía Pública)", CORRIENTES),
    ("SAN MARTÍN 611 (y BELGRANO)  ·  SAN LUIS · LA CAPITAL · SAN LUIS", SAN_LUIS),
    # "X DE <provincia>" es el nombre de una institución, no "LOCALIDAD. PROVINCIA".
    ("ALCAIDÍA DE MUJERES DE FORMOSA", FORMOSA),
    ("JEFATURA DE POLICÍA DE LA PROVINCIA DE SALTA", SALTA),
    ("HOSPITAL MILITAR \"SALTA\"", SALTA),
    # La provincia aparece una vez y el texto nombra una localidad del
    # departamento La Capital: gana la localidad, como antes.
    (
        "Villa California  ·  SAN JOSÉ DEL RINCÓN · LA CAPITAL · SANTA FE",
        _ciudad("san_jose_del_rincon", "la_capital", "santa_fe"),
    ),
    ("ROSARIO. SANTA FE", _ciudad("rosario", "rosario", "santa_fe")),
    ("CIUDAD EVITA. BS. AS.", _ciudad("ciudad_evita", "la_matanza", "buenos_aires")),
    ("VILLA ELISA. BS. AS.", f"lugar:CIUDAD:villa_elisa|{_prov('buenos_aires')}"),
    ("Goya", _ciudad("goya", "goya", "corrientes")),
]


@pytest.mark.parametrize("raw,esperada", CASOS_SIN_CAMBIOS)
def test_textos_que_nombran_la_capital_no_cambian(raw: str, esperada: str) -> None:
    assert _resolver(raw) == esperada

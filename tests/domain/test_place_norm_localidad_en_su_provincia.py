"""Regresión: "LOCALIDAD. PROVINCIA" se busca en la provincia que el texto nombra.

Contexto del defecto: `_resolve_explicit_province_locality` buscaba la
localidad en todo el país y después exigía que cayera en la provincia del
texto. Si la localidad tenía homónimos en otras provincias, ganaba uno de
ellos ("SAN NICOLAS" -> el barrio porteño; "AVELLANEDA" empataba entre
Buenos Aires, Córdoba y Santa Fe) y el intento se descartaba; como
`explicit_hint_consumed` bloquea el match de cadena completa, el texto
terminaba en el respaldo por sufijo de `PROVINCE_ABBR`, que armaba
`CIUDAD:<texto>|PROVINCIA:<provincia>` sin consultar Georef: una clave sin
departamento, separada del nodo de Georef de la misma ciudad ("AVELLANEDA.
BS. AS.": 93 aristas en `CIUDAD:avellaneda|PROVINCIA:buenos_aires` contra 28
en el nodo con departamento), o una ciudad que no existe ("CRUZ ALTA.
TUCUMAN" es un departamento). Además los municipios del catálogo de Georef no
traen departamento, así que resolver por municipio también dejaba la ciudad
colgada de la provincia ("METAN. SALTA", "CAMPANA. BS. AS.").

Este archivo fija que:
- la localidad se busca sólo en la provincia nombrada;
- un municipio se lleva a su localidad cabecera, con departamento;
- en el respaldo por sufijo gana un segmento del texto que sea lugar de
  Georef; un topónimo limpio que el catálogo no tiene conserva su clave
  `CIUDAD:X|PROVINCIA:Y`, y lo que no es topónimo (instituciones, calles,
  "Provincia de X") afirma sólo la provincia;
- "SAN NICOLAS. BS. AS." es San Nicolás de los Arroyos;
- un barrio porteño con "Bs As" va al barrio si el nombre es sólo de CABA, y
  a la provincia si también existe en Buenos Aires, salvo pista de CABA;
- lo que ya resolvía bien no cambia.
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


def _barrio(barrio: str, comuna: str) -> str:
    return _ciudad(barrio, comuna, "ciudad_autonoma_de_buenos_aires")


CABA = f"lugar:CIUDAD:ciudad_autonoma_de_buenos_aires|{_prov('ciudad_autonoma_de_buenos_aires')}"


def _resolver(raw: str) -> str:
    place = resolve_place(raw, georef_catalog_path=GEOREF_CATALOG)
    assert place is not None
    return place["lugar_key"]


# Valores reales de `parque_de_la_memoria.json` cuya localidad tiene
# homónimos en otras provincias: antes quedaban sin departamento.
CASOS_HOMONIMOS = [
    ("AVELLANEDA. BS. AS.", _ciudad("avellaneda", "avellaneda", "buenos_aires")),
    ("Avellaneda, Bs. As.", _ciudad("avellaneda", "avellaneda", "buenos_aires")),
    ("SAN JUSTO. BS. AS.", _ciudad("san_justo", "la_matanza", "buenos_aires")),
    ("CASTELAR. BS. AS.", _ciudad("castelar", "moron", "buenos_aires")),
    ("GODOY CRUZ. MENDOZA", _ciudad("godoy_cruz", "godoy_cruz", "mendoza")),
    ("SANTA LUCIA. TUCUMAN", _ciudad("santa_lucia", "monteros", "tucuman")),
    ("PILAR. BS. AS.", _ciudad("pilar", "pilar", "buenos_aires")),
    ("PILAR. CORDOBA", _ciudad("pilar", "rio_segundo", "cordoba")),
    ("VILLA ELISA. BS. AS.", _ciudad("villa_elisa", "la_plata", "buenos_aires")),
    ("SAN LORENZO. SANTA FE", _ciudad("san_lorenzo", "san_lorenzo", "santa_fe")),
    ("25 de mayo, BsAs", _ciudad("25_de_mayo", "25_de_mayo", "buenos_aires")),
    # No está en los datos: el homónimo de Santa Fe tampoco puede perder su
    # departamento contra el de Buenos Aires.
    ("AVELLANEDA. SANTA FE", _ciudad("avellaneda", "general_obligado", "santa_fe")),
    # "SAN MARTIN" en Buenos Aires es General San Martín.
    ("SAN MARTIN. BS. AS.", _ciudad("general_san_martin", "general_san_martin", "buenos_aires")),
    # EQUIV_CITIES da el nombre de Georef ("Villa José León Suárez").
    (
        "JOSE LEON SUAREZ. BS. AS.",
        _ciudad("villa_jose_leon_suarez", "general_san_martin", "buenos_aires"),
    ),
    # Abreviaturas de títulos.
    ("Gral. Villegas, Bs. As.", _ciudad("general_villegas", "general_villegas", "buenos_aires")),
    ("Cnel. Pringles, Bs. As.", _ciudad("coronel_pringles", "coronel_pringles", "buenos_aires")),
    ("PTE. DERQUI. BS. AS.", _ciudad("presidente_derqui", "pilar", "buenos_aires")),
    # Sin provincia se asume Buenos Aires, y también se busca ahí.
    ("Castelar", _ciudad("castelar", "moron", "buenos_aires")),
]


@pytest.mark.parametrize("raw,esperada", CASOS_HOMONIMOS)
def test_localidad_se_busca_en_su_provincia(raw: str, esperada: str) -> None:
    assert _resolver(raw) == esperada


def test_san_nicolas_bs_as_es_san_nicolas_de_los_arroyos() -> None:
    # En el Parque los barrios porteños se escriben "CAPITAL FEDERAL (San
    # Nicolas (...))", y el campo Domicilios de víctimas con este lugar dice
    # "Juan B. Justo 636 San Nicolás, Pcia De Bs As.".
    esperada = _ciudad("san_nicolas_de_los_arroyos", "san_nicolas", "buenos_aires")
    for raw in (
        "SAN NICOLAS. BS. AS.",
        "SAN NICOLAS. BS. AS. (Alberti 791 (San Nicolas))",
        "San Nicolas, Bs. As.",
        "San Nicolás - Bs As.",
    ):
        assert _resolver(raw) == esperada, raw


# Un nombre de Georef que es departamento y no ciudad: se afirma el
# departamento ("Cruz Alta" no es una ciudad de Tucumán).
CASOS_DEPARTAMENTO = [
    ("CRUZ ALTA. TUCUMAN", _dep("cruz_alta", "tucuman")),
    ("Cruz Alta, Tucumán", _dep("cruz_alta", "tucuman")),
    ("COLON. CORDOBA", _dep("colon", "cordoba")),
]


@pytest.mark.parametrize("raw,esperada", CASOS_DEPARTAMENTO)
def test_departamento_no_se_vuelve_ciudad(raw: str, esperada: str) -> None:
    assert _resolver(raw) == esperada


# Municipios de Georef (sin departamento) llevados a su localidad cabecera, o
# al departamento homónimo si el catálogo no trae la localidad.
CASOS_MUNICIPIO = [
    ("METAN. SALTA", _ciudad("san_jose_de_metan_est_metan", "metan", "salta")),
    ("Metán, Salta", _ciudad("san_jose_de_metan_est_metan", "metan", "salta")),
    (
        "GOBERNADOR VIRASORO. CORRIENTES",
        _ciudad("gobernador_igr_valentin_virasoro", "santo_tome", "corrientes"),
    ),
    ("Jachal, San Juan", _ciudad("san_jose_de_jachal", "jachal", "san_juan")),
    ("YERBA BUENA. TUCUMAN", _ciudad("yerba_buena_marcos_paz", "yerba_buena", "tucuman")),
    ("Bolívar, Bs. As.", _ciudad("san_carlos_de_bolivar", "bolivar", "buenos_aires")),
    ("CAMPANA. BS. AS.", _ciudad("campana", "campana", "buenos_aires")),
]


@pytest.mark.parametrize("raw,esperada", CASOS_MUNICIPIO)
def test_municipio_va_a_su_localidad_cabecera(raw: str, esperada: str) -> None:
    assert _resolver(raw) == esperada


# Un topónimo limpio que el catálogo del loader no tiene (asentamientos o
# barrios de Georef, o con otra grafía) conserva su clave de antes, sin
# departamento: la provincia sola perdería el nombre. La capital homónima no
# gana ("CLARKE. SANTA FE").
CASOS_TOPONIMO_FUERA_DEL_CATALOGO = [
    ("CLARKE. SANTA FE", f"lugar:CIUDAD:clarke|{_prov('santa_fe')}"),
    ("DON TORCUATO. BS. AS.", f"lugar:CIUDAD:don_torcuato|{_prov('buenos_aires')}"),
    ("VILLA LUJAN. TUCUMAN", f"lugar:CIUDAD:villa_lujan|{_prov('tucuman')}"),
    ("FERREYRA. CORDOBA", f"lugar:CIUDAD:ferreyra|{_prov('cordoba')}"),
    ("Nicanor E. Molinas, Santa Fé", f"lugar:CIUDAD:nicanor_e_molinas|{_prov('santa_fe')}"),
    # La narración que la normalización descarta no cuenta como segmento: no
    # va a Morón.
    (
        "VILLA TESEI. BS. AS. (Vivienda allanada en Luna 540, Villa Tesei, Morón, Bs. As.)",
        f"lugar:CIUDAD:villa_tesei|{_prov('buenos_aires')}",
    ),
]


@pytest.mark.parametrize("raw,esperada", CASOS_TOPONIMO_FUERA_DEL_CATALOGO)
def test_toponimo_fuera_del_catalogo_conserva_su_clave(raw: str, esperada: str) -> None:
    assert _resolver(raw) == esperada


# Si un segmento del texto es un lugar de Georef de la provincia, gana ése en
# vez de una clave armada con el texto entero.
CASOS_SEGMENTO = [
    ("Miramar - Gral. Alvarado - Bs As", _ciudad("miramar", "general_alvarado", "buenos_aires")),
    ("Junín, Provincia de Buenos Aires", _ciudad("junin", "junin", "buenos_aires")),
    ("Santa Lucia, Pcia de Tucuman", _ciudad("santa_lucia", "monteros", "tucuman")),
    ("Su estudio jurídico (San Miguel de Tucumán)", _ciudad("san_miguel_de_tucuman", "capital", "tucuman")),
    ("RECONQUISTA · GRAL. OBLIGADO · SANTA FE", _ciudad("reconquista", "general_obligado", "santa_fe")),
    ("J. B. ALBERDI. TUCUMAN", _ciudad("juan_bautista_alberdi", "juan_bautista_alberdi", "tucuman")),
]


@pytest.mark.parametrize("raw,esperada", CASOS_SEGMENTO)
def test_segmento_que_es_lugar_de_georef_gana(raw: str, esperada: str) -> None:
    assert _resolver(raw) == esperada


# Instituciones, calles y restos de prosa no son ciudades: se afirma sólo la
# provincia.
CASOS_SOLO_PROVINCIA = [
    ("Provincia de Córdoba", _prov("cordoba")),
    ('HOSPITAL MILITAR "TUCUMÁN"', _prov("tucuman")),
    ("MUNICIPALIDAD DE CÓRDOBA", _prov("cordoba")),
    ("SAN PABLO BRASIL a BUENOS AIRES", _prov("buenos_aires")),
]


@pytest.mark.parametrize("raw,esperada", CASOS_SOLO_PROVINCIA)
def test_lo_que_no_es_toponimo_afirma_solo_la_provincia(raw: str, esperada: str) -> None:
    assert _resolver(raw) == esperada


# Barrios porteños con "Bs As" o "Buenos Aires". Hoy ningún texto real de las
# fuentes cargadas los usa así; la regla tiene que estar igual.
CASOS_BARRIO_SOLO_CABA = [
    ("Palermo, Bs As", _barrio("palermo", "comuna_14")),
    ("Chacarita, Bs. As.", _barrio("chacarita", "comuna_15")),
    ("Boedo, Bs. As.", _barrio("boedo", "comuna_5")),
    ("Recoleta, Bs. As.", _barrio("recoleta", "comuna_2")),
    ("Villa Devoto, Bs As", _barrio("villa_devoto", "comuna_11")),
    ("Liniers, Buenos Aires", _barrio("liniers", "comuna_9")),
    ("Villa Pueyrredón, Bs. As.", _barrio("villa_pueyrredon", "comuna_12")),
    ("Agronomía, Bs. As.", _barrio("agronomia", "comuna_15")),
    ("Villa Real, Bs. As.", _barrio("villa_real", "comuna_10")),
    ("Barracas, Bs. As.", _barrio("barracas", "comuna_4")),
    ("Flores, Bs. As.", _barrio("flores", "comuna_7")),
    ("La Boca, Bs As", _barrio("boca", "comuna_4")),
    ("Palermo Viejo, Bs. As.", _barrio("palermo", "comuna_14")),
    # Barrios que Georef no tiene: la Ciudad, como "CAPITAL FEDERAL (Once)".
    ("Once, Bs. As.", CABA),
    ("Congreso. BS. AS.", CABA),
]


@pytest.mark.parametrize("raw,esperada", CASOS_BARRIO_SOLO_CABA)
def test_barrio_solo_porteno_con_bs_as_va_al_barrio(raw: str, esperada: str) -> None:
    assert _resolver(raw) == esperada


# El nombre existe en los dos lados: "Bs As" no alcanza para elegir.
CASOS_BARRIO_HOMONIMO = [
    ("Saavedra, Bs. As.", _prov("buenos_aires")),
    ("Abasto, Bs As", _prov("buenos_aires")),
    # Colegiales es también un asentamiento de San Pedro, que el catálogo no trae.
    ("Colegiales, Bs. As.", _prov("buenos_aires")),
    # General Belgrano.
    ("Belgrano, Buenos Aires", _prov("buenos_aires")),
    # Sin el formato del Parque ("BS. AS."), San Nicolás sigue siendo ambiguo.
    ("San Nicolás, Buenos Aires", _prov("buenos_aires")),
]


@pytest.mark.parametrize("raw,esperada", CASOS_BARRIO_HOMONIMO)
def test_barrio_homonimo_con_bs_as_afirma_solo_la_provincia(raw: str, esperada: str) -> None:
    assert _resolver(raw) == esperada


# Con una pista de CABA, el homónimo va al barrio.
CASOS_BARRIO_CON_PISTA = [
    ("Saavedra, Capital, Bs. As.", _barrio("saavedra", "comuna_12")),
    ("Saavedra (C1430), Bs As", _barrio("saavedra", "comuna_12")),
    ("Belgrano CF, Bs As", _barrio("belgrano", "comuna_13")),
    ("Colegiales, C.A.B.A., Bs As", _barrio("colegiales", "comuna_13")),
    ("Abasto, Capital, Bs As", CABA),
]


@pytest.mark.parametrize("raw,esperada", CASOS_BARRIO_CON_PISTA)
def test_barrio_homonimo_con_pista_de_caba_va_al_barrio(raw: str, esperada: str) -> None:
    assert _resolver(raw) == esperada


# Textos que ya resolvían bien y no deben cambiar.
CASOS_SIN_CAMBIOS = [
    ("LA PLATA. BS. AS.", _ciudad("la_plata", "la_plata", "buenos_aires")),
    ("LAS FLORES. BS. AS.", _ciudad("las_flores", "las_flores", "buenos_aires")),
    ("CAPITAL FEDERAL (Palermo (Plaza Italia))", _barrio("palermo", "comuna_14")),
    ("CAPITAL FEDERAL (Once)", CABA),
    (
        "CAPITAL FEDERAL (San Nicolas (Corrientes y Callao))",
        _barrio("san_nicolas", "comuna_1"),
    ),
    ("ROSARIO. SANTA FE", _ciudad("rosario", "rosario", "santa_fe")),
    ("SANTA FE. SANTA FE", _ciudad("santa_fe", "la_capital", "santa_fe")),
    ("CIUDAD EVITA. BS. AS.", _ciudad("ciudad_evita", "la_matanza", "buenos_aires")),
    ("Villa Ballester, Bs. As.", _ciudad("villa_ballester", "general_san_martin", "buenos_aires")),
    # Las capitales de EQUIV_CITIES siguen como estaban (fuera de alcance).
    ("CORDOBA CAPITAL", f"lugar:CIUDAD:cordoba|{_prov('cordoba')}"),
    ("José León Suárez", f"lugar:CIUDAD:villa_jose_leon_suarez|{_prov('buenos_aires')}"),
]


@pytest.mark.parametrize("raw,esperada", CASOS_SIN_CAMBIOS)
def test_lo_que_ya_resolvia_bien_no_cambia(raw: str, esperada: str) -> None:
    assert _resolver(raw) == esperada

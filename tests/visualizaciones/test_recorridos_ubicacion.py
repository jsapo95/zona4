"""Reglas de ubicación de la visualización de recorridos.

Cada caso salió de revisar a mano los textos reales del Parque de la Memoria:
son errores que el resolver de lugares cometía sobre texto narrativo y que
`construir_datos.py` evita.
"""

import sys
from pathlib import Path

import pytest

RECORRIDOS = Path(__file__).resolve().parents[2] / "visualizaciones" / "recorridos"
sys.path.insert(0, str(RECORRIDOS))

import construir_datos as cd  # noqa: E402


@pytest.fixture(scope="module")
def centroides():
    return cd.Centroides(cd.CENTROIDES)


@pytest.fixture(scope="module")
def sitios():
    return cd.SitiosEAAF()


def _cerca(coords, lat, lon, tolerancia=0.1):
    return coords is not None and abs(coords[0] - lat) < tolerancia and abs(coords[1] - lon) < tolerancia


def test_san_martin_de_buenos_aires_es_general_san_martin(centroides):
    # En Georef hay un paraje "San Martín" en Magdalena; la clave del grafo
    # viene de EQUIV_CITIES y se refiere al partido de General San Martín.
    coords, _ = centroides.ubicar("lugar:CIUDAD:san_martin|lugar:PROVINCIA:buenos_aires|lugar:PAIS:argentina")
    assert _cerca(coords, -34.58, -58.54)


def test_sin_departamento_y_nombre_ambiguo_no_se_ubica_por_asentamiento(centroides):
    coords, motivo = centroides.ubicar("lugar:PROVINCIA:buenos_aires|lugar:PAIS:argentina")
    assert coords is None and motivo == "solo_provincia"


def test_rio_de_la_plata_no_es_la_ciudad_de_la_plata(centroides):
    coords, _ = cd.ubicar_fragmento("Su cuerpo apareció en el Río de la Plata con herida de arma de fuego", centroides)
    assert coords is None


def test_localidad_con_provincia_no_se_muda_a_la_capital_provincial(centroides):
    coords, _ = cd.ubicar_fragmento("Cafferata y Ayolas (hoy calle Uruguay), Rosario, Santa Fe", centroides)
    assert _cerca(coords, -32.95, -60.66)  # Rosario, no la ciudad de Santa Fe


def test_interseccion_de_calles_no_engancha_ciudades_homonimas(centroides):
    # "Perito Moreno y Dellepiane" es una esquina de CABA, no Moreno (Bs. As.).
    coords, _ = cd.ubicar_fragmento("la intersección de las avenidas Perito Moreno y Dellepiane", centroides)
    assert coords is None


def test_nombre_entre_comillas_no_es_una_localidad(centroides):
    coords, _ = cd.ubicar_fragmento(
        'el paraje conocido como "La Cueva de los Leones", a 10 km. del centro de Bahía Blanca', centroides
    )
    assert _cerca(coords, -38.72, -62.27)  # Bahía Blanca, no Leones (Córdoba)


def test_capital_federal_sin_barrio_va_al_centro_de_caba(centroides):
    coords, _ = cd.ubicar_fragmento("27/07/78, Beauchef y Pedro Goyena, Capital Federal", centroides)
    assert coords is not None and coords[2] == cd.CABA_GENERICA


@pytest.mark.parametrize("texto, sitio", [
    ("Sus restos fueron exhumados en el Cementerio Municipal de Ezpeleta, La Plata", "Cementerio de Ezpeleta"),
    ("Sus restos fueron hallados en el Poozo de Vargas, Tucumán", "Pozo de Vargas"),
    ("Restos hallados enel Arsenal Miguel de Azcuénaga, Tucumán.", "Ex CCD Arsenal Miguel de Azcuénaga"),
    ("Sus restos fueron exhumados en el Cementerio de Gral. Lavalle, Bs. As.", "Cementerio de General Lavalle"),
])
def test_sitios_del_eaaf_por_alias(sitios, texto, sitio):
    assert sitios.buscar(texto)["nombre"] == sitio


def test_general_villegas_no_es_el_cementerio_de_villegas_de_la_matanza(sitios, centroides):
    texto = "Sus restos fueron exhumados en el Cementerio de Gral. Villegas, Bs. As."
    assert sitios.buscar(texto) is None
    hallazgo = cd.ubicar_hallazgo(texto, sitios, centroides)
    assert _cerca(hallazgo and (hallazgo["lat"], hallazgo["lon"]), -35.03, -63.01, tolerancia=0.2)

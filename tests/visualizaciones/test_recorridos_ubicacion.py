"""Reglas de ubicación de la visualización de recorridos.

Cada caso salió de revisar a mano los textos reales del Parque de la Memoria:
son errores que el resolver de lugares cometía sobre texto narrativo y que
`construir_datos.py` evita.
"""

import json
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


# --- Agrupación por partido (vista de recorridos frecuentes) ---------------

def test_localidades_del_mismo_partido_comparten_nodo(centroides):
    ballester, _ = centroides.ubicar(
        "lugar:CIUDAD:villa_ballester|lugar:DEPARTAMENTO:general_san_martin|lugar:PROVINCIA:buenos_aires|lugar:PAIS:argentina"
    )
    san_martin, _ = centroides.ubicar("lugar:CIUDAD:san_martin|lugar:PROVINCIA:buenos_aires|lugar:PAIS:argentina")
    assert ballester[4] == san_martin[4] == ("General San Martín", "Buenos Aires")


def test_en_caba_cada_barrio_es_un_nodo_y_sin_barrio_es_otro(centroides):
    # Con toda CABA en un solo nodo, el mapa de flujos mostraba un centro del
    # que salía todo, cuando 237 de 250 secuestros ahí no dicen el barrio.
    palermo, _ = centroides.ubicar(
        "lugar:CIUDAD:palermo|lugar:DEPARTAMENTO:comuna_14|lugar:PROVINCIA:ciudad_autonoma_de_buenos_aires|lugar:PAIS:argentina"
    )
    generica, _ = centroides.ubicar(
        "lugar:CIUDAD:ciudad_autonoma_de_buenos_aires|lugar:PROVINCIA:ciudad_autonoma_de_buenos_aires|lugar:PAIS:argentina"
    )
    assert palermo[4][0] == "Palermo"
    assert generica[4][0] == cd.NOMBRE_CABA_PARTIDO
    assert centroides.partido(*palermo[4])["nombre"] == "Palermo"


def test_errores_conocidos_del_grafo_no_se_dibujan():
    uruguay = "lugar:DEPARTAMENTO:uruguay|lugar:PROVINCIA:entre_rios|lugar:PAIS:argentina"
    san_juan = "lugar:CIUDAD:san_juan|lugar:DEPARTAMENTO:capital|lugar:PROVINCIA:san_juan|lugar:PAIS:argentina"
    cruz_alta = [{"detalle": {"descripcion_lugar_de_secuestro": "CRUZ ALTA. TUCUMAN (Ingenio San Juan)"}}]
    san_juan_real = [{"detalle": {"descripcion_lugar_de_secuestro": "SAN JUAN"}}]
    assert cd.error_conocido_del_grafo("ASESINADO_EN", uruguay, [])
    assert cd.error_conocido_del_grafo("SECUESTRADO_EN", san_juan, cruz_alta)
    # Un secuestro real en San Juan sigue dibujándose.
    assert not cd.error_conocido_del_grafo("SECUESTRADO_EN", san_juan, san_juan_real)


def test_el_nodo_de_un_partido_esta_en_su_centroide(centroides):
    fila = centroides.partido("General San Martín", "Buenos Aires")
    assert _cerca((fila["lat"], fila["lon"]), -34.55, -58.56)


# --- CCD sin coordenadas propias (casos de la revisión adversarial) -------

@pytest.mark.parametrize("lugar, esperado", [
    # Sin la provincia, "SAN NICOLAS" caía en el barrio porteño (Obelisco).
    ({"nombre": "BRIGADA DE INVESTIGACIONES DE SAN NICOLAS", "ubicacion": "Alem 114", "fuente": "minjus_ccds"},
     "San Nicolás"),
    # La calle "José Hernández" es también una localidad de La Plata.
    ({"nombre": "CEMENTERIO DE GRAND BOURG", "ubicacion": "José Hernández s/n (esquina Pasco) | Malvinas Argentinas",
      "fuente": "minjus_ccds"}, "Grand Bourg (Malvinas Argentinas)"),
    # "entre Mitre y 9 de julio" no es la localidad "Julio".
    ({"nombre": "COMISARÍA DE CAMPANA", "ubicacion": "Rawson 362 _ entre Mitre y 9 de julio | Campana",
      "fuente": "minjus_ccds"}, "Campana"),
    # La dirección sólo da el partido; el nombre, la ciudad.
    ({"nombre": "CUARTEL DE BOMBEROS DE MAR DEL PLATA",
      "ubicacion": "SALTA 2440 e/GASCON y FALUCHO MAR DEL PLATA · GRAL. PUEYRREDON · BUENOS AIRES",
      "fuente": "minjus_ccds"}, "Mar del Plata (General Pueyrredón)"),
    # MinJus tiene algún CCD fuera de Buenos Aires.
    ({"nombre": "QUINTA DE FUNES", "ubicacion": "Ruta Nacional Nº 9 y San José | Funes", "fuente": "minjus_ccds"},
     "Funes (Rosario)"),
])
def test_localidad_de_ccd_sin_coordenadas(centroides, lugar, esperado):
    assert cd.localidad_del_ccd(lugar, centroides)[3] == esperado


def test_coordenadas_ruvte_corregidas_quedan_lejos_de_su_direccion(centroides):
    # Cada corrección de la lista tiene que seguir justificada por los datos.
    with open(cd.RAIZ / "data" / "sources" / "ccds.json", encoding="utf-8") as f:
        ccds = {c["id_ccd"]: c for c in json.load(f)}
    for id_ccd in cd.COORDENADAS_RUVTE_ERRONEAS:
        c = ccds[id_ccd]
        lugar = {"nombre": c["denominacion"], "ubicacion": c["ubicacion"], "zona": c["zona"], "fuente": "ccds_json"}
        localidad = cd.localidad_del_ccd(lugar, centroides)
        lejos = cd.km(c["lat"], c["lon"], localidad[0], localidad[1])
        # O muy lejos de su dirección, o lejos y con las coordenadas de otro CCD
        # cercano con otra dirección (Olimpo tiene las de Coordinación Federal).
        vecino = min(cd.km(c["lat"], c["lon"], o["lat"], o["lon"])
                     for o in ccds.values() if o is not c and o.get("lat") is not None and o["ubicacion"] != c["ubicacion"])
        assert lejos > 20 or (lejos > 8 and vecino < 1.5), id_ccd


def test_barrio_abreviado_no_engancha_una_localidad_homonima(centroides, sitios):
    texto = "Aparición:Su cuerpo s encontró el 14/12/75 en Bº Esperanza, Villa Celina, La Matanza; Ente:"
    assert cd.ubicar_hallazgo(texto, sitios, centroides)["nombre"] == "La Matanza"


def test_prefijo_de_otro_pueblo_no_se_usa(centroides):
    # "Guadalupe Norte" (General Obligado) no es Guadalupe: mejor no ubicar.
    coords, motivo = centroides.ubicar("lugar:CIUDAD:guadalupe|lugar:PROVINCIA:santa_fe|lugar:PAIS:argentina")
    assert coords is None and motivo == "sin_centroide"


def test_prefijo_de_nombre_compuesto_si(centroides):
    coords, _ = centroides.ubicar("lugar:CIUDAD:villa_mariano_moreno|lugar:PROVINCIA:tucuman|lugar:PAIS:argentina")
    assert coords is not None


def test_fronterita_es_el_ingenio_de_famailla(centroides):
    coords, _ = centroides.ubicar("lugar:CIUDAD:fronterita|lugar:PROVINCIA:tucuman|lugar:PAIS:argentina")
    assert coords[4] == ("Famaillá", "Tucumán")


def test_cementerio_sin_sector_no_inventa_el_sector(sitios, centroides):
    texto = "Identificado por el EAAF en 2010. Sus restos fueron exhumados en el Cementerio de Avellaneda, Bs. As."
    assert cd.ubicar_hallazgo(texto, sitios, centroides)["nombre"] == "Cementerio de Avellaneda (Avellaneda)"


def test_la_piedad_de_otra_provincia_no_es_la_de_rosario(sitios, centroides):
    texto = "Identificada por el EAAF en el 2008. Sus restos exhumados en el Cementerio de la Piedad, Oberá, Misiones."
    assert sitios.buscar(texto) is None
    rosario = "Sus restos fueron exhumados en el Cementerio La Piedad, Rosario, Santa Fe."
    assert sitios.buscar(rosario)["nombre"] == "Cementerio La Piedad"


def test_provincia_de_otro_dato_no_descarta_el_sitio(sitios):
    # Lo que va después del punto y coma es otro dato, no el lugar del sitio.
    texto = "Restos hallados en el Cementerio de la Chacarita; secuestrada en Rosario, Santa Fe."
    assert sitios.buscar(texto)["nombre"] == "Cementerio de la Chacarita"


def test_rio_lujan_no_es_la_ciudad_de_lujan(centroides):
    coords, _ = cd.ubicar_fragmento("Río Luján", centroides)
    assert coords is None


def test_bs_as_tambien_vale_para_un_sitio_de_caba(sitios):
    texto = "Identificada en el 2010 por el EAAF. Cementerio de Chacarita, Bs As."
    assert sitios.buscar(texto)["nombre"] == "Cementerio de la Chacarita"

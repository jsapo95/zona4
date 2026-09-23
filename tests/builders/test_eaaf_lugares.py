from __future__ import annotations

from zona4_graph_loader.builders.eaaf_lugares import build_eaaf_lugares_rows
from zona4_graph_loader.io.raw_files import read_raw_csv

FILA_CEM = {
    "PROVINCIA": "Buenos Aires",
    "LOCALIDAD": "Almirante Brown",
    "CEM - CCD - EP": "CEM",
    "LUGAR DE HALLAZGO": "Cementerio de Almirante Brown",
    "HOJA DE REFERENCIA": "Zona_Sur-Rafael_Calzada",
    "Lat": "-34.795355931418285",
    "Long": "-58.34562565092717",
    "Suma de CASOS": "30",
    "Suma de EXHUMADOS": "30",
    "Suma de ID": "10",
}

FILA_EXTRANJERA = dict(FILA_CEM, PROVINCIA="Uruguay", LOCALIDAD="Montevideo",
                       **{"LUGAR DE HALLAZGO": "Playa Malvin"})


def test_genera_lugar_con_coordenadas():
    dataset = build_eaaf_lugares_rows([FILA_CEM])
    lugares = [l for l in dataset["lugares"] if l["tipo_entidad"] == "Lugar"]
    sitio = next(l for l in lugares if l["tipoGeopolitico"] == "CEMENTERIO")
    assert sitio["nombre"] == "CEMENTERIO DE ALMIRANTE BROWN"
    assert sitio["lat"] == -34.795355931418285
    assert sitio["lon"] == -58.34562565092717
    assert sitio["fuente"] == "eaaf_lugares"


def test_mapea_tipos_cem_ccd_ep():
    def tipo_de(valor):
        dataset = build_eaaf_lugares_rows([dict(FILA_CEM, **{"CEM - CCD - EP": valor})])
        sitios = [l for l in dataset["lugares"]
                  if l["tipo_entidad"] == "Lugar" and l["fuente"] == "eaaf_lugares"]
        return {l["tipoGeopolitico"] for l in sitios}

    assert "CEMENTERIO" in tipo_de("CEM")
    assert "CCD" in tipo_de("CCD")
    assert "ENTERRAMIENTO" in tipo_de("EP")


def test_construye_jerarquia_sitio_localidad_provincia_pais():
    dataset = build_eaaf_lugares_rows([FILA_CEM])
    pares = {(j["child_key"], j["parent_key"]) for j in dataset["jerarquias"]
             if j["tipo_relacion"] == "PARTE_DE"}
    keys = {l["lugar_key"] for l in dataset["lugares"]}

    assert "lugar:PAIS:argentina" in keys
    assert any(p == "lugar:PAIS:argentina" for _, p in pares)
    assert len(pares) == 3  # sitio->localidad, localidad->provincia, provincia->pais


def test_lugar_extranjero_usa_pais_code_propio():
    dataset = build_eaaf_lugares_rows([FILA_EXTRANJERA])
    paises = [l for l in dataset["lugares"] if l["tipoGeopolitico"] == "PAIS"]
    assert any(l["pais_code"] == "UY" for l in paises)


def test_genera_direccion_ccd_con_coordenadas():
    dataset = build_eaaf_lugares_rows([FILA_CEM])
    direcciones = [l for l in dataset["lugares"] if l["tipo_entidad"] == "DireccionCCD"]
    assert len(direcciones) == 1
    assert direcciones[0]["coordenadas"] == "-34.795355931418285,-58.34562565092717"
    links = [j for j in dataset["jerarquias"] if j["tipo_relacion"] == "UBICADA_EN"]
    assert len(links) == 1


def test_direccion_ccd_declara_tipo_direccion_segun_la_fuente():
    """Fix E (auditoría 2026-08-29, hallazgo I5): antes de este fix, un
    cementerio real llevaba la misma label `:DirecciónCCD` -sin ninguna
    marca- que un centro clandestino real. `tipo_direccion` reutiliza la
    misma clasificación que ya trae la fuente en "CEM - CCD - EP" para el
    :Lugar asociado, no una suposición nueva.
    """
    dataset = build_eaaf_lugares_rows([FILA_CEM])
    direccion = next(l for l in dataset["lugares"] if l["tipo_entidad"] == "DireccionCCD")
    assert direccion["tipo_direccion"] == "CEMENTERIO"

    dataset_ccd = build_eaaf_lugares_rows([dict(FILA_CEM, **{"CEM - CCD - EP": "CCD"})])
    direccion_ccd = next(l for l in dataset_ccd["lugares"] if l["tipo_entidad"] == "DireccionCCD")
    assert direccion_ccd["tipo_direccion"] == "CCD"


def test_fila_sin_coordenadas_no_genera_direccion():
    dataset = build_eaaf_lugares_rows([dict(FILA_CEM, Lat="", Long="")])
    assert [l for l in dataset["lugares"] if l["tipo_entidad"] == "DireccionCCD"] == []


def test_sobre_el_archivo_real():
    filas = read_raw_csv("eaaf_lugares.csv")
    dataset = build_eaaf_lugares_rows(filas)
    sitios = [l for l in dataset["lugares"]
              if l["tipo_entidad"] == "Lugar" and l["fuente"] == "eaaf_lugares"]
    assert len(sitios) == 91

    # Una fila (Cementerio San Antonio de Padua, San Miguel) trae notacion
    # cientifica de Excel con coma decimal ("-3,45376E+15") que _to_float
    # convierte en un float valido pero absurdo como coordenada. Se descarta
    # esa unica fila; las 90 restantes conservan sus coordenadas.
    sin_coordenadas = [l for l in sitios if l.get("lat") is None]
    assert len(sin_coordenadas) == 1
    assert sin_coordenadas[0]["nombre"] == "CEMENTERIO SAN ANTONIO DE PADUA"
    assert all(l.get("lat") is not None for l in sitios if l is not sin_coordenadas[0])

    # 90 sitios tienen coordenadas validas, asi que deben producir 90
    # direcciones distintas (la fila descartada no genera DirecciónCCD). Se
    # compara el set de claves (no solo len(direcciones)) para que una
    # colision que pise una direccion con otra no quede enmascarada.
    direcciones = [l for l in dataset["lugares"] if l["tipo_entidad"] == "DireccionCCD"]
    direccion_keys = {d["direccion_ccd_key"] for d in direcciones}
    assert len(direcciones) == 90
    assert len(direccion_keys) == 90


def test_coordenada_fuera_de_rango_no_genera_lat_lon_ni_direccion():
    # Notacion cientifica de Excel con coma decimal: parsea a un float valido
    # pero con una magnitud absurda para una coordenada real.
    fila = dict(FILA_CEM, Lat="-3,45376E+15", Long="-5,8739E+16")
    dataset = build_eaaf_lugares_rows([fila])
    sitios = [l for l in dataset["lugares"]
              if l["tipo_entidad"] == "Lugar" and l["fuente"] == "eaaf_lugares"]
    assert len(sitios) == 1
    assert sitios[0]["lat"] is None
    assert sitios[0]["lon"] is None
    assert [l for l in dataset["lugares"] if l["tipo_entidad"] == "DireccionCCD"] == []
    assert [j for j in dataset["jerarquias"] if j["tipo_relacion"] == "UBICADA_EN"] == []


def test_direccion_key_no_colisiona_entre_sitios_homonimos():
    # "Cementerio Norte" aparece en el archivo real en Buenos Aires, Entre
    # Rios y Tucuman: mismo nombre de sitio, distinta jerarquia. La clave de
    # DireccionCCD no puede salir solo del nombre o los tres se pisarian.
    fila_ba = dict(
        FILA_CEM,
        PROVINCIA="Buenos Aires",
        LOCALIDAD="San Andres de Giles",
        **{"LUGAR DE HALLAZGO": "Cementerio Norte"},
    )
    fila_er = dict(
        FILA_CEM,
        PROVINCIA="Entre Rios",
        LOCALIDAD="Gualeguaychu",
        **{"LUGAR DE HALLAZGO": "Cementerio Norte"},
        Lat="-32.99333519409497",
        Long="-58.53783566631421",
    )

    dataset = build_eaaf_lugares_rows([fila_ba, fila_er])
    direcciones = [l for l in dataset["lugares"] if l["tipo_entidad"] == "DireccionCCD"]
    sitios = [l for l in dataset["lugares"]
              if l["tipo_entidad"] == "Lugar" and l["fuente"] == "eaaf_lugares"]

    assert len({d["direccion_ccd_key"] for d in direcciones}) == 2
    assert len({s["lugar_key"] for s in sitios}) == 2

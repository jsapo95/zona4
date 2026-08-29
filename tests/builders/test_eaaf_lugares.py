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


def test_fila_sin_coordenadas_no_genera_direccion():
    dataset = build_eaaf_lugares_rows([dict(FILA_CEM, Lat="", Long="")])
    assert [l for l in dataset["lugares"] if l["tipo_entidad"] == "DireccionCCD"] == []


def test_sobre_el_archivo_real():
    filas = read_raw_csv("eaaf_lugares.csv")
    dataset = build_eaaf_lugares_rows(filas)
    sitios = [l for l in dataset["lugares"]
              if l["tipo_entidad"] == "Lugar" and l["fuente"] == "eaaf_lugares"]
    assert len(sitios) == 91
    assert all(l.get("lat") is not None for l in sitios)

    # Los 91 sitios tienen coordenadas, asi que deben producir 91 direcciones
    # distintas. Se compara el set de claves (no solo len(direcciones)) para
    # que una colision que pise una direccion con otra no quede enmascarada.
    direcciones = [l for l in dataset["lugares"] if l["tipo_entidad"] == "DireccionCCD"]
    direccion_keys = {d["direccion_ccd_key"] for d in direcciones}
    assert len(direcciones) == 91
    assert len(direccion_keys) == 91


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

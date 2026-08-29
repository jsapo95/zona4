from __future__ import annotations

from zona4_graph_loader.builders.minjus_ccds import build_minjus_ccds_rows, slug_ccd
from zona4_graph_loader.io.raw_files import read_raw_json

CCD = {
    "source_url": "https://derechoshumanos.mjus.gba.gob.ar/centrodedetencion/242-arsenal-de-artilleria-de-marina-de-zarate",
    "titulo": "Arsenal de Artillería de Marina de Zárate",
    "metadatos": {
        "Otras denominaciones": "ARSENAL DE LA ARMADA / ARSENAL NAVAL DE ZÁRATE",
        "Dependencia": "ARMADA",
        "Domicilio": "Estrada 350, B2800HUA Zárate, Provincia de Buenos Aires",
    },
    "secciones": {"Reseña": "En esta unidad de la Armada Argentina..."},
    "victimas": [],
}


def test_slug_acepta_las_dos_grafias_del_dataset():
    assert slug_ccd("/centrodedetencion/242-arsenal") == "242-arsenal"
    assert slug_ccd("/centrodetencion/69-comisaria-5") == "69-comisaria-5"
    assert slug_ccd(None) is None


def test_genera_lugar_ccd():
    dataset, _ = build_minjus_ccds_rows([CCD])
    ccds = [l for l in dataset["lugares"]
            if l["tipo_entidad"] == "Lugar" and l["tipoGeopolitico"] == "CCD"]
    assert len(ccds) == 1
    assert ccds[0]["nombre"] == "ARSENAL DE ARTILLERÍA DE MARINA DE ZÁRATE"
    assert ccds[0]["fuente"] == "minjus_ccds"


def test_domicilio_va_crudo_a_direccion_ccd():
    dataset, _ = build_minjus_ccds_rows([CCD])
    direcciones = [l for l in dataset["lugares"] if l["tipo_entidad"] == "DireccionCCD"]
    assert len(direcciones) == 1
    assert direcciones[0]["direccionExacta"] == (
        "Estrada 350, B2800HUA Zárate, Provincia de Buenos Aires"
    )
    assert direcciones[0]["coordenadas"] == "DESCONOCIDAS"


def test_expone_mapa_slug_a_lugar_key():
    _, key_by_slug = build_minjus_ccds_rows([CCD])
    assert key_by_slug["242-arsenal-de-artilleria-de-marina-de-zarate"].startswith("lugar:CCD:")


def test_dedup_reutiliza_ccd_existente():
    existentes = {"ARSENAL DE ARTILLERIA DE MARINA DE ZARATE": "lugar:CCD:ruvte_123"}
    dataset, key_by_slug = build_minjus_ccds_rows([CCD], existing_ccds=existentes)
    assert key_by_slug["242-arsenal-de-artilleria-de-marina-de-zarate"] == "lugar:CCD:ruvte_123"
    nuevos = [l for l in dataset["lugares"]
              if l["tipo_entidad"] == "Lugar" and l["fuente"] == "minjus_ccds"]
    assert nuevos == []


def test_nombre_distinto_no_se_dedupea():
    existentes = {"ESCUELA DE MECANICA DE LA ARMADA": "lugar:CCD:ruvte_1"}
    dataset, _ = build_minjus_ccds_rows([CCD], existing_ccds=existentes)
    nuevos = [l for l in dataset["lugares"]
              if l["tipo_entidad"] == "Lugar" and l["fuente"] == "minjus_ccds"]
    assert len(nuevos) == 1


def test_dependencia_se_guarda_como_jurisdiccion():
    dataset, _ = build_minjus_ccds_rows([CCD])
    ccd = next(l for l in dataset["lugares"] if l["tipoGeopolitico"] == "CCD")
    assert ccd["jurisdiccion"] == "ARMADA"


def test_sobre_el_archivo_real():
    data = read_raw_json("derechos_humanos_minjus_gba_centros_clandestinos.json")
    dataset, key_by_slug = build_minjus_ccds_rows(data)
    assert len(key_by_slug) == 87
    # .get(): las filas de DireccionCCD no traen tipoGeopolitico (igual que en
    # builders/ccds.py), así que l["tipoGeopolitico"] rompería con KeyError.
    ccds = [l for l in dataset["lugares"] if l.get("tipoGeopolitico") == "CCD"]
    assert len(ccds) == 87


def test_numeros_distintos_en_el_nombre_no_se_dedupean():
    """Bug real encontrado contra los datos: name_similarity_score descarta los
    tokens de un solo caracter como ruido (`_remove_trash`), asi que numeros de
    un digito como "5" o "8" nunca llegan a activar el chequeo `nums1 != nums2`
    de esa funcion. Sin un guardia propio, "COMISARIA 8a DE LA PLATA" (dato real
    de MinJus) matchea con score 1.0 contra "COMISARIA 5a DE LA PLATA" (CCD real
    de RUVTE), fusionando dos comisarias distintas en un solo nodo.
    """
    ccd_comisaria_8 = {
        "source_url": "https://derechoshumanos.mjus.gba.gob.ar/centrodedetencion/1-comisaria-8-de-la-plata",
        "titulo": "Comisaría 8ª de La Plata",
        "metadatos": {"Dependencia": "POLICÍA", "Domicilio": "-"},
        "secciones": {},
        "victimas": [],
    }
    existentes = {"COMISARÍA 5ª DE LA PLATA": "lugar:CCD:ruvte_5"}
    dataset, key_by_slug = build_minjus_ccds_rows([ccd_comisaria_8], existing_ccds=existentes)

    assert key_by_slug["1-comisaria-8-de-la-plata"] != "lugar:CCD:ruvte_5"
    nuevos = [l for l in dataset["lugares"]
              if l["tipo_entidad"] == "Lugar" and l["fuente"] == "minjus_ccds"]
    assert len(nuevos) == 1
    assert nuevos[0]["nombre"] == "COMISARÍA 8ª DE LA PLATA"

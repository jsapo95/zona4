from __future__ import annotations

from typing import Any, Dict, List, Optional

from zona4_graph_loader.builders.base import CanonicalDataset
from zona4_graph_loader.domain.place_norm import make_lugar_key
from zona4_graph_loader.domain.text_norm import clean_text, slugify_name

FUENTE = "eaaf_lugares"

# Fuente para los nodos de andamiaje geográfico (PAIS/PROVINCIA/CIUDAD) que este
# builder crea al armar la jerarquía; sigue la misma convención que
# builders/lugares.py para no inflar el conteo de sitios propios del EAAF.
FUENTE_JERARQUIA = "normalizacion_lugar"

# CEM = cementerio, CCD = centro clandestino, EP = enterramiento en predio.
TIPO_SITIO = {
    "CEM": "CEMENTERIO",
    "CCD": "CCD",
    "EP": "ENTERRAMIENTO",
}

# Provincias del dataset que en realidad son países extranjeros.
PAISES_EXTRANJEROS = {
    "URUGUAY": "UY",
    "BOLIVIA": "BO",
    "BRASIL": "BR",
    "CHILE": "CL",
    "PARAGUAY": "PY",
}


def _to_float(value: Any) -> Optional[float]:
    text = clean_text(value)
    if text is None:
        return None
    try:
        return float(text.replace(",", "."))
    except ValueError:
        return None


def build_eaaf_lugares_rows(rows: List[Dict[str, str]]) -> CanonicalDataset:
    """Convierte el consolidado de sitios de hallazgo del EAAF al CDM.

    Cada fila trae provincia, localidad, tipo de sitio y coordenadas exactas, así
    que la jerarquía se arma sin recurrir a Georef.
    """
    lugares: Dict[str, Dict[str, Any]] = {}
    direcciones: Dict[str, Dict[str, Any]] = {}
    jerarquias: List[Dict[str, Any]] = []
    pares_parte_de: set[tuple[str, str]] = set()

    def registrar_parte_de(child_key: str, parent_key: str) -> None:
        if (child_key, parent_key) in pares_parte_de:
            return
        pares_parte_de.add((child_key, parent_key))
        jerarquias.append({
            "tipo_relacion": "PARTE_DE",
            "child_key": child_key,
            "parent_key": parent_key,
        })

    for row in rows:
        nombre_sitio = clean_text(row.get("LUGAR DE HALLAZGO"))
        provincia = clean_text(row.get("PROVINCIA"))
        localidad = clean_text(row.get("LOCALIDAD"))
        if not nombre_sitio or not provincia:
            continue

        provincia_upper = provincia.upper()
        pais_nombre = provincia_upper if provincia_upper in PAISES_EXTRANJEROS else "ARGENTINA"
        pais_code = PAISES_EXTRANJEROS.get(provincia_upper, "AR")
        pais_key = make_lugar_key("PAIS", pais_nombre, None)
        lugares.setdefault(pais_key, {
            "lugar_key": pais_key,
            "nombre": pais_nombre,
            "tipoGeopolitico": "PAIS",
            "pais_code": pais_code,
            "fuente": FUENTE_JERARQUIA,
            "tipo_entidad": "Lugar",
        })

        # En las filas extranjeras la columna PROVINCIA trae el país, así que el
        # contenedor intermedio pasa a ser la localidad directamente.
        if provincia_upper in PAISES_EXTRANJEROS:
            contenedor_key = pais_key
        else:
            provincia_key = make_lugar_key("PROVINCIA", provincia_upper, pais_key)
            lugares.setdefault(provincia_key, {
                "lugar_key": provincia_key,
                "nombre": provincia_upper,
                "tipoGeopolitico": "PROVINCIA",
                "pais_code": pais_code,
                "fuente": FUENTE_JERARQUIA,
                "tipo_entidad": "Lugar",
            })
            registrar_parte_de(provincia_key, pais_key)
            contenedor_key = provincia_key

        if localidad:
            localidad_upper = localidad.upper()
            localidad_key = make_lugar_key("CIUDAD", localidad_upper, contenedor_key)
            lugares.setdefault(localidad_key, {
                "lugar_key": localidad_key,
                "nombre": localidad_upper,
                "tipoGeopolitico": "CIUDAD",
                "pais_code": pais_code,
                "fuente": FUENTE_JERARQUIA,
                "tipo_entidad": "Lugar",
            })
            registrar_parte_de(localidad_key, contenedor_key)
            contenedor_key = localidad_key

        tipo_sitio = TIPO_SITIO.get((clean_text(row.get("CEM - CCD - EP")) or "").upper(), "SITIO_HALLAZGO")
        nombre_upper = nombre_sitio.upper()
        sitio_key = make_lugar_key(tipo_sitio, nombre_upper, contenedor_key)
        lat = _to_float(row.get("Lat"))
        lon = _to_float(row.get("Long"))

        lugares[sitio_key] = {
            "lugar_key": sitio_key,
            "nombre": nombre_upper,
            "tipoGeopolitico": tipo_sitio,
            "pais_code": pais_code,
            "fuente": FUENTE,
            "lat": lat,
            "lon": lon,
            "ubicacion": clean_text(row.get("HOJA DE REFERENCIA")),
            "tipo_entidad": "Lugar",
        }
        registrar_parte_de(sitio_key, contenedor_key)

        if lat is not None and lon is not None:
            # Se deriva del sitio_key (único por fila) y no solo del nombre: dos
            # sitios en provincias distintas pueden compartir nombre (p.ej. hay
            # tres "Cementerio Norte" en el dataset real) y colisionarían si la
            # clave saliera únicamente de nombre_upper.
            direccion_key = f"direccion_ccd:eaaf:{slugify_name(sitio_key)}"
            direcciones[direccion_key] = {
                "direccion_ccd_key": direccion_key,
                "coordenadas": f"{lat},{lon}",
                "direccionExacta": nombre_upper,
                "lugar_key": sitio_key,
                # Sin tipoGeopolitico propio; se declara en None para que un
                # filtro que recorra dataset["lugares"] sin acotar por
                # tipo_entidad no reviente con KeyError.
                "tipoGeopolitico": None,
                "tipo_entidad": "DireccionCCD",
            }
            jerarquias.append({
                "tipo_relacion": "UBICADA_EN",
                "direccion_ccd_key": direccion_key,
                "lugar_key": sitio_key,
            })

    return {
        "lugares": list(lugares.values()) + list(direcciones.values()),
        "jerarquias": jerarquias,
    }

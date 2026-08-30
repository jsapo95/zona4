from __future__ import annotations

from pathlib import Path

ALIAS_ROOT_PARENT_KEY = "__ROOT__"
BATCH_SIZE = 500

SPANISH_MONTHS = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}

REL_MAP = {
    "madre": "MADRE",
    "padre": "PADRE",
    "hermanx": "HERMANO",
    "hermano": "HERMANO",
    "hermana": "HERMANO",
    "abuela materna": "ABUELA_MATERNA",
    "abuela paterna": "ABUELA_PATERNA",
    "esposo": "PAREJA",
    "esposa": "PAREJA",
    "conyuge": "PAREJA",
    "pareja": "PAREJA",
    "ex esposo": "PAREJA",
    "ex esposa": "PAREJA",
    "companero": "PAREJA",
    "companera": "PAREJA",
    "novio": "PAREJA",
    "novia": "PAREJA",
    "hijo": "HIJO",
    "hija": "HIJO",
}

UNKNOWN_PLACE_VALUES = {
    "SE DESCONOCE",
    "NO HAY INFORMACION",
    "SIN DATOS",
    "DESCONOCIDO",
}

# Fix E (auditoría 2026-08-29, hallazgo I3d): valores de `Fuerza`
# (juicios_condenados, minjus_imputados) que no nombran una organización
# real, sino la ausencia de un dato o -en el caso de "CIVIL"- la ausencia
# misma de fuerza represiva. Materializarlos como :Org con aristas PARTE_DE
# afirma que centenares de represores distintos comparten membresía en una
# única organización llamada "SIN ESPECIFICAR" (109 casos reales,
# combinando ambas fuentes) o "CIVIL" (87 casos reales) -ninguna de las dos
# es una organización. Derivado de la distribución real de `Fuerza` en
# ambas fuentes (sólo coincidencia exacta tras upper(); no se recorta
# ningún prefijo, para no descartar de más un valor real que simplemente
# mencione "sin especificar" como parte de un nombre más largo -no se
# encontró ningún caso así en los datos).
SENTINEL_ORG_VALUES = {
    "SIN ESPECIFICAR",
    "POLICIA (SIN ESPECIFICAR)",
    "CIVIL",
    "NO ESPECIFICADO",
    "NO DETERMINADO",
    "DESCONOCIDA",
    "DESCONOCIDO",
}

# Fix E (auditoría 2026-08-29, hallazgo I3d): mismo problema, para
# `lugar_de_trabajo`/`dónde_estudió` (minjus_victimas) que alimentan
# :Institución vía TRABAJO_EN/ESTUDIO_EN. Coincidencia exacta únicamente:
# los valores narrativos más largos que empiezan con una de estas palabras
# pero agregan información real ("DESCONOCIDO, PERO LA VICTIMA ESTUDIABA
# PARA SER MAESTRO...") no son sentinels puros y quedan fuera de este
# hallazgo (ver hallazgo I3c, no arreglado en este fix).
SENTINEL_INSTITUCION_VALUES = {
    "NO DETERMINADO",
    "NO ESPECIFICADO",
    "NO ESPECIFICA",
    "DESCONOCIDO",
    "DESCONOCIDA",
}

EQUIV_CITIES = {
    "CAPITAL": ("CIUDAD", "CIUDAD AUTONOMA DE BUENOS AIRES", None),
    "CAPITAL FEDERAL": ("CIUDAD", "CIUDAD AUTONOMA DE BUENOS AIRES", None),
    "FEDERAL": ("CIUDAD", "CIUDAD AUTONOMA DE BUENOS AIRES", None),
    "CABA": ("CIUDAD", "CIUDAD AUTONOMA DE BUENOS AIRES", None),
    "CIUDAD DE BS AS": ("CIUDAD", "CIUDAD AUTONOMA DE BUENOS AIRES", None),
    "CIUDAD DE BUENOS AIRES": ("CIUDAD", "CIUDAD AUTONOMA DE BUENOS AIRES", None),
    "CORDOBA CAPITAL": ("CIUDAD", "CORDOBA", "CORDOBA"),
    "MENDOZA CAPITAL": ("CIUDAD", "MENDOZA", "MENDOZA"),
    "SAN MIGUEL DE TUCUMAN": ("CIUDAD", "SAN MIGUEL DE TUCUMAN", "TUCUMAN"),
    "JOSE LEON SUAREZ SAN MARTIN": ("CIUDAD", "VILLA JOSE LEON SUAREZ", "BUENOS AIRES"),
    "LIBERTADOR GENERAL SAN MARTIN": ("CIUDAD", "SAN MARTIN", "BUENOS AIRES"),
    # Task 14: localidades reales del partido de General San Martín (Buenos
    # Aires) que, sin esta entrada, quedan mal georresueltas por
    # `_resolve_segmented_place` hacia una provincia distinta (ver
    # tests/domain/test_place_norm_san_martin.py). El valor crudo de
    # `archivo_memoria_san_martin.json` no trae el sufijo "SAN MARTIN", por
    # lo que "JOSE LEON SUAREZ SAN MARTIN" (arriba) nunca se dispara para
    # esta fuente; se agrega la clave sin sufijo para cubrirla.
    "JOSE LEON SUAREZ": ("CIUDAD", "VILLA JOSE LEON SUAREZ", "BUENOS AIRES"),
    # La menos específica de las tres: "San Andrés" también nombra el
    # archipiélago colombiano y una localidad de Lavalle, Mendoza. Como
    # EQUIV_CITIES se consulta antes que _resolve_foreign_place (ver
    # resolve_place), un "San Andrés" colombiano de una fuente futura
    # (ej. exilio/asilo) caería silenciosamente en Buenos Aires en vez de
    # reconocerse como extranjero. "San Andrés de Giles" normaliza a otra
    # clave distinta y no se ve afectado.
    "SAN ANDRES": ("CIUDAD", "VILLA SAN ANDRES", "BUENOS AIRES"),
    "VILLA CONCEPCION": ("CIUDAD", "VILLA CONCEPCION", "BUENOS AIRES"),
}

PROVINCE_ABBR = {
    "BS AS": "BUENOS AIRES",
    "BSAS": "BUENOS AIRES",
    "BS A S": "BUENOS AIRES",
    "BUENOS AIRES": "BUENOS AIRES",
    "BSA": "BUENOS AIRES",
    "SANTA FE": "SANTA FE",
    "TUCUMAN": "TUCUMAN",
    "CORDOBA": "CORDOBA",
    "MENDOZA": "MENDOZA",
}

DIRECTIONAL_TOKENS = {
    "ESTE",
    "OESTE",
    "NORTE",
    "SUR",
}

GEOREF_CATALOG_PATH = Path("data/processed/georef_catalog.json")
GEOREF_MIN_SCORE = 0.76
GEOREF_AMBIGUITY_DELTA = 0.02

# Approximate ranking by population (largest to smallest) used only as weak tie-break fallback.
PROVINCE_PRIORITY = [
    "BUENOS AIRES",
    "CORDOBA",
    "SANTA FE",
    "CIUDAD AUTONOMA DE BUENOS AIRES",
    "MENDOZA",
    "TUCUMAN",
    "ENTRE RIOS",
    "SALTA",
    "MISIONES",
    "CHACO",
    "CORRIENTES",
    "SANTIAGO DEL ESTERO",
    "SAN JUAN",
    "JUJUY",
    "RIO NEGRO",
    "NEUQUEN",
    "FORMOSA",
    "CHUBUT",
    "SAN LUIS",
    "CATAMARCA",
    "LA RIOJA",
    "LA PAMPA",
    "SANTA CRUZ",
    "TIERRA DEL FUEGO",
]

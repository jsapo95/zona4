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

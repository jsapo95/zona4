from __future__ import annotations

import re
import unicodedata
from typing import Any, Optional


def norm_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def strip_accents(value: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", value) if not unicodedata.combining(c))


def slugify_name(value: str) -> str:
    text = strip_accents(value.lower())
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = norm_space(text)
    return text.replace(" ", "_")


def clean_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    value = norm_space(value)
    if value in {"", "-", "No hay informacion."}:
        return None
    return value


def persona_key_from_name(name: str) -> str:
    return f"nombre:{slugify_name(name)}"


def genero_from_sexo(sexo: Any) -> str:
    """Normaliza `detalle.Sexo` (p.ej. "Masculino", "Femenino") al vocabulario
    fijo de `Persona.genero`. Factorizado (Fix E, hallazgo I1) para que
    `builders/personas.py` y `builders/ccds.py` -que necesita el género para
    no emitir `PARIO_EN` sobre un registro marcado como masculino- lean el
    mismo campo de la misma manera en vez de reimplementar la normalización.
    """
    texto = clean_text(sexo)
    if not texto:
        return "INDETERMINADO"
    bajo = texto.lower()
    if "masc" in bajo:
        return "MASCULINO"
    if "fem" in bajo:
        return "FEMENINO"
    return "INDETERMINADO"

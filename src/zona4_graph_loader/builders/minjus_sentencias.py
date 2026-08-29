from __future__ import annotations

from typing import Any, Dict, List, Optional

from zona4_graph_loader.domain.date_norm import parse_ddmmyyyy
from zona4_graph_loader.domain.text_norm import clean_text

FUENTE = "minjus_sentencias"


def slug_sentencia(url: Optional[str]) -> Optional[str]:
    """Extrae el identificador de sentencia de cualquiera de las formas de URL.

    El dataset mezcla tres formatos: absoluta, relativa con prefijo `/sentencia/`
    y slug pelado (en `condenas_recibidas`).
    """
    text = clean_text(url)
    if text is None:
        return None
    if "/sentencia/" in text:
        text = text.split("/sentencia/", 1)[1]
    return text.strip("/") or None


def build_sentencias_index(data: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Índice slug -> metadatos de sentencia.

    No genera nodos: el modelo V1.2 no tiene :Sentencia ni :Causa. Los metadatos
    alimentan `origen` y `fecha` de las aristas TORTURO_A.
    """
    index: Dict[str, Dict[str, Any]] = {}
    for item in data:
        slug = slug_sentencia(item.get("url_detalle"))
        if not slug:
            continue
        tecnicos = item.get("datos_tecnicos") or {}
        index[slug] = {
            "titulo": clean_text(item.get("titulo")),
            "tribunal": clean_text(tecnicos.get("tribunal")),
            "fecha": parse_ddmmyyyy(clean_text(tecnicos.get("fecha"))),
            "origen": f"{FUENTE}:{slug}",
        }
    return index

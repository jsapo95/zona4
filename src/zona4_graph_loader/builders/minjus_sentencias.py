from __future__ import annotations

from typing import Any, Dict, List, Optional

from zona4_graph_loader.domain.date_norm import parse_ddmmyyyy
from zona4_graph_loader.domain.text_norm import clean_text

FUENTE = "minjus_sentencias"

# Fallback compartido por los builders de imputados y víctimas para las aristas
# TORTURO_A cuyo bloque de sentencia no trae ninguna URL de sentencia (no hay
# slug del que derivar un origen específico). Al ser una constante compartida
# en lugar de un literal por-builder, ambos lados de una misma arista TORTURO_A
# terminan de acuerdo por construcción, no por coincidencia.
FUENTE_TORTURO_A_SIN_SENTENCIA = "minjus_sentencias:desconocida"


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

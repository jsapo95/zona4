from __future__ import annotations

from typing import Any, Dict, List, Optional

from zona4_graph_loader.domain.date_norm import parse_ddmmyyyy
from zona4_graph_loader.domain.text_norm import clean_text

FUENTE = "minjus_sentencias"

# Fallback compartido por los builders de imputados y víctimas para las aristas
# TORTURO_A/IMPUTADO_POR cuyo bloque de sentencia no trae ninguna URL de
# sentencia (no hay slug del que derivar un origen específico). Al ser una
# constante compartida en lugar de un literal por-builder, ambos lados de una
# misma arista terminan de acuerdo por construcción, no por coincidencia.
FUENTE_TORTURO_A_SIN_SENTENCIA = "minjus_sentencias:desconocida"

# Vocabulario de `delitos` (fix C1 / Fix A) que la fuente MinJus asocia a cada
# par imputado-víctima. Calculado sobre el vocabulario real de
# derechos_humanos_minjus_gba_{imputados,victimas}.json: sólo estas dos
# variantes (con y sin "seguidos de muerte") nombran tormentos/tortura. El
# resto del vocabulario observado -Privación Ilegítima de la libertad,
# Homicidio, Violencia y amenazas, Infracción de deber de funcionario,
# Desaparicion Forzada, Genocidio, Allanamiento ilegal, Asociación ilícita,
# Abuso sexual, Retención de menor de 10 años, Abuso deshonesto, Robo,
# Sustracción de menor, Violación, Sustracción de identidad, Reducción a la
# servidumbre, Amenazas, Falsificación de instrumento público, Lesiones
# Graves, Absuelto, Aborto forzado, Hurto, Secuestro extorsivo, Falsedad
# Ideológica, Intimidación púbilica, Supresión de documento público, Apremios
# ilegales, abandono de persona- son delitos reales y distintos que la fuente
# nunca llama tormentos, incluido "Apremios ilegales" (duress ilegal es un
# tipo penal propio, no la familia de tormentos). Compartido entre los
# builders de imputados y víctimas para que la clasificación de un mismo par
# sea idéntica en ambos lados, igual que FUENTE_TORTURO_A_SIN_SENTENCIA arriba.
DELITOS_TORTURA = {"tormentos", "tormentos seguidos de muerte"}


def _normalizar_delito(delito: str) -> str:
    return " ".join(delito.strip().lower().split())


def clasificar_relacion_por_delitos(delitos: Optional[List[Any]]) -> str:
    """"TORTURO_A" si algún delito de la lista pertenece a la familia de
    tormentos; "IMPUTADO_POR" en cualquier otro caso, incluida la lista vacía
    o ausente. La sentencia condena por delitos específicos por cada par
    imputado-víctima (campo `delitos`); antes de este fix se ignoraba por
    completo y todo par recibía TORTURO_A sin mirarlo (C1).
    """
    for delito in delitos or []:
        texto = clean_text(delito)
        if texto and _normalizar_delito(texto) in DELITOS_TORTURA:
            return "TORTURO_A"
    return "IMPUTADO_POR"


def limpiar_delitos(delitos: Optional[List[Any]]) -> List[str]:
    """Lista de delitos saneada (sin vacíos, texto original preservado) para
    que la arista TORTURO_A/IMPUTADO_POR quede auditable: ningún delito que
    la sentencia atribuye a un par se pierde, sea cual sea el tipo de arista
    que termine emitiéndose.
    """
    limpios: List[str] = []
    for delito in delitos or []:
        texto = clean_text(delito)
        if texto:
            limpios.append(texto)
    return limpios


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
    alimentan `origen` y `fecha_sentencia` de las aristas TORTURO_A. `fecha_sentencia`
    es la fecha del fallo, no la del hecho: TORTURO_A.fecha se deja en
    "DESCONOCIDA" porque la fuente no registra cuándo ocurrió la tortura.
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
            # Renombrado de "fecha" a "fecha_sentencia" (Fix 9): es la fecha en
            # que el tribunal dictó la sentencia, no la fecha del hecho (la
            # tortura) que la arista TORTURO_A describe. Llamarla "fecha" a
            # secas invitaba a que los builders la volcaran directamente en
            # TORTURO_A.fecha, afirmando que el hecho ocurrió el día del fallo
            # -décadas después del secuestro en los casos medidos sobre datos
            # reales.
            "fecha_sentencia": parse_ddmmyyyy(clean_text(tecnicos.get("fecha"))),
            "origen": f"{FUENTE}:{slug}",
        }
    return index

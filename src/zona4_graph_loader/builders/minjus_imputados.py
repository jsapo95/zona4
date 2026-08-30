from __future__ import annotations

from typing import Any, Dict, List, Optional

from zona4_graph_loader.builders.base import CanonicalDataset
from zona4_graph_loader.constants import SENTINEL_ORG_VALUES
from zona4_graph_loader.builders.minjus_sentencias import FUENTE as FUENTE_SENTENCIAS
from zona4_graph_loader.builders.minjus_sentencias import (
    FUENTE_TORTURO_A_SIN_SENTENCIA,
    clasificar_relacion_por_delitos,
    limpiar_delitos,
    slug_sentencia,
)
from zona4_graph_loader.domain.date_norm import parse_ddmmyyyy, validar_fecha_de_nacimiento
from zona4_graph_loader.domain.text_norm import clean_text, slugify_name

FUENTE = "minjus_imputados"


def slug_persona_minjus(url: Optional[str], prefijo: str) -> Optional[str]:
    text = clean_text(url)
    if text is None:
        return None
    marcador = f"/{prefijo}/"
    if marcador in text:
        text = text.split(marcador, 1)[1]
    return text.strip("/") or None


def build_minjus_imputados_rows(
    data: List[Dict[str, Any]],
    *,
    sentencias_index: Dict[str, Dict[str, Any]],
) -> CanonicalDataset:
    """Convierte los imputados de MinJus GBA al CDM.

    Las aristas TORTURO_A apuntan a `minjus_victima:{slug}`, las mismas claves que
    genera el builder de víctimas, de modo que la reconciliación no tenga que
    inventar placeholders.
    """
    personas: List[Dict[str, Any]] = []
    relaciones: List[Dict[str, Any]] = []
    entidades: Dict[str, Dict[str, Any]] = {}
    rel_contexto: List[Dict[str, Any]] = []

    for item in data:
        slug = slug_persona_minjus(item.get("source_url"), "imputado")
        nombre = clean_text(item.get("nombre"))
        if not slug or not nombre:
            continue

        persona_key = f"minjus_imputado:{slug}"
        datos = item.get("datos_personales") or {}
        fuerza = clean_text(datos.get("fuerza"))
        fuerza_upper = fuerza.upper() if fuerza else None

        personas.append({
            "persona_key": persona_key,
            "nombre": nombre,
            "genero": "INDETERMINADO",
            "fuente": FUENTE,
            "roles": ["REPRESOR"],
            # Fix E (auditoría 2026-08-29, hallazgo I6): un valor imposible
            # (p.ej. Massera, Emilio Eduardo: fuente "08/11/2010", cuando en
            # verdad nació en 1925 y murió en 2010 -la fuente probablemente
            # confundió fecha de nacimiento con fecha de fallecimiento)
            # queda en None (persistido luego como "DESCONOCIDA" si
            # corresponde) en vez de afirmar una fecha de nacimiento
            # imposible. No se corrige el valor: se descarta.
            "fecha_nacimiento": validar_fecha_de_nacimiento(
                parse_ddmmyyyy(clean_text(datos.get("fecha_de_nacimiento")))
            ),
            # Fix E (auditoría 2026-08-29, hallazgo I3d): igual que en
            # juicios_condenados.py -se persiste el valor crudo aunque sea
            # un sentinel, y por eso no genera :Org/PARTE_DE más abajo.
            "fuerza": fuerza_upper,
        })

        if fuerza_upper and fuerza_upper not in SENTINEL_ORG_VALUES:
            # Fix E (hallazgo I3d): "SIN ESPECIFICAR" / "CIVIL" / "POLICIA
            # (SIN ESPECIFICAR)" no son organizaciones -combinando esta
            # fuente con juicios_condenados.py, agrupaban falsamente a 109,
            # 87 y 46 represores distintos respectivamente bajo una única
            # membresía compartida.
            entidad_key = f"org:{slugify_name(fuerza_upper)}"
            entidades.setdefault(entidad_key, {
                "entidad_key": entidad_key,
                "tipo_entidad": "Org",
                "nombre": fuerza_upper,
                "tipoOrg": "FUERZA",
                "fuente": FUENTE,
            })
            rel_contexto.append({
                "persona_key": persona_key,
                "entidad_key": entidad_key,
                "tipo_relacion": "PARTE_DE",
                "fecha": "DESCONOCIDA",
                "origen": FUENTE,
            })

        apodo = clean_text(datos.get("apodo"))
        if apodo:
            alias_key = f"alias_persona:{slugify_name(apodo)}|{slug}"
            entidades.setdefault(alias_key, {
                "entidad_key": alias_key,
                "tipo_entidad": "AliasPersona",
                "alias": apodo,
                "fuente": FUENTE,
            })
            rel_contexto.append({
                "persona_key": persona_key,
                "entidad_key": alias_key,
                "tipo_relacion": "IDENTIFICA_A",
                "fecha": "DESCONOCIDA",
                "origen": FUENTE,
            })

        for bloque in item.get("sentencias_y_victimas") or []:
            slug_sent = slug_sentencia(bloque.get("sentencia_url"))
            meta = sentencias_index.get(slug_sent or "")
            if meta:
                origen = meta["origen"]
                fecha_sentencia = meta.get("fecha_sentencia") or "DESCONOCIDA"
            elif slug_sent:
                # Slug real pero fuera del índice (sentencia no encontrada en el
                # archivo de sentencias). Se deriva del propio slug, no de un
                # literal por-builder, para que el mismo hecho compartido con el
                # builder de víctimas produzca el mismo `fuente` aunque el índice
                # cambie entre corridas.
                origen = f"{FUENTE_SENTENCIAS}:{slug_sent}"
                fecha_sentencia = "DESCONOCIDA"
            else:
                origen = FUENTE_TORTURO_A_SIN_SENTENCIA
                fecha_sentencia = "DESCONOCIDA"

            for victima in bloque.get("victimas_asociadas") or []:
                slug_victima = slug_persona_minjus(victima.get("victima_url"), "victima")
                if not slug_victima:
                    continue
                delitos = victima.get("delitos")
                relaciones.append({
                    "source_key": persona_key,
                    "target_key": f"minjus_victima:{slug_victima}",
                    # Fix C1: sólo TORTURO_A cuando la sentencia condena por
                    # tormentos a esta víctima en particular; el resto de los
                    # pares (p.ej. sustracción de menor) recibe IMPUTADO_POR.
                    # Ambos tipos llevan `delitos` para que la arista sea
                    # auditable frente a la sentencia real.
                    "tipo": clasificar_relacion_por_delitos(delitos),
                    "delitos": limpiar_delitos(delitos),
                    # La fuente no registra cuándo ocurrió la tortura (el
                    # hecho): "fecha" queda en DESCONOCIDA en vez de tomar la
                    # fecha del fallo, que es procedencia (Fix 9), no el hecho.
                    "fecha": "DESCONOCIDA",
                    "fecha_sentencia": fecha_sentencia,
                    "fuente": origen,
                    "target_nombre": clean_text(victima.get("victima_nombre")),
                    "target_genero": "INDETERMINADO",
                    "target_fuente": "minjus_victimas",
                })

    return {
        "personas": personas,
        "relaciones_interpersonales": relaciones,
        "entidades_contexto": list(entidades.values()),
        "relaciones_contexto": rel_contexto,
    }

from __future__ import annotations

from typing import Any, Dict, List

from zona4_graph_loader.builders.base import CanonicalDataset
from zona4_graph_loader.constants import SENTINEL_INSTITUCION_VALUES, SENTINEL_ORG_VALUES
from zona4_graph_loader.builders.minjus_ccds import slug_ccd
from zona4_graph_loader.builders.minjus_imputados import slug_persona_minjus
from zona4_graph_loader.builders.minjus_sentencias import FUENTE as FUENTE_SENTENCIAS
from zona4_graph_loader.builders.minjus_sentencias import (
    FUENTE_TORTURO_A_SIN_SENTENCIA,
    clasificar_relacion_por_delitos,
    limpiar_delitos,
    slug_sentencia,
)
from zona4_graph_loader.domain.date_norm import parse_ddmmyyyy, validar_fecha_de_hecho
from zona4_graph_loader.domain.text_norm import clean_text, slugify_name

FUENTE = "minjus_victimas"


def build_minjus_victimas_rows(
    data: List[Dict[str, Any]],
    *,
    ccd_key_by_slug: Dict[str, str],
    sentencias_index: Dict[str, Dict[str, Any]],
) -> CanonicalDataset:
    """Convierte las víctimas de MinJus GBA al CDM.

    NO genera aristas SECUESTRADO_EN: `lugar_de_secuestro` es texto narrativo y su
    parsing quedó fuera de alcance. La fecha de secuestro se persiste en el nodo
    (`fecha_secuestro`) para no perderla y para alimentar la reconciliación.

    La capa espacial sale de `centros_clandestinos`, que trae URLs resolubles
    contra el mapa que produce el builder de CCDs.
    """
    personas: List[Dict[str, Any]] = []
    eventos: List[Dict[str, Any]] = []
    relaciones: List[Dict[str, Any]] = []
    entidades: Dict[str, Dict[str, Any]] = {}
    rel_contexto: List[Dict[str, Any]] = []

    def registrar_entidad(entidad_key, tipo_entidad, campo, valor, tipo_relacion, persona_key, *, slug_valor):
        """Registra una entidad de contexto y su arista, salvo que `slug_valor`
        (el slug del valor de origen, antes de mezclarlo con ningún otro
        componente de la clave) sea vacío.

        MinJus usa el guión largo "–" (y a veces un "." suelto) como placeholder
        de "sin dato" en varios campos de `datos_personales`, y ninguno de los
        dos está en el conjunto de centinelas de `clean_text` (que es compartido
        por todos los builders). `slugify_name` reduce ambos a la cadena vacía,
        así que un slug vacío es la señal de que el valor de origen no era un
        dato real. Sin este guardia, esos placeholders se convierten en nodos
        reales (`org:`, `institucion:`, `profesion:`) que actúan como atractores
        falsos: docenas de víctimas terminarían compartiendo una "organización"
        u "oficio" que nunca existió. Para el alias, `entidad_key` lleva además
        el slug de la persona (`alias_persona:{slug}|{persona_slug}`), que nunca
        es vacío, así que hay que chequear `slug_valor` (el término del apodo)
        por separado en vez de derivarlo de `entidad_key`. El fix se localiza
        aquí, no en `text_norm.clean_text`, porque ese sentinel set es
        compartido por todos los builders del proyecto.
        """
        if not slug_valor:
            return
        entidades.setdefault(entidad_key, {
            "entidad_key": entidad_key,
            "tipo_entidad": tipo_entidad,
            campo: valor,
            "fuente": FUENTE,
        })
        rel_contexto.append({
            "persona_key": persona_key,
            "entidad_key": entidad_key,
            "tipo_relacion": tipo_relacion,
            "fecha": "DESCONOCIDA",
            "origen": FUENTE,
        })

    for item in data:
        slug = slug_persona_minjus(item.get("source_url"), "victima")
        nombre = clean_text(item.get("nombre"))
        if not slug or not nombre:
            continue

        persona_key = f"minjus_victima:{slug}"
        datos = item.get("datos_personales") or {}
        # Fix E (auditoría 2026-08-29, hallazgo I6): 5 de los 12 registros con
        # `Persona.fecha_secuestro` imposible (fuera de 1976-1983, algunos en
        # 2023-2077) vienen de este campo. Esa misma fecha se propaga a
        # `PRESENTE_EN` más abajo, así que validarla acá corrige ambos a la
        # vez. Se descarta (None -> "DESCONOCIDA"), no se corrige el valor.
        fecha_secuestro = validar_fecha_de_hecho(
            parse_ddmmyyyy(clean_text(datos.get("fecha_de_secuestro")))
        )

        personas.append({
            "persona_key": persona_key,
            "nombre": nombre,
            "genero": "INDETERMINADO",
            "fuente": FUENTE,
            "roles": ["VICTIMA"],
            "fecha_secuestro": fecha_secuestro,
        })

        # Fix E (auditoría 2026-08-29, hallazgo I3d, hallado en verificación
        # posterior a la carga completa): "No determinado"/"Desconocida"/
        # "No especificado" también aparecen como valor de `militancia` (4
        # registros reales: Álvarez Carrera, Bietti, Botazzi, Gildengers) y
        # generaban un :Org sentinel igual que `Fuerza` -mismo defecto,
        # campo distinto. Mismo guardia, sin propiedad de respaldo nueva en
        # la persona (a diferencia de `fuerza`): "militancia" no tiene hoy
        # una propiedad `Persona.militancia` a la que sumarse sin abrir otra
        # decisión de modelado fuera de alcance.
        militancia = clean_text(datos.get("militancia"))
        if militancia and militancia.upper() not in SENTINEL_ORG_VALUES:
            slug_militancia = slugify_name(militancia.upper())
            registrar_entidad(
                f"org:{slug_militancia}", "Org", "nombre",
                militancia.upper(), "PARTE_DE", persona_key,
                slug_valor=slug_militancia,
            )

        # Fix E (auditoría 2026-08-29, hallazgo I3d): "NO DETERMINADO",
        # "NO ESPECIFICADO", "NO ESPECIFICA", "DESCONOCIDO"/"DESCONOCIDA" no
        # nombran una institución -son la ausencia del dato. Materializarlos
        # crea un puñado de nodos :Institución que agrupan falsamente a
        # personas sin ningún vínculo real entre sí más que "la fuente no
        # sabía dónde trabajaban/estudiaban". Coincidencia exacta únicamente:
        # valores narrativos más largos que empiezan con una de estas
        # palabras pero agregan información real ("DESCONOCIDO, PERO LA
        # VICTIMA ESTUDIABA PARA SER MAESTRO...") no son sentinels puros y
        # quedan fuera de este fix (hallazgo I3c, no arreglado).
        trabajo = clean_text(datos.get("lugar_de_trabajo"))
        if trabajo and trabajo.upper() not in SENTINEL_INSTITUCION_VALUES:
            slug_trabajo = slugify_name(trabajo.upper())
            registrar_entidad(
                f"institucion:{slug_trabajo}", "Institucion", "nombre",
                trabajo.upper(), "TRABAJO_EN", persona_key,
                slug_valor=slug_trabajo,
            )

        # `dónde_estudió` son instituciones (facultades, colegios, universidades:
        # "UBA", "UNLP", "Facultad de Medicina"), no oficios. Un mismo valor
        # puede coincidir con `lugar_de_trabajo` para alguien que trabajó y
        # estudió en el mismo sitio: eso es correcto, no una colisión a
        # desambiguar — un solo nodo Institucion con dos aristas de tipo
        # distinto (TRABAJO_EN, ESTUDIO_EN).
        estudios = clean_text(datos.get("dónde_estudió"))
        if estudios and estudios.upper() not in SENTINEL_INSTITUCION_VALUES:
            slug_estudios = slugify_name(estudios.upper())
            registrar_entidad(
                f"institucion:{slug_estudios}", "Institucion", "nombre",
                estudios.upper(), "ESTUDIO_EN", persona_key,
                slug_valor=slug_estudios,
            )

        apodo = clean_text(datos.get("apodo"))
        if apodo:
            slug_apodo = slugify_name(apodo)
            registrar_entidad(
                f"alias_persona:{slug_apodo}|{slug}", "AliasPersona", "alias",
                apodo, "IDENTIFICA_A", persona_key,
                slug_valor=slug_apodo,
            )

        for ccd in item.get("centros_clandestinos") or []:
            slug_centro = slug_ccd(ccd.get("url"))
            lugar_key = ccd_key_by_slug.get(slug_centro or "")
            if not lugar_key:
                continue
            eventos.append({
                "persona_key": persona_key,
                "lugar_key": lugar_key,
                "tipo_relacion": "PRESENTE_EN",
                "fecha": fecha_secuestro or "DESCONOCIDA",
                "origen": FUENTE,
            })

        for sentencia in item.get("sentencias") or []:
            slug_sent = slug_sentencia(sentencia.get("sentencia_url"))
            meta = sentencias_index.get(slug_sent or "")
            if meta:
                origen = meta["origen"]
                fecha_sentencia = meta.get("fecha_sentencia") or "DESCONOCIDA"
            elif slug_sent:
                # Slug real pero fuera del índice (sentencia no encontrada en el
                # archivo de sentencias). Se deriva del propio slug, no de un
                # literal por-builder, para que el mismo hecho compartido con el
                # builder de imputados produzca el mismo `fuente` aunque el
                # índice cambie entre corridas.
                origen = f"{FUENTE_SENTENCIAS}:{slug_sent}"
                fecha_sentencia = "DESCONOCIDA"
            else:
                origen = FUENTE_TORTURO_A_SIN_SENTENCIA
                fecha_sentencia = "DESCONOCIDA"

            for imputado in sentencia.get("imputados") or []:
                slug_imputado = slug_persona_minjus(imputado.get("imputado_url"), "imputado")
                if not slug_imputado:
                    continue
                delitos = imputado.get("delitos")
                relaciones.append({
                    "source_key": f"minjus_imputado:{slug_imputado}",
                    "target_key": persona_key,
                    # Fix C1: sólo TORTURO_A cuando la sentencia condena por
                    # tormentos a esta víctima en particular; el resto de los
                    # pares (p.ej. sustracción de menor) recibe IMPUTADO_POR.
                    # Ambos tipos llevan `delitos` para que la arista sea
                    # auditable frente a la sentencia real. Misma función
                    # compartida que usa el builder de imputados, para que
                    # ambos lados de un mismo par clasifiquen igual.
                    "tipo": clasificar_relacion_por_delitos(delitos),
                    "delitos": limpiar_delitos(delitos),
                    # La fuente no registra cuándo ocurrió la tortura (el
                    # hecho): "fecha" queda en DESCONOCIDA en vez de tomar la
                    # fecha del fallo, que es procedencia (Fix 9), no el hecho.
                    "fecha": "DESCONOCIDA",
                    "fecha_sentencia": fecha_sentencia,
                    "fuente": origen,
                    "target_nombre": nombre,
                    "target_genero": "INDETERMINADO",
                    "target_fuente": FUENTE,
                })

    return {
        "personas": personas,
        "eventos_espaciales": eventos,
        "relaciones_interpersonales": relaciones,
        "entidades_contexto": list(entidades.values()),
        "relaciones_contexto": rel_contexto,
    }

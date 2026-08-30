from __future__ import annotations

from typing import Any, Dict, List

from zona4_graph_loader.builders.base import CanonicalDataset
from zona4_graph_loader.domain.text_norm import clean_text

FUENTE = "archivo_memoria"
INSTITUCION_UNIVERSITARIA_KEY = "institucion:universidad_sin_especificar"


def build_archivo_memoria_rows(data: List[Dict[str, Any]]) -> CanonicalDataset:
    """Convierte el Archivo de la Memoria de San Martín al CDM.

    Fix B (auditoría 2026-08-29, hallazgo C2): este builder generaba una
    arista `SECUESTRADO_EN` a partir del campo `lugar`. Se investigó qué
    denota `lugar` en los 303 registros y NO es el lugar del secuestro:

    - `lugar` sólo toma 11 valores distintos, todos barrios del Partido de
      General San Martín (San Martín, Villa Ballester, José León Suárez,
      Villa Lynch, Villa Maipú, San Andrés, Villa Concepción, Billinghurst,
      Tropezón, Villa Zagala, Villa Libertad) — es la categoría barrial bajo
      la que el archivo municipal organiza cada ficha, no un dato extraído
      del hecho.
    - En 159/303 registros (52 %) la frase de secuestro de `descripcion`
      nombra explícitamente OTRO lugar (a veces otra jurisdicción: Barrancas
      de Belgrano/CABA, Vicente López, Morón, Don Torcuato, La Tablada,
      Boulogne/San Isidro, etc.), contradiciendo a `lugar`.
    - En 64/303 registros (21 %) el valor de `lugar` ni siquiera aparece en
      ningún lugar del texto de `descripcion` (ni como domicilio, ni como
      lugar de trabajo, ni como residencia familiar): es metadata curatorial
      del archivo, no un hecho biográfico verificable en la propia fuente.

    Re-tipar la arista a `PRESENTE_EN` (presencia genérica) tampoco es
    honesto: no hay ninguna fecha ni evidencia de que la persona haya estado
    en ese barrio en un momento dado -y mezclaría entidades geopolíticas de
    barrio en un tipo de arista que hoy apunta 100% a `:Lugar` de tipo CCD.
    Por eso se elige NO generar ningún evento espacial ni nodo `:Lugar` a
    partir de `lugar`: el dato no soporta ninguna arista geográfica del
    modelo sin inventar lo que la fuente no dice. La fecha de desaparición
    se sigue persistiendo en `Persona.fecha_secuestro`, igual que hace
    MinJus con su propio `lugar_de_secuestro` narrativo.

    Efecto: esta fuente pierde su capa espacial completa (0 aristas
    geográficas desde archivo_memoria; antes 303 `SECUESTRADO_EN`). Es el
    foco geográfico declarado del proyecto para esta fuente, así que se
    reporta sin atenuantes en el reporte de fixes.
    """
    personas: List[Dict[str, Any]] = []
    entidades: Dict[str, Dict[str, Any]] = {}
    rel_contexto: List[Dict[str, Any]] = []

    for indice, item in enumerate(data):
        nombre = clean_text(item.get("nombre"))
        if not nombre:
            continue

        persona_key = f"{FUENTE}:{indice}"
        personas.append({
            "persona_key": persona_key,
            "nombre": nombre,
            "genero": "INDETERMINADO",
            "fuente": FUENTE,
            "roles": ["VICTIMA"],
            "fecha_nacimiento": clean_text(item.get("fecha_nacimiento")),
            "fecha_secuestro": clean_text(item.get("fecha_desaparicion_normalizada")),
        })

        if item.get("estudiante_universitario"):
            entidades.setdefault(INSTITUCION_UNIVERSITARIA_KEY, {
                "entidad_key": INSTITUCION_UNIVERSITARIA_KEY,
                "tipo_entidad": "Institucion",
                "nombre": "UNIVERSIDAD SIN ESPECIFICAR",
                "fuente": FUENTE,
            })
            rel_contexto.append({
                "persona_key": persona_key,
                "entidad_key": INSTITUCION_UNIVERSITARIA_KEY,
                "tipo_relacion": "ESTUDIO_EN",
                "fecha": "DESCONOCIDA",
                "origen": FUENTE,
            })

    return {
        "personas": personas,
        "entidades_contexto": list(entidades.values()),
        "relaciones_contexto": rel_contexto,
    }

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from zona4_graph_loader.builders.base import CanonicalDataset
from zona4_graph_loader.domain.name_similarity import name_similarity_score, name_token_set
from zona4_graph_loader.domain.text_norm import slugify_name

# De mayor a menor prioridad. La clave canónica de un merge sale de la fuente
# más alta de esta lista, para que un merge nunca reescriba las claves de lo que
# ya estaba cargado en el grafo.
SOURCE_PRIORITY = [
    "detalles_personas",
    "nietxs_relacion",
    "archivo_memoria",
    "minjus_victimas",
    "minjus_imputados",
    "juicios_condenados",
]

FUZZY_THRESHOLD = 0.96
MAX_FUZZY_CANDIDATES = 3

# Campos que _absorber ya trata con lógica propia: no se pisan con el volcado
# genérico de campos de `otro`.
_ABSORBER_CAMPOS_ESPECIALES = {"persona_key", "nombre", "fuente", "roles", "claves_alt", "genero"}


@dataclass
class IdentityReport:
    merges: List[Dict[str, Any]] = field(default_factory=list)
    candidatos: List[Dict[str, Any]] = field(default_factory=list)


def _priority(fuente: Optional[str]) -> int:
    try:
        return SOURCE_PRIORITY.index(fuente or "")
    except ValueError:
        return len(SOURCE_PRIORITY)


def _canonical_of(personas: List[Dict[str, Any]]) -> Dict[str, Any]:
    return min(personas, key=lambda p: (_priority(p.get("fuente")), p["persona_key"]))


def _fechas_confirman(a: Dict[str, Any], b: Dict[str, Any]) -> Optional[str]:
    """Devuelve el campo de fecha que confirma que `a` y `b` son la misma persona.

    Evalúa AMBOS campos de fecha. Si alguno está presente en los dos registros y
    los valores no coinciden, es un veto: se devuelve None sin importar si el
    otro campo sí coincide. Solo si ningún campo compartido contradice al otro
    se devuelve el primer campo que efectivamente confirmó la coincidencia.
    """
    confirmaciones: List[str] = []
    for campo in ("fecha_nacimiento", "fecha_secuestro"):
        va, vb = a.get(campo), b.get(campo)
        if va and vb:
            if va != vb:
                return None
            confirmaciones.append(campo)
    return confirmaciones[0] if confirmaciones else None


def _fechas_contradicen(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    """True si algún campo de fecha presente en ambos registros no coincide."""
    for campo in ("fecha_nacimiento", "fecha_secuestro"):
        va, vb = a.get(campo), b.get(campo)
        if va and vb and va != vb:
            return True
    return False


def _absorber(canonico: Dict[str, Any], otro: Dict[str, Any]) -> None:
    """Vuelca en `canonico` la información de `otro` sin pisar lo que ya tiene."""
    claves_alt = set(canonico.get("claves_alt") or [])
    claves_alt.add(otro["persona_key"])
    claves_alt.update(otro.get("claves_alt") or [])
    claves_alt.discard(canonico["persona_key"])
    canonico["claves_alt"] = sorted(claves_alt)

    fuentes = set()
    for persona in (canonico, otro):
        fuente = persona.get("fuente")
        if fuente:
            fuentes.update(fuente.split("|"))
    canonico["fuente"] = "|".join(sorted(fuentes))

    canonico["roles"] = sorted(set(canonico.get("roles") or []) | set(otro.get("roles") or []))

    # Cualquier otro campo de `otro`, ausente o falsy en `canonico`, se completa.
    # Los campos con manejo propio (arriba, o género abajo) quedan afuera para
    # no pisarlos dos veces.
    for campo, valor in otro.items():
        if campo in _ABSORBER_CAMPOS_ESPECIALES:
            continue
        if not canonico.get(campo) and valor:
            canonico[campo] = valor

    if canonico.get("genero") in (None, "INDETERMINADO") and otro.get("genero") not in (
        None, "INDETERMINADO",
    ):
        canonico["genero"] = otro["genero"]


def _reescribir_referencias(dataset: CanonicalDataset, key_map: Dict[str, str]) -> None:
    if not key_map:
        return

    relaciones = dataset.get("relaciones_interpersonales")
    if relaciones:
        for fila in relaciones:
            for campo in ("source_key", "target_key"):
                if fila.get(campo) in key_map:
                    fila[campo] = key_map[fila[campo]]
        # Un merge puede dejar una relación apuntando a sí misma (ambos extremos
        # resueltos al mismo canónico); esa fila sería un self-loop en el grafo.
        dataset["relaciones_interpersonales"] = [
            fila for fila in relaciones if fila.get("source_key") != fila.get("target_key")
        ]

    for fila in dataset.get("eventos_espaciales", []):
        if fila.get("persona_key") in key_map:
            fila["persona_key"] = key_map[fila["persona_key"]]
    for fila in dataset.get("relaciones_contexto", []):
        if fila.get("persona_key") in key_map:
            fila["persona_key"] = key_map[fila["persona_key"]]


def _candidato(a: str, b: str, metodo: str, score: float, slug: str, confianza: str) -> Dict[str, Any]:
    # Orden estable para que la arista no dependa del orden de iteración.
    origen, destino = sorted((a, b))
    return {
        "placeholder_key": origen,
        "candidate_key": destino,
        "metodo": metodo,
        "score": round(score, 3),
        "slug": slug,
        "confianza": confianza,
        "fuente": "reconciliacion_cross_fuente",
    }


def resolve_identities(dataset: CanonicalDataset) -> IdentityReport:
    """Fusiona personas equivalentes entre fuentes y propone candidatos dudosos.

    Muta `dataset` in place: reemplaza `personas` por la lista deduplicada y
    reescribe las referencias en relaciones y eventos.
    """
    report = IdentityReport()
    personas = dataset.get("personas") or []
    if not personas:
        return report

    por_slug: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for persona in personas:
        nombre = persona.get("nombre")
        if not nombre:
            continue
        por_slug[slugify_name(nombre)].append(persona)

    key_map: Dict[str, str] = {}
    absorbidas: Set[str] = set()

    # --- Paso 1: merge determinista dentro de cada bloque de nombre idéntico ---
    for slug, grupo in por_slug.items():
        if len(grupo) < 2:
            continue

        ordenado = sorted(grupo, key=lambda p: (_priority(p.get("fuente")), p["persona_key"]))
        n = len(ordenado)

        # Grafo de confirmación: hay arista entre i y j solo si vienen de
        # fuentes distintas Y una fecha los confirma sin contradicción.
        confirmado = [[False] * n for _ in range(n)]
        for i in range(n):
            for j in range(i + 1, n):
                if ordenado[i].get("fuente") == ordenado[j].get("fuente"):
                    continue
                if _fechas_confirman(ordenado[i], ordenado[j]) is not None:
                    confirmado[i][j] = confirmado[j][i] = True

        # Componentes conexas de ese grafo.
        visitado = [False] * n
        componentes: List[List[int]] = []
        for i in range(n):
            if visitado[i]:
                continue
            visitado[i] = True
            pila = [i]
            componente = [i]
            while pila:
                actual = pila.pop()
                for vecino in range(n):
                    if confirmado[actual][vecino] and not visitado[vecino]:
                        visitado[vecino] = True
                        pila.append(vecino)
                        componente.append(vecino)
            componentes.append(sorted(componente))

        for indices in componentes:
            if len(indices) < 2:
                continue

            # Una componente conexa solo fusiona si es un clique completo: cada
            # par dentro de ella debe estar confirmado. Si un tercer registro la
            # conecta pero no todos los pares se confirman entre sí (o alguno
            # comparte fuente), es una componente ambigua: nadie se fusiona y
            # todos quedan disponibles para la revisión humana como candidatos.
            es_clique = all(
                confirmado[a][b]
                for pos, a in enumerate(indices)
                for b in indices[pos + 1:]
            )
            if not es_clique:
                continue

            cluster = [ordenado[i] for i in indices]
            canonico = _canonical_of(cluster)
            otros = [p for p in cluster if p is not canonico]

            # El motivo de cada merge se congela ANTES de tocar `canonico`: una
            # vez que `_absorber` empieza a mutarlo, comparar contra el estado
            # mutado ya no refleja lo que realmente confirmó la fusión.
            motivos: List[str] = []
            for otro in otros:
                motivo = _fechas_confirman(canonico, otro)
                if motivo is None:
                    raise ValueError(
                        "Inconsistencia interna: clique confirmado sin fecha entre "
                        f"{canonico['persona_key']!r} y {otro['persona_key']!r}"
                    )
                motivos.append(motivo)

            for otro, motivo in zip(otros, motivos):
                _absorber(canonico, otro)
                key_map[otro["persona_key"]] = canonico["persona_key"]
                absorbidas.add(otro["persona_key"])
                report.merges.append({
                    "canonical_key": canonico["persona_key"],
                    "absorbed_key": otro["persona_key"],
                    "motivo": motivo,
                })

        # Los que quedaron sin fusionar dentro del bloque, pero vienen de fuentes
        # distintas, son candidatos para revisión humana. Se clasifican una sola
        # vez: si sus fechas contradicen directamente, la etiqueta lo advierte;
        # si simplemente no hay fecha que confirme ni contradiga, es el caso
        # "mismo nombre sin fecha" de siempre.
        sobrevivientes = [p for p in ordenado if p["persona_key"] not in absorbidas]
        for i, a in enumerate(sobrevivientes):
            for b in sobrevivientes[i + 1:]:
                if a.get("fuente") == b.get("fuente"):
                    continue
                if _fechas_contradicen(a, b):
                    report.candidatos.append(
                        _candidato(a["persona_key"], b["persona_key"],
                                   "nombre_exacto_fecha_contradictoria", 0.5, slug, "baja")
                    )
                else:
                    report.candidatos.append(
                        _candidato(a["persona_key"], b["persona_key"],
                                   "nombre_exacto_sin_fecha", 0.9, slug, "media")
                    )

    dataset["personas"] = [p for p in personas if p["persona_key"] not in absorbidas]
    _reescribir_referencias(dataset, key_map)

    # --- Paso 2: candidatos fuzzy entre bloques distintos ---
    slugs = sorted({slugify_name(p["nombre"]) for p in dataset["personas"] if p.get("nombre")})
    token_sets = {s: name_token_set(s.replace("_", " ")) for s in slugs}
    por_token: Dict[str, Set[str]] = defaultdict(set)
    for slug, tokens in token_sets.items():
        for token in tokens:
            por_token[token].add(slug)

    claves_por_slug: Dict[str, List[str]] = defaultdict(list)
    fuente_por_clave: Dict[str, Optional[str]] = {}
    for persona in dataset["personas"]:
        if not persona.get("nombre"):
            continue
        claves_por_slug[slugify_name(persona["nombre"])].append(persona["persona_key"])
        fuente_por_clave[persona["persona_key"]] = persona.get("fuente")

    vistos: Set[Tuple[str, str]] = set()
    for slug in slugs:
        pool: Set[str] = set()
        for token in token_sets[slug]:
            pool.update(por_token.get(token, set()))
        pool.discard(slug)

        puntuados: List[Tuple[float, str]] = []
        for otro_slug in pool:
            if abs(len(token_sets[otro_slug]) - len(token_sets[slug])) > 2:
                continue
            score = name_similarity_score(slug.replace("_", " "), otro_slug.replace("_", " "))
            if score >= FUZZY_THRESHOLD:
                puntuados.append((score, otro_slug))

        puntuados.sort(key=lambda item: (-item[0], item[1]))
        for score, otro_slug in puntuados[:MAX_FUZZY_CANDIDATES]:
            par_slug = tuple(sorted((slug, otro_slug)))
            if par_slug in vistos:
                continue
            vistos.add(par_slug)
            for clave_a in claves_por_slug[slug]:
                for clave_b in claves_por_slug[otro_slug]:
                    if fuente_por_clave[clave_a] == fuente_por_clave[clave_b]:
                        continue
                    report.candidatos.append(
                        _candidato(clave_a, clave_b, "set_dice_typo_v1", score, slug, "baja")
                    )

    return report

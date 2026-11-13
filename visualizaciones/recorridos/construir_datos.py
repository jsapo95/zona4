#!/usr/bin/env python3
"""Arma los datos de la visualización de recorridos (`datos/recorridos.js`).

Cada persona víctima se ubica en hasta cuatro etapas abstractas:

    0. secuestro   arista SECUESTRADO_EN del CDM (Parque de la Memoria)
    1. cautiverio  aristas PRESENTE_EN del CDM (CCDs de RUVTE y MinJus GBA)
    2. asesinato   arista ASESINADO_EN del CDM (Parque de la Memoria)
    3. final       lugar de hallazgo de los restos, leído del campo
                   `descripcion_datos_de_identificacion` del Parque (no está
                   en el grafo)

Las etapas no son fechas: el grafo no guarda el orden entre CCDs ni la fecha
de ingreso a cada uno (ver Claude-Felipe/README, trampa de PRESENTE_EN). Si una
persona pasó por varios CCDs, en la etapa 1 aparece en todos a la vez, cada
uno con peso 1/k.

Se arman dos grupos:

    A  con lugar final conocido: los restos fueron hallados y el texto dice dónde.
    B  sin lugar final conocido: desaparecidas o asesinadas sin hallazgo de
       restos registrado. Las personas liberadas, fugadas o restituidas
       quedan afuera de los dos grupos (se cuentan aparte).

Uso:
    .venv/Scripts/python visualizaciones/recorridos/construir_datos.py
"""

from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(AQUI))

from cdm import construir_cdm  # noqa: E402
from zona4_graph_loader.builders.minjus_imputados import slug_persona_minjus  # noqa: E402
from zona4_graph_loader.domain.place_norm import resolve_place  # noqa: E402
from zona4_graph_loader.domain.text_norm import strip_accents  # noqa: E402

SALIDA = AQUI / "datos" / "recorridos.js"
CENTROIDES = AQUI / "datos" / "centroides_georef.json"
CABA = "ciudad autonoma de buenos aires"

ETAPAS = [
    {"id": "secuestro", "nombre": "Secuestro", "arista": "SECUESTRADO_EN"},
    {"id": "cautiverio", "nombre": "Centro clandestino", "arista": "PRESENTE_EN"},
    {"id": "asesinato", "nombre": "Asesinato", "arista": "ASESINADO_EN"},
    {"id": "final", "nombre": "Hallazgo de restos", "arista": None},
]

# Precisión de cada coordenada, de más a menos fina. La visualización la
# muestra y la usa para dispersar levemente los puntos que comparten centroide.
SITIO, LOCALIDAD, CABA_GENERICA, DEPARTAMENTO = "sitio", "localidad", "caba", "departamento"
NOMBRE_CABA = "Ciudad de Buenos Aires (sin barrio)"


def norm(texto: Optional[str]) -> str:
    """Minúsculas, sin acentos ni puntuación; expande abreviaturas frecuentes."""
    if not texto:
        return ""
    t = strip_accents(texto).lower().replace("_", " ")
    t = re.sub(r"[^a-z0-9]+", " ", t)
    t = re.sub(r"\bgral\b", "general", t)
    t = re.sub(r"\bpcia\b", "provincia", t)
    t = re.sub(r"\bbs as\b", "buenos aires", t)
    return re.sub(r"\s+", " ", t).strip()


def segmentos(lugar_key: str) -> Dict[str, str]:
    """`lugar:CIUDAD:la_plata|lugar:PROVINCIA:buenos_aires|...` -> {CIUDAD: 'la plata', ...}."""
    out = {}
    for parte in lugar_key.split("|"):
        _, tipo, slug = parte.split(":", 2)
        out[tipo] = norm(slug)
    return out


# --------------------------------------------------------------------------
# Coordenadas
# --------------------------------------------------------------------------

# Nombres del grafo que Georef escribe distinto (revisados a mano en Georef).
ALIAS_LOCALIDADES = {
    "william morris": "william c morris",
    "villa tesei": "villa santos tesei",
    "lavallol": "llavallol",
    "pte derqui": "presidente derqui",
    "gregogio de laferrere": "gregorio de laferrere",
    "pompeya": "nueva pompeya",
    "palermo chico": "palermo",
    "bosques de palermo": "palermo",
}

def _nombre(row: Dict[str, Any]) -> str:
    """Nombre de Georef con tildes, con su partido si no es el mismo nombre."""
    nombre, depto = row["nombre"], row.get("departamento")
    if row.get("provincia", "").startswith("Ciudad Aut"):
        return f"{nombre} (CABA)"
    return f"{nombre} ({depto})" if depto and norm(depto) != norm(nombre) else nombre


class Centroides:
    """Centroides de Georef indexados por (nombre, provincia) normalizados."""

    def __init__(self, path: Path) -> None:
        with path.open(encoding="utf-8") as f:
            cat = json.load(f)
        self.provincias = {norm(p["nombre"]): p for p in cat["provincias"]}
        self.indices: Dict[str, Dict[Tuple[str, str], List[Dict[str, Any]]]] = {}
        for nivel in ("localidades", "municipios", "asentamientos", "departamentos"):
            idx: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
            for row in cat[nivel]:
                idx[(norm(row["nombre"]), self._provincia(norm(row["provincia"])))].append(row)
            self.indices[nivel] = idx

    def _provincia(self, nombre: str) -> str:
        # "tierra del fuego antartida e islas..." en Georef, "tierra del fuego" en el grafo.
        if nombre in self.provincias:
            return nombre
        for completo in self.provincias:
            if completo.startswith(nombre) or nombre.startswith(completo):
                return completo
        return nombre

    def _buscar(self, nivel: str, nombre: str, provincia: str, departamento: str = "") -> Optional[Dict[str, Any]]:
        filas = self.indices[nivel].get((nombre, self._provincia(provincia)), [])
        if departamento:
            mismas = [r for r in filas if norm(r.get("departamento")) == departamento]
            filas = mismas or filas
        return filas[0] if filas else None

    def _por_prefijo(self, nombre: str, provincia: str) -> Optional[Tuple[float, float]]:
        """Promedio de los asentamientos "<nombre> ..." (Don Torcuato Este/Oeste)."""
        provincia = self._provincia(provincia)
        filas = [
            rows[0] for (n, p), rows in self.indices["asentamientos"].items()
            if p == provincia and n.startswith(nombre + " ")
        ]
        if not filas:
            return None
        lat = sum(r["lat"] for r in filas) / len(filas)
        lon = sum(r["lon"] for r in filas) / len(filas)
        # Si los asentamientos están lejos entre sí no es un mismo lugar.
        if max(abs(r["lat"] - lat) + abs(r["lon"] - lon) for r in filas) > 0.05:
            return None
        return lat, lon

    def por_nombre(self, nombre: str, provincia: Optional[str] = None) -> Optional[Tuple[float, float, str, str]]:
        """Busca un nombre exacto de localidad en todo el país (o en una provincia).

        Sólo devuelve algo si todas las coincidencias caen en el mismo lugar:
        "Caballito" o "Ezeiza" sí; "San Martín" (hay decenas) no.
        """
        if provincia == "capital federal":
            provincia = CABA
        nombre = ALIAS_LOCALIDADES.get(nombre, nombre)
        filas = [
            r for (n, p), rows in self.indices["localidades"].items() if n == nombre
            and (provincia is None or p == self._provincia(provincia)) for r in rows
        ]
        if not filas:
            return None
        if max(abs(r["lat"] - filas[0]["lat"]) + abs(r["lon"] - filas[0]["lon"]) for r in filas) > 0.05:
            return None
        return filas[0]["lat"], filas[0]["lon"], LOCALIDAD, _nombre(filas[0])

    def ubicar(self, lugar_key: str) -> Tuple[Optional[Tuple[float, float, str, str]], str]:
        """Devuelve ((lat, lon, precision, nombre), motivo). Si no ubica, la tupla es None."""
        seg = segmentos(lugar_key)
        if seg.get("PAIS") != "argentina":
            return None, "exterior"
        provincia = seg.get("PROVINCIA", "")
        ciudad, departamento = seg.get("CIUDAD"), seg.get("DEPARTAMENTO", "")
        if ciudad:
            if ciudad == CABA:
                p = self.provincias[CABA]
                return (p["lat"], p["lon"], CABA_GENERICA, NOMBRE_CABA), "ok"
            # Las claves CIUDAD sin DEPARTAMENTO vienen de EQUIV_CITIES o de
            # abreviaturas, no de Georef: "SAN MARTIN" es General San Martín y
            # "JOSE LEON SUAREZ" es Villa José León Suárez. Se prueban esas
            # variantes en localidades y municipios antes que los
            # asentamientos, donde "San Martín" es un paraje de Magdalena.
            variantes = (ciudad, f"general {ciudad}", f"villa {ciudad}", f"el {ciudad}",
                         f"ingeniero {ciudad}", ALIAS_LOCALIDADES.get(ciudad, ciudad))
            for nivel in ("localidades", "municipios"):
                for variante in variantes:
                    row = self._buscar(nivel, variante, provincia, departamento)
                    if row:
                        return (row["lat"], row["lon"], LOCALIDAD, _nombre(row)), "ok"
            # Un asentamiento sólo si el nombre es único en la provincia.
            filas = self.indices["asentamientos"].get((ciudad, self._provincia(provincia)), [])
            if len(filas) == 1:
                return (filas[0]["lat"], filas[0]["lon"], LOCALIDAD, _nombre(filas[0])), "ok"
            row = self._buscar("departamentos", ciudad, provincia)
            if row:
                return (row["lat"], row["lon"], DEPARTAMENTO, _nombre(row)), "ok"
            prefijo = self._por_prefijo(ciudad, provincia)
            if prefijo:
                return (*prefijo, LOCALIDAD, ciudad.title()), "ok"
        if departamento:
            row = self._buscar("departamentos", departamento, provincia)
            if row:
                return (row["lat"], row["lon"], DEPARTAMENTO, _nombre(row)), "ok"
        if provincia == CABA and not ciudad:
            p = self.provincias[CABA]
            return (p["lat"], p["lon"], CABA_GENERICA, NOMBRE_CABA), "ok"
        if not ciudad and not departamento:
            # Sólo provincia: el centroide de Buenos Aires cae en medio de la
            # pampa, lejos de todo hecho real. Se prefiere no dibujarlo.
            return None, "solo_provincia"
        return None, "sin_centroide"


def ubicar_texto(texto: str, centroides: Centroides) -> Tuple[Optional[Tuple[float, float, str]], Optional[str]]:
    """Resuelve un texto libre con el resolver del grafo y lo ubica por centroide."""
    resuelto = resolve_place(texto)
    if not resuelto or not resuelto.get("lugar_key"):
        return None, None
    coords, _ = centroides.ubicar(resuelto["lugar_key"])
    return coords, resuelto.get("nombre_canonico")


PISTAS_PROVINCIA = {
    "buenos aires": "BS. AS.", "provincia de buenos aires": "BS. AS.", "bs as": "BS. AS.",
    "cordoba": "CORDOBA", "cba": "CORDOBA", "santa fe": "SANTA FE", "sta fe": "SANTA FE",
    "tucuman": "TUCUMAN", "entre rios": "ENTRE RIOS", "e rios": "ENTRE RIOS", "mendoza": "MENDOZA",
    "chaco": "CHACO", "corrientes": "CORRIENTES", "salta": "SALTA", "jujuy": "JUJUY",
    "misiones": "MISIONES", "neuquen": "NEUQUEN", "rio negro": "RIO NEGRO", "chubut": "CHUBUT",
    "la rioja": "LA RIOJA", "catamarca": "CATAMARCA", "san juan": "SAN JUAN", "san luis": "SAN LUIS",
    "santiago del estero": "SANTIAGO DEL ESTERO", "formosa": "FORMOSA", "la pampa": "LA PAMPA",
    "capital federal": "CAPITAL FEDERAL", "cap fed": "CAPITAL FEDERAL",
    "ciudad de buenos aires": "CAPITAL FEDERAL",
}
# Una calle, una intersección o un número no son un topónimo: el resolver
# los engancha con ciudades homónimas ("Perito Moreno y Dellepiane" -> Moreno).
_NO_TOPONIMO = re.compile(r"\d|\b(y|e|entre|esq|esquina|av|avenida|calle|ruta|km|camino|altura|frente)\b")
_ABREVIATURAS = [
    (r"\bBs\.?\s*As\b\.?", "Buenos Aires"), (r"\bCap\.?\s*Fed\b\.?", "Capital Federal"),
    (r"\bPcia\b\.?", "Provincia "), (r"\bGral\b\.?", "General"), (r"\bSgto\b\.?", "Sargento"),
    (r"\bSta\b\.?", "Santa"), (r"\bPque\b\.?", "Parque"), (r"\bDto\b\.?", "Departamento"),
    (r"\bE\.\s*R[ií]os\b", "Entre Ríos"), (r"\bCba\b\.?", "Córdoba"), (r"\bVte\b\.?", "Vicente"),
    (r"\bPza\b\.?", "Plaza"), (r"\bCem\b\.?", "Cementerio"), (r"\bMdP\b", "Mar del Plata"),
]
# Cuerpos de agua: "Río de la Plata" no es La Plata; no hay un punto honesto.
_AGUA = re.compile(r"\b(rio de la plata|riachuelo|aguas del|costa uruguaya)\b")
_FECHA = re.compile(
    r"\b\d{1,2}/\d{1,2}/\d{2,4}\b|\b\d{1,2} de [a-z]+ de \d{4}\b|\b(en )?(el )?(año )?(19|20)\d{2}\b", re.I
)
_PALABRAS_VACIAS = {"el", "la", "los", "las", "del", "de", "en", "un", "una"}


def expandir_abreviaturas(texto: str) -> str:
    for abrev, completo in _ABREVIATURAS:
        texto = re.sub(abrev, completo, texto, flags=re.I)
    return texto


def _candidatos(texto: str) -> List[str]:
    """Segmentos de `texto` que pueden ser un topónimo, en orden de prueba."""
    out = []
    # El punto de una inicial ("F. Alcorta") no separa segmentos.
    for s in re.split(r"[,;:|·•–]|(?<!\b[A-Za-z])\.", texto):
        # Lo que va entre comillas es el nombre propio de un sitio ("La Cueva
        # de los Leones"), no una localidad: se saca.
        s = re.sub(r"[\"“”«»][^\"“”«»]*[\"“”«»]?", " ", s).strip()
        n = norm(s)
        # "Bº Esperanza": un barrio suelto engancha localidades homónimas.
        if not n or n in PISTAS_PROVINCIA or _NO_TOPONIMO.search(n) or re.match(r"(b|barrio)\b", n):
            continue
        piezas = [s]
        if len(n.split()) > 4:
            # Narración: probar los trozos cortos entre "en", "localidad de",
            # etc. ("...un aeroclub en la localidad de Alvear" -> "Alvear").
            piezas = re.split(r"\b(?:en|localidad de|ciudad de|partido de|barrio de)\b", s)
        for pieza in piezas:
            palabras = pieza.split()
            while palabras and palabras[-1].lower() in _PALABRAS_VACIAS:
                palabras.pop()
            while palabras and palabras[0].lower() in {"en", "de", "del", "un", "una"}:
                palabras.pop(0)
            if len(piezas) > 1 and (len(palabras) > 4 or re.match(r"(b|barrio)\b", norm(" ".join(palabras)))):
                continue
            if palabras and " ".join(palabras).lower() not in _PALABRAS_VACIAS:
                out.append(" ".join(palabras))
    return out


def ubicar_fragmento(texto: str, centroides: Centroides) -> Tuple[Optional[Tuple[float, float, str]], Optional[str]]:
    """Ubica un texto narrativo por segmentos, prefiriendo no ubicar a ubicar mal.

    Saca fechas y códigos postales, parte por comas y puntos, descarta
    segmentos con números, calles o intersecciones, usa los nombres de
    provincia sólo como pista y prueba lo que va entre paréntesis al final.
    """
    t = expandir_abreviaturas(_FECHA.sub(" ", texto))
    t = re.sub(r"\b[A-Z]\d{4}[A-Z]{0,3}\b", " ", t)
    if _AGUA.search(norm(t)):
        return None, None
    entre_parentesis = " , ".join(re.findall(r"\(([^)]*)\)?", t))
    principal = re.sub(r"\([^)]*\)?", " ", t)
    segmentos_ = [s.strip() for s in re.split(r"[,;:|·•–.]", principal) if s.strip()]
    pista = next((PISTAS_PROVINCIA[norm(s)] for s in reversed(segmentos_) if norm(s) in PISTAS_PROVINCIA), None)
    provincia_pista = norm(pista) if pista else None
    for s in _candidatos(principal) + _candidatos(entre_parentesis):
        coords = centroides.por_nombre(norm(s), provincia_pista)
        if coords:
            return coords, s.upper()
        coords, nombre = ubicar_texto(f"{s}. {pista}" if pista else s, centroides)
        if coords:
            return coords, nombre
    if pista == "CAPITAL FEDERAL":
        # Una calle de CABA sin barrio: la ciudad alcanza como ubicación.
        p = centroides.provincias[CABA]
        return (p["lat"], p["lon"], CABA_GENERICA, NOMBRE_CABA), NOMBRE_CABA
    return None, None


def leer_sitios_eaaf() -> List[Dict[str, Any]]:
    sitios = []
    with (RAIZ / "data" / "raw" / "eaaf_lugares.csv").open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f, delimiter=";"):
            try:
                lat, lon = float(row["Lat"].strip()), float(row["Long"].strip())
            except ValueError:
                continue
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                continue  # mismo criterio que builders/eaaf_lugares.py
            sitios.append({
                "nombre": row["LUGAR DE HALLAZGO"].strip(),
                "localidad": row["LOCALIDAD"].strip(),
                "provincia": row["PROVINCIA"].strip(),
                "tipo": {"CEM": "cementerio", "CCD": "ccd", "EP": "espacio público"}.get(row["CEM - CCD - EP"].strip(), "sitio"),
                "lat": lat,
                "lon": lon,
            })
    return sitios


# Alias que el texto del Parque usa para sitios de EAAF y que no salen de
# "cementerio de <localidad>". Cada uno se revisó contra los textos reales.
ALIAS_SITIOS = {
    "pozo de vargas": "Pozo de Vargas",
    "pozo de varg": "Pozo de Vargas",
    "poozo de varg": "Pozo de Vargas",
    "arsenal miguel de az": "Ex CCD Arsenal Miguel de Azcuénaga",
    "arsenal de miguel az": "Ex CCD Arsenal Miguel de Azcuénaga",
    "la perla": "Ex CCD La Perla",
    "pozo de arana": "Comisaría de Arana",
    "puesto vasco": "Subcomisaría de Don Bosco- Puesto Vasco",
    "hospital posadas": "El Chalet- Hospital Nacional Profesor Alejandro Posadas",
    "chacarita": "Cementerio de la Chacarita",
    "la piedad": "Cementerio La Piedad",
    "cementerio de rosario": "Cementerio La Piedad",
    "cementerio de avellaneda": "Cementerio de Avellaneda- Sector 134",
    "cementerio municipal de avellaneda": "Cementerio de Avellaneda- Sector 134",
    "cementerio de avellanda": "Cementerio de Avellaneda- Sector 134",
    "cementerio de rafael calzada": "Cementerio de Almirante Brown",
    "cementerio municipal de rafael calzada": "Cementerio de Almirante Brown",
    "cementerio de derqui": "Cementerio de Presidente Derqui",
    "cementerio de san vicente cordoba": "Cementerio San Vicente",
    "cementerio de san martin": "Cementerio de General San Martín",
    "cementerio de general san martin": "Cementerio de General San Martín",
    "cementerio municipal de general san martin": "Cementerio de General San Martín",
    "cementerio de jose leon suarez": "Cementerio de General San Martín",
    "cementerio de san fernando": "Cementerio de San Fernando",
    "cementerio de virreyes": "Cementerio de San Fernando",
    "cementerio de boulogne": "Cementerio de Boulogne",
    "cementerio de buologne": "Cementerio de Boulogne",
    "cementerio de vicente lopez": "Cementerio de Olivos",
    "cementerio de merlo": "Cementerio Santa Mónica",
    "cementerio de mar del plata": "Cementerio Parque",
    "cementerio parque de mar del plata": "Cementerio Parque",
    "cementerio de berzategui": "Cementerio Parque Municipal de Berazategui",
    "cementerio de berazategui": "Cementerio Parque Municipal de Berazategui",
    "cementerio de san andres de giles": "Cementerio Norte|San Andrés de Giles",
    "cementerio norte de tucuman": "Cementerio Norte|San Miguel de Tucumán",
    "cementerio norte de la ciudad de tucuman": "Cementerio Norte|San Miguel de Tucumán",
    "cementerio norte tucuman": "Cementerio Norte|San Miguel de Tucumán",
    "cementerio de santa fe": "Cementerio Santa Fe de la Vera Cruz",
    "cementerio municipal de santa fe": "Cementerio Santa Fe de la Vera Cruz",
    "cementerio de colonia": "Cementerio de Colonia del Sacramento",
    "colonia uruguay": "Cementerio de Colonia del Sacramento",
    "cementerio de catamarca": "Cementerio Fray Mamerto Esquiú",
    "cementerio de andino": "Cementerio San Juan Bautista",
    "cementerio de timbues": "Cementerio Jesús María",
    "cementerio de parana": "Cementerio Santísima Trinidad",
    "cementerio de paso de los libres": "Cementerio de la Santa Cruz|Paso de los Libres",
    "cementerio de empedrado": "Cementerio San Roque",
    "cementerio de clodomira": "Cementerio La Esperanza",
    "cementerio de la ciudad de mendoza": "Cementerio de la ciudad de Mendoza",
    "cementerio de mendoza": "Cementerio de la ciudad de Mendoza",
    "laguna de rocha": "Cementerio de Rocha",
    "arsenal miguel de azu": "Ex CCD Arsenal Miguel de Azcuénaga",
    "cementerio de pozo hondo": "Cementerio de Pozo Hondo",
    "en pozo hondo": "Cementerio de Pozo Hondo",
}


class SitiosEAAF:
    def __init__(self) -> None:
        self.sitios = leer_sitios_eaaf()
        por_clave = {}
        for s in self.sitios:
            por_clave.setdefault(s["nombre"], s)
            por_clave[f"{s['nombre']}|{s['localidad']}"] = s
        alias: Dict[str, Dict[str, Any]] = {}
        for s in self.sitios:
            if s["tipo"] == "cementerio":
                alias.setdefault(f"cementerio de {norm(s['localidad'])}", s)
            alias.setdefault(norm(s["nombre"]), s)
        for frase, clave in ALIAS_SITIOS.items():
            alias[frase] = por_clave[clave]
        # "cementerio norte" a secas es ambiguo (hay varios): sólo con localidad.
        alias.pop("cementerio norte", None)
        self.alias = sorted(alias.items(), key=lambda kv: -len(kv[0]))

    def buscar(self, texto: str) -> Optional[Dict[str, Any]]:
        t = f" {norm(expandir_abreviaturas(texto))} ".replace(" cementario ", " cementerio ")
        t = re.sub(r" cementerio (municipal|parque) de ", " cementerio de ", t)
        for frase, sitio in self.alias:
            # Los alias manuales valen como prefijo ("arsenal miguel de az").
            if f" {frase} " in t or (frase in ALIAS_SITIOS and f" {frase}" in t):
                return sitio
        return None


_FRAGMENTO_LUGAR = [
    re.compile(r"aparici[oó]n\s*:\s*(?P<l>[^;]+)", re.I),
    re.compile(r"(?:hallad[oa]s?|exhumad[oa]s?|encontrad[oa]s?|apareci[oó]|aparecen?|enterrad[oa]s?)\s+(?:\S+\s+){0,8}?en\s+(?P<l>[^;]+)", re.I),
]


def ubicar_hallazgo(texto: str, sitios: SitiosEAAF, centroides: Centroides) -> Optional[Dict[str, Any]]:
    """Ubica el lugar donde se hallaron los restos según el texto del Parque."""
    sitio = sitios.buscar(texto)
    if sitio:
        return {"nombre": f"{sitio['nombre']} ({sitio['localidad']})", "tipo": sitio["tipo"],
                "lat": sitio["lat"], "lon": sitio["lon"], "precision": SITIO}
    for patron in _FRAGMENTO_LUGAR:
        m = patron.search(texto)
        if not m:
            continue
        fragmento = m.group("l")
        coords, nombre = ubicar_fragmento(fragmento, centroides)
        if coords:
            return {"nombre": coords[3] if len(coords) > 3 else (nombre or fragmento).title(), "tipo": "localidad del hallazgo",
                    "lat": coords[0], "lon": coords[1], "precision": coords[2]}
    return None


# --------------------------------------------------------------------------
# Estado de cada persona según las fuentes
# --------------------------------------------------------------------------

SOBREVIVIENTE = {"Persona liberada", "Persona fugado", "Persona restituida"}


def leer_fuentes() -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    with (RAIZ / "data" / "sources" / "parque_de_la_memoria.json").open(encoding="utf-8") as f:
        parque = {f"registro:{r['registro']}": r for r in json.load(f)}
    with (RAIZ / "data" / "raw" / "derechos_humanos_minjus_gba_victimas.json").open(encoding="utf-8") as f:
        minjus = {}
        for r in json.load(f):
            slug = slug_persona_minjus(r.get("source_url"), "victima")
            if slug:
                minjus[f"minjus_victima:{slug}"] = r
    return parque, minjus


# --------------------------------------------------------------------------
# Armado
# --------------------------------------------------------------------------

def main() -> None:
    print("corriendo el pipeline hasta el CDM (≈1 min)...", flush=True)
    cdm = construir_cdm()
    centroides = Centroides(CENTROIDES)
    sitios = SitiosEAAF()
    parque, minjus = leer_fuentes()

    lugares_cdm = {l["lugar_key"]: l for l in cdm["lugares"] if l.get("tipo_entidad") == "Lugar"}

    # Tabla de lugares de salida: [lat, lon, nombre, tipo, precision].
    lugares_out: List[List[Any]] = []
    indice_lugar: Dict[Any, int] = {}
    motivos: Dict[str, Counter] = defaultdict(Counter)

    def agregar_lugar(clave: str, lat: float, lon: float, nombre: str, tipo: str, precision: str) -> int:
        # Dos claves del grafo pueden caer en el mismo punto con el mismo
        # nombre (CORDOBA con y sin DEPARTAMENTO): se dibujan como un lugar.
        mismo_punto = (nombre, tipo, round(lat, 4), round(lon, 4))
        if clave not in indice_lugar:
            if mismo_punto not in indice_lugar:
                indice_lugar[mismo_punto] = len(lugares_out)
                lugares_out.append([round(lat, 5), round(lon, 5), nombre, tipo, precision])
            indice_lugar[clave] = indice_lugar[mismo_punto]
        return indice_lugar[clave]

    resolucion_grafo: Dict[str, Tuple[Optional[int], str]] = {}

    def resolver_lugar_del_grafo(lugar_key: str) -> Tuple[Optional[int], str]:
        lugar = lugares_cdm.get(lugar_key, {})
        nombre = (lugar.get("nombre") or lugar_key).title()
        if lugar.get("tipoGeopolitico") == "CCD":
            if lugar.get("lat") is not None and lugar.get("lon") is not None:
                return agregar_lugar(lugar_key, lugar["lat"], lugar["lon"], nombre, "ccd", SITIO), "ok"
            sitio = sitios.buscar(lugar.get("nombre", ""))
            if sitio:
                return agregar_lugar(lugar_key, sitio["lat"], sitio["lon"], nombre, "ccd", SITIO), "ok"
            # Sin coordenadas propias: se ubica por la localidad de su
            # dirección o, si no hay dirección, por la de su nombre
            # ("COMISARÍA 8ª DE LA PLATA").
            for parte in (lugar.get("ubicacion") or "", re.split(r"\bDE\b", lugar.get("nombre") or "")[-1]):
                coords, _ = ubicar_fragmento(parte, centroides) if parte.strip() else (None, None)
                if coords:
                    return agregar_lugar(lugar_key, coords[0], coords[1], nombre, "ccd", coords[2]), "ccd_por_localidad"
            return None, "ccd_sin_coordenadas"
        coords, motivo = centroides.ubicar(lugar_key)
        if not coords:
            return None, motivo
        return agregar_lugar(lugar_key, coords[0], coords[1], coords[3], "localidad", coords[2]), motivo

    def lugar_del_grafo(lugar_key: str, etapa: str) -> Optional[int]:
        if lugar_key not in resolucion_grafo:
            resolucion_grafo[lugar_key] = resolver_lugar_del_grafo(lugar_key)
        idx, motivo = resolucion_grafo[lugar_key]
        motivos[etapa][motivo] += 1
        return idx

    eventos: Dict[str, Dict[str, List[str]]] = defaultdict(lambda: defaultdict(list))
    for ev in cdm["eventos_espaciales"]:
        for etapa in ETAPAS:
            if ev["tipo_relacion"] == etapa["arista"] and ev["lugar_key"] not in eventos[ev["persona_key"]][etapa["id"]]:
                eventos[ev["persona_key"]][etapa["id"]].append(ev["lugar_key"])

    personas_out = []
    resumen = Counter()
    conocidas = {e["id"]: Counter() for e in ETAPAS}

    for persona in cdm["personas"]:
        if "VICTIMA" not in persona["roles"]:
            continue
        claves = [persona["persona_key"], *persona.get("claves_alt", [])]
        fichas_parque = [parque[k] for k in claves if k in parque]
        fichas_minjus = [minjus[k] for k in claves if k in minjus]
        estados = [f["detalle"].get("descripcion_estado") for f in fichas_parque]
        estados += [(f.get("datos_personales") or {}).get("situación_actual") for f in fichas_minjus]
        estados = [e for e in estados if e]
        textos_hallazgo = [f["detalle"].get("descripcion_datos_de_identificacion") for f in fichas_parque]
        textos_hallazgo = [t for t in textos_hallazgo if t]

        etapas: List[List[int]] = []
        for etapa in ETAPAS[:3]:
            idx = []
            for lugar_key in eventos[persona["persona_key"]][etapa["id"]]:
                conocidas[etapa["id"]]["registrado"] += 1
                i = lugar_del_grafo(lugar_key, etapa["id"])
                if i is not None and i not in idx:
                    idx.append(i)
            etapas.append(idx)

        final: List[int] = []
        hallazgo = None
        if textos_hallazgo:
            conocidas["final"]["registrado"] += 1
            hallazgo = ubicar_hallazgo(textos_hallazgo[0], sitios, centroides)
            if hallazgo:
                motivos["final"]["ok"] += 1
                final.append(agregar_lugar(f"hallazgo:{hallazgo['nombre']}", hallazgo["lat"], hallazgo["lon"],
                                           hallazgo["nombre"], hallazgo["tipo"], hallazgo["precision"]))
            else:
                motivos["final"]["texto_sin_lugar"] += 1
        etapas.append(final)

        if textos_hallazgo:
            grupo = "A"
        elif any(e in SOBREVIVIENTE for e in estados):
            resumen["excluidas_sobrevivientes"] += 1
            continue
        else:
            grupo = "B"

        if not any(etapas):
            resumen[f"sin_ningun_punto_{grupo}"] += 1
            continue
        if grupo == "A" and not final:
            resumen["A_sin_lugar_final_ubicable"] += 1
        resumen[f"grupo_{grupo}"] += 1
        for etapa, idx in zip(ETAPAS, etapas):
            if idx:
                conocidas[etapa["id"]][grupo] += 1

        estado = next((e for e in estados if "desaparec" in e.lower()), estados[0] if estados else "Sin dato")
        personas_out.append({
            "n": persona["nombre"],
            "g": grupo,
            "s": estado.replace("Persona ", "").capitalize(),
            "e": etapas,
            "u": [f.get("detail_url") for f in fichas_parque] + [f.get("source_url") for f in fichas_minjus],
            "h": textos_hallazgo[0] if textos_hallazgo else None,
        })

    datos = {
        "generado": date.today().isoformat(),
        "etapas": [{"id": e["id"], "nombre": e["nombre"]} for e in ETAPAS],
        "lugares": lugares_out,
        "personas": personas_out,
        "resumen": {
            "personas": dict(resumen),
            "por_etapa": {k: dict(v) for k, v in conocidas.items()},
            "ubicacion": {k: dict(v) for k, v in motivos.items()},
        },
    }
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    with SALIDA.open("w", encoding="utf-8") as f:
        f.write("// Generado por construir_datos.py; no editar a mano.\n")
        f.write("window.RECORRIDOS = ")
        json.dump(datos, f, ensure_ascii=False, separators=(",", ":"))
        f.write(";\n")

    print(f"escrito {SALIDA} ({SALIDA.stat().st_size / 1e6:.1f} MB)")
    print(json.dumps(datos["resumen"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

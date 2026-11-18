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
import math
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
NOMBRE_CABA_PARTIDO = "Ciudad de Buenos Aires (sin barrio)"


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

# Lugares del grafo cuyo homónimo en Georef es otro lugar; se ubican en su
# partido. "Fronterita" en Georef es un paraje de Leales; en las fuentes es el
# ingenio La Fronterita, que el propio grafo ubica en Famaillá ("Ingenio
# Fronterita", lugar de secuestro de otra ficha del Parque).
PARTIDO_DE_LOCALIDAD = {
    ("fronterita", "tucuman"): "famailla",
}


def _nombre(row: Dict[str, Any]) -> str:
    """Nombre de Georef con tildes, con su partido si no es el mismo nombre."""
    nombre, depto = row["nombre"], row.get("departamento")
    if row.get("provincia", "").startswith("Ciudad Aut"):
        return f"{nombre} (CABA)"
    return f"{nombre} ({depto})" if depto and norm(depto) != norm(nombre) else nombre


def _partido(row: Dict[str, Any], nivel: str) -> Tuple[str, str]:
    """(partido o departamento, provincia) de una fila de Georef.

    Agrupa los lugares para comparar recorridos: Villa Ballester y San Andrés
    caen los dos en General San Martín. En CABA el grupo es el barrio: la
    ciudad entera como un solo nodo parecía un centro del que salía todo.
    """
    provincia = row.get("provincia") or ""
    if provincia.startswith("Ciudad Aut"):
        return row["nombre"], provincia
    if nivel in ("departamentos", "municipios") or not row.get("departamento"):
        return row["nombre"], provincia
    return row["departamento"], provincia


def _tupla(row: Dict[str, Any], precision: str, nivel: str) -> Tuple[float, float, str, str, Tuple[str, str]]:
    return row["lat"], row["lon"], precision, _nombre(row), _partido(row, nivel)


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
        # Uno solo vale si es un nombre compuesto ("Villa Mariano Moreno - El
        # Colmenar"), no otro pueblo ("Guadalupe Norte" no es Guadalupe, barrio
        # de Santa Fe).
        if len(filas) == 1 and " - " not in filas[0]["nombre"]:
            return None
        lat = sum(r["lat"] for r in filas) / len(filas)
        lon = sum(r["lon"] for r in filas) / len(filas)
        # Si los asentamientos están lejos entre sí no es un mismo lugar.
        if max(abs(r["lat"] - lat) + abs(r["lon"] - lon) for r in filas) > 0.05:
            return None
        return lat, lon

    def partido(self, nombre: str, provincia: str) -> Dict[str, Any]:
        """Fila del partido/departamento (centroide); en CABA, del barrio."""
        if provincia.startswith("Ciudad Aut"):
            if nombre == NOMBRE_CABA_PARTIDO:
                return {**self.provincias[CABA], "nombre": NOMBRE_CABA_PARTIDO}
            return self._buscar("localidades", norm(nombre), CABA) or self._buscar("departamentos", norm(nombre), CABA)
        for nivel in ("departamentos", "municipios"):
            row = self._buscar(nivel, norm(nombre), norm(provincia))
            if row:
                return row
        raise KeyError(f"partido sin centroide: {nombre}, {provincia}")

    def por_nombre(self, nombre: str, provincia: Optional[str] = None) -> Optional[Tuple[Any, ...]]:
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
        return _tupla(filas[0], LOCALIDAD, "localidades")

    def ubicar(self, lugar_key: str) -> Tuple[Optional[Tuple[Any, ...]], str]:
        """Devuelve ((lat, lon, precision, nombre, partido), motivo). Si no ubica, la tupla es None."""
        seg = segmentos(lugar_key)
        if seg.get("PAIS") != "argentina":
            return None, "exterior"
        provincia = seg.get("PROVINCIA", "")
        ciudad, departamento = seg.get("CIUDAD"), seg.get("DEPARTAMENTO", "")
        if ciudad:
            partido_conocido = PARTIDO_DE_LOCALIDAD.get((ciudad, self._provincia(provincia)))
            if partido_conocido:
                row = self._buscar("departamentos", partido_conocido, provincia)
                return _tupla(row, DEPARTAMENTO, "departamentos"), "ok"
            if ciudad == CABA:
                p = self.provincias[CABA]
                return (p["lat"], p["lon"], CABA_GENERICA, NOMBRE_CABA, (NOMBRE_CABA_PARTIDO, p["nombre"])), "ok"
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
                        # Un municipio es un partido: su centroide no es el de una localidad.
                        return _tupla(row, LOCALIDAD if nivel == "localidades" else DEPARTAMENTO, nivel), "ok"
            # Un asentamiento sólo si el nombre es único en la provincia.
            filas = self.indices["asentamientos"].get((ciudad, self._provincia(provincia)), [])
            if len(filas) == 1:
                return _tupla(filas[0], LOCALIDAD, "asentamientos"), "ok"
            row = self._buscar("departamentos", ciudad, provincia)
            if row:
                return _tupla(row, DEPARTAMENTO, "departamentos"), "ok"
            prefijo = self._por_prefijo(ciudad, provincia)
            if prefijo:
                return (*prefijo, LOCALIDAD, ciudad.title(), None), "ok"
        if departamento:
            row = self._buscar("departamentos", departamento, provincia)
            if row:
                return _tupla(row, DEPARTAMENTO, "departamentos"), "ok"
        if provincia == CABA and not ciudad:
            p = self.provincias[CABA]
            return (p["lat"], p["lon"], CABA_GENERICA, NOMBRE_CABA, (NOMBRE_CABA_PARTIDO, p["nombre"])), "ok"
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
    "ciudad de buenos aires": "CAPITAL FEDERAL", "caba": "CAPITAL FEDERAL",
}
# Nombre de la provincia (como en el EAAF) de las pistas que no lo dicen igual.
PROVINCIA_DE_PISTA = {"BS. AS.": "buenos aires", "CAPITAL FEDERAL": "ciudad autonoma de buenos aires"}
# Una calle, una intersección o un número no son un topónimo: el resolver
# los engancha con ciudades homónimas ("Perito Moreno y Dellepiane" -> Moreno).
_NO_TOPONIMO = re.compile(r"\d|\b(y|e|entre|esq|esquina|av|avenida|calle|ruta|km|camino|altura|frente|s n)\b")
_INTERSECCION = re.compile(r"\b(y|e|entre|esq|esquina)\b")
_ABREVIATURAS = [
    (r"\bBs\.?\s*As\b\.?", "Buenos Aires"), (r"\bCap\.?\s*Fed\b\.?", "Capital Federal"),
    (r"\bPcia\b\.?", "Provincia "), (r"\bGral\b\.?", "General"), (r"\bSgto\b\.?", "Sargento"),
    (r"\bSta\b\.?", "Santa"), (r"\bPque\b\.?", "Parque"), (r"\bDto\b\.?", "Departamento"),
    (r"\bE\.\s*R[ií]os\b", "Entre Ríos"), (r"\bCba\b\.?", "Córdoba"), (r"\bVte\b\.?", "Vicente"),
    (r"\bPza\b\.?", "Plaza"), (r"\bL\.\s*Olmos\b", "Lisandro Olmos"), (r"\bCem\b\.?", "Cementerio"), (r"\bMdP\b", "Mar del Plata"),
]
# Cuerpos de agua: "Río de la Plata" no es La Plata; no hay un punto honesto.
_AGUA = re.compile(r"\b(rio de la plata|rio lujan|riachuelo|aguas del|costa uruguaya)\b")
_FECHA = re.compile(
    r"\b\d{1,2}/\d{1,2}/\d{2,4}\b|\b\d{1,2} de [a-z]+ de \d{4}\b|\b(en )?(el )?(año )?(19|20)\d{2}\b", re.I
)
_PALABRAS_VACIAS = {"el", "la", "los", "las", "del", "de", "en", "un", "una"}


def expandir_abreviaturas(texto: str) -> str:
    for abrev, completo in _ABREVIATURAS:
        texto = re.sub(abrev, completo, texto, flags=re.I)
    return texto


_BARRIO = re.compile(r"(b|bo|barrio)\b")


def _candidatos(texto: str) -> List[str]:
    """Segmentos de `texto` que pueden ser un topónimo, en orden de prueba."""
    out = []
    # El punto de una inicial ("F. Alcorta") no separa segmentos.
    for s in re.split(r"[,;:|·•–]|(?<!\b[A-Za-z])\.", texto):
        # Lo que va entre comillas es el nombre propio de un sitio ("La Cueva
        # de los Leones"), no una localidad: se saca.
        s = re.sub(r"[\"“”«»][^\"“”«»]*[\"“”«»]?", " ", s).strip()
        n = norm(s)
        # Una dirección ("CHILE 2635 MAR DEL PLATA") deja probar lo que sigue
        # al último número, si es corto y no es otra calle.
        if re.search(r"\d", n) and not _INTERSECCION.search(n):
            cola = re.split(r"\d+\S*", s)[-1].strip()
            # "km. 35 del Arroyo Morales" no es una dirección: lo que sigue a
            # "de/del" es un accidente geográfico, no la localidad.
            if 0 < len(norm(cola).split()) <= 4 and not _NO_TOPONIMO.search(norm(cola)) \
                    and not re.match(r"(de|del|y)\b", norm(cola)):
                s, n = cola, norm(cola)
        # "Bº Esperanza": un barrio suelto engancha localidades homónimas
        # ("º" se normaliza como "o").
        if not n or n in PISTAS_PROVINCIA or _NO_TOPONIMO.search(n) or _BARRIO.match(n):
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
            if len(piezas) > 1 and (len(palabras) > 4 or _BARRIO.match(norm(" ".join(palabras)))):
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
        return (p["lat"], p["lon"], CABA_GENERICA, NOMBRE_CABA, (NOMBRE_CABA_PARTIDO, p["nombre"])), NOMBRE_CABA
    return None, None


def km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia aproximada en km (equirrectangular: alcanza para comparar)."""
    x = math.radians(lon2 - lon1) * math.cos(math.radians((lat1 + lat2) / 2))
    return 6371 * math.hypot(x, math.radians(lat2 - lat1))


# CCD de `ccds.json` (RUVTE) cuyas coordenadas contradicen su propia
# dirección. Se encontraron comparando cada coordenada con la localidad de su
# `ubicacion` (más de 20 km) o buscando coordenadas copiadas de otro CCD
# cercano con otra dirección, y se revisaron a mano: la comparación sola da
# falsos positivos (la Comisaría 4ª de San Isidro está en la calle Balcarce).
COORDENADAS_RUVTE_ERRONEAS = {
    "86": "Comisaría 1ª de San Martín: cae en la ciudad de 9 de Julio, que es el nombre de la calle",
    "291": "Regimiento de Infantería 6 (Mercedes): cae en CABA",
    "670": "Brigada Güemes (Ciudad Evita): cae cerca de Quilmes",
    "268": "Escuelita de Neuquén (Neuquén capital): cae cerca de Zapala",
    "1": "Olimpo (Ramón Falcón 4151, Vélez Sarsfield): tiene las de Coordinación Federal (id 226), a 150 m",
    "201": "Planta Transmisora de Plátanos (Berazategui): cae a 1 km del Pozo de Quilmes (id 44)",
    "82": "Unidad Penal 8 de Olmos (Lisandro Olmos): tiene las de la Brigada de Investigaciones de La Plata (id 147), a 300 m",
}


def pista_de_provincia(lugar: Dict[str, Any]) -> str:
    """Provincia de un CCD para orientar al resolver de texto.

    RUVTE la trae en `zona` ("Zona 4 · Provincia de BUENOS AIRES"); MinJus GBA
    es toda de la provincia de Buenos Aires salvo direcciones en CABA. Sin
    pista, "SAN NICOLAS" cae en el barrio porteño y no en San Nicolás de los
    Arroyos.
    """
    zona, ubicacion = norm(lugar.get("zona")), norm(lugar.get("ubicacion"))
    if "capital federal" in zona or re.search(r"\b(caba|capital federal)\b", ubicacion):
        return "Capital Federal"
    m = re.search(r"provincia de (.+)$", zona)
    if m:
        return m.group(1)
    return "Buenos Aires" if lugar.get("fuente") == "minjus_ccds" else ""


def localidad_del_ccd(lugar: Dict[str, Any], centroides: "Centroides") -> Optional[Tuple[Any, ...]]:
    """Localidad de la dirección de un CCD o, si no hay, la de su nombre
    ("COMISARÍA 8ª DE LA PLATA"). CABA sin barrio queda como último recurso."""
    pista = pista_de_provincia(lugar)
    # Gana la más precisa, en este orden: una localidad de la dirección o del
    # nombre del CCD ("... DE GRAND BOURG"), la ciudad cabecera del partido
    # (Tandil en Tandil), el centroide del partido, CABA sin barrio.
    candidatos: List[Tuple[int, Tuple[Any, ...]]] = []
    ubicacion = lugar.get("ubicacion") or ""
    # MinJus escribe "calle | partido". El partido se busca como partido
    # ("Malvinas Argentinas" es también una localidad de Almirante Brown), y
    # la calle sola, que puede llamarse como una localidad ("José Hernández").
    if "|" in ubicacion and pista:
        ubicacion, cola = ubicacion.rsplit("|", 1)
        for nivel in ("departamentos", "municipios"):
            row = centroides._buscar(nivel, norm(cola), norm(pista))
            if row:
                ciudad = centroides._buscar("localidades", norm(cola), norm(pista), norm(row["nombre"]))
                if ciudad and norm(ciudad.get("departamento")) == norm(row["nombre"]):
                    candidatos.append((1, _tupla(ciudad, LOCALIDAD, "localidades")))
                candidatos.append((2, _tupla(row, DEPARTAMENTO, nivel)))
                break
        else:
            ubicacion = f"{ubicacion}, {cola}"
    rango = {LOCALIDAD: 0, DEPARTAMENTO: 2, CABA_GENERICA: 3}
    # Si con la provincia no aparece nada, se prueba sin ella: MinJus tiene
    # algún CCD fuera de Buenos Aires (Quinta de Funes, en Santa Fe).
    for con_pista in ((True, False) if pista else (False,)):
        for parte in (ubicacion, re.split(r"\bDE\b", lugar.get("nombre") or "")[-1]):
            if parte.strip():
                coords, _ = ubicar_fragmento(f"{parte}. {pista}" if con_pista else parte, centroides)
                if coords:
                    candidatos.append((rango.get(coords[2], 4), coords))
        if candidatos:
            break
    # `min` se queda con el primero entre iguales: la dirección antes que el nombre.
    return min(candidatos, key=lambda c: c[0])[1] if candidatos else None


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
            def entero(columna: str) -> Optional[int]:
                valor = (row.get(columna) or "").strip()
                return int(valor) if valor.isdigit() else None

            sitios.append({
                "nombre": row["LUGAR DE HALLAZGO"].strip(),
                "localidad": row["LOCALIDAD"].strip(),
                "provincia": row["PROVINCIA"].strip(),
                # EP = enterramiento, igual que en builders/eaaf_lugares.py.
                "tipo": {"CEM": "cementerio", "CCD": "ccd", "EP": "enterramiento"}.get(row["CEM - CCD - EP"].strip(), "sitio"),
                "lat": lat,
                "lon": lon,
                # Totales del sitio según el EAAF, no de cada persona.
                "casos": entero("Suma de CASOS"),
                "exhumados": entero("Suma de EXHUMADOS"),
                "identificados": entero("Suma de ID"),
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
        # Cada frase por separado: la provincia de un sitio va en su misma
        # frase, y otra frase puede nombrar otra (la del secuestro).
        frases = [_normalizar_sitio(f) for f in re.split(r";|\.\s+(?=[A-ZÁÉÍÓÚÑ])", expandir_abreviaturas(texto))]
        for frase, sitio in self.alias:
            for t in frases:
                # Los alias manuales valen como prefijo ("arsenal miguel de az").
                if f" {frase} " in t or (frase in ALIAS_SITIOS and f" {frase}" in t):
                    if _misma_provincia(t[t.index(f" {frase}") + len(frase) + 1:], sitio):
                        return sitio
        return None


def _normalizar_sitio(texto: str) -> str:
    t = f" {norm(texto)} ".replace(" cementario ", " cementerio ")
    return re.sub(r" cementerio (municipal|parque) de ", " cementerio de ", t)


def _misma_provincia(cola: str, sitio: Dict[str, Any]) -> bool:
    """False si lo que sigue al nombre del sitio, en su frase, nombra otra
    provincia: "Cementerio de la Piedad, Oberá, Misiones" no es La Piedad de
    Rosario."""
    nombradas = {_REGION.get(q, q) for q in (PROVINCIA_DE_PISTA.get(p, norm(p)) for frase, p in PISTAS_PROVINCIA.items()
                                            if re.search(rf"\b{re.escape(frase)}\b", cola))}
    provincia = norm(sitio["provincia"])
    return not nombradas or _REGION.get(provincia, provincia) in nombradas


# Los textos dicen "Bs. As." también para CABA ("Cementerio de Chacarita, Bs
# As."): para esta comparación, CABA y la provincia de Buenos Aires son lo mismo.
_REGION = {"ciudad autonoma de buenos aires": "buenos aires"}


_FRAGMENTO_LUGAR = [
    re.compile(r"aparici[oó]n\s*:\s*(?P<l>[^;]+)", re.I),
    re.compile(r"(?:hallad[oa]s?|exhumad[oa]s?|encontrad[oa]s?|apareci[oó]|aparecen?|enterrad[oa]s?)\s+(?:\S+\s+){0,8}?en\s+(?P<l>[^;]+)", re.I),
]


def ubicar_hallazgo(texto: str, sitios: SitiosEAAF, centroides: Centroides) -> Optional[Dict[str, Any]]:
    """Ubica el lugar donde se hallaron los restos según el texto del Parque."""
    sitio = sitios.buscar(texto)
    if sitio:
        # El EAAF distingue sectores de un cementerio ("Cementerio de
        # Avellaneda- Sector 134" y "-Fondo"); si el texto no dice cuál, se
        # nombra el cementerio sin sector (las coordenadas son del primero).
        nombre = sitio["nombre"]
        partes = re.split(r"\s*-\s*(?=Sector|Fondo)", nombre)
        if len(partes) > 1 and norm(partes[1]) not in norm(texto):
            nombre = partes[0]
        return {"nombre": f"{nombre} ({sitio['localidad']})", "tipo": sitio["tipo"],
                "lat": sitio["lat"], "lon": sitio["lon"], "precision": SITIO,
                "sitio_eaaf": {k: sitio[k] for k in ("casos", "exhumados", "identificados")}}
    for patron in _FRAGMENTO_LUGAR:
        m = patron.search(texto)
        if not m:
            continue
        fragmento = m.group("l")
        coords, nombre = ubicar_fragmento(fragmento, centroides)
        if coords:
            return {"nombre": coords[3] if len(coords) > 3 else (nombre or fragmento).title(), "tipo": "localidad del hallazgo",
                    "lat": coords[0], "lon": coords[1], "precision": coords[2],
                    "partido": coords[4] if len(coords) > 4 else None,
                    "direccion": direccion_del_fragmento(fragmento)}
    return None


_FECHA_HALLAZGO = re.compile(
    r"(?:aparici[oó]n\s*:[^;]*?|(?:apareci[oó]|aparecen?|hallad[oa]s?|encontr[oó]|encontrad[oa]s?)\D{0,25}?)"
    r"(\d{1,2}/\d{1,2}/\d{2,4}|\d{1,2} de [a-záéíóú]+ de \d{4})",
    re.I,
)
_AÑO_IDENTIFICACION = re.compile(r"identificad[oa]s?\b[^.]{0,120}?\b((?:19[89]|20[0-2])\d)\b", re.I)


def direccion_del_fragmento(fragmento: str) -> Optional[str]:
    """Lo que el texto dice del lugar, más preciso que la localidad.

    "Aparición: Dorrego y F. Alcorta (Palermo), 04/12/76" ->
    "Dorrego y F. Alcorta (Palermo)". Sin fechas ni "Ente:", hasta el fin de
    la primera oración.
    """
    # Fin de oración: un punto tras una palabra de 4 letras o más ("Av." o
    # "Bs. As." no cortan). Tampoco van los nombres de quienes aparecieron
    # junto a la persona: ya tienen su propia ficha.
    t = re.split(r"(?<=[a-záéíóúñ]{4})\.\s+(?=[A-ZÁÉÍÓÚ])|;|,?\s+junto (?:con|a)\b", fragmento)[0]
    t = _FECHA.sub(" ", t)
    # Lo que queda colgando de una fecha que se sacó ("Asesinada el , San Martín").
    t = re.sub(r"\b(el|del)\s*(?=[,.]|$)|\bel\s+(?=en\b)", "", t)
    t = re.sub(r"\s+([,.])", r"\1", re.sub(r"\s+", " ", t))
    t = t.strip(" ,-").lstrip(".").strip()
    t = re.sub(r"^(?:en|el|la)\s+", "", t, flags=re.I)
    return (t if len(t) <= 120 else t[:119].rsplit(" ", 1)[0] + "…") or None


def detalle_hallazgo(texto: str, hallazgo: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Datos del hallazgo que el texto del Parque dice explícitamente."""
    detalle: Dict[str, Any] = {}
    m = _FECHA_HALLAZGO.search(texto)
    if m:
        detalle["fecha_aparicion"] = m.group(1)
    m = _AÑO_IDENTIFICACION.search(texto)
    if m:
        detalle["año_identificacion"] = int(m.group(1))
    if hallazgo:
        detalle["tipo"] = hallazgo["tipo"]
        if hallazgo.get("sitio_eaaf"):
            detalle["sitio_eaaf"] = hallazgo["sitio_eaaf"]
        direccion = hallazgo.get("direccion")
        # Sólo si dice más que el nombre del lugar ("Caballito" no agrega).
        if direccion and norm(direccion) not in norm(hallazgo["nombre"]):
            detalle["direccion"] = direccion
    return detalle


# --------------------------------------------------------------------------
# Estado de cada persona según las fuentes
# --------------------------------------------------------------------------

# Aristas que el grafo ubica mal y cuyo arreglo todavía no está en `main`.
# No se dibujan (no se corrigen acá: el arreglo va en el loader). Cuando el
# arreglo llegue, la entrada se borra. Cada una: lugar del grafo, texto de la
# ficha del Parque que la delata (o None si toda arista a ese lugar está mal).
ERRORES_CONOCIDOS_DEL_GRAFO = [
    # El país Uruguay ("Canelones, Uruguay. Cruce Ruta 9 y Ruta 70") resuelto
    # como el departamento Uruguay de Entre Ríos: las 6 aristas a ese lugar.
    # Arreglo: branch fix/uruguay-pais-no-departamento.
    ("lugar:DEPARTAMENTO:uruguay|lugar:PROVINCIA:entre_rios|lugar:PAIS:argentina", None),
    # "CRUZ ALTA. TUCUMAN (Ingenio San Juan…)" resuelto como San Juan capital (9).
    ("lugar:CIUDAD:san_juan|lugar:DEPARTAMENTO:capital|lugar:PROVINCIA:san_juan|lugar:PAIS:argentina", r"CRUZ ALTA"),
    # "PUENTE SAAVEDRA. BS. AS." resuelto en el partido de Saavedra (Pigüé).
    ("lugar:CIUDAD:puente|lugar:DEPARTAMENTO:saavedra|lugar:PROVINCIA:buenos_aires|lugar:PAIS:argentina", None),
]
PAISES_VECINOS = {"uruguay", "paraguay", "chile", "brasil", "bolivia", "peru"}
_CAMPO_DE_ARISTA = {"SECUESTRADO_EN": "descripcion_lugar_de_secuestro", "ASESINADO_EN": "Lugar de asesinato"}


def error_conocido_del_grafo(arista: Optional[str], lugar_key: str, fichas_parque: List[Dict[str, Any]]) -> bool:
    for clave, patron in ERRORES_CONOCIDOS_DEL_GRAFO:
        if lugar_key != clave:
            continue
        if patron is None:
            return True
        campo = _CAMPO_DE_ARISTA.get(arista or "")
        textos = [(f.get("detalle") or {}).get(campo) or "" for f in fichas_parque] if campo else []
        if any(re.search(patron, t, re.I) for t in textos):
            return True
    return False


SOBREVIVIENTE = {"Persona liberada", "Persona fugado", "Persona restituida"}
# Estado de MinJus que no dice si la persona sigue desaparecida: varias fichas
# "Persona fallecido" cuentan en el relato que fue liberada y murió después.
# Sin una ficha del Parque, esas personas (y las de MinJus sin estado) no
# entran en el grupo B.
ESTADO_INCIERTO_MINJUS = {"Persona fallecido"}
# MinJus escribe el estado distinto que el Parque; se muestra con las
# palabras del Parque para que la misma situación se lea igual.
ESTADOS_MINJUS = {
    "Persona desaparecida": "Detenido/a desaparecido/a",
    "Persona asesinada": "Asesinado/a",
    "Persona asesinado": "Asesinado/a",
    "Persona fallecido": "Fallecido/a",
}


def _fecha_iso(valor: Optional[str]) -> Optional[str]:
    return valor if valor and re.fullmatch(r"\d{4}-\d{2}-\d{2}", valor) else None


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
    # La consola de Windows usa cp1252 y no puede imprimir "≈" ni algunos nombres.
    sys.stdout.reconfigure(encoding="utf-8")
    print("corriendo el pipeline hasta el CDM (≈1 min)...", flush=True)
    cdm = construir_cdm()
    centroides = Centroides(CENTROIDES)
    sitios = SitiosEAAF()
    parque, minjus = leer_fuentes()

    lugares_cdm = {l["lugar_key"]: l for l in cdm["lugares"] if l.get("tipo_entidad") == "Lugar"}

    # Tabla de lugares de salida: [lat, lon, nombre, tipo, precision, nodo].
    # `nodo` indexa `nodos_out`: el partido para localidades y el propio
    # lugar para CCD y sitios del EAAF. Es el nivel en que se comparan los
    # recorridos en la vista de flujos.
    lugares_out: List[List[Any]] = []
    indice_lugar: Dict[Any, int] = {}
    nodos_out: List[List[Any]] = []
    indice_nodo: Dict[Any, int] = {}
    motivos: Dict[str, Counter] = defaultdict(Counter)

    def nodo_de(lat: float, lon: float, nombre: str, tipo: str, partido: Optional[Tuple[str, str]]) -> int:
        if partido:
            fila = centroides.partido(*partido)
            clave, lat, lon, nombre, tipo = ("partido", *partido), fila["lat"], fila["lon"], fila["nombre"], "partido"
            if partido[1].startswith("Ciudad Aut"):
                # Un barrio porteño, o CABA sin barrio: un lugar impreciso que
                # el mapa de flujos oculta de cerca.
                tipo = "impreciso" if nombre == NOMBRE_CABA_PARTIDO else "barrio"
                nombre = nombre if tipo == "impreciso" else f"{nombre} (CABA)"
            # "Capital" se repite en varias provincias: se aclara cuál.
            if norm(nombre) in ("capital", "la capital"):
                nombre = f"{partido[1]} (capital)"
            # Un partido que se llama como un país o una provincia ("Uruguay",
            # en Entre Ríos) lleva la provincia, para que no se lea como el país.
            elif norm(nombre) in PAISES_VECINOS or norm(nombre) in centroides.provincias:
                nombre = f"{nombre} ({partido[1]})"
        else:
            clave = (nombre, tipo, round(lat, 4), round(lon, 4))
        if clave not in indice_nodo:
            indice_nodo[clave] = len(nodos_out)
            nodos_out.append([round(lat, 5), round(lon, 5), nombre, tipo])
        return indice_nodo[clave]

    def agregar_lugar(clave: str, lat: float, lon: float, nombre: str, tipo: str, precision: str,
                      partido: Optional[Tuple[str, str]] = None) -> int:
        # Dos claves del grafo pueden caer en el mismo punto con el mismo
        # nombre (CORDOBA con y sin DEPARTAMENTO): se dibujan como un lugar.
        mismo_punto = (nombre, tipo, round(lat, 4), round(lon, 4))
        if clave not in indice_lugar:
            if mismo_punto not in indice_lugar:
                indice_lugar[mismo_punto] = len(lugares_out)
                nodo = nodo_de(lat, lon, nombre, tipo, partido)
                lugares_out.append([round(lat, 5), round(lon, 5), nombre, tipo, precision, nodo])
            indice_lugar[clave] = indice_lugar[mismo_punto]
        return indice_lugar[clave]

    resolucion_grafo: Dict[str, Tuple[Optional[int], str]] = {}

    def resolver_lugar_del_grafo(lugar_key: str) -> Tuple[Optional[int], str]:
        lugar = lugares_cdm.get(lugar_key, {})
        nombre = (lugar.get("nombre") or lugar_key).title()
        if lugar.get("tipoGeopolitico") == "CCD":
            localidad = localidad_del_ccd(lugar, centroides)
            if lugar.get("lat") is not None and lugar.get("lon") is not None:
                # Algunas coordenadas de RUVTE contradicen su propia dirección:
                # para esas (revisadas una por una) se usa la localidad.
                if lugar.get("id_ccd") in COORDENADAS_RUVTE_ERRONEAS and localidad:
                    return agregar_lugar(lugar_key, localidad[0], localidad[1], nombre, "ccd", localidad[2]), "ccd_coordenadas_corregidas"
                return agregar_lugar(lugar_key, lugar["lat"], lugar["lon"], nombre, "ccd", SITIO), "ok"
            sitio = sitios.buscar(lugar.get("nombre", ""))
            if sitio:
                return agregar_lugar(lugar_key, sitio["lat"], sitio["lon"], nombre, "ccd", SITIO), "ok"
            if localidad:
                return agregar_lugar(lugar_key, localidad[0], localidad[1], nombre, "ccd", localidad[2]), "ccd_por_localidad"
            return None, "ccd_sin_coordenadas"
        coords, motivo = centroides.ubicar(lugar_key)
        if not coords:
            return None, motivo
        return agregar_lugar(lugar_key, coords[0], coords[1], coords[3], "localidad", coords[2], coords[4]), motivo

    def lugar_del_grafo(lugar_key: str, etapa: str) -> Optional[int]:
        if lugar_key not in resolucion_grafo:
            resolucion_grafo[lugar_key] = resolver_lugar_del_grafo(lugar_key)
        idx, motivo = resolucion_grafo[lugar_key]
        motivos[etapa][motivo] += 1
        return idx

    eventos: Dict[str, Dict[str, List[str]]] = defaultdict(lambda: defaultdict(list))
    fecha_secuestro: Dict[str, str] = {}
    for ev in cdm["eventos_espaciales"]:
        if ev["tipo_relacion"] == "SECUESTRADO_EN" and re.fullmatch(r"\d{4}-\d{2}-\d{2}", ev.get("fecha") or ""):
            fecha_secuestro.setdefault(ev["persona_key"], ev["fecha"])
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
        # 13 fichas del Parque traen en el lugar de secuestro el asesinato
        # ("asesinado 29/09/76 ROSARIO. SANTA FE"): el lugar va a la etapa 2 y
        # la fecha no es la del secuestro.
        secuestro_es_asesinato = any(
            re.match(r"\s*asesinad[oa]\b", f["detalle"].get("descripcion_lugar_de_secuestro") or "", re.I)
            for f in fichas_parque)

        etapas: List[List[int]] = []
        for etapa in ETAPAS[:3]:
            idx = []
            for lugar_key in eventos[persona["persona_key"]][etapa["id"]]:
                conocidas[etapa["id"]]["registrado"] += 1
                if error_conocido_del_grafo(etapa["arista"], lugar_key, fichas_parque):
                    motivos[etapa["id"]]["error_conocido_del_grafo"] += 1
                    continue
                i = lugar_del_grafo(lugar_key, etapa["id"])
                if i is not None and i not in idx:
                    idx.append(i)
            etapas.append(idx)
        if secuestro_es_asesinato:
            etapas[2] += [i for i in etapas[0] if i not in etapas[2]]
            etapas[0] = []

        final: List[int] = []
        hallazgo = None
        if textos_hallazgo:
            conocidas["final"]["registrado"] += 1
            hallazgo = ubicar_hallazgo(textos_hallazgo[0], sitios, centroides)
            if hallazgo:
                motivos["final"]["ok"] += 1
                final.append(agregar_lugar(f"hallazgo:{hallazgo['nombre']}", hallazgo["lat"], hallazgo["lon"],
                                           hallazgo["nombre"], hallazgo["tipo"], hallazgo["precision"],
                                           hallazgo.get("partido")))
            else:
                motivos["final"]["texto_sin_lugar"] += 1
        etapas.append(final)

        if textos_hallazgo:
            grupo = "A"
        elif any(e in SOBREVIVIENTE for e in estados):
            resumen["excluidas_sobrevivientes"] += 1
            continue
        elif fichas_minjus and not fichas_parque and all(e in ESTADO_INCIERTO_MINJUS for e in estados):
            resumen["excluidas_estado_incierto"] += 1
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
        estado = ESTADOS_MINJUS.get(estado, estado)
        personas_out.append({
            "n": persona["nombre"],
            "g": grupo,
            "s": estado.replace("Persona ", "").capitalize(),
            "e": etapas,
            "u": [f.get("detail_url") for f in fichas_parque] + [f.get("source_url") for f in fichas_minjus],
            "h": textos_hallazgo[0] if textos_hallazgo else None,
            "hd": detalle_hallazgo(textos_hallazgo[0], hallazgo) if textos_hallazgo else None,
            # Fecha de secuestro: la de la arista del Parque o, si no hay, la
            # de la ficha de MinJus / Archivo San Martín.
            "f": None if secuestro_es_asesinato else
                 fecha_secuestro.get(persona["persona_key"]) or _fecha_iso(persona.get("fecha_secuestro")),
        })

    # Un partido se dibuja en su lugar más usado (casi siempre la ciudad), no
    # en el centroide del departamento: en el interior ese centroide cae a
    # decenas de km de la ciudad (Confluencia queda lejos de Neuquén capital).
    uso = Counter(li for p in personas_out for lista in p["e"] for li in lista)
    mas_usado: Dict[int, Tuple[int, int]] = {}
    for li, veces in uso.items():
        nodo = lugares_out[li][5]
        if nodos_out[nodo][3] == "partido" and veces > mas_usado.get(nodo, (0, -1))[0]:
            mas_usado[nodo] = (veces, li)
    for nodo, (_, li) in mas_usado.items():
        nodos_out[nodo][0], nodos_out[nodo][1] = lugares_out[li][0], lugares_out[li][1]

    datos = {
        "generado": date.today().isoformat(),
        "etapas": [{"id": e["id"], "nombre": e["nombre"]} for e in ETAPAS],
        "lugares": lugares_out,
        "nodos": nodos_out,
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

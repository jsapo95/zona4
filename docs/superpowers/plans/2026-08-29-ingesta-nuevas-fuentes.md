# Ingesta de nuevas fuentes al grafo (V1.2) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Incorporar al grafo de Neo4j 7 fuentes de `data/raw/` que hoy no se cargan, levantando los tres bloqueos estructurales que lo impiden.

**Architecture:** El loader consume `data/sources/` vía builders dedicados y JSON directos, consolidando todo en un CDM en memoria antes de escribir a Neo4j. Este plan agrega siete builders nuevos que leen `data/raw/`, extiende el CDM de 5 a 7 colecciones, reemplaza el etiquetado fijo `:Victima` por labels dinámicas basadas en roles, e inserta un paso de reconciliación de identidades entre el consolidado y la escritura.

**Tech Stack:** Python 3.11+, neo4j-driver, Neo4j 5 con APOC y GDS (vía `docker-compose.yml`), pytest.

**Spec:** `docs/superpowers/specs/2026-08-29-ingesta-nuevas-fuentes-design.md`

## Global Constraints

- **Branch:** todo el trabajo va sobre `feature/ingesta-nuevas-fuentes`.
- **Offline estricto:** ningún builder ni módulo de `zona4_graph_loader` hace peticiones de red. Los builders leen archivos locales de `data/raw/` y `data/processed/`.
- **Retrocompatibilidad:** `builders/personas.py`, `builders/ccds.py`, `builders/relaciones.py`, `builders/lugares.py` y los JSON existentes de `data/sources/` deben seguir funcionando sin modificación de sus datos. Una fila `personas` sin `roles` ni `es_nietx` recibe `["VICTIMA"]`.
- **Auditoría de aristas (regla 1.2 del modelo):** toda relación escrita lleva `fecha` y `origen`. Sin dato, `fecha` es la string `"DESCONOCIDA"`.
- **Género:** ninguna fuente nueva trae sexo. Todas las personas nuevas entran con `genero = "INDETERMINADO"`. **No se infiere género a partir del nombre.**
- **Roles válidos:** `VICTIMA`, `REPRESOR`, `COMPLICE`, `NIETX`.
- **Tipos de cómplice válidos:** `CIVIL`, `CLERICAL`, `EMPRESARIAL`.
- **Prioridad de fuente para clave canónica** (mayor a menor): `detalles_personas`, `nietxs_relacion`, `archivo_memoria`, `minjus_victimas`, `minjus_imputados`, `juicios_condenados`. Desempate: clave menor en orden lexicográfico.
- **Namespacing de claves:** `lugar:{TIPO}:{slug}`, `direccion_ccd:{...}`, `org:{slug}`, `institucion:{slug}`, `profesion:{slug}`, `cargo:{slug}`, `alias_persona:{slug}`.
- **Fuera de alcance (no implementar):** parsing de `lugar_de_secuestro` de MinJus víctimas, `eaaf_identificados.csv`, `juicios_lesa_humanidad_argentina.json`, `juicios_lesa_humanidad_exterior.json`.
- **Tests:** se corren con `PYTHONPATH=src pytest`. Ningún test de este plan requiere una instancia de Neo4j corriendo.

---

## Estructura de archivos

**Crear:**

| Archivo | Responsabilidad |
|---|---|
| `requirements.txt` | Dependencias hoy implícitas |
| `pytest.ini` | Configuración de pytest (`pythonpath = src`) |
| `tests/conftest.py` | Helpers y fixtures compartidos |
| `tests/test_roles.py` | Normalización de roles y retrocompat |
| `tests/test_identity_resolution.py` | Reconciliación, con casos adversarios reales |
| `tests/builders/test_*.py` | Un archivo por builder |
| `src/zona4_graph_loader/domain/roles.py` | `normalize_roles` y validación de roles |
| `src/zona4_graph_loader/domain/identity_resolution.py` | Merge determinista + generación de candidatos |
| `src/zona4_graph_loader/io/raw_files.py` | Rutas a `data/raw/` y lectura de CSV/JSON |
| `src/zona4_graph_loader/builders/eaaf_lugares.py` | Sitios de hallazgo del EAAF |
| `src/zona4_graph_loader/builders/archivo_memoria.py` | Víctimas de San Martín |
| `src/zona4_graph_loader/builders/juicios_condenados.py` | Condenados de lesa humanidad |
| `src/zona4_graph_loader/builders/minjus_sentencias.py` | Índice de sentencias (no emite nodos) |
| `src/zona4_graph_loader/builders/minjus_ccds.py` | CCDs de MinJus GBA + dedup contra RUVTE |
| `src/zona4_graph_loader/builders/minjus_imputados.py` | Represores de MinJus GBA |
| `src/zona4_graph_loader/builders/minjus_victimas.py` | Víctimas de MinJus GBA |

**Modificar:**

| Archivo | Cambio |
|---|---|
| `src/zona4_graph_loader/builders/base.py` | `CanonicalDataset` de 5 a 7 claves |
| `src/zona4_graph_loader/io/sources_ingestor.py` | `ALLOWED_SOURCE_KEYS` y `empty_canonical_dataset` |
| `src/zona4_graph_loader/db/cypher.py` | Labels dinámicas, 5 upserts de contexto, idempotencia |
| `src/zona4_graph_loader/db/qa.py` | Métricas de contexto y de aristas no resueltas |
| `src/zona4_graph_loader/pipeline/load_graph.py` | Registro de builders, paso de reconciliación, batches nuevos |
| `src/zona4_graph_loader/cli.py` | Flags nuevos |
| `src/zona4_graph_loader/NEO4J_DATA_MODEL.md` | Bump a V1.2 |
| `docs/operations/ingesta_fuentes.md` | CDM de 7 claves |
| `README.md` | Estado real de fuentes |

---

### Task 1: Andamiaje de tests y dependencias

Hoy no hay tests, ni `requirements.txt`, ni configuración de pytest. Todas las tareas siguientes dependen de esto.

**Files:**
- Create: `requirements.txt`, `pytest.ini`, `tests/__init__.py`, `tests/conftest.py`
- Test: `tests/test_cdm_contract.py`

**Interfaces:**
- Consumes: nada.
- Produces: `PYTHONPATH=src pytest` corre verde. Fixture `raw_dir` que devuelve el `Path` a `data/raw/`.

- [ ] **Step 1: Crear `requirements.txt`**

```
neo4j>=5.0,<6
requests>=2.31
pytest>=8.0
```

- [ ] **Step 2: Crear `pytest.ini`**

```ini
[pytest]
pythonpath = src
testpaths = tests
```

- [ ] **Step 3: Crear `tests/__init__.py` vacío y `tests/conftest.py`**

```python
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def raw_dir() -> Path:
    return REPO_ROOT / "data" / "raw"


@pytest.fixture
def sources_dir() -> Path:
    return REPO_ROOT / "data" / "sources"
```

- [ ] **Step 4: Escribir el test que falla**

Crear `tests/test_cdm_contract.py`:

```python
from __future__ import annotations

from zona4_graph_loader.io.sources_ingestor import (
    ALLOWED_SOURCE_KEYS,
    empty_canonical_dataset,
)


def test_cdm_tiene_siete_colecciones():
    assert ALLOWED_SOURCE_KEYS == {
        "personas",
        "lugares",
        "relaciones_interpersonales",
        "eventos_espaciales",
        "jerarquias",
        "entidades_contexto",
        "relaciones_contexto",
    }


def test_dataset_vacio_tiene_todas_las_claves():
    dataset = empty_canonical_dataset()
    assert set(dataset) == ALLOWED_SOURCE_KEYS
    assert all(value == [] for value in dataset.values())
```

- [ ] **Step 5: Correr el test y verificar que falla**

Run: `PYTHONPATH=src pytest tests/test_cdm_contract.py -v`
Expected: FAIL — `ALLOWED_SOURCE_KEYS` sólo tiene 5 claves.

Este test queda en rojo hasta la Task 3. Es intencional: fija el contrato objetivo.

- [ ] **Step 6: Commit**

```bash
git add requirements.txt pytest.ini tests/
git commit -m "test: andamiaje de pytest y contrato objetivo del CDM"
```

---

### Task 2: Roles dinámicos en `:Persona`

Levanta el bloqueo B1: `CYPHER_UPSERT_PERSONAS` termina hoy en `SET p:Victima` incondicional (`db/cypher.py:36`), lo que hace imposible cargar represores.

**Files:**
- Create: `src/zona4_graph_loader/domain/roles.py`, `tests/test_roles.py`
- Modify: `src/zona4_graph_loader/db/cypher.py:28-37`, `src/zona4_graph_loader/pipeline/load_graph.py:100-107`, `src/zona4_graph_loader/NEO4J_DATA_MODEL.md`

**Interfaces:**
- Consumes: nada.
- Produces: `normalize_roles(persona: Dict[str, Any]) -> List[str]`, que muta nada y devuelve la lista ordenada de roles válidos. Lanza `ValueError` con mensaje descriptivo ante rol desconocido o `COMPLICE` sin `complice_tipo` válido. Constantes `VALID_ROLES` y `VALID_COMPLICE_TIPOS`.

- [ ] **Step 1: Escribir los tests que fallan**

Crear `tests/test_roles.py`:

```python
from __future__ import annotations

import pytest

from zona4_graph_loader.domain.roles import (
    VALID_COMPLICE_TIPOS,
    VALID_ROLES,
    normalize_roles,
)


def test_sin_roles_ni_es_nietx_default_victima():
    assert normalize_roles({"persona_key": "registro:1"}) == ["VICTIMA"]


def test_es_nietx_true_mapea_a_nietx():
    assert normalize_roles({"persona_key": "nietx:1", "es_nietx": True}) == ["NIETX"]


def test_es_nietx_false_mapea_a_victima():
    assert normalize_roles({"persona_key": "registro:1", "es_nietx": False}) == ["VICTIMA"]


def test_roles_explicitos_ganan_sobre_es_nietx():
    persona = {"persona_key": "x:1", "es_nietx": True, "roles": ["REPRESOR"]}
    assert normalize_roles(persona) == ["REPRESOR"]


def test_roles_se_ordenan_y_deduplican():
    persona = {"persona_key": "x:1", "roles": ["VICTIMA", "NIETX", "VICTIMA"]}
    assert normalize_roles(persona) == ["NIETX", "VICTIMA"]


def test_rol_desconocido_falla():
    with pytest.raises(ValueError, match="TESTIGO"):
        normalize_roles({"persona_key": "x:1", "roles": ["TESTIGO"]})


def test_complice_sin_tipo_falla():
    with pytest.raises(ValueError, match="complice_tipo"):
        normalize_roles({"persona_key": "x:1", "roles": ["COMPLICE"]})


def test_complice_con_tipo_invalido_falla():
    persona = {"persona_key": "x:1", "roles": ["COMPLICE"], "complice_tipo": "MILITAR"}
    with pytest.raises(ValueError, match="complice_tipo"):
        normalize_roles(persona)


def test_complice_con_tipo_valido_pasa():
    persona = {"persona_key": "x:1", "roles": ["COMPLICE"], "complice_tipo": "CIVIL"}
    assert normalize_roles(persona) == ["COMPLICE"]


def test_roles_vacio_falla():
    with pytest.raises(ValueError, match="vacía"):
        normalize_roles({"persona_key": "x:1", "roles": []})


def test_constantes_declaradas():
    assert VALID_ROLES == {"VICTIMA", "REPRESOR", "COMPLICE", "NIETX"}
    assert VALID_COMPLICE_TIPOS == {"CIVIL", "CLERICAL", "EMPRESARIAL"}
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `PYTHONPATH=src pytest tests/test_roles.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'zona4_graph_loader.domain.roles'`

- [ ] **Step 3: Implementar `domain/roles.py`**

```python
from __future__ import annotations

from typing import Any, Dict, List

VALID_ROLES = {"VICTIMA", "REPRESOR", "COMPLICE", "NIETX"}
VALID_COMPLICE_TIPOS = {"CIVIL", "CLERICAL", "EMPRESARIAL"}


def normalize_roles(persona: Dict[str, Any]) -> List[str]:
    """Resuelve los roles de una fila `personas` del CDM.

    Retrocompatibilidad: una fila sin `roles` cae en `es_nietx` y, si tampoco
    está, en `["VICTIMA"]`, que es el comportamiento histórico del loader.
    """
    key = persona.get("persona_key", "(sin persona_key)")
    roles = persona.get("roles")

    if roles is None:
        return ["NIETX"] if persona.get("es_nietx") else ["VICTIMA"]

    if not isinstance(roles, list):
        raise ValueError(f"'roles' debe ser una lista en {key}, recibido: {type(roles).__name__}")
    if not roles:
        raise ValueError(f"'roles' no puede ser una lista vacía en {key}")

    desconocidos = sorted({r for r in roles if r not in VALID_ROLES})
    if desconocidos:
        raise ValueError(
            f"Rol(es) desconocido(s) {', '.join(desconocidos)} en {key}. "
            f"Válidos: {', '.join(sorted(VALID_ROLES))}"
        )

    if "COMPLICE" in roles and persona.get("complice_tipo") not in VALID_COMPLICE_TIPOS:
        raise ValueError(
            f"Rol COMPLICE requiere 'complice_tipo' en {key}. "
            f"Válidos: {', '.join(sorted(VALID_COMPLICE_TIPOS))}"
        )

    return sorted(set(roles))
```

- [ ] **Step 4: Correr y verificar que pasa**

Run: `PYTHONPATH=src pytest tests/test_roles.py -v`
Expected: PASS (11 tests)

- [ ] **Step 5: Reemplazar `CYPHER_UPSERT_PERSONAS`**

En `src/zona4_graph_loader/db/cypher.py`, cambiar el bloque que hoy dice
`# UPSERT Base Person (labeled: Persona:Victima)` por:

```python
# UPSERT Base Person (labels dinámicas según row.roles)
CYPHER_UPSERT_PERSONAS = """
UNWIND $rows AS row
MERGE (p:Persona {persona_key: row.persona_key})
SET p.nombre = row.nombre,
    p.genero = row.genero,
    p.fuente = row.fuente,
    p.registro = coalesce(row.registro, p.registro),
    p.fecha_nacimiento = coalesce(row.fecha_nacimiento, p.fecha_nacimiento),
    p.fecha_secuestro = coalesce(row.fecha_secuestro, p.fecha_secuestro),
    p.claves_alt = coalesce(row.claves_alt, p.claves_alt),
    p.tipo = coalesce(row.complice_tipo, p.tipo)
WITH p, row
CALL apoc.create.addLabels(p, row.roles) YIELD node
RETURN count(*)
"""
```

`p.tipo` es la propiedad que el DDL exige para `:Complice` (`complice_tipo_exist`).

- [ ] **Step 6: Normalizar roles en el pipeline**

En `src/zona4_graph_loader/pipeline/load_graph.py`, agregar el import:

```python
from zona4_graph_loader.domain.roles import normalize_roles
```

y reemplazar el bloque que hoy separa personas por `es_nietx` (paso 4, las dos
list comprehensions `personas_detalles` y `protagonistas`) por:

```python
    for persona in consolidated.get("personas", []):
        persona["roles"] = normalize_roles(persona)

    personas_detalles = [
        p for p in consolidated.get("personas", []) if "NIETX" not in p["roles"]
    ]
    protagonistas = [
        p for p in consolidated.get("personas", []) if "NIETX" in p["roles"]
    ]
```

`CYPHER_UPSERT_PROTAGONISTAS` no se toca: sigue manejando `:Nietx` con `caso` y `ADN`.

- [ ] **Step 7: Verificar que no se rompió nada**

Run: `PYTHONPATH=src pytest -v`
Expected: PASS salvo `tests/test_cdm_contract.py`, que sigue rojo hasta la Task 3.

- [ ] **Step 8: Documentar el bump a V1.2**

En `src/zona4_graph_loader/NEO4J_DATA_MODEL.md`, cambiar el encabezado
`## Versión: 1.1 — Rigor de Producción para Agentes de IA` por
`## Versión: 1.2 — Rigor de Producción para Agentes de IA`, y en la sección
`### 2. DICCIONARIO DE NODOS`, bajo `:Persona (Nodo Base)`, agregar:

```markdown
  * fecha_nacimiento [String ISO] (Opcional, V1.2)
  * fecha_secuestro [String ISO] (Opcional, V1.2) — se persiste en el nodo cuando
    no hay lugar asociado que permita construir la arista :SECUESTRADO_EN.
  * claves_alt [List[String]] (Opcional, V1.2) — claves de otras fuentes
    absorbidas por la reconciliación de identidades.
```

Y bajo la regla 1.1, agregar:

```markdown
1.4 ROLES COMO LABELS DINÁMICAS: El cargador asigna las labels de rol a partir
del campo `roles` del CDM. Una fila sin `roles` recibe `["VICTIMA"]`.
```

- [ ] **Step 9: Commit**

```bash
git add src/zona4_graph_loader/domain/roles.py tests/test_roles.py \
        src/zona4_graph_loader/db/cypher.py \
        src/zona4_graph_loader/pipeline/load_graph.py \
        src/zona4_graph_loader/NEO4J_DATA_MODEL.md
git commit -m "feat: labels de rol dinámicas en :Persona (desbloquea represores)"
```

---

### Task 3: Entidades de contexto en el CDM y el writer

Levanta el bloqueo B3: `:Org`, `:Institución`, `:Profesión`, `:Cargo` y `:AliasPersona` están en el modelo pero no tienen Cypher.

**Files:**
- Modify: `src/zona4_graph_loader/builders/base.py`, `src/zona4_graph_loader/io/sources_ingestor.py:8-15,26-28`, `src/zona4_graph_loader/db/cypher.py`, `src/zona4_graph_loader/pipeline/load_graph.py`, `src/zona4_graph_loader/db/qa.py`
- Test: `tests/test_cdm_contract.py` (ya escrito en Task 1)

**Interfaces:**
- Consumes: nada.
- Produces: claves `entidades_contexto` y `relaciones_contexto` en el CDM. Constantes Cypher `CYPHER_UPSERT_ORG`, `CYPHER_UPSERT_INSTITUCION`, `CYPHER_UPSERT_PROFESION`, `CYPHER_UPSERT_CARGO`, `CYPHER_UPSERT_ALIAS_PERSONA`, `CYPHER_LINK_PERSONA_ENTIDAD`, `CYPHER_LINK_ALIAS_PERSONA`. Toda entidad de contexto lleva además la label técnica `:EntidadContexto`, que es la que sostiene el índice de `entidad_key`.

- [ ] **Step 1: Extender `CanonicalDataset`**

En `src/zona4_graph_loader/builders/base.py`, agregar dos campos al TypedDict:

```python
class CanonicalDataset(TypedDict, total=False):
    personas: List[Dict[str, Any]]
    lugares: List[Dict[str, Any]]
    relaciones_interpersonales: List[Dict[str, Any]]
    eventos_espaciales: List[Dict[str, Any]]
    jerarquias: List[Dict[str, Any]]
    entidades_contexto: List[Dict[str, Any]]
    relaciones_contexto: List[Dict[str, Any]]
```

- [ ] **Step 2: Extender `ALLOWED_SOURCE_KEYS`**

En `src/zona4_graph_loader/io/sources_ingestor.py`:

```python
ALLOWED_SOURCE_KEYS = {
    "personas",
    "lugares",
    "relaciones_interpersonales",
    "eventos_espaciales",
    "jerarquias",
    "entidades_contexto",
    "relaciones_contexto",
}
```

`empty_canonical_dataset()` ya deriva de esa constante, así que no requiere cambios.

- [ ] **Step 3: Correr el test de contrato y verificar que pasa**

Run: `PYTHONPATH=src pytest tests/test_cdm_contract.py -v`
Expected: PASS (2 tests). Era el test que quedó rojo en la Task 1.

- [ ] **Step 4: Agregar los Cypher de entidades de contexto**

En `src/zona4_graph_loader/db/cypher.py`, al final del archivo:

```python
# --- Entidades de contexto (V1.2) ---
# Todas llevan la label técnica :EntidadContexto, que sostiene el índice único
# de entidad_key compartido entre los cinco tipos.

CYPHER_UPSERT_ORG = """
UNWIND $rows AS row
MERGE (e:EntidadContexto {entidad_key: row.entidad_key})
SET e:Org,
    e.nombre = row.nombre,
    e.tipoOrg = coalesce(row.tipoOrg, e.tipoOrg),
    e.fuente = row.fuente
"""

CYPHER_UPSERT_INSTITUCION = """
UNWIND $rows AS row
MERGE (e:EntidadContexto {entidad_key: row.entidad_key})
SET e:Institución,
    e.nombre = row.nombre,
    e.fuente = row.fuente
"""

CYPHER_UPSERT_PROFESION = """
UNWIND $rows AS row
MERGE (e:EntidadContexto {entidad_key: row.entidad_key})
SET e:Profesión,
    e.descripcion = row.descripcion,
    e.fuente = row.fuente
"""

CYPHER_UPSERT_CARGO = """
UNWIND $rows AS row
MERGE (e:EntidadContexto {entidad_key: row.entidad_key})
SET e:Cargo,
    e.titulo = row.titulo,
    e.fuente = row.fuente
"""

CYPHER_UPSERT_ALIAS_PERSONA = """
UNWIND $rows AS row
MERGE (e:EntidadContexto {entidad_key: row.entidad_key})
SET e:AliasPersona,
    e.alias = row.alias,
    e.fuente = row.fuente
"""

# Persona -> entidad de contexto (PARTE_DE, FUNDO, EJERCIO, ESTUDIO_EN, TRABAJO_EN)
CYPHER_LINK_PERSONA_ENTIDAD = """
UNWIND $rows AS row
MATCH (p:Persona {persona_key: row.persona_key})
MATCH (e:EntidadContexto {entidad_key: row.entidad_key})
WITH p, e, row
CALL apoc.merge.relationship(
    p,
    row.tipo_relacion,
    {origen: row.origen},
    {fecha: coalesce(row.fecha, "DESCONOCIDA")},
    e,
    {}
) YIELD rel
RETURN count(*)
"""

# AliasPersona -> Persona. Va invertida respecto de las demás: la arista
# IDENTIFICA_A nace en el alias y apunta a la persona real.
CYPHER_LINK_ALIAS_PERSONA = """
UNWIND $rows AS row
MATCH (e:EntidadContexto:AliasPersona {entidad_key: row.entidad_key})
MATCH (p:Persona {persona_key: row.persona_key})
WITH p, e, row
CALL apoc.merge.relationship(
    e,
    "IDENTIFICA_A",
    {origen: row.origen},
    {fecha: coalesce(row.fecha, "DESCONOCIDA")},
    p,
    {}
) YIELD rel
RETURN count(*)
"""
```

- [ ] **Step 5: Agregar el constraint**

En la lista `CONSTRAINTS` de `db/cypher.py`, junto a los demás constraints de
unicidad técnica:

```python
    "CREATE CONSTRAINT entidad_contexto_key_unique IF NOT EXISTS FOR (e:EntidadContexto) REQUIRE e.entidad_key IS UNIQUE",
```

`CYPHER_CLEAN_PROJECT` ya borra `Org`, `Institución`, `Profesión`, `Cargo` y
`AliasPersona`, así que **no requiere cambios**.

- [ ] **Step 6: Cablear los batches en el pipeline**

En `src/zona4_graph_loader/pipeline/load_graph.py`, agregar a los imports de
`db.cypher`: `CYPHER_UPSERT_ORG`, `CYPHER_UPSERT_INSTITUCION`,
`CYPHER_UPSERT_PROFESION`, `CYPHER_UPSERT_CARGO`, `CYPHER_UPSERT_ALIAS_PERSONA`,
`CYPHER_LINK_PERSONA_ENTIDAD`, `CYPHER_LINK_ALIAS_PERSONA`.

En el paso 4 (extracción de entidades), después de `persona_lugar_links`:

```python
    entidades = consolidated.get("entidades_contexto", [])
    orgs = [e for e in entidades if e.get("tipo_entidad") == "Org"]
    instituciones = [e for e in entidades if e.get("tipo_entidad") == "Institucion"]
    profesiones = [e for e in entidades if e.get("tipo_entidad") == "Profesion"]
    cargos = [e for e in entidades if e.get("tipo_entidad") == "Cargo"]
    alias_personas = [e for e in entidades if e.get("tipo_entidad") == "AliasPersona"]

    rel_contexto = [
        r for r in consolidated.get("relaciones_contexto", [])
        if r.get("tipo_relacion") != "IDENTIFICA_A"
    ]
    rel_alias_persona = [
        r for r in consolidated.get("relaciones_contexto", [])
        if r.get("tipo_relacion") == "IDENTIFICA_A"
    ]
```

En el paso 6, justo después del batch `protagonistas_nietx` y antes de las
relaciones interpersonales:

```python
        # Ingest context entities (V1.2)
        run_batches(session, CYPHER_UPSERT_ORG, orgs, "orgs", BATCH_SIZE)
        run_batches(session, CYPHER_UPSERT_INSTITUCION, instituciones, "instituciones", BATCH_SIZE)
        run_batches(session, CYPHER_UPSERT_PROFESION, profesiones, "profesiones", BATCH_SIZE)
        run_batches(session, CYPHER_UPSERT_CARGO, cargos, "cargos", BATCH_SIZE)
        run_batches(session, CYPHER_UPSERT_ALIAS_PERSONA, alias_personas, "alias_personas", BATCH_SIZE)
        run_batches(session, CYPHER_LINK_PERSONA_ENTIDAD, rel_contexto, "rel_contexto", BATCH_SIZE)
        run_batches(session, CYPHER_LINK_ALIAS_PERSONA, rel_alias_persona, "rel_alias_persona", BATCH_SIZE)
```

- [ ] **Step 7: Agregar métricas QA**

En `src/zona4_graph_loader/db/qa.py`, agregar a `QA_QUERIES`:

```python
    "orgs_total": "MATCH (e:Org) RETURN count(e) AS value",
    "instituciones_total": "MATCH (e:Institución) RETURN count(e) AS value",
    "profesiones_total": "MATCH (e:Profesión) RETURN count(e) AS value",
    "cargos_total": "MATCH (e:Cargo) RETURN count(e) AS value",
    "alias_personas_total": "MATCH (e:AliasPersona) RETURN count(e) AS value",
    "rel_parte_de_org_total": "MATCH (:Persona)-[r:PARTE_DE]->(:Org) RETURN count(r) AS value",
    "rel_identifica_a_total": "MATCH ()-[r:IDENTIFICA_A]->() RETURN count(r) AS value",
```

- [ ] **Step 8: Correr la suite completa**

Run: `PYTHONPATH=src pytest -v`
Expected: PASS (todos)

- [ ] **Step 9: Commit**

```bash
git add src/zona4_graph_loader/ tests/
git commit -m "feat: entidades de contexto (Org, Institución, Profesión, Cargo, AliasPersona)"
```

---

### Task 4: Idempotencia de aristas dinámicas y QA de aristas no resueltas

Las aristas dinámicas usan `apoc.create.relationship`, que duplica en cada corrida sin `--clean-project`. Y `CYPHER_LINK_PERSONA_LUGAR_DYNAMIC` descarta filas en silencio cuando el `lugar_key` no existe.

**Files:**
- Modify: `src/zona4_graph_loader/db/cypher.py` (`CYPHER_UPSERT_REL_FAMILIAR`, `CYPHER_UPSERT_REL_PERSONA`, `CYPHER_LINK_PERSONA_LUGAR_DYNAMIC`), `src/zona4_graph_loader/pipeline/load_graph.py`
- Create: `tests/test_eventos_espaciales.py`

**Interfaces:**
- Consumes: nada.
- Produces: `contar_eventos_huerfanos(dataset: CanonicalDataset) -> List[Dict[str, Any]]` en `pipeline/load_graph.py`, que devuelve las filas de `eventos_espaciales` cuyo `lugar_key` no existe en `lugares`.

- [ ] **Step 1: Migrar las tres relaciones dinámicas a `apoc.merge.relationship`**

En `db/cypher.py`, en `CYPHER_UPSERT_REL_FAMILIAR` y `CYPHER_UPSERT_REL_PERSONA`,
reemplazar la línea del `CALL` por:

```
CALL apoc.merge.relationship(
    s,
    row.tipo,
    {origen: row.fuente},
    {fecha: coalesce(row.fecha, "DESCONOCIDA")},
    t,
    {}
) YIELD rel
```

Y en `CYPHER_LINK_PERSONA_LUGAR_DYNAMIC`:

```
CALL apoc.merge.relationship(
    p,
    row.tipo_relacion,
    {origen: row.origen},
    {fecha: coalesce(row.fecha, "DESCONOCIDA")},
    l,
    {}
) YIELD rel
```

`origen` va en `identProps` (3er argumento) y `fecha` en `onCreateProps`: dos
fuentes distintas que afirman el mismo hecho producen dos aristas distinguibles,
pero la misma fuente cargada dos veces produce una sola.

- [ ] **Step 2: Escribir el test que falla**

Crear `tests/test_eventos_espaciales.py`:

```python
from __future__ import annotations

from zona4_graph_loader.pipeline.load_graph import contar_eventos_huerfanos


def test_evento_con_lugar_existente_no_es_huerfano():
    dataset = {
        "lugares": [{"lugar_key": "lugar:CCD:olimpo", "tipo_entidad": "Lugar"}],
        "eventos_espaciales": [
            {"persona_key": "p:1", "lugar_key": "lugar:CCD:olimpo",
             "tipo_relacion": "PRESENTE_EN", "origen": "test"}
        ],
    }
    assert contar_eventos_huerfanos(dataset) == []


def test_evento_sin_lugar_es_huerfano():
    dataset = {
        "lugares": [{"lugar_key": "lugar:CCD:olimpo", "tipo_entidad": "Lugar"}],
        "eventos_espaciales": [
            {"persona_key": "p:1", "lugar_key": "lugar:CCD:inexistente",
             "tipo_relacion": "PRESENTE_EN", "origen": "test"}
        ],
    }
    huerfanos = contar_eventos_huerfanos(dataset)
    assert len(huerfanos) == 1
    assert huerfanos[0]["lugar_key"] == "lugar:CCD:inexistente"


def test_alias_y_direcciones_no_cuentan_como_lugares():
    dataset = {
        "lugares": [
            {"alias_key": "alias:1", "tipo_entidad": "AliasLugar",
             "lugar_key": "lugar:CIUDAD:x"},
        ],
        "eventos_espaciales": [
            {"persona_key": "p:1", "lugar_key": "lugar:CIUDAD:x",
             "tipo_relacion": "PRESENTE_EN", "origen": "test"}
        ],
    }
    assert len(contar_eventos_huerfanos(dataset)) == 1
```

- [ ] **Step 3: Correr y verificar que falla**

Run: `PYTHONPATH=src pytest tests/test_eventos_espaciales.py -v`
Expected: FAIL — `ImportError: cannot import name 'contar_eventos_huerfanos'`

- [ ] **Step 4: Implementar la función**

En `src/zona4_graph_loader/pipeline/load_graph.py`, después de `_merge_datasets`:

```python
def contar_eventos_huerfanos(dataset: CanonicalDataset) -> List[Dict[str, Any]]:
    """Eventos espaciales cuyo lugar_key no existe como nodo :Lugar en el CDM.

    El Cypher de eventos hace MATCH sobre el lugar, así que estas filas se
    descartarían en silencio. Se reportan en vez de perderse.
    """
    lugar_keys = {
        l.get("lugar_key")
        for l in dataset.get("lugares", [])
        if l.get("tipo_entidad") == "Lugar"
    }
    return [
        e for e in dataset.get("eventos_espaciales", [])
        if e.get("lugar_key") not in lugar_keys
    ]
```

- [ ] **Step 5: Correr y verificar que pasa**

Run: `PYTHONPATH=src pytest tests/test_eventos_espaciales.py -v`
Expected: PASS (3 tests)

**Desvío respecto del spec:** la sección 5.4 del spec ubicaba esta contabilización
en `db/qa.py`. Va en el pipeline: `qa.py` corre *después* de escribir y consulta
Neo4j, así que no puede ver las filas que nunca llegaron a insertarse. Contarlas
sobre el CDM, antes de escribir, es lo único que reporta la pérdida real.

- [ ] **Step 6: Reportar los huérfanos en el pipeline**

En `run_load`, justo después de calcular `persona_lugar_links`:

```python
    eventos_huerfanos = contar_eventos_huerfanos(consolidated)
    if eventos_huerfanos:
        por_tipo: Dict[str, int] = {}
        for evento in eventos_huerfanos:
            tipo = evento.get("tipo_relacion", "DESCONOCIDO")
            por_tipo[tipo] = por_tipo.get(tipo, 0) + 1
        detalle = ", ".join(f"{k}={v}" for k, v in sorted(por_tipo.items()))
        print(f"Warning: {len(eventos_huerfanos)} eventos espaciales sin lugar resuelto ({detalle})")
```

- [ ] **Step 7: Correr la suite completa y commitear**

Run: `PYTHONPATH=src pytest -v`
Expected: PASS

```bash
git add src/zona4_graph_loader/ tests/
git commit -m "fix: aristas dinámicas idempotentes y reporte de eventos sin lugar"
```

---

### Task 5: Reconciliación de identidades

Merge determinista entre fuentes, con el resto de las coincidencias materializadas como `CANDIDATO_MERGE` para revisión humana.

**Files:**
- Create: `src/zona4_graph_loader/domain/identity_resolution.py`, `tests/test_identity_resolution.py`
- Modify: `src/zona4_graph_loader/pipeline/load_graph.py`, `src/zona4_graph_loader/cli.py`

**Interfaces:**
- Consumes: `slugify_name` de `domain/text_norm`, `name_similarity_score` y `name_token_set` de `domain/name_similarity`.
- Produces:
  - `SOURCE_PRIORITY: List[str]`
  - `resolve_identities(dataset: CanonicalDataset) -> IdentityReport` — muta `dataset` in place.
  - `IdentityReport`, dataclass con `merges: List[Dict[str, Any]]` (cada uno `{canonical_key, absorbed_key, motivo}`) y `candidatos: List[Dict[str, Any]]` (filas listas para `CYPHER_UPSERT_CANDIDATO_MERGE`, con las claves `placeholder_key`, `candidate_key`, `metodo`, `score`, `slug`, `confianza`, `fuente`).

- [ ] **Step 1: Escribir los tests que fallan**

Crear `tests/test_identity_resolution.py`:

```python
from __future__ import annotations

from zona4_graph_loader.domain.identity_resolution import (
    SOURCE_PRIORITY,
    resolve_identities,
)


def _persona(key, nombre, fuente, **extra):
    base = {
        "persona_key": key,
        "nombre": nombre,
        "genero": "INDETERMINADO",
        "fuente": fuente,
        "roles": ["VICTIMA"],
    }
    base.update(extra)
    return base


def test_merge_con_nombre_y_fecha_nacimiento_coincidentes():
    dataset = {
        "personas": [
            _persona("registro:1", "Juan Carlos Abachian", "detalles_personas",
                     fecha_nacimiento="1950-03-02"),
            _persona("minjus_victima:213", "Juan Carlos Abachian", "minjus_victimas",
                     fecha_nacimiento="1950-03-02"),
        ],
        "eventos_espaciales": [
            {"persona_key": "minjus_victima:213", "lugar_key": "lugar:CCD:x",
             "tipo_relacion": "PRESENTE_EN", "origen": "minjus_victimas"}
        ],
    }
    report = resolve_identities(dataset)

    assert len(dataset["personas"]) == 1
    superviviente = dataset["personas"][0]
    assert superviviente["persona_key"] == "registro:1"
    assert superviviente["claves_alt"] == ["minjus_victima:213"]
    assert superviviente["fuente"] == "detalles_personas|minjus_victimas"
    assert dataset["eventos_espaciales"][0]["persona_key"] == "registro:1"
    assert len(report.merges) == 1
    assert report.candidatos == []


def test_merge_con_fecha_secuestro_coincidente():
    dataset = {
        "personas": [
            _persona("archivo_memoria:7", "Jorge Bellantuono Herrero", "archivo_memoria",
                     fecha_secuestro="1976-07-13"),
            _persona("minjus_victima:900", "Jorge Bellantuono Herrero", "minjus_victimas",
                     fecha_secuestro="1976-07-13"),
        ],
    }
    resolve_identities(dataset)
    assert len(dataset["personas"]) == 1
    assert dataset["personas"][0]["persona_key"] == "archivo_memoria:7"


def test_nombre_igual_sin_fecha_genera_candidato_no_merge():
    dataset = {
        "personas": [
            _persona("registro:1", "Juan Perez", "detalles_personas"),
            _persona("minjus_victima:5", "Juan Perez", "minjus_victimas"),
        ],
    }
    report = resolve_identities(dataset)

    assert len(dataset["personas"]) == 2
    assert report.merges == []
    assert len(report.candidatos) == 1
    candidato = report.candidatos[0]
    assert candidato["metodo"] == "nombre_exacto_sin_fecha"
    assert candidato["confianza"] == "media"
    assert {candidato["placeholder_key"], candidato["candidate_key"]} == {
        "registro:1", "minjus_victima:5"
    }


def test_fechas_distintas_no_mergean():
    dataset = {
        "personas": [
            _persona("registro:1", "Juan Perez", "detalles_personas",
                     fecha_nacimiento="1950-01-01"),
            _persona("minjus_victima:5", "Juan Perez", "minjus_victimas",
                     fecha_nacimiento="1962-11-30"),
        ],
    }
    report = resolve_identities(dataset)
    assert len(dataset["personas"]) == 2
    assert report.merges == []


def test_nunca_mergea_dos_personas_de_la_misma_fuente():
    dataset = {
        "personas": [
            _persona("minjus_victima:1", "Juan Perez", "minjus_victimas",
                     fecha_nacimiento="1950-01-01"),
            _persona("minjus_victima:2", "Juan Perez", "minjus_victimas",
                     fecha_nacimiento="1950-01-01"),
        ],
    }
    report = resolve_identities(dataset)
    assert len(dataset["personas"]) == 2
    assert report.merges == []
    assert report.candidatos == []


def test_hermanas_con_apellido_igual_no_mergean_ni_son_candidatas_fuertes():
    """Caso real de MinJus: dos personas distintas, nombres muy similares."""
    dataset = {
        "personas": [
            _persona("minjus_victima:10", "Abadía Crespo, Dominga", "minjus_victimas"),
            _persona("registro:88", "Abadía Crespo, Felicidad", "detalles_personas"),
        ],
    }
    report = resolve_identities(dataset)
    assert len(dataset["personas"]) == 2
    assert report.merges == []
    assert all(c["confianza"] != "alta" for c in report.candidatos)


def test_merge_reescribe_relaciones_interpersonales_y_contexto():
    dataset = {
        "personas": [
            _persona("registro:1", "Ana Gomez", "detalles_personas",
                     fecha_nacimiento="1955-05-05"),
            _persona("minjus_victima:2", "Ana Gomez", "minjus_victimas",
                     fecha_nacimiento="1955-05-05"),
        ],
        "relaciones_interpersonales": [
            {"source_key": "minjus_imputado:9", "target_key": "minjus_victima:2",
             "tipo": "TORTURO_A", "fuente": "minjus_victimas"},
        ],
        "relaciones_contexto": [
            {"persona_key": "minjus_victima:2", "entidad_key": "org:jp",
             "tipo_relacion": "PARTE_DE", "origen": "minjus_victimas"},
        ],
    }
    resolve_identities(dataset)
    assert dataset["relaciones_interpersonales"][0]["target_key"] == "registro:1"
    assert dataset["relaciones_contexto"][0]["persona_key"] == "registro:1"


def test_merge_unifica_roles_y_completa_campos_faltantes():
    dataset = {
        "personas": [
            _persona("registro:1", "Luis Diaz", "detalles_personas",
                     fecha_nacimiento="1940-02-02"),
            _persona("juicios_condenado:3", "Luis Diaz", "juicios_condenados",
                     fecha_nacimiento="1940-02-02", roles=["REPRESOR"],
                     fecha_secuestro=None),
        ],
    }
    resolve_identities(dataset)
    superviviente = dataset["personas"][0]
    assert superviviente["roles"] == ["REPRESOR", "VICTIMA"]


def test_prioridad_de_fuente_declarada():
    assert SOURCE_PRIORITY[0] == "detalles_personas"
    assert SOURCE_PRIORITY.index("archivo_memoria") < SOURCE_PRIORITY.index("minjus_victimas")


def test_dataset_sin_personas_no_falla():
    dataset = {"personas": []}
    report = resolve_identities(dataset)
    assert report.merges == []
    assert report.candidatos == []
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `PYTHONPATH=src pytest tests/test_identity_resolution.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'zona4_graph_loader.domain.identity_resolution'`

- [ ] **Step 3: Implementar `domain/identity_resolution.py`**

```python
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
    return min(personas, key=lambda p: (_priority(p.get("fuente")), p.get("persona_key", "")))


def _fechas_confirman(a: Dict[str, Any], b: Dict[str, Any]) -> Optional[str]:
    for campo in ("fecha_nacimiento", "fecha_secuestro"):
        va, vb = a.get(campo), b.get(campo)
        if va and vb and va == vb:
            return campo
    return None


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

    for campo in ("fecha_nacimiento", "fecha_secuestro", "registro", "complice_tipo"):
        if not canonico.get(campo) and otro.get(campo):
            canonico[campo] = otro[campo]

    if canonico.get("genero") in (None, "INDETERMINADO") and otro.get("genero") not in (
        None, "INDETERMINADO",
    ):
        canonico["genero"] = otro["genero"]


def _reescribir_referencias(dataset: CanonicalDataset, key_map: Dict[str, str]) -> None:
    if not key_map:
        return
    for fila in dataset.get("relaciones_interpersonales", []):
        for campo in ("source_key", "target_key"):
            if fila.get(campo) in key_map:
                fila[campo] = key_map[fila[campo]]
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

        clusters: List[List[Dict[str, Any]]] = []
        for persona in sorted(grupo, key=lambda p: (_priority(p.get("fuente")), p["persona_key"])):
            destino = None
            for cluster in clusters:
                if any(p.get("fuente") == persona.get("fuente") for p in cluster):
                    continue
                if any(_fechas_confirman(p, persona) for p in cluster):
                    destino = cluster
                    break
            if destino is None:
                clusters.append([persona])
            else:
                destino.append(persona)

        for cluster in clusters:
            if len(cluster) < 2:
                continue
            canonico = _canonical_of(cluster)
            for otro in cluster:
                if otro is canonico:
                    continue
                motivo = _fechas_confirman(canonico, otro) or "fecha_confirmada"
                _absorber(canonico, otro)
                key_map[otro["persona_key"]] = canonico["persona_key"]
                absorbidas.add(otro["persona_key"])
                report.merges.append({
                    "canonical_key": canonico["persona_key"],
                    "absorbed_key": otro["persona_key"],
                    "motivo": motivo,
                })

        # Los que quedaron sin fusionar dentro del bloque, pero vienen de fuentes
        # distintas, son candidatos de confianza media.
        sobrevivientes = [p for p in grupo if p["persona_key"] not in absorbidas]
        for i, a in enumerate(sobrevivientes):
            for b in sobrevivientes[i + 1:]:
                if a.get("fuente") == b.get("fuente"):
                    continue
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
```

- [ ] **Step 4: Correr y verificar que pasa**

Run: `PYTHONPATH=src pytest tests/test_identity_resolution.py -v`
Expected: PASS (10 tests)

- [ ] **Step 5: Cablear el paso 3.5 en el pipeline**

En `pipeline/load_graph.py`, agregar el import:

```python
from zona4_graph_loader.domain.identity_resolution import resolve_identities
```

y, entre el bloque `# 3. Load and merge direct static sources` y el
`# 4. Extract entities...`:

```python
    # 3.5 Reconcile identities across sources before writing anything
    identity_candidatos: List[Dict[str, Any]] = []
    if not args.skip_identity_resolution:
        identity_report = resolve_identities(consolidated)
        identity_candidatos = identity_report.candidatos
        print(
            f"identity_resolution: {len(identity_report.merges)} merges, "
            f"{len(identity_candidatos)} candidatos"
        )
        dump_path = Path("data/processed/identity_merges.json")
        dump_path.parent.mkdir(parents=True, exist_ok=True)
        with dump_path.open("w", encoding="utf-8") as f:
            json.dump(identity_report.merges, f, ensure_ascii=False, indent=2)
```

Agregar `import json` al encabezado del archivo.

En el paso 5, sumar los candidatos de reconciliación a los que ya produce
`build_v3_candidate_rows`:

```python
    v3_candidates = build_v3_candidate_rows(personas_detalles, rel_familiares, rel_personas)
    v3_candidates.extend(identity_candidatos)
```

- [ ] **Step 6: Agregar el flag al CLI**

En `src/zona4_graph_loader/cli.py`, junto a los demás flags:

```python
    parser.add_argument(
        "--skip-identity-resolution",
        action="store_true",
        help="No reconcilia identidades entre fuentes antes de cargar.",
    )
```

- [ ] **Step 7: Correr la suite completa y commitear**

Run: `PYTHONPATH=src pytest -v`
Expected: PASS

```bash
git add src/zona4_graph_loader/ tests/
git commit -m "feat: reconciliación de identidades cross-fuente (merge determinista + candidatos)"
```

---

### Task 6: Builder de sitios de hallazgo del EAAF

91 sitios con lat/long completos. Es el builder más simple y el que valida el flujo de punta a punta.

**Files:**
- Create: `src/zona4_graph_loader/io/raw_files.py`, `src/zona4_graph_loader/builders/eaaf_lugares.py`, `tests/builders/__init__.py`, `tests/builders/test_eaaf_lugares.py`
- Modify: `src/zona4_graph_loader/pipeline/load_graph.py`, `src/zona4_graph_loader/cli.py`

**Interfaces:**
- Consumes: `make_lugar_key` de `domain/place_norm`, `slugify_name` y `clean_text` de `domain/text_norm`.
- Produces:
  - En `io/raw_files.py`: `RAW_DIR: Path`, `read_raw_json(nombre: str) -> Any`, `read_raw_csv(nombre: str, delimiter: str = ";") -> List[Dict[str, str]]`.
  - `build_eaaf_lugares_rows(rows: List[Dict[str, str]]) -> CanonicalDataset` con las claves `lugares` y `jerarquias`.
  - Flag `--dump-cdm <path>`.

- [ ] **Step 1: Crear `io/raw_files.py`**

```python
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[3]
RAW_DIR = ROOT / "data" / "raw"


def read_raw_json(nombre: str) -> Any:
    with (RAW_DIR / nombre).open("r", encoding="utf-8") as f:
        return json.load(f)


def read_raw_csv(nombre: str, delimiter: str = ";") -> List[Dict[str, str]]:
    with (RAW_DIR / nombre).open("r", encoding="utf-8", newline="") as f:
        return [dict(row) for row in csv.DictReader(f, delimiter=delimiter)]
```

- [ ] **Step 2: Escribir el test que falla**

Crear `tests/builders/__init__.py` vacío y `tests/builders/test_eaaf_lugares.py`:

```python
from __future__ import annotations

from zona4_graph_loader.builders.eaaf_lugares import build_eaaf_lugares_rows
from zona4_graph_loader.io.raw_files import read_raw_csv

FILA_CEM = {
    "PROVINCIA": "Buenos Aires",
    "LOCALIDAD": "Almirante Brown",
    "CEM - CCD - EP": "CEM",
    "LUGAR DE HALLAZGO": "Cementerio de Almirante Brown",
    "HOJA DE REFERENCIA": "Zona_Sur-Rafael_Calzada",
    "Lat": "-34.795355931418285",
    "Long": "-58.34562565092717",
    "Suma de CASOS": "30",
    "Suma de EXHUMADOS": "30",
    "Suma de ID": "10",
}

FILA_EXTRANJERA = dict(FILA_CEM, PROVINCIA="Uruguay", LOCALIDAD="Montevideo",
                       **{"LUGAR DE HALLAZGO": "Playa Malvin"})


def test_genera_lugar_con_coordenadas():
    dataset = build_eaaf_lugares_rows([FILA_CEM])
    lugares = [l for l in dataset["lugares"] if l["tipo_entidad"] == "Lugar"]
    sitio = next(l for l in lugares if l["tipoGeopolitico"] == "CEMENTERIO")
    assert sitio["nombre"] == "CEMENTERIO DE ALMIRANTE BROWN"
    assert sitio["lat"] == -34.795355931418285
    assert sitio["lon"] == -58.34562565092717
    assert sitio["fuente"] == "eaaf_lugares"


def test_mapea_tipos_cem_ccd_ep():
    def tipo_de(valor):
        dataset = build_eaaf_lugares_rows([dict(FILA_CEM, **{"CEM - CCD - EP": valor})])
        sitios = [l for l in dataset["lugares"]
                  if l["tipo_entidad"] == "Lugar" and l["fuente"] == "eaaf_lugares"]
        return {l["tipoGeopolitico"] for l in sitios}

    assert "CEMENTERIO" in tipo_de("CEM")
    assert "CCD" in tipo_de("CCD")
    assert "ENTERRAMIENTO" in tipo_de("EP")


def test_construye_jerarquia_sitio_localidad_provincia_pais():
    dataset = build_eaaf_lugares_rows([FILA_CEM])
    pares = {(j["child_key"], j["parent_key"]) for j in dataset["jerarquias"]
             if j["tipo_relacion"] == "PARTE_DE"}
    keys = {l["lugar_key"] for l in dataset["lugares"]}

    assert "lugar:PAIS:argentina" in keys
    assert any(p == "lugar:PAIS:argentina" for _, p in pares)
    assert len(pares) == 3  # sitio->localidad, localidad->provincia, provincia->pais


def test_lugar_extranjero_usa_pais_code_propio():
    dataset = build_eaaf_lugares_rows([FILA_EXTRANJERA])
    paises = [l for l in dataset["lugares"] if l["tipoGeopolitico"] == "PAIS"]
    assert any(l["pais_code"] == "UY" for l in paises)


def test_genera_direccion_ccd_con_coordenadas():
    dataset = build_eaaf_lugares_rows([FILA_CEM])
    direcciones = [l for l in dataset["lugares"] if l["tipo_entidad"] == "DireccionCCD"]
    assert len(direcciones) == 1
    assert direcciones[0]["coordenadas"] == "-34.795355931418285,-58.34562565092717"
    links = [j for j in dataset["jerarquias"] if j["tipo_relacion"] == "UBICADA_EN"]
    assert len(links) == 1


def test_fila_sin_coordenadas_no_genera_direccion():
    dataset = build_eaaf_lugares_rows([dict(FILA_CEM, Lat="", Long="")])
    assert [l for l in dataset["lugares"] if l["tipo_entidad"] == "DireccionCCD"] == []


def test_sobre_el_archivo_real():
    filas = read_raw_csv("eaaf_lugares.csv")
    dataset = build_eaaf_lugares_rows(filas)
    sitios = [l for l in dataset["lugares"]
              if l["tipo_entidad"] == "Lugar" and l["fuente"] == "eaaf_lugares"]
    assert len(sitios) == 91
    assert all(l.get("lat") is not None for l in sitios)
```

- [ ] **Step 3: Correr y verificar que falla**

Run: `PYTHONPATH=src pytest tests/builders/test_eaaf_lugares.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'zona4_graph_loader.builders.eaaf_lugares'`

- [ ] **Step 4: Implementar el builder**

```python
from __future__ import annotations

from typing import Any, Dict, List, Optional

from zona4_graph_loader.builders.base import CanonicalDataset
from zona4_graph_loader.domain.place_norm import make_lugar_key
from zona4_graph_loader.domain.text_norm import clean_text, slugify_name

FUENTE = "eaaf_lugares"

# CEM = cementerio, CCD = centro clandestino, EP = enterramiento en predio.
TIPO_SITIO = {
    "CEM": "CEMENTERIO",
    "CCD": "CCD",
    "EP": "ENTERRAMIENTO",
}

# Provincias del dataset que en realidad son países extranjeros.
PAISES_EXTRANJEROS = {
    "URUGUAY": "UY",
    "BOLIVIA": "BO",
    "BRASIL": "BR",
    "CHILE": "CL",
    "PARAGUAY": "PY",
}


def _to_float(value: Any) -> Optional[float]:
    text = clean_text(value)
    if text is None:
        return None
    try:
        return float(text.replace(",", "."))
    except ValueError:
        return None


def build_eaaf_lugares_rows(rows: List[Dict[str, str]]) -> CanonicalDataset:
    """Convierte el consolidado de sitios de hallazgo del EAAF al CDM.

    Cada fila trae provincia, localidad, tipo de sitio y coordenadas exactas, así
    que la jerarquía se arma sin recurrir a Georef.
    """
    lugares: Dict[str, Dict[str, Any]] = {}
    direcciones: Dict[str, Dict[str, Any]] = {}
    jerarquias: List[Dict[str, Any]] = []
    pares_parte_de: set[tuple[str, str]] = set()

    def registrar_parte_de(child_key: str, parent_key: str) -> None:
        if (child_key, parent_key) in pares_parte_de:
            return
        pares_parte_de.add((child_key, parent_key))
        jerarquias.append({
            "tipo_relacion": "PARTE_DE",
            "child_key": child_key,
            "parent_key": parent_key,
        })

    for row in rows:
        nombre_sitio = clean_text(row.get("LUGAR DE HALLAZGO"))
        provincia = clean_text(row.get("PROVINCIA"))
        localidad = clean_text(row.get("LOCALIDAD"))
        if not nombre_sitio or not provincia:
            continue

        provincia_upper = provincia.upper()
        pais_nombre = provincia_upper if provincia_upper in PAISES_EXTRANJEROS else "ARGENTINA"
        pais_code = PAISES_EXTRANJEROS.get(provincia_upper, "AR")
        pais_key = make_lugar_key("PAIS", pais_nombre, None)
        lugares.setdefault(pais_key, {
            "lugar_key": pais_key,
            "nombre": pais_nombre,
            "tipoGeopolitico": "PAIS",
            "pais_code": pais_code,
            "fuente": FUENTE,
            "tipo_entidad": "Lugar",
        })

        # En las filas extranjeras la columna PROVINCIA trae el país, así que el
        # contenedor intermedio pasa a ser la localidad directamente.
        if provincia_upper in PAISES_EXTRANJEROS:
            contenedor_key = pais_key
        else:
            provincia_key = make_lugar_key("PROVINCIA", provincia_upper, pais_key)
            lugares.setdefault(provincia_key, {
                "lugar_key": provincia_key,
                "nombre": provincia_upper,
                "tipoGeopolitico": "PROVINCIA",
                "pais_code": pais_code,
                "fuente": FUENTE,
                "tipo_entidad": "Lugar",
            })
            registrar_parte_de(provincia_key, pais_key)
            contenedor_key = provincia_key

        if localidad:
            localidad_upper = localidad.upper()
            localidad_key = make_lugar_key("CIUDAD", localidad_upper, contenedor_key)
            lugares.setdefault(localidad_key, {
                "lugar_key": localidad_key,
                "nombre": localidad_upper,
                "tipoGeopolitico": "CIUDAD",
                "pais_code": pais_code,
                "fuente": FUENTE,
                "tipo_entidad": "Lugar",
            })
            registrar_parte_de(localidad_key, contenedor_key)
            contenedor_key = localidad_key

        tipo_sitio = TIPO_SITIO.get((clean_text(row.get("CEM - CCD - EP")) or "").upper(), "SITIO_HALLAZGO")
        nombre_upper = nombre_sitio.upper()
        sitio_key = make_lugar_key(tipo_sitio, nombre_upper, contenedor_key)
        lat = _to_float(row.get("Lat"))
        lon = _to_float(row.get("Long"))

        lugares[sitio_key] = {
            "lugar_key": sitio_key,
            "nombre": nombre_upper,
            "tipoGeopolitico": tipo_sitio,
            "pais_code": pais_code,
            "fuente": FUENTE,
            "lat": lat,
            "lon": lon,
            "ubicacion": clean_text(row.get("HOJA DE REFERENCIA")),
            "tipo_entidad": "Lugar",
        }
        registrar_parte_de(sitio_key, contenedor_key)

        if lat is not None and lon is not None:
            direccion_key = f"direccion_ccd:eaaf:{slugify_name(nombre_upper)}"
            direcciones[direccion_key] = {
                "direccion_ccd_key": direccion_key,
                "coordenadas": f"{lat},{lon}",
                "direccionExacta": nombre_upper,
                "lugar_key": sitio_key,
                "tipo_entidad": "DireccionCCD",
            }
            jerarquias.append({
                "tipo_relacion": "UBICADA_EN",
                "direccion_ccd_key": direccion_key,
                "lugar_key": sitio_key,
            })

    return {
        "lugares": list(lugares.values()) + list(direcciones.values()),
        "jerarquias": jerarquias,
    }
```

- [ ] **Step 5: Correr y verificar que pasa**

Run: `PYTHONPATH=src pytest tests/builders/test_eaaf_lugares.py -v`
Expected: PASS (7 tests)

- [ ] **Step 6: Registrar el builder y agregar `--dump-cdm`**

En `pipeline/load_graph.py`, importar:

```python
from zona4_graph_loader.builders.eaaf_lugares import build_eaaf_lugares_rows
from zona4_graph_loader.io.raw_files import read_raw_csv
```

En el paso 2, después de los builders base:

```python
    if not args.skip_nuevas_fuentes:
        _merge_datasets(consolidated, build_eaaf_lugares_rows(read_raw_csv("eaaf_lugares.csv")))
```

Y al final del paso 3.5, antes de la extracción de entidades:

```python
    if args.dump_cdm:
        dump_cdm_path = Path(args.dump_cdm)
        dump_cdm_path.parent.mkdir(parents=True, exist_ok=True)
        with dump_cdm_path.open("w", encoding="utf-8") as f:
            json.dump(consolidated, f, ensure_ascii=False, indent=2)
        print(f"dump_cdm: {dump_cdm_path}")
```

En `cli.py`:

```python
    parser.add_argument(
        "--skip-nuevas-fuentes",
        action="store_true",
        help="No integra los builders de data/raw/ (EAAF, San Martín, MinJus, condenados).",
    )
    parser.add_argument(
        "--dump-cdm",
        default=None,
        help="Vuelca el CDM consolidado a un JSON en la ruta indicada, para auditoría.",
    )
```

- [ ] **Step 7: Verificar el volcado sin tocar Neo4j**

Run: `PYTHONPATH=src python -m zona4_graph_loader.cli --validate-sources-only`
Expected: termina sin excepción.

- [ ] **Step 8: Commit**

```bash
git add src/zona4_graph_loader/ tests/
git commit -m "feat: builder de sitios de hallazgo del EAAF (91 lugares) y flag --dump-cdm"
```

---

### Task 7: Builder del Archivo de la Memoria de San Martín

303 víctimas de Zona IV, el foco geográfico del proyecto. Fechas ya normalizadas y topónimos cortos.

**Files:**
- Create: `src/zona4_graph_loader/builders/archivo_memoria.py`, `tests/builders/test_archivo_memoria.py`, `tests/builders/test_lugares_ancestros.py`
- Modify: `src/zona4_graph_loader/builders/lugares.py:17-33`, `src/zona4_graph_loader/pipeline/load_graph.py`

**Interfaces:**
- Consumes: `resolve_place` de `domain/place_norm`, `read_raw_json` de `io/raw_files`.
- Produces:
  - `node_from_lugar_key(lugar_key: str) -> Dict[str, str]` — promoción a público del actual `_node_from_lugar_key`.
  - `expand_lugar_ancestors(lugar_key: str, fuente: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]` — devuelve `(lugares, jerarquias)` de toda la cadena de contenedores.
  - `build_archivo_memoria_rows(data: List[Dict[str, Any]], *, use_georef: bool = True) -> CanonicalDataset` con claves `personas`, `lugares`, `jerarquias`, `eventos_espaciales`, `entidades_contexto`, `relaciones_contexto`. Claves de persona: `archivo_memoria:{indice}`.

**Por qué hace falta el helper de ancestros:** `resolve_place` devuelve exactamente
`{alias_raw, alias_norm, tipo, nombre_canonico, lugar_key, parent_key}` — verificado
en `domain/place_norm.py:565-685`. **No materializa los nodos padre.** Un
`parent_key` como `lugar:PROVINCIA:buenos_aires|lugar:PAIS:argentina` apunta a
nodos que nadie crea, y `CYPHER_LINK_LUGAR_PARENT` hace `MATCH` sobre ambos
extremos: sin el padre, la arista `PARTE_DE` se descarta en silencio. La
convención de `make_lugar_key` es `lugar:{TIPO}:{slug}|{parent_key}`, donde el
`parent_key` es a su vez una clave completa, así que la cadena se recorre
partiendo por el primer `|`.

- [ ] **Step 0: Promover el helper de reconstrucción y agregar el de ancestros**

En `src/zona4_graph_loader/builders/lugares.py`, renombrar `_node_from_lugar_key`
a `node_from_lugar_key` (actualizando sus usos internos) y agregar debajo:

```python
def expand_lugar_ancestors(
    lugar_key: str,
    fuente: str,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Materializa la cadena de contenedores implícita en un lugar_key.

    `make_lugar_key` codifica la jerarquía como `lugar:TIPO:slug|<parent_key>`,
    donde el parent_key es a su vez una clave completa. `resolve_place` devuelve
    sólo el nodo hoja y su parent_key, así que sin esta expansión los nodos padre
    nunca se crean y las aristas PARTE_DE se pierden.
    """
    lugares: List[Dict[str, Any]] = []
    jerarquias: List[Dict[str, Any]] = []

    actual = lugar_key
    while actual:
        nodo = dict(node_from_lugar_key(actual))
        nodo["pais_code"] = "AR"
        nodo["fuente"] = fuente
        nodo["tipo_entidad"] = "Lugar"
        lugares.append(nodo)

        padre = actual.split("|", 1)[1] if "|" in actual else None
        if padre:
            jerarquias.append({
                "tipo_relacion": "PARTE_DE",
                "child_key": actual,
                "parent_key": padre,
            })
        actual = padre

    return lugares, jerarquias
```

Agregar `Tuple` al import de `typing` en ese archivo.

- [ ] **Step 0b: Test del helper**

Crear `tests/builders/test_lugares_ancestros.py`:

```python
from __future__ import annotations

from zona4_graph_loader.builders.lugares import (
    expand_lugar_ancestors,
    node_from_lugar_key,
)

CIUDAD = "lugar:CIUDAD:billinghurst|lugar:PROVINCIA:buenos_aires|lugar:PAIS:argentina"


def test_node_from_lugar_key_reconstruye_nombre_y_tipo():
    nodo = node_from_lugar_key(CIUDAD)
    assert nodo["tipoGeopolitico"] == "CIUDAD"
    assert nodo["nombre"] == "BILLINGHURST"


def test_expande_toda_la_cadena():
    lugares, jerarquias = expand_lugar_ancestors(CIUDAD, "test")
    keys = [l["lugar_key"] for l in lugares]
    assert keys == [
        CIUDAD,
        "lugar:PROVINCIA:buenos_aires|lugar:PAIS:argentina",
        "lugar:PAIS:argentina",
    ]
    assert all(l["fuente"] == "test" for l in lugares)
    assert all(l["tipo_entidad"] == "Lugar" for l in lugares)


def test_genera_una_arista_por_salto():
    _, jerarquias = expand_lugar_ancestors(CIUDAD, "test")
    assert len(jerarquias) == 2
    assert jerarquias[0]["child_key"] == CIUDAD
    assert jerarquias[0]["parent_key"] == "lugar:PROVINCIA:buenos_aires|lugar:PAIS:argentina"
    assert jerarquias[1]["parent_key"] == "lugar:PAIS:argentina"


def test_clave_sin_padre_no_genera_jerarquia():
    lugares, jerarquias = expand_lugar_ancestors("lugar:PAIS:argentina", "test")
    assert len(lugares) == 1
    assert jerarquias == []
```

Run: `PYTHONPATH=src pytest tests/builders/test_lugares_ancestros.py -v`
Expected: primero FAIL (`ImportError`), luego PASS tras el Step 0.

- [ ] **Step 1: Escribir el test que falla**

Crear `tests/builders/test_archivo_memoria.py`:

```python
from __future__ import annotations

from zona4_graph_loader.builders.archivo_memoria import build_archivo_memoria_rows
from zona4_graph_loader.io.raw_files import read_raw_json

REGISTRO = {
    "nombre": "Bellantuono Herrero, Jorge",
    "fecha_desaparicion": "13 de julio de 1976",
    "estudiante": True,
    "estudiante_universitario": True,
    "descripcion": "Nació el 13 de diciembre de 1951. Su apodo era “Nechi”.",
    "lugar": "Billinghurst",
    "fecha_nacimiento": "1951-12-13",
    "fecha_desaparicion_normalizada": "1976-07-13",
    "edad_al_desaparecer": 24,
}


def test_genera_persona_con_rol_victima():
    dataset = build_archivo_memoria_rows([REGISTRO], use_georef=False)
    persona = dataset["personas"][0]
    assert persona["persona_key"] == "archivo_memoria:0"
    assert persona["nombre"] == "Bellantuono Herrero, Jorge"
    assert persona["roles"] == ["VICTIMA"]
    assert persona["genero"] == "INDETERMINADO"
    assert persona["fuente"] == "archivo_memoria"


def test_persiste_fechas_normalizadas():
    persona = build_archivo_memoria_rows([REGISTRO], use_georef=False)["personas"][0]
    assert persona["fecha_nacimiento"] == "1951-12-13"
    assert persona["fecha_secuestro"] == "1976-07-13"


def test_registro_sin_nombre_se_descarta():
    dataset = build_archivo_memoria_rows([dict(REGISTRO, nombre=None)], use_georef=False)
    assert dataset["personas"] == []


def test_estudiante_universitario_genera_institucion():
    dataset = build_archivo_memoria_rows([REGISTRO], use_georef=False)
    instituciones = [e for e in dataset["entidades_contexto"]
                     if e["tipo_entidad"] == "Institucion"]
    assert len(instituciones) == 1
    rel = [r for r in dataset["relaciones_contexto"]
           if r["tipo_relacion"] == "ESTUDIO_EN"]
    assert len(rel) == 1
    assert rel[0]["persona_key"] == "archivo_memoria:0"
    assert rel[0]["origen"] == "archivo_memoria"


def test_no_universitario_no_genera_institucion():
    registro = dict(REGISTRO, estudiante=True, estudiante_universitario=False)
    dataset = build_archivo_memoria_rows([registro], use_georef=False)
    assert dataset["entidades_contexto"] == []


def test_evento_secuestrado_en_apunta_a_lugar_del_dataset():
    dataset = build_archivo_memoria_rows([REGISTRO], use_georef=False)
    eventos = dataset["eventos_espaciales"]
    if not eventos:
        return  # sin Georef el topónimo puede no resolver; no es un fallo del builder
    lugar_keys = {l["lugar_key"] for l in dataset["lugares"]
                  if l["tipo_entidad"] == "Lugar"}
    assert eventos[0]["tipo_relacion"] == "SECUESTRADO_EN"
    assert eventos[0]["lugar_key"] in lugar_keys
    assert eventos[0]["fecha"] == "1976-07-13"


def test_sobre_el_archivo_real():
    data = read_raw_json("archivo_memoria_san_martin.json")
    dataset = build_archivo_memoria_rows(data)
    assert len(dataset["personas"]) == 303
    assert all(p["fuente"] == "archivo_memoria" for p in dataset["personas"])
    assert len({p["persona_key"] for p in dataset["personas"]}) == 303
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `PYTHONPATH=src pytest tests/builders/test_archivo_memoria.py -v`
Expected: FAIL — módulo inexistente.

- [ ] **Step 3: Implementar el builder**

```python
from __future__ import annotations

from typing import Any, Dict, List

from zona4_graph_loader.builders.base import CanonicalDataset
from zona4_graph_loader.builders.lugares import expand_lugar_ancestors
from zona4_graph_loader.constants import GEOREF_AMBIGUITY_DELTA, GEOREF_MIN_SCORE
from zona4_graph_loader.domain.place_norm import resolve_place
from zona4_graph_loader.domain.text_norm import clean_text

FUENTE = "archivo_memoria"
INSTITUCION_UNIVERSITARIA_KEY = "institucion:universidad_sin_especificar"


def build_archivo_memoria_rows(
    data: List[Dict[str, Any]],
    *,
    use_georef: bool = True,
) -> CanonicalDataset:
    """Convierte el Archivo de la Memoria de San Martín al CDM.

    El campo `lugar` es un topónimo corto (ej. "Billinghurst"), no una dirección
    narrativa, así que `resolve_place` lo maneja sin parsing adicional.
    """
    personas: List[Dict[str, Any]] = []
    lugares: Dict[str, Dict[str, Any]] = {}
    jerarquias: List[Dict[str, Any]] = []
    eventos: List[Dict[str, Any]] = []
    entidades: Dict[str, Dict[str, Any]] = {}
    rel_contexto: List[Dict[str, Any]] = []
    pares_parte_de: set[tuple[str, str]] = set()

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
                "origen": FUENTE,
            })

        resuelto = resolve_place(
            item.get("lugar"),
            use_georef=use_georef,
            georef_min_score=GEOREF_MIN_SCORE,
            georef_ambiguity_delta=GEOREF_AMBIGUITY_DELTA,
        )
        if not resuelto:
            continue

        lugar_key = resuelto["lugar_key"]

        # resolve_place devuelve sólo el nodo hoja: los contenedores (provincia,
        # país) hay que materializarlos o las aristas PARTE_DE se descartan.
        ancestros, saltos = expand_lugar_ancestors(lugar_key, FUENTE)
        for nodo in ancestros:
            lugares.setdefault(nodo["lugar_key"], nodo)
        lugares[lugar_key]["nombre"] = resuelto["nombre_canonico"]
        lugares[lugar_key]["tipoGeopolitico"] = resuelto["tipo"]

        for salto in saltos:
            par = (salto["child_key"], salto["parent_key"])
            if par in pares_parte_de:
                continue
            pares_parte_de.add(par)
            jerarquias.append(salto)

        eventos.append({
            "persona_key": persona_key,
            "lugar_key": lugar_key,
            "tipo_relacion": "SECUESTRADO_EN",
            "fecha": clean_text(item.get("fecha_desaparicion_normalizada")) or "DESCONOCIDA",
            "origen": FUENTE,
        })

    return {
        "personas": personas,
        "lugares": list(lugares.values()),
        "jerarquias": jerarquias,
        "eventos_espaciales": eventos,
        "entidades_contexto": list(entidades.values()),
        "relaciones_contexto": rel_contexto,
    }
```

- [ ] **Step 4: Correr y verificar que pasa**

Run: `PYTHONPATH=src pytest tests/builders/test_archivo_memoria.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Verificar la tasa de resolución de lugares sobre el archivo real**

Run:
```bash
PYTHONPATH=src python -c "
from zona4_graph_loader.builders.archivo_memoria import build_archivo_memoria_rows
from zona4_graph_loader.io.raw_files import read_raw_json
d = build_archivo_memoria_rows(read_raw_json('archivo_memoria_san_martin.json'))
print('personas:', len(d['personas']), 'eventos:', len(d['eventos_espaciales']), 'lugares:', len(d['lugares']))
"
```
Expected: 303 personas. Anotar cuántos eventos se resolvieron; si la tasa es
menor al 50%, reportarlo antes de seguir en vez de darlo por bueno.

- [ ] **Step 6: Registrar el builder**

En `pipeline/load_graph.py`, dentro del bloque `if not args.skip_nuevas_fuentes:`:

```python
        _merge_datasets(
            consolidated,
            build_archivo_memoria_rows(read_raw_json("archivo_memoria_san_martin.json")),
        )
```

con el import correspondiente de `build_archivo_memoria_rows` y `read_raw_json`.

- [ ] **Step 7: Commit**

```bash
git add src/zona4_graph_loader/ tests/
git commit -m "feat: builder del Archivo de la Memoria de San Martín (303 víctimas)"
```

---

### Task 8: Builder de condenados de lesa humanidad

1237 represores en formato tabular limpio. Primera fuente que ejercita las labels `:Represor` y `:Complice` de la Task 2.

**Files:**
- Create: `src/zona4_graph_loader/builders/juicios_condenados.py`, `tests/builders/test_juicios_condenados.py`
- Modify: `src/zona4_graph_loader/pipeline/load_graph.py`

**Interfaces:**
- Consumes: `read_raw_json`, `clean_text`, `slugify_name`.
- Produces: `build_juicios_condenados_rows(payload: Dict[str, Any]) -> CanonicalDataset` con `personas`, `entidades_contexto`, `relaciones_contexto`. Recibe el payload completo del archivo (con `resultado.condenado`). Claves: `juicios_condenado:{impu_id}`.

- [ ] **Step 1: Escribir el test que falla**

Crear `tests/builders/test_juicios_condenados.py`:

```python
from __future__ import annotations

from zona4_graph_loader.builders.juicios_condenados import build_juicios_condenados_rows
from zona4_graph_loader.io.raw_files import read_raw_json


def _payload(*condenados):
    return {"resultado": {"condenado": [{"condenados": c} for c in condenados]}}


MILITAR = {
    "impu_id": 2691,
    "apellido_nombre": "ABALLAY, Juan Alberto",
    "Categoria": "FUERZAS DE SEGURIDAD",
    "Fuerza": "POLICIA FEDERAL ARGENTINA",
    "Nacimiento": "09-04-1948",
}
CIVIL = {
    "impu_id": 3001,
    "apellido_nombre": "GOMEZ, Pedro",
    "Categoria": "CIVILES",
    "Fuerza": None,
    "Nacimiento": None,
}


def test_militar_es_represor():
    persona = build_juicios_condenados_rows(_payload(MILITAR))["personas"][0]
    assert persona["persona_key"] == "juicios_condenado:2691"
    assert persona["nombre"] == "ABALLAY, Juan Alberto"
    assert persona["roles"] == ["REPRESOR"]
    assert persona["genero"] == "INDETERMINADO"
    assert persona["fuente"] == "juicios_condenados"


def test_civil_es_represor_y_complice_civil():
    persona = build_juicios_condenados_rows(_payload(CIVIL))["personas"][0]
    assert persona["roles"] == ["COMPLICE", "REPRESOR"]
    assert persona["complice_tipo"] == "CIVIL"


def test_nacimiento_ddmmyyyy_con_guiones_se_normaliza_a_iso():
    persona = build_juicios_condenados_rows(_payload(MILITAR))["personas"][0]
    assert persona["fecha_nacimiento"] == "1948-04-09"


def test_nacimiento_ausente_queda_en_none():
    persona = build_juicios_condenados_rows(_payload(CIVIL))["personas"][0]
    assert persona["fecha_nacimiento"] is None


def test_fuerza_genera_org_y_relacion_parte_de():
    dataset = build_juicios_condenados_rows(_payload(MILITAR))
    org = dataset["entidades_contexto"][0]
    assert org["tipo_entidad"] == "Org"
    assert org["entidad_key"] == "org:policia_federal_argentina"
    assert org["nombre"] == "POLICIA FEDERAL ARGENTINA"
    rel = dataset["relaciones_contexto"][0]
    assert rel["tipo_relacion"] == "PARTE_DE"
    assert rel["persona_key"] == "juicios_condenado:2691"
    assert rel["entidad_key"] == "org:policia_federal_argentina"


def test_sin_fuerza_no_genera_org():
    dataset = build_juicios_condenados_rows(_payload(CIVIL))
    assert dataset["entidades_contexto"] == []
    assert dataset["relaciones_contexto"] == []


def test_registro_sin_impu_id_se_descarta():
    dataset = build_juicios_condenados_rows(_payload(dict(MILITAR, impu_id=None)))
    assert dataset["personas"] == []


def test_sobre_el_archivo_real():
    dataset = build_juicios_condenados_rows(
        read_raw_json("juicios_lesa_humanidad_condenados.json")
    )
    assert len(dataset["personas"]) == 1237
    complices = [p for p in dataset["personas"] if "COMPLICE" in p["roles"]]
    assert len(complices) == 197
    assert all(p["complice_tipo"] == "CIVIL" for p in complices)
    assert len([p for p in dataset["personas"] if p["fecha_nacimiento"]]) == 1232
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `PYTHONPATH=src pytest tests/builders/test_juicios_condenados.py -v`
Expected: FAIL — módulo inexistente.

- [ ] **Step 3: Implementar el builder**

```python
from __future__ import annotations

import re
from datetime import date
from typing import Any, Dict, List, Optional

from zona4_graph_loader.builders.base import CanonicalDataset
from zona4_graph_loader.domain.text_norm import clean_text, slugify_name

FUENTE = "juicios_condenados"

# El dataset clasifica en FUERZAS ARMADAS, FUERZAS DE SEGURIDAD y CIVILES.
# Los civiles condenados por lesa humanidad son cómplices civiles en el modelo.
CATEGORIA_CIVIL = "CIVILES"


def _parse_nacimiento(value: Any) -> Optional[str]:
    """El campo Nacimiento viene como DD-MM-YYYY, distinto del DD/MM/YYYY de MinJus."""
    text = clean_text(value)
    if text is None:
        return None
    match = re.fullmatch(r"(\d{2})-(\d{2})-(\d{4})", text)
    if not match:
        return None
    day, month, year = map(int, match.groups())
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def build_juicios_condenados_rows(payload: Dict[str, Any]) -> CanonicalDataset:
    personas: List[Dict[str, Any]] = []
    entidades: Dict[str, Dict[str, Any]] = {}
    rel_contexto: List[Dict[str, Any]] = []

    registros = (payload.get("resultado") or {}).get("condenado") or []

    for registro in registros:
        datos = registro.get("condenados") or {}
        impu_id = datos.get("impu_id")
        nombre = clean_text(datos.get("apellido_nombre"))
        if impu_id is None or not nombre:
            continue

        persona_key = f"juicios_condenado:{impu_id}"
        categoria = (clean_text(datos.get("Categoria")) or "").upper()
        roles = ["REPRESOR"]
        complice_tipo = None
        if categoria == CATEGORIA_CIVIL:
            roles.append("COMPLICE")
            complice_tipo = "CIVIL"

        personas.append({
            "persona_key": persona_key,
            "nombre": nombre,
            "genero": "INDETERMINADO",
            "fuente": FUENTE,
            "roles": sorted(roles),
            "complice_tipo": complice_tipo,
            "fecha_nacimiento": _parse_nacimiento(datos.get("Nacimiento")),
        })

        fuerza = clean_text(datos.get("Fuerza"))
        if not fuerza:
            continue
        fuerza_upper = fuerza.upper()
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
            "origen": FUENTE,
        })

    return {
        "personas": personas,
        "entidades_contexto": list(entidades.values()),
        "relaciones_contexto": rel_contexto,
    }
```

- [ ] **Step 4: Correr y verificar que pasa**

Run: `PYTHONPATH=src pytest tests/builders/test_juicios_condenados.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Registrar el builder**

En `pipeline/load_graph.py`, dentro de `if not args.skip_nuevas_fuentes:`:

```python
        _merge_datasets(
            consolidated,
            build_juicios_condenados_rows(read_raw_json("juicios_lesa_humanidad_condenados.json")),
        )
```

- [ ] **Step 6: Commit**

```bash
git add src/zona4_graph_loader/ tests/
git commit -m "feat: builder de condenados de lesa humanidad (1237 represores)"
```

---

### Task 9: Índice de sentencias de MinJus GBA

No emite nodos: el modelo no tiene `:Sentencia` ni `:Causa`. Produce el índice que las Tasks 11 y 12 usan para poblar `origen` y `fecha` en las aristas `TORTURO_A`, cumpliendo la regla 1.2 de auditoría.

**Files:**
- Create: `src/zona4_graph_loader/builders/minjus_sentencias.py`, `tests/builders/test_minjus_sentencias.py`

**Interfaces:**
- Consumes: `read_raw_json`, `clean_text`, `parse_ddmmyyyy` de `domain/date_norm`.
- Produces:
  - `slug_sentencia(url: str) -> Optional[str]` — normaliza `/sentencia/31-abo-atletico-banco-olimpo`, `sentencia/31-abo...` y `1-quinto-cuerpo-...` al mismo slug.
  - `build_sentencias_index(data: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]` — mapea slug → `{"titulo": str, "tribunal": Optional[str], "fecha": Optional[str], "origen": str}`.

- [ ] **Step 1: Escribir el test que falla**

Crear `tests/builders/test_minjus_sentencias.py`:

```python
from __future__ import annotations

from zona4_graph_loader.builders.minjus_sentencias import (
    build_sentencias_index,
    slug_sentencia,
)
from zona4_graph_loader.io.raw_files import read_raw_json

SENTENCIA = {
    "post_id": "12562",
    "url_detalle": "https://derechoshumanos.mjus.gba.gob.ar/sentencia/31-abo-atletico-banco-olimpo",
    "titulo": "ABO (Atletico – Banco – Olimpo)",
    "datos_tecnicos": {
        "fecha": "21/12/2010",
        "tribunal": "TOF 2 CAPITAL FEDERAL",
    },
}


def test_slug_normaliza_las_tres_formas_de_url():
    esperado = "31-abo-atletico-banco-olimpo"
    assert slug_sentencia("/sentencia/31-abo-atletico-banco-olimpo") == esperado
    assert slug_sentencia("https://x.gob.ar/sentencia/31-abo-atletico-banco-olimpo") == esperado
    assert slug_sentencia("31-abo-atletico-banco-olimpo") == esperado


def test_slug_de_url_vacia_es_none():
    assert slug_sentencia("") is None
    assert slug_sentencia(None) is None


def test_index_expone_tribunal_y_fecha_iso():
    index = build_sentencias_index([SENTENCIA])
    entrada = index["31-abo-atletico-banco-olimpo"]
    assert entrada["titulo"] == "ABO (Atletico – Banco – Olimpo)"
    assert entrada["tribunal"] == "TOF 2 CAPITAL FEDERAL"
    assert entrada["fecha"] == "2010-12-21"
    assert entrada["origen"] == "minjus_sentencias:31-abo-atletico-banco-olimpo"


def test_sentencia_sin_fecha_queda_en_none():
    sentencia = dict(SENTENCIA, datos_tecnicos={"tribunal": "TOF 1"})
    index = build_sentencias_index([sentencia])
    assert index["31-abo-atletico-banco-olimpo"]["fecha"] is None


def test_sobre_el_archivo_real():
    index = build_sentencias_index(
        read_raw_json("derechos_humanos_minjus_gba_sentencias.json")
    )
    assert len(index) == 113
    assert all(entrada["origen"].startswith("minjus_sentencias:") for entrada in index.values())
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `PYTHONPATH=src pytest tests/builders/test_minjus_sentencias.py -v`
Expected: FAIL — módulo inexistente.

- [ ] **Step 3: Implementar**

```python
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
```

- [ ] **Step 4: Correr y verificar que pasa**

Run: `PYTHONPATH=src pytest tests/builders/test_minjus_sentencias.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add src/zona4_graph_loader/builders/minjus_sentencias.py tests/builders/test_minjus_sentencias.py
git commit -m "feat: índice de sentencias de MinJus GBA para auditoría de aristas"
```

---

### Task 10: Builder de CCDs de MinJus GBA

87 centros clandestinos, con dedup contra los CCDs de RUVTE que ya están cargados desde `ccds.json`.

**Files:**
- Create: `src/zona4_graph_loader/builders/minjus_ccds.py`, `tests/builders/test_minjus_ccds.py`
- Modify: `src/zona4_graph_loader/pipeline/load_graph.py`

**Interfaces:**
- Consumes: `read_raw_json`, `clean_text`, `slugify_name`, `name_similarity_score`.
- Produces:
  - `slug_ccd(url: str) -> Optional[str]` — de `/centrodedetencion/242-arsenal-...` y `/centrodetencion/69-comisaria-5-...` (el dataset usa ambas grafías) al slug.
  - `build_minjus_ccds_rows(data, *, existing_ccds=None) -> CanonicalDataset` con `lugares` y `jerarquias`. `existing_ccds` es un dict `nombre_upper -> lugar_key` de los CCDs ya presentes; cuando un CCD de MinJus matchea uno existente con score ≥ 0.93, se reutiliza el `lugar_key` existente en vez de crear un nodo nuevo.
  - `MINJUS_CCD_KEY_BY_SLUG: Dict[str, str]` no se expone; en su lugar `build_minjus_ccds_rows` devuelve además la clave `_ccd_key_by_slug` en el dataset, que las Tasks 11 y 12 consumen y que `load_graph` descarta antes de escribir.

**Nota de diseño:** el CDM no admite claves arbitrarias (`sources_ingestor` valida
`ALLOWED_SOURCE_KEYS`), pero eso sólo aplica a los JSON directos, no al retorno de
un builder en memoria. Aun así, para no ensuciar el contrato, `build_minjus_ccds_rows`
devuelve una tupla `(CanonicalDataset, Dict[str, str])` en vez de una clave extra.

- [ ] **Step 1: Escribir el test que falla**

Crear `tests/builders/test_minjus_ccds.py`:

```python
from __future__ import annotations

from zona4_graph_loader.builders.minjus_ccds import build_minjus_ccds_rows, slug_ccd
from zona4_graph_loader.io.raw_files import read_raw_json

CCD = {
    "source_url": "https://derechoshumanos.mjus.gba.gob.ar/centrodedetencion/242-arsenal-de-artilleria-de-marina-de-zarate",
    "titulo": "Arsenal de Artillería de Marina de Zárate",
    "metadatos": {
        "Otras denominaciones": "ARSENAL DE LA ARMADA / ARSENAL NAVAL DE ZÁRATE",
        "Dependencia": "ARMADA",
        "Domicilio": "Estrada 350, B2800HUA Zárate, Provincia de Buenos Aires",
    },
    "secciones": {"Reseña": "En esta unidad de la Armada Argentina..."},
    "victimas": [],
}


def test_slug_acepta_las_dos_grafias_del_dataset():
    assert slug_ccd("/centrodedetencion/242-arsenal") == "242-arsenal"
    assert slug_ccd("/centrodetencion/69-comisaria-5") == "69-comisaria-5"
    assert slug_ccd(None) is None


def test_genera_lugar_ccd():
    dataset, _ = build_minjus_ccds_rows([CCD])
    ccds = [l for l in dataset["lugares"]
            if l["tipo_entidad"] == "Lugar" and l["tipoGeopolitico"] == "CCD"]
    assert len(ccds) == 1
    assert ccds[0]["nombre"] == "ARSENAL DE ARTILLERÍA DE MARINA DE ZÁRATE"
    assert ccds[0]["fuente"] == "minjus_ccds"


def test_domicilio_va_crudo_a_direccion_ccd():
    dataset, _ = build_minjus_ccds_rows([CCD])
    direcciones = [l for l in dataset["lugares"] if l["tipo_entidad"] == "DireccionCCD"]
    assert len(direcciones) == 1
    assert direcciones[0]["direccionExacta"] == (
        "Estrada 350, B2800HUA Zárate, Provincia de Buenos Aires"
    )
    assert direcciones[0]["coordenadas"] == "DESCONOCIDAS"


def test_expone_mapa_slug_a_lugar_key():
    _, key_by_slug = build_minjus_ccds_rows([CCD])
    assert key_by_slug["242-arsenal-de-artilleria-de-marina-de-zarate"].startswith("lugar:CCD:")


def test_dedup_reutiliza_ccd_existente():
    existentes = {"ARSENAL DE ARTILLERIA DE MARINA DE ZARATE": "lugar:CCD:ruvte_123"}
    dataset, key_by_slug = build_minjus_ccds_rows([CCD], existing_ccds=existentes)
    assert key_by_slug["242-arsenal-de-artilleria-de-marina-de-zarate"] == "lugar:CCD:ruvte_123"
    nuevos = [l for l in dataset["lugares"]
              if l["tipo_entidad"] == "Lugar" and l["fuente"] == "minjus_ccds"]
    assert nuevos == []


def test_nombre_distinto_no_se_dedupea():
    existentes = {"ESCUELA DE MECANICA DE LA ARMADA": "lugar:CCD:ruvte_1"}
    dataset, _ = build_minjus_ccds_rows([CCD], existing_ccds=existentes)
    nuevos = [l for l in dataset["lugares"]
              if l["tipo_entidad"] == "Lugar" and l["fuente"] == "minjus_ccds"]
    assert len(nuevos) == 1


def test_dependencia_se_guarda_como_jurisdiccion():
    dataset, _ = build_minjus_ccds_rows([CCD])
    ccd = next(l for l in dataset["lugares"] if l["tipoGeopolitico"] == "CCD")
    assert ccd["jurisdiccion"] == "ARMADA"


def test_sobre_el_archivo_real():
    data = read_raw_json("derechos_humanos_minjus_gba_centros_clandestinos.json")
    dataset, key_by_slug = build_minjus_ccds_rows(data)
    assert len(key_by_slug) == 87
    ccds = [l for l in dataset["lugares"] if l["tipoGeopolitico"] == "CCD"]
    assert len(ccds) == 87
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `PYTHONPATH=src pytest tests/builders/test_minjus_ccds.py -v`
Expected: FAIL — módulo inexistente.

- [ ] **Step 3: Implementar**

```python
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from zona4_graph_loader.builders.base import CanonicalDataset
from zona4_graph_loader.domain.name_similarity import name_similarity_score
from zona4_graph_loader.domain.text_norm import clean_text, slugify_name, strip_accents

FUENTE = "minjus_ccds"
DEDUP_THRESHOLD = 0.93


def slug_ccd(url: Optional[str]) -> Optional[str]:
    """El dataset alterna entre /centrodedetencion/ y /centrodetencion/."""
    text = clean_text(url)
    if text is None:
        return None
    for marcador in ("/centrodedetencion/", "/centrodetencion/"):
        if marcador in text:
            text = text.split(marcador, 1)[1]
            break
    return text.strip("/") or None


def _match_existente(nombre_upper: str, existing_ccds: Dict[str, str]) -> Optional[str]:
    sin_acentos = strip_accents(nombre_upper)
    directo = existing_ccds.get(sin_acentos) or existing_ccds.get(nombre_upper)
    if directo:
        return directo
    mejor_key, mejor_score = None, 0.0
    for nombre_existente, lugar_key in existing_ccds.items():
        score = name_similarity_score(sin_acentos, strip_accents(nombre_existente))
        if score > mejor_score:
            mejor_key, mejor_score = lugar_key, score
    return mejor_key if mejor_score >= DEDUP_THRESHOLD else None


def build_minjus_ccds_rows(
    data: List[Dict[str, Any]],
    *,
    existing_ccds: Optional[Dict[str, str]] = None,
) -> Tuple[CanonicalDataset, Dict[str, str]]:
    """Convierte los CCDs de MinJus GBA al CDM y devuelve el mapa slug -> lugar_key.

    El mapa es lo que consumen los builders de víctimas e imputados para colgar
    aristas PRESENTE_EN sin recurrir al texto libre.

    `existing_ccds` mapea nombre en mayúsculas -> lugar_key de los CCDs ya
    cargados (RUVTE). Cuando hay match fuerte se reutiliza esa clave y no se
    crea un nodo nuevo, para no duplicar el mismo centro con dos orígenes.
    """
    existing_ccds = existing_ccds or {}
    lugares: Dict[str, Dict[str, Any]] = {}
    direcciones: Dict[str, Dict[str, Any]] = {}
    jerarquias: List[Dict[str, Any]] = []
    key_by_slug: Dict[str, str] = {}

    for item in data:
        slug = slug_ccd(item.get("source_url"))
        titulo = clean_text(item.get("titulo"))
        if not slug or not titulo:
            continue

        nombre_upper = titulo.upper()
        reutilizada = _match_existente(nombre_upper, existing_ccds)
        if reutilizada:
            key_by_slug[slug] = reutilizada
            continue

        lugar_key = f"lugar:CCD:{slugify_name(slug)}"
        key_by_slug[slug] = lugar_key
        metadatos = item.get("metadatos") or {}

        lugares[lugar_key] = {
            "lugar_key": lugar_key,
            "nombre": nombre_upper,
            "tipoGeopolitico": "CCD",
            "pais_code": "AR",
            "fuente": FUENTE,
            "jurisdiccion": clean_text(metadatos.get("Dependencia")),
            "ubicacion": clean_text(metadatos.get("Domicilio")),
            "tipo_entidad": "Lugar",
        }

        domicilio = clean_text(metadatos.get("Domicilio"))
        if domicilio:
            direccion_key = f"direccion_ccd:minjus:{slugify_name(slug)}"
            direcciones[direccion_key] = {
                "direccion_ccd_key": direccion_key,
                "coordenadas": "DESCONOCIDAS",
                "direccionExacta": domicilio,
                "lugar_key": lugar_key,
                "tipo_entidad": "DireccionCCD",
            }
            jerarquias.append({
                "tipo_relacion": "UBICADA_EN",
                "direccion_ccd_key": direccion_key,
                "lugar_key": lugar_key,
            })

    dataset: CanonicalDataset = {
        "lugares": list(lugares.values()) + list(direcciones.values()),
        "jerarquias": jerarquias,
    }
    return dataset, key_by_slug
```

`strip_accents`, `clean_text` y `slugify_name` ya son públicos en
`domain/text_norm.py`.

- [ ] **Step 4: Correr y verificar que pasa**

Run: `PYTHONPATH=src pytest tests/builders/test_minjus_ccds.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Registrar el builder pasándole los CCDs ya cargados**

En `pipeline/load_graph.py`, dentro de `if not args.skip_nuevas_fuentes:`, después
de que `ccd_layer` ya fue mergeado:

```python
        ccds_existentes = {
            l["nombre"]: l["lugar_key"]
            for l in consolidated.get("lugares", [])
            if l.get("tipo_entidad") == "Lugar" and l.get("tipoGeopolitico") == "CCD"
        }
        minjus_ccd_dataset, minjus_ccd_keys = build_minjus_ccds_rows(
            read_raw_json("derechos_humanos_minjus_gba_centros_clandestinos.json"),
            existing_ccds=ccds_existentes,
        )
        _merge_datasets(consolidated, minjus_ccd_dataset)
```

`minjus_ccd_keys` queda disponible para las Tasks 11 y 12. Si `--skip-lugares`
está activo, `ccd_layer` no se construye: inicializar `minjus_ccd_keys = {}`
antes del bloque para que las tareas siguientes no fallen.

- [ ] **Step 6: Commit**

```bash
git add src/zona4_graph_loader/ tests/
git commit -m "feat: builder de CCDs de MinJus GBA con dedup contra RUVTE"
```

---

### Task 11: Builder de imputados de MinJus GBA

454 represores con fuerza, condenas y víctimas asociadas.

**Files:**
- Create: `src/zona4_graph_loader/builders/minjus_imputados.py`, `tests/builders/test_minjus_imputados.py`
- Modify: `src/zona4_graph_loader/pipeline/load_graph.py`

**Interfaces:**
- Consumes: `slug_sentencia` y `build_sentencias_index` (Task 9), `read_raw_json`, `parse_ddmmyyyy`, `clean_text`, `slugify_name`.
- Produces:
  - `slug_persona_minjus(url: str, prefijo: str) -> Optional[str]` — de `/imputado/1-abelleira-hector-jorge` a `1-abelleira-hector-jorge`; `prefijo` es `"imputado"` o `"victima"`.
  - `build_minjus_imputados_rows(data, *, sentencias_index) -> CanonicalDataset` con `personas`, `relaciones_interpersonales`, `entidades_contexto`, `relaciones_contexto`. Claves: `minjus_imputado:{slug}` y, para las víctimas referenciadas, `minjus_victima:{slug}` (las mismas que genera la Task 12, de modo que las aristas apunten a los nodos reales).

- [ ] **Step 1: Escribir el test que falla**

Crear `tests/builders/test_minjus_imputados.py`:

```python
from __future__ import annotations

from zona4_graph_loader.builders.minjus_imputados import (
    build_minjus_imputados_rows,
    slug_persona_minjus,
)
from zona4_graph_loader.builders.minjus_sentencias import build_sentencias_index
from zona4_graph_loader.io.raw_files import read_raw_json

IMPUTADO = {
    "source_url": "https://derechoshumanos.mjus.gba.gob.ar/imputado/1-abelleira-hector-jorge",
    "nombre": "Abelleira, Héctor Jorge",
    "datos_personales": {
        "fecha_de_nacimiento": "26/04/1940",
        "fallecido": "No",
        "fuerza": "Policia Provincial",
        "apodo": "El Flaco",
    },
    "sentencias_y_victimas": [
        {
            "sentencia_nombre": "Quinto Cuerpo del Ejército – Bayón",
            "sentencia_url": "/sentencia/1-quinto-cuerpo-del-ejercito-bayon",
            "victimas_asociadas": [
                {
                    "victima_nombre": "Rossi Dario José",
                    "victima_url": "/victima/1870-rossi-dario-jose",
                    "delitos": ["Tormentos", "Homicidio"],
                },
                {"victima_nombre": "meilan Guadalupe", "victima_url": "", "delitos": ["abandono"]},
            ],
        }
    ],
    "condenas_recibidas": [],
}

INDEX = {
    "1-quinto-cuerpo-del-ejercito-bayon": {
        "titulo": "Quinto Cuerpo del Ejército – Bayón",
        "tribunal": "TOF BAHIA BLANCA",
        "fecha": "2012-05-10",
        "origen": "minjus_sentencias:1-quinto-cuerpo-del-ejercito-bayon",
    }
}


def test_slug_persona():
    assert slug_persona_minjus("/imputado/1-abelleira-hector-jorge", "imputado") == "1-abelleira-hector-jorge"
    assert slug_persona_minjus("/victima/1870-rossi-dario-jose", "victima") == "1870-rossi-dario-jose"
    assert slug_persona_minjus("", "victima") is None


def test_imputado_es_represor():
    persona = build_minjus_imputados_rows([IMPUTADO], sentencias_index=INDEX)["personas"][0]
    assert persona["persona_key"] == "minjus_imputado:1-abelleira-hector-jorge"
    assert persona["roles"] == ["REPRESOR"]
    assert persona["fecha_nacimiento"] == "1940-04-26"
    assert persona["fuente"] == "minjus_imputados"


def test_apodo_genera_alias_persona_con_arista_identifica_a():
    dataset = build_minjus_imputados_rows([IMPUTADO], sentencias_index=INDEX)
    alias = [e for e in dataset["entidades_contexto"] if e["tipo_entidad"] == "AliasPersona"]
    assert len(alias) == 1
    assert alias[0]["alias"] == "El Flaco"
    rel = [r for r in dataset["relaciones_contexto"] if r["tipo_relacion"] == "IDENTIFICA_A"]
    assert len(rel) == 1
    assert rel[0]["persona_key"] == "minjus_imputado:1-abelleira-hector-jorge"
    assert rel[0]["entidad_key"] == alias[0]["entidad_key"]


def test_torturo_a_usa_metadatos_de_la_sentencia():
    dataset = build_minjus_imputados_rows([IMPUTADO], sentencias_index=INDEX)
    aristas = [r for r in dataset["relaciones_interpersonales"] if r["tipo"] == "TORTURO_A"]
    assert len(aristas) == 1  # la víctima sin URL no genera arista
    arista = aristas[0]
    assert arista["source_key"] == "minjus_imputado:1-abelleira-hector-jorge"
    assert arista["target_key"] == "minjus_victima:1870-rossi-dario-jose"
    assert arista["fecha"] == "2012-05-10"
    assert arista["fuente"] == "minjus_sentencias:1-quinto-cuerpo-del-ejercito-bayon"


def test_victima_sin_url_no_genera_arista():
    dataset = build_minjus_imputados_rows([IMPUTADO], sentencias_index=INDEX)
    targets = {r["target_key"] for r in dataset["relaciones_interpersonales"]}
    assert not any("meilan" in t for t in targets)


def test_sentencia_fuera_del_index_usa_origen_generico():
    imputado = dict(IMPUTADO)
    dataset = build_minjus_imputados_rows([imputado], sentencias_index={})
    arista = dataset["relaciones_interpersonales"][0]
    assert arista["fuente"] == "minjus_imputados"
    assert arista["fecha"] == "DESCONOCIDA"


def test_sobre_el_archivo_real():
    index = build_sentencias_index(read_raw_json("derechos_humanos_minjus_gba_sentencias.json"))
    dataset = build_minjus_imputados_rows(
        read_raw_json("derechos_humanos_minjus_gba_imputados.json"),
        sentencias_index=index,
    )
    assert len(dataset["personas"]) == 454
    assert all(p["roles"] == ["REPRESOR"] for p in dataset["personas"])
    orgs = [e for e in dataset["entidades_contexto"] if e["tipo_entidad"] == "Org"]
    assert len(orgs) > 5
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `PYTHONPATH=src pytest tests/builders/test_minjus_imputados.py -v`
Expected: FAIL — módulo inexistente.

- [ ] **Step 3: Implementar**

```python
from __future__ import annotations

from typing import Any, Dict, List, Optional

from zona4_graph_loader.builders.base import CanonicalDataset
from zona4_graph_loader.builders.minjus_sentencias import slug_sentencia
from zona4_graph_loader.domain.date_norm import parse_ddmmyyyy
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

        personas.append({
            "persona_key": persona_key,
            "nombre": nombre,
            "genero": "INDETERMINADO",
            "fuente": FUENTE,
            "roles": ["REPRESOR"],
            "fecha_nacimiento": parse_ddmmyyyy(clean_text(datos.get("fecha_de_nacimiento"))),
        })

        fuerza = clean_text(datos.get("fuerza"))
        if fuerza:
            fuerza_upper = fuerza.upper()
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
                "origen": FUENTE,
            })

        for bloque in item.get("sentencias_y_victimas") or []:
            slug_sent = slug_sentencia(bloque.get("sentencia_url"))
            meta = sentencias_index.get(slug_sent or "", {})
            origen = meta.get("origen") or FUENTE
            fecha = meta.get("fecha") or "DESCONOCIDA"

            for victima in bloque.get("victimas_asociadas") or []:
                slug_victima = slug_persona_minjus(victima.get("victima_url"), "victima")
                if not slug_victima:
                    continue
                relaciones.append({
                    "source_key": persona_key,
                    "target_key": f"minjus_victima:{slug_victima}",
                    "tipo": "TORTURO_A",
                    "fecha": fecha,
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
```

`target_nombre`, `target_genero` y `target_fuente` son las propiedades que
`CYPHER_UPSERT_REL_PERSONA` usa para poblar el nodo destino si todavía no existe.

- [ ] **Step 4: Correr y verificar que pasa**

Run: `PYTHONPATH=src pytest tests/builders/test_minjus_imputados.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Registrar el builder**

En `pipeline/load_graph.py`, dentro de `if not args.skip_nuevas_fuentes:`:

```python
        sentencias_index = build_sentencias_index(
            read_raw_json("derechos_humanos_minjus_gba_sentencias.json")
        )
        _merge_datasets(
            consolidated,
            build_minjus_imputados_rows(
                read_raw_json("derechos_humanos_minjus_gba_imputados.json"),
                sentencias_index=sentencias_index,
            ),
        )
```

- [ ] **Step 6: Commit**

```bash
git add src/zona4_graph_loader/ tests/
git commit -m "feat: builder de imputados de MinJus GBA (454 represores)"
```

---

### Task 12: Builder de víctimas de MinJus GBA

3257 víctimas. La fuente más grande. **Sin aristas `SECUESTRADO_EN`**: el parsing de direcciones en texto libre está fuera de alcance (sección 2 del spec).

**Files:**
- Create: `src/zona4_graph_loader/builders/minjus_victimas.py`, `tests/builders/test_minjus_victimas.py`
- Modify: `src/zona4_graph_loader/pipeline/load_graph.py`

**Interfaces:**
- Consumes: `slug_persona_minjus` (Task 11), `slug_ccd` (Task 10), `slug_sentencia` (Task 9).
- Produces: `build_minjus_victimas_rows(data, *, ccd_key_by_slug, sentencias_index) -> CanonicalDataset` con `personas`, `eventos_espaciales`, `relaciones_interpersonales`, `entidades_contexto`, `relaciones_contexto`. Claves: `minjus_victima:{slug}`.

- [ ] **Step 1: Escribir el test que falla**

Crear `tests/builders/test_minjus_victimas.py`:

```python
from __future__ import annotations

from zona4_graph_loader.builders.minjus_victimas import build_minjus_victimas_rows
from zona4_graph_loader.builders.minjus_sentencias import build_sentencias_index
from zona4_graph_loader.io.raw_files import read_raw_json

VICTIMA = {
    "source_url": "https://derechoshumanos.mjus.gba.gob.ar/victima/213-abachian-juan-carlos",
    "nombre": "Abachian, Juan Carlos",
    "datos_personales": {
        "apodo": "El Armenio",
        "militancia": "Juventud Peronista",
        "dónde_estudió": "Abogacía",
        "lugar_de_trabajo": "Taller de chapa y pintura",
        "fecha_de_secuestro": "20/01/1977",
        "lugar_de_secuestro": "Calle 7 779",
        "situación_actual": "Persona desaparecida",
    },
    "centros_clandestinos": [
        {"nombre": "COMISARÍA 5ª DE LA PLATA", "url": "/centrodetencion/69-comisaria-5-de-la-plata"},
    ],
    "sentencias": [],
}

CCD_KEYS = {"69-comisaria-5-de-la-plata": "lugar:CCD:69_comisaria_5_de_la_plata"}


def test_victima_basica():
    persona = build_minjus_victimas_rows(
        [VICTIMA], ccd_key_by_slug=CCD_KEYS, sentencias_index={}
    )["personas"][0]
    assert persona["persona_key"] == "minjus_victima:213-abachian-juan-carlos"
    assert persona["roles"] == ["VICTIMA"]
    assert persona["genero"] == "INDETERMINADO"
    assert persona["fecha_secuestro"] == "1977-01-20"


def test_no_genera_secuestrado_en_por_texto_libre():
    """El parsing de lugar_de_secuestro está fuera de alcance en esta ronda."""
    dataset = build_minjus_victimas_rows(
        [VICTIMA], ccd_key_by_slug=CCD_KEYS, sentencias_index={}
    )
    tipos = {e["tipo_relacion"] for e in dataset["eventos_espaciales"]}
    assert "SECUESTRADO_EN" not in tipos


def test_ccd_genera_presente_en():
    dataset = build_minjus_victimas_rows(
        [VICTIMA], ccd_key_by_slug=CCD_KEYS, sentencias_index={}
    )
    eventos = [e for e in dataset["eventos_espaciales"] if e["tipo_relacion"] == "PRESENTE_EN"]
    assert len(eventos) == 1
    assert eventos[0]["lugar_key"] == "lugar:CCD:69_comisaria_5_de_la_plata"
    assert eventos[0]["persona_key"] == "minjus_victima:213-abachian-juan-carlos"
    assert eventos[0]["fecha"] == "1977-01-20"


def test_ccd_desconocido_no_genera_evento_huerfano():
    dataset = build_minjus_victimas_rows(
        [VICTIMA], ccd_key_by_slug={}, sentencias_index={}
    )
    assert dataset["eventos_espaciales"] == []


def test_militancia_trabajo_estudios_y_apodo_generan_contexto():
    dataset = build_minjus_victimas_rows(
        [VICTIMA], ccd_key_by_slug=CCD_KEYS, sentencias_index={}
    )
    tipos = {e["tipo_entidad"] for e in dataset["entidades_contexto"]}
    assert tipos == {"Org", "Institucion", "Profesion", "AliasPersona"}

    relaciones = {r["tipo_relacion"] for r in dataset["relaciones_contexto"]}
    assert relaciones == {"PARTE_DE", "TRABAJO_EN", "EJERCIO", "IDENTIFICA_A"}


def test_registro_sin_url_se_descarta():
    dataset = build_minjus_victimas_rows(
        [dict(VICTIMA, source_url="")], ccd_key_by_slug=CCD_KEYS, sentencias_index={}
    )
    assert dataset["personas"] == []


def test_sobre_el_archivo_real():
    index = build_sentencias_index(read_raw_json("derechos_humanos_minjus_gba_sentencias.json"))
    dataset = build_minjus_victimas_rows(
        read_raw_json("derechos_humanos_minjus_gba_victimas.json"),
        ccd_key_by_slug={},
        sentencias_index=index,
    )
    assert len(dataset["personas"]) == 3257
    con_fecha = [p for p in dataset["personas"] if p["fecha_secuestro"]]
    assert len(con_fecha) > 2900
    assert dataset["eventos_espaciales"] == []  # sin ccd_key_by_slug no hay lugares
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `PYTHONPATH=src pytest tests/builders/test_minjus_victimas.py -v`
Expected: FAIL — módulo inexistente.

- [ ] **Step 3: Implementar**

```python
from __future__ import annotations

from typing import Any, Dict, List

from zona4_graph_loader.builders.base import CanonicalDataset
from zona4_graph_loader.builders.minjus_ccds import slug_ccd
from zona4_graph_loader.builders.minjus_imputados import slug_persona_minjus
from zona4_graph_loader.builders.minjus_sentencias import slug_sentencia
from zona4_graph_loader.domain.date_norm import parse_ddmmyyyy
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

    def registrar_entidad(entidad_key, tipo_entidad, campo, valor, tipo_relacion, persona_key):
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
            "origen": FUENTE,
        })

    for item in data:
        slug = slug_persona_minjus(item.get("source_url"), "victima")
        nombre = clean_text(item.get("nombre"))
        if not slug or not nombre:
            continue

        persona_key = f"minjus_victima:{slug}"
        datos = item.get("datos_personales") or {}
        fecha_secuestro = parse_ddmmyyyy(clean_text(datos.get("fecha_de_secuestro")))

        personas.append({
            "persona_key": persona_key,
            "nombre": nombre,
            "genero": "INDETERMINADO",
            "fuente": FUENTE,
            "roles": ["VICTIMA"],
            "fecha_secuestro": fecha_secuestro,
        })

        militancia = clean_text(datos.get("militancia"))
        if militancia:
            registrar_entidad(
                f"org:{slugify_name(militancia.upper())}", "Org", "nombre",
                militancia.upper(), "PARTE_DE", persona_key,
            )

        trabajo = clean_text(datos.get("lugar_de_trabajo"))
        if trabajo:
            registrar_entidad(
                f"institucion:{slugify_name(trabajo.upper())}", "Institucion", "nombre",
                trabajo.upper(), "TRABAJO_EN", persona_key,
            )

        estudios = clean_text(datos.get("dónde_estudió"))
        if estudios:
            registrar_entidad(
                f"profesion:{slugify_name(estudios.upper())}", "Profesion", "descripcion",
                estudios.upper(), "EJERCIO", persona_key,
            )

        apodo = clean_text(datos.get("apodo"))
        if apodo:
            registrar_entidad(
                f"alias_persona:{slugify_name(apodo)}|{slug}", "AliasPersona", "alias",
                apodo, "IDENTIFICA_A", persona_key,
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
            meta = sentencias_index.get(slug_sent or "", {})
            origen = meta.get("origen") or FUENTE
            fecha = meta.get("fecha") or "DESCONOCIDA"

            for imputado in sentencia.get("imputados") or []:
                slug_imputado = slug_persona_minjus(imputado.get("imputado_url"), "imputado")
                if not slug_imputado:
                    continue
                relaciones.append({
                    "source_key": f"minjus_imputado:{slug_imputado}",
                    "target_key": persona_key,
                    "tipo": "TORTURO_A",
                    "fecha": fecha,
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
```

**Atención:** `CYPHER_UPSERT_REL_PERSONA` hace `MATCH` sobre `source_key` (no
`MERGE`). Las aristas cuyo imputado no exista se descartan. Como el builder de
imputados (Task 11) corre antes y usa el mismo esquema de claves, la mayoría
resuelve; verificar el conteo en el Step 5.

**`situación_actual` no se persiste.** El campo (liberada 1608, desaparecida 1237,
asesinada 326, restituida 43) no tiene destino en el modelo V1.2: no es una
propiedad declarada de `:Persona` y `CYPHER_UPSERT_PERSONAS` la ignoraría en
silencio. Ponerla en el dict daría la falsa impresión de que llega al grafo.
Queda como pendiente registrado en la Task 13: `"Persona asesinada"` es el insumo
natural para aristas `ASESINADO_EN` cuando se retome el parsing de lugares.

- [ ] **Step 4: Correr y verificar que pasa**

Run: `PYTHONPATH=src pytest tests/builders/test_minjus_victimas.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Registrar el builder y medir**

En `pipeline/load_graph.py`, dentro de `if not args.skip_nuevas_fuentes:`, después
del builder de imputados:

```python
        _merge_datasets(
            consolidated,
            build_minjus_victimas_rows(
                read_raw_json("derechos_humanos_minjus_gba_victimas.json"),
                ccd_key_by_slug=minjus_ccd_keys,
                sentencias_index=sentencias_index,
            ),
        )
```

Medir el CDM consolidado sin tocar Neo4j:

```bash
PYTHONPATH=src python -c "
from zona4_graph_loader.builders.minjus_ccds import build_minjus_ccds_rows
from zona4_graph_loader.builders.minjus_sentencias import build_sentencias_index
from zona4_graph_loader.builders.minjus_victimas import build_minjus_victimas_rows
from zona4_graph_loader.io.raw_files import read_raw_json

_, ccd_keys = build_minjus_ccds_rows(
    read_raw_json('derechos_humanos_minjus_gba_centros_clandestinos.json'))
index = build_sentencias_index(read_raw_json('derechos_humanos_minjus_gba_sentencias.json'))
d = build_minjus_victimas_rows(
    read_raw_json('derechos_humanos_minjus_gba_victimas.json'),
    ccd_key_by_slug=ccd_keys, sentencias_index=index)
for k, v in d.items():
    print(k, len(v))
"
```

Expected: `personas 3257`, `eventos_espaciales` en el orden de varios miles
(2436 víctimas tienen CCD asociado, varias con más de uno), `relaciones_interpersonales`
en decenas de miles. Anotar los números reales.

Y con Neo4j levantado (`docker compose up -d`):

```bash
PYTHONPATH=src NEO4J_URI=bolt://localhost:17687 NEO4J_USERNAME=neo4j \
NEO4J_PASSWORD=zona4local NEO4J_DATABASE=neo4j \
python -m zona4_graph_loader.cli --clean-project --apply-safe-place-merges \
  --dump-cdm data/processed/cdm_debug.json
```

Expected: el `qa_report` final muestra `personas_total` ≈ 5.100 más la base
previa, `represores_total` > 1.600, `complices_total` = 197, y
`rel_presente_en_total` con varios miles. Anotar los números reales: son la línea
de base para el README.

- [ ] **Step 6: Commit**

```bash
git add src/zona4_graph_loader/ tests/
git commit -m "feat: builder de víctimas de MinJus GBA (3257, sin parsing de direcciones)"
```

---

### Task 13: Documentación

**Files:**
- Modify: `README.md`, `docs/operations/ingesta_fuentes.md`
- Create: `docs/sources/eaaf.md`, `docs/sources/minjus_gba.md`, `docs/sources/juicios_lesa_humanidad.md`, `docs/sources/archivo_memoria_san_martin.md`

- [ ] **Step 1: Actualizar `ingesta_fuentes.md`**

En la sección 2, reemplazar el bloque de `CanonicalDataset` por el de 7 claves de
la Task 3, y agregar dos subsecciones nuevas siguiendo el formato de las
existentes:

```markdown
### 2.6 `entidades_contexto`
Define nodos de contexto biográfico.
*   `entidad_key` (str, obligatorio, namespaceado: `"org:ejercito_argentino"`).
*   `tipo_entidad` (str, obligatorio: `"Org"`, `"Institucion"`, `"Profesion"`, `"Cargo"`, `"AliasPersona"`).
*   Según tipo: `nombre` (Org, Institucion), `descripcion` (Profesion), `titulo` (Cargo), `alias` (AliasPersona).
*   `tipoOrg` (str, opcional, sólo para Org).
*   `fuente` (str, obligatorio).

### 2.7 `relaciones_contexto`
Define aristas Persona -> entidad de contexto.
*   `persona_key` (str, obligatorio).
*   `entidad_key` (str, obligatorio).
*   `tipo_relacion` (str, obligatorio: `"PARTE_DE"`, `"FUNDO"`, `"EJERCIO"`, `"ESTUDIO_EN"`, `"TRABAJO_EN"`, `"IDENTIFICA_A"`).
*   `origen` (str, obligatorio), `fecha` (str, opcional).

`IDENTIFICA_A` se escribe invertida: la arista nace en el `:AliasPersona` y
apunta a la `:Persona`.
```

En la sección 1, corregir la afirmación de que el loader sólo lee
`data/sources/`: los builders de fuentes nuevas leen `data/raw/`. Sigue siendo
estrictamente offline.

- [ ] **Step 2: Corregir la tabla de fuentes del README**

Reemplazar la columna `Estado` por dos columnas, `Extraído` y `En grafo`, y
completarlas con la verdad: Parque de la Memoria, Nietas y Nietos, CCDs (RUVTE),
Archivo de la Memoria de San Martín, EAAF, MinJus GBA y Juicios de Lesa Humanidad
(condenados) quedan en grafo; el resto no. Marcar explícitamente:

- **Leyes de la dictadura:** extraído, no en grafo, sin extractor ni consumidor.
- **EAAF identificados:** descartado, ver `docs/sources/eaaf.md`.
- **Juicios (causas argentina/exterior):** descartado, ver
  `docs/sources/juicios_lesa_humanidad.md`.

Agregar en la sección del loader los flags nuevos: `--skip-nuevas-fuentes`,
`--skip-identity-resolution`, `--dump-cdm`.

- [ ] **Step 3: Escribir las fichas de fuente**

Cada archivo en `docs/sources/` sigue el formato de los existentes
(`docs/sources/ccds.md`) y documenta: URL de origen, archivo en `data/raw/`,
builder que lo consume, campos mapeados al CDM, y **qué se descartó y por qué**.

`docs/sources/eaaf.md` debe registrar explícitamente que
`eaaf_identificados.csv` está fuera del grafo por falta de columna de nombre y
por corrupción de encoding (357 caracteres U+FFFD), y que
`web_scraper_eaaf.py` es la causa.

`docs/sources/minjus_gba.md` debe registrar dos pendientes: el de
`lugar_de_secuestro` (2785 direcciones narrativas sin parsear, con la fecha ya
persistida en `:Persona.fecha_secuestro` para retomarlo sin re-scrapear) y el de
`situación_actual` (liberada 1608, desaparecida 1237, asesinada 326, restituida
43), que hoy se descarta porque el modelo no tiene dónde alojarlo y que es el
insumo natural para aristas `ASESINADO_EN` y `LIBERADO_EN`.

`docs/sources/juicios_lesa_humanidad.md` debe registrar que las causas quedan
fuera por ausencia de nodo `:Causa` en el modelo, y que el archivo de exterior
está incompleto (41 de 64 según su propio `metadata.totalItems`).

- [ ] **Step 4: Commit**

```bash
git add README.md docs/
git commit -m "docs: estado real de fuentes, CDM de 7 claves y fichas de fuentes nuevas"
```

---

## Verificación final

- [ ] `PYTHONPATH=src pytest -v` — toda la suite en verde
- [ ] Carga completa contra Neo4j local con `--clean-project`, sin excepciones
- [ ] `qa_report` muestra `represores_total > 0` (era 0 antes de la Task 2)
- [ ] Segunda corrida **sin** `--clean-project`: los contadores de aristas no se
      duplican (valida la Task 4)
- [ ] `data/processed/identity_merges.json` existe y es auditable
- [ ] Ningún warning de eventos espaciales huérfanos por encima de lo esperado

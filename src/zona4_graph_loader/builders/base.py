from __future__ import annotations

from typing import Any, Dict, List, Protocol, TypedDict

# Los cinco tipo_entidad que el pipeline sabe particionar en
# pipeline.load_graph.run_load (orgs/instituciones/profesiones/cargos/
# alias_personas). Una fila de `entidades_contexto` con un tipo_entidad fuera
# de este conjunto no cae en ninguna partición y se descarta en silencio antes
# de esta constante existir; ver el contrato en tests/test_cdm_contract.py.
TIPOS_ENTIDAD_CONTEXTO = {"Org", "Institucion", "Profesion", "Cargo", "AliasPersona"}


class CanonicalDataset(TypedDict, total=False):
    personas: List[Dict[str, Any]]
    lugares: List[Dict[str, Any]]
    relaciones_interpersonales: List[Dict[str, Any]]
    eventos_espaciales: List[Dict[str, Any]]
    jerarquias: List[Dict[str, Any]]
    entidades_contexto: List[Dict[str, Any]]
    relaciones_contexto: List[Dict[str, Any]]


class SourceBuilder(Protocol):
    """Protocol for data source adapters converting raw/processed files to CDM format."""
    def build(self) -> CanonicalDataset:
        ...

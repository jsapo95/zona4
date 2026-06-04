from __future__ import annotations

from typing import Any, Dict, List, Protocol, TypedDict


class CanonicalDataset(TypedDict, total=False):
    personas: List[Dict[str, Any]]
    lugares: List[Dict[str, Any]]
    relaciones_interpersonales: List[Dict[str, Any]]
    eventos_espaciales: List[Dict[str, Any]]
    jerarquias: List[Dict[str, Any]]


class SourceBuilder(Protocol):
    """Protocol for data source adapters converting raw/processed files to CDM format."""
    def build(self) -> CanonicalDataset:
        ...

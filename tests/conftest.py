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

from __future__ import annotations

import re
from typing import Optional

from zona4_graph_loader.constants import REL_MAP
from zona4_graph_loader.domain.text_norm import norm_space, strip_accents


def normalize_relation(value: Optional[str]) -> str:
    if not value:
        return "OTRA"
    text = strip_accents(value.lower())
    text = norm_space(re.sub(r"[\.,;:_\-]+", " ", text))
    return REL_MAP.get(text, "OTRA")

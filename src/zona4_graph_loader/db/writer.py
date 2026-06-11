from __future__ import annotations

from typing import Any, Dict, Iterable, List, LiteralString, cast

from neo4j import Query


def chunked(items: List[Dict[str, Any]], size: int) -> Iterable[List[Dict[str, Any]]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def run_batches(session, cypher: str, rows: List[Dict[str, Any]], label: str, batch_size: int) -> None:
    total = 0
    for batch in chunked(rows, batch_size):
        session.run(Query(cast(LiteralString, cypher)), rows=batch).consume()
        total += len(batch)
    print(f"{label}: {total}")

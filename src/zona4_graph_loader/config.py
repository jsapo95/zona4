from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class Config:
    uri: str
    username: str
    password: str
    database: str


def get_config() -> Config:
    uri = os.getenv("NEO4J_URI")
    username = os.getenv("NEO4J_USERNAME", "neo4j")
    password = os.getenv("NEO4J_PASSWORD")
    database = os.getenv("NEO4J_DATABASE", "neo4j")
    if not uri or not password:
        raise RuntimeError("Faltan variables de entorno: NEO4J_URI y/o NEO4J_PASSWORD")
    return Config(uri=uri, username=username, password=password, database=database)

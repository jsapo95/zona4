"""
Parser e integrador para los registros de la base de datos del Parque de la Memoria (PLACEHOLDER).

Este script está reservado para procesar los datos extraídos de:
https://basededatos.parquedelamemoria.org.ar/registros/

Salida esperada:
- data/processed/parque_de_la_memoria.json (datos estructurados y normalizados)
"""

def parse_parque_memoria_records(input_file_path: str):
    """
    Lee archivos descargados de Parque de la Memoria (ej. CSV, JSON raw o HTML)
    y genera el esquema unificado de personas y relaciones.
    """
    raise NotImplementedError(
        "El parseador e integrador de registros de Parque de la Memoria se implementará aquí "
        "en la siguiente fase de desarrollo de extractores."
    )

if __name__ == "__main__":
    print("Iniciando parseo de registros de Parque de la Memoria (Placeholder)...")

"""
Scraper de la base de datos de Nietas y Nietos de Abuelas de Plaza de Mayo (PLACEHOLDER).

Este script está reservado para la lógica de crawling y parsing de la web:
https://www.abuelas.org.ar/nietas-y-nietos/buscador

Salida esperada:
- data/raw/nietos_y_nietas_raw.json (o .html)
- data/processed/nietos_y_nietas.json (estructurado)
"""

def fetch_nietxs_data():
    """
    Realiza las peticiones HTTP al buscador de Abuelas de Plaza de Mayo,
    extrae el HTML, parsea los perfiles y genera la estructura básica.
    """
    raise NotImplementedError(
        "La lógica de scraping interactivo online/offline de Abuelas se implementará aquí "
        "en la siguiente fase de desarrollo de extractores."
    )

if __name__ == "__main__":
    print("Iniciando extracción de Nietxs (Placeholder)...")
    fetch_nietxs_data()

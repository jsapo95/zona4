"""
Cliente de la API del servicio Georref - Gobierno Nacional de Argentina (PLACEHOLDER).

Este módulo está reservado para interactuar con la API en línea de georreferenciación,
realizando consultas de reverse-geocoding y desambiguación espacial dinámica.
"""

class GeorefClient:
    def __init__(self, base_url: str = "https://apis.datos.gob.ar/georef/api"):
        self.base_url = base_url

    def resolve_place_online(self, name: str, province: str = None) -> dict:
        """
        Consulta la API de Georef para resolver un toponímico dado
        y retorna su estructura geopolítica anidada y coordenadas.
        """
        raise NotImplementedError(
            "El cliente de API en línea de Georef se implementará aquí "
            "en la siguiente fase de desarrollo de extractores."
        )

if __name__ == "__main__":
    print("Iniciando pruebas del cliente Georef en línea (Placeholder)...")

import json
import logging
import os
from typing import Any, Dict, Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

# --- CONFIGURACIÓN DE LOGS ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


# --- CONFIGURACIÓN GENERAL ---
TIMEOUT_SECONDS = 30

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# Parámetros compartidos por ambas consultas
DEFAULT_PARAMS = {
    "campo": "cant_imputados",
    "order": "DESC",
    "size": 20000,
    "estado": "con sentencia;en tramite de debate oral",
}

# Mapeo de endpoints y sus respectivos archivos de salida
ENDPOINTS_CONFIG = {
    "argentina": {
        "url": "http://api.juiciosdelesahumanidad.ar/api/v1.0/historico/causa/busqueda/combinada",
        "filepath": "data/raw/juicios_lesa_humanidad_argentina.json",
    },
    "exterior": {
        "url": "http://api.juiciosdelesahumanidad.ar/api/v1.0/causas_exterior/",
        "filepath": "data/raw/juicios_lesa_humanidad_exterior.json",
    },
}


class JuiciosAPIClient:
    """Cliente robusto para interactuar con la API de Juicios de Lesa Humanidad."""

    def __init__(self, base_url: str):
        self.base_url = base_url
        self.session = self._init_session()

    def _init_session(self) -> requests.Session:
        """Inicializa una sesión de requests con política de reintentos automática."""
        session = requests.Session()
        session.headers.update(HEADERS)

        retries = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504],
        )
        session.mount("http://", HTTPAdapter(max_retries=retries))
        session.mount("https://", HTTPAdapter(max_retries=retries))
        return session

    def fetch_all_data(self, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Realiza la petición GET a la API de manera segura."""
        try:
            logger.info(f"Conectando a {self.base_url}...")
            response = self.session.get(
                self.base_url, params=params, timeout=TIMEOUT_SECONDS
            )

            response.raise_for_status()

            logger.info("Datos recibidos exitosamente. Parseando JSON...")
            return response.json()

        except requests.exceptions.HTTPError as http_err:
            logger.error(
                f"Error HTTP del servidor: {http_err.response.status_code} - {http_err.response.text}"
            )
        except requests.exceptions.ConnectionError:
            logger.error("Error de conexión. Verifica la disponibilidad del servidor.")
        except requests.exceptions.Timeout:
            logger.error(f"La petición excedió el tiempo límite de {TIMEOUT_SECONDS}s.")
        except json.JSONDecodeError:
            logger.error("La respuesta no tiene un formato JSON válido.")
        except requests.exceptions.RequestException as e:
            logger.error(f"Error inesperado en la petición: {e}")

        return None


def save_to_json_file(data: Dict[str, Any], filepath: str) -> None:
    """Guarda un diccionario en un archivo JSON asegurando la existencia del directorio."""
    try:
        # Asegura que la estructura de carpetas (data/raw/) exista
        directorio = os.path.dirname(filepath)
        if directorio:
            os.makedirs(directorio, exist_ok=True)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        logger.info(f"¡Éxito! Archivo guardado correctamente en: {filepath}")
    except IOError as e:
        logger.error(f"Error de E/S al intentar escribir el archivo: {e}")


def main() -> None:
    """Función principal (Punto de entrada del script)."""
    for origen, config in ENDPOINTS_CONFIG.items():
        logger.info(f"--- Iniciando descarga de causas: {origen.upper()} ---")
        
        client = JuiciosAPIClient(base_url=config["url"])
        data = client.fetch_all_data(params=DEFAULT_PARAMS)

        if data is not None:
            save_to_json_file(data, filepath=config["filepath"])
        else:
            logger.error(f"No se pudieron obtener los datos de causas del {origen}.")
        
        print("\n")  # Separador visual en consola


if __name__ == "__main__":
    main()
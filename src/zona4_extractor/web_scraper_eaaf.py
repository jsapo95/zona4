import os
import logging
import requests

# Configuración de Logging profesional para auditoría del proceso
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("EAAFDownloader")

# Mapeo de configuraciones: URL de origen -> Ruta de destino local
DOWNLOAD_CONFIG = {
    "https://labusqueda.eaaf.org.ar/get-csv-cors.php?file=Consolidado_Micrositio_EAAFIdentificados_DATASET.csv": "data/raw/eaaf_identificados.csv",
    "https://labusqueda.eaaf.org.ar/get-csv-cors.php?file=Consolidado_Micrositio_EAAFLugares_DATASET.csv": "data/raw/eaaf_lugares.csv"
}

def descargar_archivo_csv(url: str, ruta_destino: str, timeout: int = 30) -> bool:
    """
    Descarga un archivo CSV, maneja la decodificación de texto (ej. latin1 a UTF-8)
    y lo guarda localmente de forma estandarizada.
    """
    directorio = os.path.dirname(ruta_destino)
    if directorio and not os.path.exists(directorio):
        os.makedirs(directorio, exist_ok=True)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ...",
        "Accept": "text/csv,application/csv"
    }

    logger.info(f"Iniciando descarga desde: {url}")
    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        
        # requests detecta automáticamente el encoding del servidor (ej. ISO-8859-1)
        # Si no lo detecta bien, forzamos latin1 que cubre eñes y acentos rotos
        if response.encoding is None or response.encoding.lower() == 'iso-8859-1':
            response.encoding = 'latin1'
            
        # Guardamos forzando la escritura en UTF-8 nativo
        with open(ruta_destino, 'w', encoding='utf-8', newline='') as f:
            f.write(response.text)
                        
        logger.info(f"Descarga exitosa en UTF-8. Guardado en: {ruta_destino}")
        return True

    except Exception as e:
        logger.error(f"Error procesando la descarga: {e}")
        return False

def ejecutar_pipeline():
    """Orquestador principal de las descargas."""
    logger.info("Iniciando pipeline de descargas del EAAF...")
    
    exitos = 0
    for url, destino in DOWNLOAD_CONFIG.items():
        if descargar_archivo_csv(url, destino):
            exitos += 1
            
    logger.info(f"Pipeline finalizado. Descargas exitosas: {exitos}/{len(DOWNLOAD_CONFIG)}")

if __name__ == "__main__":
    ejecutar_pipeline()
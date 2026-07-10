import os
import json
import logging
import time
from typing import Dict, Any, List, Optional
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup, Tag

# Configuración de Logging para trazabilidad y auditoría
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

class CentrosDetencionScraper:
    BASE_URL = "https://derechoshumanos.mjus.gba.gob.ar/"
    START_URL = f"{BASE_URL}?post_type=centrodetencion"
    
    def __init__(self, delay: float = 1.5):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })
        self.delay = delay

    def fetch_soup(self, url: str) -> Optional[BeautifulSoup]:
        """Realiza la petición HTTP de forma segura y maneja reintentos básicos."""
        try:
            time.sleep(self.delay)  # Politeness delay
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            return BeautifulSoup(response.content, "html.parser")
        except requests.RequestException as e:
            logger.error(f"Error al requerir la URL {url}: {e}")
            return None

    def parse_list_page(self, soup: BeautifulSoup) -> List[str]:
        """Extrae los enlaces del botón 'Ver más' de la página actual del listado."""
        urls = []
        links = soup.find_all("a", class_="lesahumanidad-link-btn-ver-mas")
        for link in links:
            href = link.get("href")
            if href:
                urls.append(urljoin(self.BASE_URL, href))
        return urls

    def get_next_page_url(self, soup: BeautifulSoup) -> Optional[str]:
        """Detecta dinámicamente si existe una página siguiente."""
        next_btn = soup.find("a", class_="next")
        if next_btn and next_btn.get("href"):
            return urljoin(self.BASE_URL, next_btn.get("href"))
        return None

    def parse_detalle_centro(self, url: str) -> Optional[Dict[str, Any]]:
        """Analiza dinámicamente el contenido interno de un 'Ver más'."""
        soup = self.fetch_soup(url)
        if not soup:
            return None

        article = soup.find("article", class_="centrodetencion")
        if not article:
            logger.warning(f"No se encontró la estructura del artículo en: {url}")
            return None

        title_tag = article.find("h1")
        title = title_tag.get_text(strip=True) if title_tag else "Sin Título"

        metadata: Dict[str, str] = {}
        ficha = article.find("div", class_="lesahumanidad-ficha-items-ccd")
        if ficha and isinstance(ficha, Tag):
            for li in ficha.find_all("li"):
                strong = li.find("strong")
                if strong:
                    key = strong.get_text(strip=True).rstrip(":").strip()
                    strong.extract()
                    value = li.get_text(strip=True)
                    metadata[key] = value

        secciones: Dict[str, str] = {}
        datos_divs = article.find_all("div", class_="lesahumanidad-datos-ccd")
        for div in datos_divs:
            subtitulo_tag = div.find(class_="lesahumanidad-ccd-subtitulo")
            if subtitulo_tag:
                subtitulo = subtitulo_tag.get_text(strip=True)
                paragraphs = [p.get_text(strip=True) for p in div.find_all("p") if p.get_text(strip=True)]
                secciones[subtitulo] = "\n".join(paragraphs)

        victimas: List[Dict[str, str]] = []
        victimas_div = article.find("div", class_="lesahumanidad-victimas-de-un-ccd")
        if victimas_div and isinstance(victimas_div, Tag):
            for a_tag in victimas_div.find_all("a", class_="lesahumanidad-link-victima"):
                victimas.append({
                    "nombre": a_tag.get_text(strip=True),
                    "url": urljoin(self.BASE_URL, a_tag.get("href", ""))
                })

        return {
            "source_url": url,
            "titulo": title,
            "metadatos": metadata,
            "secciones": secciones,
            "victimas": victimas
        }

    def guardar_progreso(self, datos: List[Dict[str, Any]], ruta_archivo: str):
        """Escribe de manera segura el estado actual de la lista en el archivo JSON."""
        try:
            # Asegurar que las carpetas existan en el sistema
            directorio = os.path.dirname(ruta_archivo)
            if directorio and not os.path.exists(directorio):
                os.makedirs(directorio)
                
            with open(ruta_archivo, "w", encoding="utf-8") as f:
                json.dump(datos, f, ensure_ascii=False, indent=4)
        except IOError as e:
            logger.error(f"Error escribiendo en el archivo de salida: {e}")

    def run(self, output_filename: str = "data/raw/derechos_humanos_minjus_gba_centros_clandestinos.json"):
        """Orquesta todo el proceso de scraping y guardado secuencial."""
        all_data: List[Dict[str, Any]] = []
        current_url = self.START_URL

        logger.info("Iniciando el proceso de extracción...")
        
        while current_url:
            logger.info(f"Procesando página de listado: {current_url}")
            soup = self.fetch_soup(current_url)
            if not soup:
                break
            
            detalle_urls = self.parse_list_page(soup)
            logger.info(f"Se encontraron {len(detalle_urls)} centros en esta página.")

            # BUCLE INTERNO: Recorre cada centro clandestino individualmente
            for url in detalle_urls:
                logger.info(f"Extrayendo datos de: {url}")
                data = self.parse_detalle_centro(url)
                if data:
                    all_data.append(data)
                    # GUARDADO INCREMENTAL AUTOMÁTICO
                    self.guardar_progreso(all_data, output_filename)
            
            current_url = self.get_next_page_url(soup)

        logger.info(f"Proceso finalizado con éxito. Datos asegurados en '{output_filename}'")

if __name__ == "__main__":
    scraper = CentrosDetencionScraper(delay=1.0)
    scraper.run()
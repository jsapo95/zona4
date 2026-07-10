import os
import json
import time
import random
import logging
from typing import List, Dict, Any, Optional
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# Configuración del Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("HumanRightsCrawler")

class ExtractorHTML:
    """Clase especializada en parsear el HTML de las fichas de víctimas."""
    
    @staticmethod
    def limpiar_texto(elemento) -> str:
        return elemento.text.replace('\xa0', ' ').strip() if elemento else ""

    @classmethod
    def extraer_datos_victima(cls, html_content: str, url: str) -> Optional[Dict[str, Any]]:
        """Parsea la página de detalle de una víctima basándose en la estructura provista."""
        soup = BeautifulSoup(html_content, 'html.parser')
        article = soup.find('article', class_='victima')
        
        if not article:
            logger.warning(f"No se encontró la estructura 'article.victima' en la URL: {url}")
            return None
        
        # 1. Información Básica e Identificación
        nombre_header = article.find('h1')
        nombre = nombre_header.text.strip() if nombre_header else "Desconocido"
        
        imagen_div = article.find('div', class_='lesahumanidad-contenedor-img')
        imagen_url = imagen_div.find('img')['src'] if imagen_div and imagen_div.find('img') else ""
        
        # 2. Datos de la Ficha (Lista ul/li)
        datos_ficha = {}
        items_ficha = article.find('div', class_='lesahumanidad-ficha-items')
        if items_ficha:
            for li in items_ficha.find_all('li'):
                # Extraemos la clave desde el tag <strong> y el valor limpiando el texto remanente
                strong = li.find('strong')
                if strong:
                    clave = strong.text.replace(':', '').strip().lower().replace(' ', '_')
                    # El valor es el texto del li quitando el texto del strong
                    valor = li.text.replace(strong.text, '').strip()
                    datos_ficha[clave] = valor

        # 3. Breve relato de los hechos
        relato = ""
        subtitulo_relato = article.find('h4', class_='lesahumanidad-victima-subtitulo')
        if subtitulo_relato:
            # Buscamos el párrafo inmediatamente siguiente
            parrafo_relato = subtitulo_relato.find_next_sibling('p')
            if parrafo_relato:
                relato = parrafo_relato.text.strip()

        # 4. Centros Clandestinos de Detención (CCDs)
        ccds = []
        div_ccds = article.find('div', class_='lesahumanidad-ccds-de-una-victima')
        if div_ccds:
            for li in div_ccds.find_all('li'):
                a_ccd = li.find('a', class_='lesahumanidad-link-ccd')
                if a_ccd:
                    ccds.append({
                        "nombre": a_ccd.text.strip(),
                        "url": a_ccd.get('href', '')
                    })

        # 5. Sentencias e Imputados (Tablas Complejas)
        sentencias = []
        # Buscamos todos los bloques de sentencia que preceden a las tablas
        bloques_sentencia = article.find_all('div', class_='lesahumanidad-agrupamiento-tabla-sentencia')
        
        for bloque in bloques_sentencia:
            link_sentencia = bloque.find('a', class_='lesahumanidad-link-sentencia')
            if not link_sentencia:
                continue
                
            nombre_sentencia = link_sentencia.text.strip()
            url_sentencia = link_sentencia.get('href', '')
            
            imputados_lista = []
            # La tabla de imputados correspondiente suele ser el siguiente elemento hermano de tipo 'table'
            tabla = bloque.find_next_sibling('table', class_='lesahumanidad-tabla')
            if tabla:
                tbody = tabla.find('tbody')
                if tbody:
                    for tr in tbody.find_all('tr'):
                        td_imputado = tr.find('td', class_='lesahumanidad-tabla-victimas-sentencias-imputados-campo-imputado')
                        td_delitos = tr.find('td', class_='lesahumanidad-tabla-victimas-sentencias-imputados-campo-delitos')
                        
                        if td_imputado:
                            a_imputado = td_imputado.find('a', class_='lesahumanidad-link-imputado')
                            nombre_imputado = a_imputado.text.strip() if a_imputado else td_imputado.text.strip()
                            url_imputado = a_imputado.get('href', '') if a_imputado else ""
                            
                            delitos = [d.strip() for d in td_delitos.text.split(',')] if td_delitos else []
                            
                            imputados_lista.append({
                                "imputado_nombre": nombre_imputado,
                                "imputado_url": url_imputado,
                                "delitos": delitos
                            })
            
            sentencias.append({
                "sentencia_nombre": nombre_sentencia,
                "sentencia_url": url_sentencia,
                "imputados": imputados_lista
            })

        return {
            "source_url": url,
            "nombre": nombre,
            "imagen_url": imagen_url,
            "datos_personales": datos_ficha,
            "relato_hechos": relato,
            "centros_clandestinos": ccds,
            "sentencias": sentencias
        }


class ClienteHTTP:
    """Encapsula la sesión de red y políticas de cortesía (Polite Scraping)."""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "es-ES,es;q=0.8,en-US;q=0.5,en;q=0.3"
        })

    def obtener_html(self, url: str, retries: int = 3) -> Optional[str]:
        """Realiza peticiones HTTP GET seguras con reintentos."""
        for intento in range(retries):
            try:
                # Delay aleatorio razonable para no generar denegación de servicio (DoS)
                time.sleep(random.uniform(1.0, 2.5))
                response = self.session.get(url, timeout=15)
                response.raise_for_status()
                return response.text
            except requests.RequestException as e:
                logger.warning(f"Error al solicitar {url} (Intento {intento+1}/{retries}): {e}")
                if intento == retries - 1:
                    logger.error(f"Fallo crítico de red en URL: {url}")
                    return None


class OrquestadorCrawler:
    """Controla el flujo de navegación entre el listado paginado y los detalles."""
    
    def __init__(self, url_inicial: str, output_file: str = "data/raw/derechos_humanos_minjus_gba_victimas.json"):
        self.url_actual = url_inicial
        self.output_file = output_file
        self.cliente = ClienteHTTP()
        self.resultados = []

    def extraer_urls_perfiles(self, html_listado: str) -> List[str]:
        """Encuentra los enlaces de destino de los botones 'Ver más'."""
        soup = BeautifulSoup(html_listado, 'html.parser')
        urls = []
        
        # En WordPress, los botones 'Ver más' suelen estar dentro de un article/card que contiene el link, 
        # o el botón mismo puede ser un tag <a> o un <button> que redirige. 
        # Si la estructura tiene un wrapper con el link, buscamos el link del post/perfil:
        botones = soup.find_all('button', class_='btn-ver-mas')
        
        for boton in botones:
            # Estrategia A: Si el botón está envuelto o tiene un atributo con la URL (ej: onclick o data-url)
            # Estrategia B clásica en WP: Buscar el link del post más cercano
            parent_anchor = boton.find_parent('a')
            if parent_anchor and parent_anchor.get('href'):
                urls.append(parent_anchor.get('href'))
            else:
                # Si el botón no es hijo directo de <a>, buscamos el link del artículo contenedor
                container = boton.find_parent(['article', 'div', 'li'], class_=lambda x: x != 'btn-ver-mas')
                if container:
                    link = container.find('a')
                    if link and link.get('href'):
                        urls.append(link.get('href'))
                        
        # Si los botones no exponen directamente la url, una alternativa robusta en diseño de scrapers 
        # es buscar todos los links que lleven al tipo de post de la víctima dentro del grid:
        if not urls:
            for a in soup.find_all('a', href=True):
                if '/victima/' in a['href'] or '?victima=' in a['href']:
                    urls.append(a['href'])
                    
        # Remover duplicados manteniendo el orden
        return list(dict.fromkeys(urls))

    def buscar_siguiente_pagina(self, html_listado: str) -> Optional[str]:
        """Detecta si existe un botón de 'Siguiente' página y devuelve su enlace absoluto."""
        soup = BeautifulSoup(html_listado, 'html.parser')
        next_anchor = soup.find('a', class_='next', rel='next')
        if next_anchor and next_anchor.get('href'):
            return urljoin(self.url_actual, next_anchor['href'])
        return None

    def ejecutar(self):
        """Inicia el proceso general del Crawler."""
        logger.info("Iniciando Web Crawler...")
        pagina_nro = 1
        
        while self.url_actual:
            logger.info(f"Procesando página de listado {pagina_nro}: {self.url_actual}")
            html_listado = self.cliente.obtener_html(self.url_actual)
            
            if not html_listado:
                logger.error(f"No se pudo leer la página de listado {pagina_nro}. Abortando.")
                break
                
            urls_perfiles = self.extraer_urls_perfiles(html_listado)
            logger.info(f"Se encontraron {len(urls_perfiles)} perfiles de víctimas en esta página.")
            
            for url in urls_perfiles:
                logger.info(f"Parseando detalle de víctima: {url}")
                html_detalle = self.cliente.obtener_html(url)
                if html_detalle:
                    datos = ExtractorHTML.extraer_datos_victima(html_detalle, url)
                    if datos:
                        self.resultados.append(datos)
                        # Guardado incremental para evitar pérdidas de datos por desconexión
                        self.guardar_json_temporal()
            
            # Moverse a la siguiente página del catálogo
            self.url_actual = self.buscar_siguiente_pagina(html_listado)
            pagina_nro += 1
            
        logger.info(f"Crawler finalizado con éxito. Total de registros: {len(self.resultados)}")

    def guardar_json_temporal(self):
        """Escribe el estado actual de la extracción en el disco."""
        try:
            with open(self.output_file, 'w', encoding='utf-8') as f:
                json.dump(self.resultados, f, ensure_ascii=False, indent=4)
        except IOError as e:
            logger.error(f"Error escribiendo en el archivo de salida: {e}")


if __name__ == "__main__":
    URL_INICIAL = "https://derechoshumanos.mjus.gba.gob.ar/?post_type=victima"
    crawler = OrquestadorCrawler(url_inicial=URL_INICIAL)
    crawler.ejecutar()
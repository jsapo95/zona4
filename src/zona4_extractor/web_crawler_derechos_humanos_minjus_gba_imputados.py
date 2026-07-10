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
logger = logging.getLogger("ImputadosCrawler")

class ExtractorHTMLImputados:
    """Clase especializada en parsear el HTML de las fichas de los imputados."""

    @classmethod
    def extraer_datos_imputado(cls, html_content: str, url: str) -> Optional[Dict[str, Any]]:
        """Parsea la página de detalle de un imputado basándose en la estructura provista."""
        soup = BeautifulSoup(html_content, 'html.parser')
        article = soup.find('article', class_='imputado')
        
        if not article:
            logger.warning(f"No se encontró la estructura 'article.imputado' en la URL: {url}")
            return None
        
        # 1. Identificación básica
        nombre_header = article.find('h1')
        nombre = nombre_header.text.strip() if nombre_header else "Desconocido"
        
        imagen_div = article.find('div', class_='lesahumanidad-imputado-contenedor-img')
        imagen_url = imagen_div.find('img')['src'] if imagen_div and imagen_div.find('img') else ""
        
        # 2. Ficha de Datos Personales (Fecha de nacimiento, Fuerza, etc.)
        datos_personales = {}
        items_ficha = article.find('div', class_='lesahumanidad-ficha-items-imputado')
        if items_ficha:
            for li in items_ficha.find_all('li'):
                strong = li.find('strong')
                if strong:
                    clave = strong.text.replace(':', '').strip().lower().replace(' ', '_')
                    valor = li.text.replace(strong.text, '').strip()
                    datos_personales[clave] = valor

        # 3. Breve reseña de información
        mas_info = ""
        subtitulo_info = article.find('h4', class_='lesahumanidad-imputado-subtitulo')
        if subtitulo_info:
            parrafo_info = subtitulo_info.find_next_sibling('p')
            if parrafo_info:
                mas_info = parrafo_info.text.strip()

        # 4. Bloques de Sentencias y sus Víctimas asociadas
        sentencias_victimas = []
        # Buscamos todos los contenedores de sentencia para imputados
        bloques_sentencia = article.find_all('div', class_='lesahumanidad-agrupamiento-tabla-sentencia')
        
        for bloque in bloques_sentencia:
            link_sentencia = bloque.find('a', class_='lesahumanidad-link-sentencia')
            if not link_sentencia:
                continue
                
            nombre_sentencia = link_sentencia.text.strip()
            url_sentencia = link_sentencia.get('href', '')
            
            victimas_lista = []
            # La tabla de víctimas asociada a este bloque es el siguiente elemento hermano 'table'
            tabla = bloque.find_next_sibling('table', class_='lesahumanidad-tabla-sentencias-victimas-imputados')
            if tabla:
                tbody = tabla.find('tbody')
                if tbody:
                    for tr in tbody.find_all('tr'):
                        td_victima = tr.find('td', class_='lesahumanidad-tabla-sentencias-victimas-imputados-campo-victima')
                        td_delitos = tr.find('td', class_='lesahumanidad-tabla-sentencias-victimas-imputados-campo-delitos')
                        
                        if td_victima:
                            a_victima = td_victima.find('a', class_='lesahumanidad-link-victima')
                            nombre_victima = a_victima.text.strip() if a_victima else td_victima.text.strip()
                            url_victima = a_victima.get('href', '') if a_victima else ""
                            
                            delitos = [d.strip() for d in td_delitos.text.split(',')] if td_delitos else []
                            
                            victimas_lista.append({
                                "victima_nombre": nombre_victima,
                                "victima_url": url_victima,
                                "delitos": delitos
                            })
            
            sentencias_victimas.append({
                "sentencia_nombre": nombre_sentencia,
                "sentencia_url": url_sentencia,
                "victimas_asociadas": victimas_lista
            })

        # 5. Tabla de Condenas y Sanciones
        condenas = []
        tabla_condenas = article.find('table', class_='lesahumanidad-tabla-imputados-condenas')
        if tabla_condenas:
            tbody = tabla_condenas.find('tbody')
            if tbody:
                for tr in tbody.find_all('tr'):
                    td_sentencia = tr.find('td', class_='lesahumanidad-tabla-imputados-condenas-campo-sentencias')
                    td_sancion = tr.find('td', class_='lesahumanidad-tabla-imputados-condenas-campo-sanciones')
                    
                    if td_sentencia and td_sancion:
                        a_sentencia = td_sentencia.find('a', class_='lesahumanidad-link-sentencia')
                        nombre_sentencia_condena = a_sentencia.text.strip() if a_sentencia else td_sentencia.text.strip()
                        url_sentencia_condena = a_sentencia.get('href', '') if a_sentencia else ""
                        sancion = td_sancion.text.strip()
                        
                        condenas.append({
                            "sentencia_nombre": nombre_sentencia_condena,
                            "sentencia_url": url_sentencia_condena,
                            "sancion": sancion
                        })

        return {
            "source_url": url,
            "nombre": nombre,
            "imagen_url": imagen_url,
            "datos_personales": datos_personales,
            "mas_informacion": mas_info,
            "sentencias_y_victimas": sentencias_victimas,
            "condenas_recibidas": condenas
        }


class ClienteHTTP:
    """Clase para la gestión de solicitudes HTTP."""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
        })

    def obtener_html(self, url: str, retries: int = 3) -> Optional[str]:
        for intento in range(retries):
            try:
                time.sleep(random.uniform(1.2, 2.8))  # Polite Delay
                response = self.session.get(url, timeout=15)
                response.raise_for_status()
                return response.text
            except requests.RequestException as e:
                logger.warning(f"Error al solicitar {url} (Intento {intento+1}/{retries}): {e}")
                if intento == retries - 1:
                    logger.error(f"Fallo de conexión definitivo en {url}")
                    return None


class OrquestadorImputados:
    """Administra la navegación recursiva y la persistencia de datos."""
    
    def __init__(self, url_inicial: str, output_file: str = "data/raw/derechos_humanos_minjus_gba_imputados.json"):
        self.url_actual = url_inicial
        self.output_file = output_file
        self.cliente = ClienteHTTP()
        self.resultados = []

    def extraer_urls_imputados(self, html_listado: str) -> List[str]:
        """Extrae de forma robusta las URLs de los perfiles de los imputados en el listado."""
        soup = BeautifulSoup(html_listado, 'html.parser')
        urls = []
        
        # Estrategia primaria: buscar las etiquetas <article> con clase 'imputado'
        articulos = soup.find_all('article', class_='imputado')
        for art in articulos:
            # Buscamos el enlace en el título H2 o en la clase de su enlace 'Ver más'
            link = art.find('a', class_='lesahumanidad-link-btn-ver-mas')
            if not link:
                link = art.find('h2', class_='blog-entry-title').find('a') if art.find('h2', class_='blog-entry-title') else None
            
            if link and link.get('href'):
                urls.append(link['href'])
                
        # Estrategia de respaldo genérica
        if not urls:
            for a in soup.find_all('a', href=True):
                if '/imputado/' in a['href']:
                    urls.append(a['href'])
                    
        return list(dict.fromkeys(urls))

    def buscar_siguiente_pagina(self, html_listado: str) -> Optional[str]:
        """Localiza el botón 'Siguiente' para saltar a la próxima página de la lista."""
        soup = BeautifulSoup(html_listado, 'html.parser')
        next_anchor = soup.find('a', class_='next', rel='next')
        if next_anchor and next_anchor.get('href'):
            return urljoin(self.url_actual, next_anchor['href'])
        return None

    def ejecutar(self):
        logger.info("Iniciando extracción de imputados...")
        pagina_nro = 1
        
        while self.url_actual:
            logger.info(f"Escaneando catálogo de imputados - Página {pagina_nro}: {self.url_actual}")
            html_listado = self.cliente.obtener_html(self.url_actual)
            
            if not html_listado:
                logger.error(f"Imposible cargar el listado de la página {pagina_nro}. Deteniendo proceso.")
                break
                
            urls_perfiles = self.extraer_urls_imputados(html_listado)
            logger.info(f"Se encontraron {len(urls_perfiles)} imputados en esta página.")
            
            for url in urls_perfiles:
                logger.info(f"Procesando expediente del imputado: {url}")
                html_detalle = self.cliente.obtener_html(url)
                if html_detalle:
                    datos = ExtractorHTMLImputados.extraer_datos_imputado(html_detalle, url)
                    if datos:
                        self.resultados.append(datos)
                        self.guardar_datos()
            
            # Navegar a la siguiente página del catálogo general
            self.url_actual = self.buscar_siguiente_pagina(html_listado)
            pagina_nro += 1
            
        logger.info(f"Proceso finalizado. Se han guardado {len(self.resultados)} imputados en '{self.output_file}'")

    def guardar_datos(self):
        """Persiste de manera segura los datos recolectados en formato JSON."""
        try:
            with open(self.output_file, 'w', encoding='utf-8') as f:
                json.dump(self.resultados, f, ensure_ascii=False, indent=4)
        except IOError as e:
            logger.error(f"Error al escribir archivo de persistencia: {e}")


if __name__ == "__main__":
    URL_INICIAL = "https://derechoshumanos.mjus.gba.gob.ar/?post_type=imputado"
    crawler = OrquestadorImputados(url_inicial=URL_INICIAL)
    crawler.ejecutar()
import os
import requests
from bs4 import BeautifulSoup
import json
import time

# Configuración base de URLs
BASE_URL = "https://derechoshumanos.mjus.gba.gob.ar/"
START_URL = f"{BASE_URL}?post_type=sentencia"
ARCHIVO_SALIDA = "data/raw/derechos_humanos_minjus_gba_sentencias.json"

def parse_detalle_sentencia(url):
    """
    Ingresa al detalle de una sentencia y extrae toda su información técnica,
    resumen y la relación dinámica de víctimas con sus imputados y delitos.
    """
    print(f"   -> Extrayendo detalle de: {url}")
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
    except Exception as e:
        print(f"      Error al acceder al detalle: {e}")
        return {}

    soup = BeautifulSoup(response.content, 'html.parser')
    article = soup.find('article', class_='sentencia')
    if not article:
        return {}

    # 1. Datos de cabecera de la Sentencia
    titulo = ""
    h1_titulo = article.find('h1')
    if h1_titulo:
        titulo = h1_titulo.get_text().strip()

    # 2. Ficha de Datos Técnicos (Dinámica)
    datos_ficha = {}
    ficha_items = article.find('div', class_='lesahumanidad-ficha-items-sentencia')
    if ficha_items:
        for br in ficha_items.find_all('br'):
            br.replace_with(", ")
            
        for li in ficha_items.find_all('li'):
            if 'lesahumanidad-datos-sentencia-archivo' in li.get('class', []):
                continue
            
            strong = li.find('strong')
            if strong:
                clave = strong.get_text().replace(':', '').strip().lower().replace(' ', '_')
                valor = li.get_text().replace(strong.get_text(), '').strip()
                datos_ficha[clave] = valor

        link_pdf = ficha_items.find('a', href=True)
        if link_pdf:
            datos_ficha['sentencia_completa_pdf'] = link_pdf['href']

    # 3. Resumen de la sentencia
    resumen = ""
    subtitulo_resumen = article.find('h4', class_='lesahumanidad-sentencia-subtitulo')
    if subtitulo_resumen:
        parrafo_resumen = subtitulo_resumen.find_next_sibling('p')
        if parrafo_resumen:
            for br in parrafo_resumen.find_all('br'):
                br.replace_with("\n")
            resumen = parrafo_resumen.get_text().strip()

    # 4. Tabla Dinámica: Relación de Víctimas e Imputados
    victimas_list = []
    bloques_victimas = article.find_all('div', class_='lesahumanidad-agrupamiento-tabla-sentencia')
    for bloque in bloques_victimas:
        a_victima = bloque.find('a', class_='lesahumanidad-link-victima')
        if a_victima:
            nombre_victima = a_victima.get_text().strip()
            url_victima = a_victima.get('href', '').strip()
            if url_victima and url_victima.startswith('/'):
                url_victima = BASE_URL.rstrip('/') + url_victima
        else:
            nombre_victima = bloque.get_text().replace('Víctima:', '').strip()
            url_victima = ""

        tabla_imputados = bloque.find_next_sibling('table', class_='lesahumanidad-tabla-sentencias-victimas-imputados')
        imputados_asociados = []
        
        if tabla_imputados:
            filas = tabla_imputados.find('tbody').find_all('tr') if tabla_imputados.find('tbody') else []
            for fila in filas:
                td_imputado = fila.find('td', class_='lesahumanidad-tabla-sentencias-victimas-imputados-campo-imputado')
                td_delitos = fila.find('td', class_='lesahumanidad-tabla-sentencias-victimas-imputados-campo-delitos')
                
                if td_imputado:
                    a_imputado = td_imputado.find('a')
                    nombre_imputado = a_imputado.get_text().strip() if a_imputado else td_imputado.get_text().strip()
                    url_imputado = a_imputado.get('href', '').strip() if a_imputado else ""
                    if url_imputado and url_imputado.startswith('/'):
                        url_imputado = BASE_URL.rstrip('/') + url_imputado
                else:
                    nombre_imputado = ""
                    url_imputado = ""
                    
                delitos = td_delitos.get_text().strip() if td_delitos else ""
                
                imputados_asociados.append({
                    "imputado_nombre": nombre_imputado,
                    "imputado_url": url_imputado,
                    "delitos": [d.strip() for d in delitos.split(',') if d.strip()]
                })

        victimas_list.append({
            "victima_nombre": nombre_victima,
            "victima_url": url_victima,
            "imputados": imputados_asociados
        })

    detalle_completo = {
        "titulo": titulo,
        "datos_tecnicos": datos_ficha,
        "resumen": resumen,
        "victimas_e_imputados": victimas_list
    }
    
    return detalle_completo

def guardar_progreso(datos, ruta_archivo):
    """Escribe la lista actualizada de resultados en el archivo JSON."""
    try:
        # Asegurar que las carpetas intermedias existan
        directorio = os.path.dirname(ruta_archivo)
        if directorio and not os.path.exists(directorio):
            os.makedirs(directorio)
            
        with open(ruta_archivo, 'w', encoding='utf-8') as f:
            json.dump(datos, f, ensure_ascii=False, indent=4)
    except IOError as e:
        print(f"Error al escribir en el archivo de salida: {e}")

def scrape_sentencias():
    """
    Función principal que maneja la paginación y guarda de forma incremental
    los datos de las sentencias en un archivo JSON.
    """
    url_actual = START_URL
    todas_las_sentencias = []
    pagina = 1

    print("Iniciando scraping del catálogo de Sentencias...\n")

    while url_actual:
        print(f"=== Procesando Página {pagina} ===")
        try:
            response = requests.get(url_actual, timeout=15)
            response.raise_for_status()
        except Exception as e:
            print(f"Error al acceder a la página del listado: {e}")
            break

        soup = BeautifulSoup(response.content, 'html.parser')
        articulos = soup.find_all('article', class_='sentencia')

        for art in articulos:
            post_id = art.get('id', '').replace('post-', '')
            
            link_tag = art.find('a', class_='lesahumanidad-link-btn-ver-mas') or art.find('h2', class_='entry-title').find('a')
            if not link_tag:
                continue
                
            url_detalle = link_tag['href']

            fecha_publicacion = ""
            time_pub = art.find('time', class_='entry-date published')
            if time_pub:
                fecha_publicacion = time_pub.get_text().strip()

            fecha_actualizacion = ""
            time_upd = art.find('time', class_='updated')
            if time_upd:
                fecha_actualizacion = time_upd.get_text().strip()

            # Extraemos la información interna
            detalle_info = parse_detalle_sentencia(url_detalle)

            # Consolidamos el objeto de la sentencia
            sentencia_obj = {
                "post_id": post_id,
                "url_detalle": url_detalle,
                "fechas_metadatos": {
                    "fecha_publicacion_web": fecha_publicacion,
                    "ultima_actualizacion_web": fecha_actualizacion
                },
                **detalle_info
            }
            
            todas_las_sentencias.append(sentencia_obj)
            
            # GUARDADO INCREMENTAL: Guardamos tras procesar cada elemento individual
            guardar_progreso(todas_las_sentencias, ARCHIVO_SALIDA)
            
            time.sleep(1) # Delay prudencial respetuoso con el servidor

        # Control de Paginación
        btn_siguiente = soup.find('a', class_='next page-numbers')
        if btn_siguiente and 'href' in btn_siguiente.attrs:
            url_actual = btn_siguiente['href']
            pagina += 1
        else:
            url_actual = None

    print(f"\n¡Scraping finalizado con éxito! Todos los datos respaldados en '{ARCHIVO_SALIDA}'.")

if __name__ == "__main__":
    scrape_sentencias()
# Visualizaciones

Visualizaciones construidas sobre los datos del grafo. Cada una vive en su
carpeta con el script que arma sus datos, para que se pueda regenerar y auditar.

| Carpeta | Qué muestra |
| ------- | ----------- |
| [`recorridos/`](recorridos/README.md) | Mapa animado del recorrido de cada víctima (`recorridos.html`): secuestro, centro clandestino, asesinato y hallazgo de restos, con y sin hallazgo de restos registrado. Mapa de flujos con los recorridos más repetidos (`flujos.html`). |

Los huecos de datos que dejan ver (qué falta en el grafo, por CCD, provincia y
etapa, con las fuentes que los cubrirían) están en
[`HUECOS_DE_DATOS.md`](HUECOS_DE_DATOS.md).

## Cómo verlas

No hace falta Neo4j, ni Python, ni regenerar nada: los datos ya están en el
repo. Sí hace falta internet (el mapa base y la librería de mapas se bajan al
abrir la página).

1. Traer el código. Mientras el PR esté abierto, las visualizaciones están en el
   branch `feature/visualizacion-recorridos`:

   ```bash
   git fetch origin
   git checkout feature/visualizacion-recorridos
   ```

2. Abrir con doble clic, desde la carpeta `visualizaciones/recorridos/`:
   - `recorridos.html`: el mapa animado.
   - `flujos.html`: los recorridos frecuentes.

   Cada página tiene un link a la otra.

3. Si la página abre pero el mapa queda vacío (algunos navegadores bloquean
   archivos locales), servirla con Python desde la raíz del repo:

   ```bash
   python -m http.server 8000 --directory visualizaciones
   ```

   y abrir <http://localhost:8000/recorridos/recorridos.html>. Después de
   traer cambios, recargar con Ctrl+F5 para que el navegador no muestre la
   versión anterior.

Para regenerar los datos (cuando cambian las fuentes o el loader), ver
[`recorridos/README.md`](recorridos/README.md#cómo-regenerar-los-datos).

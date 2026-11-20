// Mapa base compartido por las visualizaciones de recorridos.
//
// Argenmap, del Instituto Geográfico Nacional. No hay mapa de respaldo: si el
// servidor del IGN no responde, el mapa queda sin fondo (los datos se ven
// igual) con un aviso y un botón para reintentar. Otros mapas base rotulan
// las Islas Malvinas como "Falkland Islands", y ese rótulo viene dibujado en
// la imagen: no se puede corregir ni ocultar desde acá.
window.MapaBase = (() => {
  "use strict";
  const DATOS = "Datos: Parque de la Memoria, RUVTE, MinJus GBA, EAAF, Georef";
  const ESPERA_IGN = 6000;

  const oscuro = () => {
    const t = document.documentElement.dataset.theme;
    return t ? t === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
  };

  // Devuelve una función que vuelve a poner las teselas (al cambiar el tema).
  function ponerEn(mapa) {
    let base, vigia, aviso;
    mapa.attributionControl.addAttribution(DATOS);

    function quitarAviso() {
      if (aviso) { mapa.removeControl(aviso); aviso = null; }
    }

    function avisar() {
      clearTimeout(vigia);
      if (base) { mapa.removeLayer(base); base = null; }
      if (aviso) return;
      aviso = L.control({ position: "topright" });
      aviso.onAdd = () => {
        const div = L.DomUtil.create("div", "aviso-mapa-base");
        div.setAttribute("role", "status");
        div.innerHTML = 'El mapa base del IGN no cargó. Los datos se ven igual, sin fondo. <button type="button">Reintentar</button>';
        L.DomEvent.disableClickPropagation(div);
        div.querySelector("button").onclick = () => poner();
        return div;
      };
      aviso.addTo(mapa);
    }

    function poner() {
      quitarAviso();
      if (base) mapa.removeLayer(base);
      clearTimeout(vigia);
      const capa = oscuro() ? "argenmap_oscuro" : "mapabase_gris";
      base = L.tileLayer(`https://wms.ign.gob.ar/geoserver/gwc/service/tms/1.0.0/${capa}@EPSG%3A3857@png/{z}/{x}/{y}.png`, {
        attribution: '<a href="https://www.ign.gob.ar/AreaServicios/Argenmap/Introduccion">Argenmap · IGN</a>',
        tms: true, maxZoom: 18,
      }).addTo(mapa);
      let cargadas = 0, errores = 0;
      base.on("tileload", () => { cargadas++; });
      base.on("tileerror", () => { if (++errores >= 3 && !cargadas) avisar(); });
      vigia = setTimeout(() => { if (!cargadas) avisar(); }, ESPERA_IGN);
    }

    poner();
    return poner;
  }

  return { oscuro, ponerEn };
})();

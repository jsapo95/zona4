// Mapa base compartido por las visualizaciones de recorridos.
//
// Argenmap, del Instituto Geográfico Nacional. Si el servidor del IGN no
// responde, se pasa a OpenStreetMap en gris (clase `teselas-respaldo`, cada
// página la estiliza) para que el mapa no quede sin geografía.
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
    let base, respaldo = false, vigia;
    function poner() {
      if (base) mapa.removeLayer(base);
      clearTimeout(vigia);
      if (respaldo) {
        base = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
          attribution: `&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> (respaldo: Argenmap no respondió) · ${DATOS}`,
          maxZoom: 19, className: "teselas-respaldo",
        }).addTo(mapa);
        return;
      }
      const capa = oscuro() ? "argenmap_oscuro" : "mapabase_gris";
      base = L.tileLayer(`https://wms.ign.gob.ar/geoserver/gwc/service/tms/1.0.0/${capa}@EPSG%3A3857@png/{z}/{x}/{y}.png`, {
        attribution: `<a href="https://www.ign.gob.ar/AreaServicios/Argenmap/Introduccion">Argenmap · IGN</a> · ${DATOS}`,
        tms: true, maxZoom: 18,
      }).addTo(mapa);
      let cargadas = 0, errores = 0;
      base.on("tileload", () => { cargadas++; });
      base.on("tileerror", () => { if (++errores >= 3 && !cargadas) pasarARespaldo(); });
      vigia = setTimeout(() => { if (!cargadas) pasarARespaldo(); }, ESPERA_IGN);
    }
    function pasarARespaldo() {
      if (respaldo) return;
      respaldo = true;
      poner();
    }
    poner();
    return poner;
  }

  return { oscuro, ponerEn };
})();

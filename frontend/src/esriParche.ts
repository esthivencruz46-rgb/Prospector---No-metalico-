// Parche de esri-leaflet 3.0.x (RasterLayer): si una capa GEOCATMIN se apaga
// o cambia (layerDefs) mientras su imagen todavía carga, la imagen llega
// tarde y la librería hace `x._map.removeLayer(...)` con `_map === null`
// → "Cannot read properties of null (reading 'removeLayer')" (visto en la
// prueba E2E al elegir una formación). Mismo código que la librería
// (src/Layers/RasterLayer.js), solo con las comprobaciones que faltan.
import L from "leaflet";
import { RasterLayer } from "esri-leaflet";

const Overlay = L.ImageOverlay.extend({
  onAdd(this: any, map: L.Map) {
    this._topLeft = map.getPixelBounds().min;
    L.ImageOverlay.prototype.onAdd.call(this, map);
  },
  _reset(this: any) {
    if (this._map.options.crs === L.CRS.EPSG3857) {
      (L.ImageOverlay.prototype as any)._reset.call(this);
    } else {
      L.DomUtil.setPosition(this._image, this._topLeft.subtract(this._map.getPixelOrigin()));
    }
  },
});

function quitar(capa: any) {
  if (capa && capa._map) capa._map.removeLayer(capa);
}

const proto = (RasterLayer as any).prototype;

proto._renderImage = function (this: any, url: string, bounds: L.LatLngBounds, contentType?: string) {
  if (!this._map) return;
  if (contentType) url = `data:${contentType};base64,${url}`;
  if (!url) return;
  const image = new (Overlay as any)(url, bounds, {
    opacity: 0,
    crossOrigin: this.options.withCredentials ? "use-credentials" : this.options.useCors,
    alt: this.options.alt,
    pane: this.options.pane || this.getPane(),
    interactive: this.options.interactive,
  }).addTo(this._map);

  // eslint-disable-next-line prefer-const
  let onLoad: (e: any) => void;
  const onError = function (this: any) {
    quitar(image);
    this.fire("error");
    image.off("load", onLoad, this);
  };
  onLoad = function (this: any, e: any) {
    image.off("error", onError, this);
    const nueva = e.target;
    if (!this._map) {
      quitar(nueva); // la capa ya se apagó: no dejar la imagen huérfana
    } else if (nueva._bounds.equals(bounds) && nueva._bounds.equals(this._map.getBounds())) {
      const vieja = this._currentImage;
      this._currentImage = nueva;
      if (this.options.position === "front") this.bringToFront();
      else if (this.options.position === "back") this.bringToBack();
      if (this.options.zIndex) this.setZIndex(this.options.zIndex);
      if (nueva._map) nueva.setOpacity(this.options.opacity);
      if (vieja && vieja !== nueva) quitar(vieja);
    } else {
      quitar(nueva);
    }
    this.fire("load", { bounds });
  };
  image.once("error", onError, this);
  image.once("load", onLoad, this);
};

proto._update = function (this: any) {
  if (!this._map) return;
  const zoom = this._map.getZoom();
  const bounds = this._map.getBounds();
  if (this._animatingZoom) return;
  if (this._map._panTransition && this._map._panTransition._inProgress) return;
  if (zoom > this.options.maxZoom || zoom < this.options.minZoom) {
    quitar(this._currentImage);
    this._currentImage = null;
    return;
  }
  const params = this._buildExportParams();
  L.Util.extend(params, this.options.requestParams);
  if (params) {
    this._requestExport(params, bounds);
    this.fire("loading", { bounds });
  } else if (this._currentImage) {
    quitar(this._currentImage);
    this._currentImage = null;
  }
};

import { useEffect, useRef, useState } from "react";
import * as turf from "@turf/turf";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "leaflet-draw/dist/leaflet.draw.css";
import "leaflet-draw";
import {
  getSoilByPoint,
  getSoilByPolygon,
  analyseFarmland,
  getCropRecommendation,
} from "../services/api";
import { Map as Mapview, MousePointer2, Pen, Satellite,MapPin } from 'lucide-react';
import { Tooltip } from "../components/Tooltip"
import { renderToStaticMarkup } from "react-dom/server";

let polyCount = 0;

function formatArea(m) {
  if (m >= 1e6) return (m / 1e6).toFixed(2) + " km²";
  if (m >= 1e4) return (m / 1e4).toFixed(2) + " ha";
  return m.toFixed(0) + " m²";
}

const LAND_COLORS = {
  farmland: "#22c55e",
  builtup: "#ec4899",
  water: "#3b82f6",
  unknown: "#a855f7",
};

const SOIL_COLORS = [
  "#b45309",
  "#d97706",
  "#f59e0b",
  "#84cc16",
  "#10b981",
  "#06b6d4",
  "#6366f1",
  "#ec4899",
  "#ef4444",
  "#8b5cf6",
];

const CROP_EMOJIS = {
  rice: "🌾",
  wheat: "🌾",
  maize: "🌽",
  corn: "🌽",
  jute: "🌿",
  cotton: "🌸",
  sugarcane: "🎋",
  tea: "🍵",
  coffee: "☕",
  banana: "🍌",
  mango: "🥭",
  grapes: "🍇",
  watermelon: "🍉",
  muskmelon: "🍈",
  apple: "🍎",
  orange: "🍊",
  papaya: "🥭",
  coconut: "🥥",
  pomegranate: "🍎",
  lentil: "🫘",
  blackgram: "🫘",
  mungbean: "🫘",
  mothbeans: "🫘",
  pigeonpeas: "🫘",
  kidneybeans: "🫘",
  chickpea: "🫘",
};
function getCropEmoji(crop) {
  return CROP_EMOJIS[crop?.toLowerCase()] || "🌱";
}

// ── Render DW FeatureCollection on Leaflet FeatureGroup ───────────────────────
// Backend feature.properties: { class, label, color, area_ha, confidence }
function renderDWGeoJSON(featureCollection, targetGroup, clipCoords) {
  targetGroup.clearLayers();
  if (!featureCollection?.features?.length) return;

  let features = featureCollection.features;

  // Clip to drawn polygon if coords provided
  if (clipCoords?.length) {
    const ring = clipCoords.map((c) => [c[1], c[0]]);
    if (
      ring[0][0] !== ring[ring.length - 1][0] ||
      ring[0][1] !== ring[ring.length - 1][1]
    )
      ring.push(ring[0]);
    const clipPoly = turf.polygon([ring]);
    const clipped = [];
    features.forEach((feat) => {
      try {
        const intersection = turf.intersect(
          turf.featureCollection([feat, clipPoly]),
        );
        if (intersection) {
          intersection.properties = feat.properties;
          clipped.push(intersection);
        }
      } catch (e) {}
    });
    features = clipped;
  }

  L.geoJSON(
    { type: "FeatureCollection", features },
    {
      interactive: true,
      style: (feature) => {
        const color = feature.properties?.color || "#94a3b8";
        return {
          color,
          fillColor: color,
          fillOpacity: 0.78,
          weight: 1,
          opacity: 1,
        };
      },
      onEachFeature: (feature, lyr) => {
        const label =
          feature.properties?.label || feature.properties?.class || "Unknown";
        const color = feature.properties?.color || "#94a3b8";
        const areaHa = feature.properties?.area_ha;
        lyr.bindTooltip(
          `<div style="font-family:system-ui,sans-serif;background:#fff;padding:6px 10px;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,.15);display:flex;align-items:center;gap:7px">
          <div style="width:11px;height:11px;border-radius:3px;background:${color};flex-shrink:0"></div>
          <div>
            <span style="font-size:12px;font-weight:700;color:#0f172a">${label}</span>
            ${areaHa != null ? `<span style="font-size:10px;color:#64748b;margin-left:5px">${areaHa.toFixed(0)} ha</span>` : ""}
          </div>
        </div>`,
          { sticky: true, permanent: false, direction: "top", opacity: 1 },
        );
        lyr.on("mouseover", function (e) {
          this.setStyle({ fillOpacity: 0.95, weight: 2 });
          this.openTooltip(e.latlng);
        });
        lyr.on("mousemove", function (e) {
          this.getTooltip()?.setLatLng(e.latlng);
        });
        lyr.on("mouseout", function () {
          this.setStyle({ fillOpacity: 0.78, weight: 1 });
          this.closeTooltip();
        });
      },
    },
  ).addTo(targetGroup);
}

export default function MapSection({
  polygons = [],
  selectedPolygonId = null,
  onPolygonCreated,
  onPolygonSelect,
}) {
  const [mode, setMode] = useState('click')

  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const drawControlRef = useRef(null);
  const drawnItemsRef = useRef(new L.FeatureGroup());
  const analysisLayerRef = useRef(new L.FeatureGroup());
  const soilLayerRef = useRef(new L.FeatureGroup());
  const dwLayerRef = useRef(new L.FeatureGroup()); // DW snapshot
  const dwLayerARef = useRef(new L.FeatureGroup()); // change period A
  const dwLayerBRef = useRef(new L.FeatureGroup()); // change period B
  const layerMapRef = useRef(new Map());
  const clickMarkerRef = useRef(null);
  const modeRef = useRef(mode);
  const normalLayerRef = useRef(null);
  const satelliteLayerRef = useRef(null);
  const labelLayerRef = useRef(null);
  const onPolygonCreatedRef = useRef(onPolygonCreated);

  const lastSoilDataRef = useRef(null);
  const lastFarmFeaturesRef = useRef(null);
  const lastCoordsRef = useRef(null);
  const lastDistribRef = useRef(null);
  const lastCenterRef = useRef(null);
  const lastPolyIdRef = useRef(null);

  const [loading, setLoading] = useState(true);
  const [analysing, setAnalysing] = useState(false);
  const [mapView, setMapView] = useState("satellite");
  const [showLandUse, setShowLandUse] = useState(false);

  const [activeLeft, setActiveLeft] = useState("satellite");
  const [activeRight, setActiveRight] = useState("click");

  useEffect(() => {
    modeRef.current = mode;
  }, [mode]);
  useEffect(() => {
    onPolygonCreatedRef.current = onPolygonCreated;
  }, [onPolygonCreated]);

  // ── Soil / farmland layer rendering ──────────────────────────────────────
  function renderLayers(landUse) {
    const soilData = lastSoilDataRef.current;
    const features = lastFarmFeaturesRef.current || [];
    const coords = lastCoordsRef.current;
    const distrib = lastDistribRef.current || [];

    analysisLayerRef.current.clearLayers();
    soilLayerRef.current.clearLayers();

    if (landUse) {
      if (coords) {
        L.geoJSON(
          {
            type: "Feature",
            geometry: {
              type: "Polygon",
              coordinates: [coords.map((c) => [c[1], c[0]])],
            },
            properties: {},
          },
          {
            interactive: false,
            style: {
              color: LAND_COLORS.farmland,
              fillColor: LAND_COLORS.farmland,
              fillOpacity: 0.2,
              weight: 0,
              stroke: false,
            },
          },
        ).addTo(analysisLayerRef.current);
      }
      if (features.length > 0 && coords) {
        const drawnBounds = L.geoJSON({
          type: "Feature",
          geometry: {
            type: "Polygon",
            coordinates: [coords.map((c) => [c[1], c[0]])],
          },
          properties: {},
        }).getBounds();
        features.forEach((feat) => {
          const label = feat.properties?.class || "unknown";
          if (label === "farmland") return;
          const color = LAND_COLORS[label] || "#888";
          const swapped = feat.geometry?.coordinates?.map((ring) =>
            ring.map((pt) => [pt[1], pt[0]]),
          );
          if (!swapped) return;
          if (!drawnBounds.contains(L.polygon(swapped).getBounds().getCenter()))
            return;
          L.polygon(swapped, {
            color,
            fillColor: color,
            fillOpacity: 0.8,
            weight: 1,
            stroke: false,
          })
            .bindTooltip(label.charAt(0).toUpperCase() + label.slice(1), {
              sticky: true,
            })
            .addTo(analysisLayerRef.current);
        });
      }
    } else {
      // ── Soil layer ──────────────────────────────────────────────────────
      const soilColorMap = Object.fromEntries(
        distrib.map((d, i) => [
          d.soil_class,
          SOIL_COLORS[i % SOIL_COLORS.length],
        ]),
      );

      if (soilData?.coverage_geojson?.features?.length > 0) {
        // Real soil coverage GeoJSON from backend — accurate regions
        L.geoJSON(soilData.coverage_geojson, {
          interactive: true,
          style: (feature) => {
            const color =
              soilColorMap[feature.properties?.soil_class] || "#94a3b8";
            return {
              color,
              fillColor: color,
              fillOpacity: 0.75,
              weight: 1,
              opacity: 0.8,
            };
          },
          onEachFeature: (feature, lyr) => {
            const soilClass = feature.properties?.soil_class;
            const pct = feature.properties?.percentage;
            const color = soilColorMap[soilClass] || "#94a3b8";
            lyr.bindTooltip(
              `<div style="background:#fff;padding:5px 10px;border-radius:7px;box-shadow:0 2px 8px rgba(0,0,0,.15);font-family:system-ui;font-size:12px;font-weight:700;color:${color}">
                ${soilClass}${pct != null ? ": " + pct.toFixed(1) + "%" : ""}
              </div>`,
              { sticky: true },
            );
            lyr.on("mouseover", function (e) {
              this.setStyle({ fillOpacity: 0.95 });
              this.openTooltip(e.latlng);
            });
            lyr.on("mousemove", function (e) {
              this.getTooltip()?.setLatLng(e.latlng);
            });
            lyr.on("mouseout", function () {
              this.setStyle({ fillOpacity: 0.75 });
              this.closeTooltip();
            });
          },
        }).addTo(soilLayerRef.current);
      } else if (coords && distrib.length > 0) {
        // Fallback: voronoi approximation if no coverage_geojson
        const polyCoords = coords.map((c) => [c[1], c[0]]);
        const ring = [...polyCoords];
        if (
          ring[0][0] !== ring[ring.length - 1][0] ||
          ring[0][1] !== ring[ring.length - 1][1]
        )
          ring.push(ring[0]);
        const clipPoly = turf.polygon([ring]);
        const bbox = turf.bbox(clipPoly);
        const total = distrib.reduce((s, d) => s + d.percentage, 0);

        const pointFeatures = [];
        distrib.forEach((d) => {
          const count = Math.max(2, Math.round((d.percentage / total) * 30));
          let attempts = 0,
            placed = 0;
          while (placed < count && attempts < 200) {
            attempts++;
            const lng = bbox[0] + Math.random() * (bbox[2] - bbox[0]);
            const lat = bbox[1] + Math.random() * (bbox[3] - bbox[1]);
            const pt = turf.point([lng, lat]);
            if (turf.booleanPointInPolygon(pt, clipPoly)) {
              pt.properties = { soil_class: d.soil_class };
              pointFeatures.push(pt);
              placed++;
            }
          }
        });

        if (pointFeatures.length > 0) {
          try {
            const voronoi = turf.voronoi(
              turf.featureCollection(pointFeatures),
              { bbox },
            );
            voronoi.features.forEach((cell, i) => {
              if (!cell) return;
              const srcPt = pointFeatures[i];
              if (!srcPt) return;
              const soilClass = srcPt.properties.soil_class;
              const color = soilColorMap[soilClass] || "#94a3b8";
              try {
                const clipped = turf.intersect(
                  turf.featureCollection([cell, clipPoly]),
                );
                if (!clipped) return;
                L.geoJSON(clipped, {
                  interactive: true,
                  style: {
                    color,
                    fillColor: color,
                    fillOpacity: 0.7,
                    weight: 0.5,
                    opacity: 0.5,
                  },
                })
                  .bindTooltip(
                    `<div style="background:#fff;padding:5px 10px;border-radius:7px;box-shadow:0 2px 8px rgba(0,0,0,.15);font-family:system-ui;font-size:12px;font-weight:700;color:${color}">
                    ${soilClass}: ${distrib.find((d) => d.soil_class === soilClass)?.percentage.toFixed(1)}%
                  </div>`,
                    { sticky: true },
                  )
                  .addTo(soilLayerRef.current);
              } catch (e) {}
            });
          } catch (e) {
            console.error("Voronoi error:", e);
          }
        }
      }
    }

    soilLayerRef.current.bringToFront();
    analysisLayerRef.current.bringToFront();
    drawnItemsRef.current.bringToFront();
  }

  useEffect(() => {
    if (lastCoordsRef.current) renderLayers(showLandUse);
  }, [showLandUse]); // eslint-disable-line

  // ── Map init ─────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    // ── Global handlers exposed to popup/panel ──

    window.__toggleLandUse = (checked) => {
      setShowLandUse(checked);
      const details = document.getElementById("landuse-details");
      if (details) details.style.display = checked ? "block" : "none";
    };

    // Called by LandCoverPanel after snapshot — fc is the full APIResponse.data
    // Backend returns: { type:'FeatureCollection', features:[...], metadata:{...} }
    // APIResponse wraps it as: { success, message, data: { type, features, metadata } }
    window.__onLandCoverResult = (fc) => {
      dwLayerARef.current.clearLayers();
      dwLayerBRef.current.clearLayers();
      renderDWGeoJSON(fc, dwLayerRef.current, lastCoordsRef.current);
      const map = mapRef.current;
      if (map) {
        dwLayerRef.current.bringToFront();
        drawnItemsRef.current.bringToFront();
      }
    };

    // Called by LandCoverPanel after change detection
    // fcA / fcB are FeatureCollections for period A and B
    window.__onChangeResult = (fcA, fcB) => {
      dwLayerRef.current.clearLayers();
      renderDWGeoJSON(fcA, dwLayerARef.current, lastCoordsRef.current);
      renderDWGeoJSON(fcB, dwLayerBRef.current, lastCoordsRef.current);
      const map = mapRef.current;
      if (map) {
        if (!map.hasLayer(dwLayerARef.current)) dwLayerARef.current.addTo(map);
        map.removeLayer(dwLayerBRef.current);
        drawnItemsRef.current.bringToFront();
      }
    };

    // Toggle which period is shown on map
    window.__showPeriod = (period) => {
      const map = mapRef.current;
      if (!map) return;
      if (period === "A") {
        if (!map.hasLayer(dwLayerARef.current)) dwLayerARef.current.addTo(map);
        if (map.hasLayer(dwLayerBRef.current))
          map.removeLayer(dwLayerBRef.current);
      } else {
        if (!map.hasLayer(dwLayerBRef.current)) dwLayerBRef.current.addTo(map);
        if (map.hasLayer(dwLayerARef.current))
          map.removeLayer(dwLayerARef.current);
      }
      drawnItemsRef.current.bringToFront();
    };

    window.__clearDWLayers = () => {
      dwLayerRef.current.clearLayers();
      dwLayerARef.current.clearLayers();
      dwLayerBRef.current.clearLayers();
    };

    window.__showCropModal = async () => {
      const soilData = lastSoilDataRef.current;
      const center = lastCenterRef.current;
      const polyId = lastPolyIdRef.current;
      if (!center) return;

      const btn = document.getElementById("crop-rec-btn");

      // Try to get ph and nitrogen from soil_quality_by_class
      let ph = null,
        nitrogen = null;
      if (soilData?.soil_quality_by_class?.length > 0) {
        const classes = soilData.soil_quality_by_class;
        const best = classes.reduce(
          (a, b) =>
            (a?.area_percentage || 0) >= (b?.area_percentage || 0) ? a : b,
          classes[0],
        );
        const ph = best?.quality?.ph ?? best?.properties?.ph;
        const nitrogen = best?.quality?.nitrogen ?? best?.properties?.nitrogen;
      }
      // Fallback: overall_weighted_quality
      if (
        (ph == null || nitrogen == null) &&
        soilData?.overall_weighted_quality
      ) {
        ph = ph ?? soilData.overall_weighted_quality.ph;
        nitrogen = nitrogen ?? soilData.overall_weighted_quality.nitrogen;
      }

      if (ph == null || nitrogen == null) {
        if (btn) {
          btn.innerHTML = "⚠️ No soil quality data";
          btn.disabled = true;
          btn.style.background = "#94a3b8";
        }
        return;
      }

      if (btn) {
        btn.disabled = true;
        btn.innerHTML = "⏳ Fetching…";
        btn.style.opacity = "0.7";
      }
      try {
        const result = await getCropRecommendation(
          ph,
          nitrogen,
          center.lat,
          center.lng,
        );
        const crops = result?.data?.recommendedCrops || [];
        const weather = result?.weather || {};

        const weatherHtml = `
          <div style="display:flex;gap:6px;margin-bottom:10px;flex-wrap:wrap">
            <div style="background:#eff6ff;border-radius:6px;padding:4px 8px;font-size:10px;color:#2563eb;font-weight:600">🌡️ ${weather.temperature?.toFixed(1)}°C</div>
            <div style="background:#f0fdf4;border-radius:6px;padding:4px 8px;font-size:10px;color:#16a34a;font-weight:600">💧 ${weather.humidity?.toFixed(0)}%</div>
            <div style="background:#faf5ff;border-radius:6px;padding:4px 8px;font-size:10px;color:#7c3aed;font-weight:600">🌧️ ${weather.rainfall?.toFixed(1)}mm</div>
          </div>`;
        const cropHtml = crops
          .map(
            (c, i) => `
          <div style="display:flex;align-items:center;gap:8px;padding:6px 0;${i < crops.length - 1 ? "border-bottom:1px solid #f1f5f9" : ""}">
            <span style="font-size:18px">${getCropEmoji(c.crop)}</span>
            <div style="flex:1">
              <div style="font-size:12px;font-weight:700;color:#0f172a;text-transform:capitalize">${c.crop}</div>
              <div style="height:4px;border-radius:99px;background:#f1f5f9;margin-top:3px;overflow:hidden">
                <div style="height:100%;width:${c.confidence}%;background:${i === 0 ? "#16a34a" : i === 1 ? "#2563eb" : "#7c3aed"};border-radius:99px"></div>
              </div>
            </div>
            <span style="font-size:11px;font-weight:600;color:#64748b">${c.confidence.toFixed(1)}%</span>
          </div>`,
          )
          .join("");

        const resultDiv = document.getElementById("crop-result-area");
        if (resultDiv) {
          resultDiv.style.display = "block";
          resultDiv.innerHTML = `
            <div style="font-size:11px;font-weight:700;color:#374151;text-transform:uppercase;letter-spacing:.5px;margin-bottom:8px">🌾 Crop Recommendations</div>
            ${weatherHtml}
            ${cropHtml || '<div style="font-size:12px;color:#94a3b8">No recommendations</div>'}`;
        }
        if (btn) btn.style.display = "none";
        if (polyId && onPolygonCreatedRef.current) {
          onPolygonCreatedRef.current({
            id: polyId,
            _cropUpdate: true,
            cropRecommendations: crops,
            weather,
          });
        }
      } catch (err) {
        console.error("Crop error:", err);
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = "🌾 Show Crop Recommendation";
          btn.style.opacity = "1";
        }
      }
    };


    const map = L.map(containerRef.current, {
      center: [20.5937, 78.9629],
      zoom: 5,
      minZoom: 4,
      maxZoom: 19,
      maxBoundsViscosity: 1.0,
    });
   

    const normalLayer = L.tileLayer(
      "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
      { attribution: "© OpenStreetMap contributors", maxZoom: 19 },
    );
    normalLayer.addTo(map);
    normalLayerRef.current = normalLayer;
    satelliteLayerRef.current = L.tileLayer(
      "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      { attribution: "© Esri", maxZoom: 19 },
    );
    labelLayerRef.current = L.tileLayer(
      "https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
      { attribution: "", maxZoom: 19, pane: "overlayPane" },
    );

    map.whenReady(() => setLoading(false));

    drawnItemsRef.current.addTo(map);
    analysisLayerRef.current.addTo(map);
    soilLayerRef.current.addTo(map);
    dwLayerRef.current.addTo(map);
    dwLayerARef.current.addTo(map);
    // dwLayerB starts hidden; added only when period B selected
    // dwLayerBRef.current.addTo(map) — NOT added here, added on demand

    const dc = new L.Control.Draw({
      edit: { featureGroup: drawnItemsRef.current, remove: true },
      draw: {
        polygon: {
          allowIntersection: false,
          showArea: false,
          shapeOptions: {
            color: "#2563eb",
            fillColor: "#3b82f6",
            fillOpacity: 0.25,
            weight: 2,
          },
        },
        polyline: false,
        rectangle: false,
        circle: false,
        marker: false,
        circlemarker: false,
      },
    });
    drawControlRef.current = dc;
    mapRef.current = map;

    // ── Click mode ──
    map.on("click", async (e) => {
      if (modeRef.current !== "click") return;
      const { lat, lng } = e.latlng;
      if (clickMarkerRef.current) {
        map.removeLayer(clickMarkerRef.current);
        clickMarkerRef.current = null;
      }
      const pinSvg = renderToStaticMarkup(
        <MapPin size={18} className="text-white" strokeWidth={2.5} />
      );      
      const icon = L.divIcon({
        html: `<div style="background:green;width:30px;height:30px;display:flex;align-items:center;justify-content:center;border:2px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,.3);border-radius:50% 50% 50% 0;transform:rotate(-45deg)">
        <div style="transform:rotate(45deg);display:flex">${pinSvg}</div>
      </div>`,
        iconSize: [30, 30],
        iconAnchor: [15, 30],
        className: "",
      });
      const marker = L.marker([lat, lng], { icon }).addTo(map);
      clickMarkerRef.current = marker;
      marker
        .bindPopup(
          `<div style="min-width:200px"><b>📍 Loading…</b><br/><small>${lat.toFixed(5)}, ${lng.toFixed(5)}</small></div>`,
        )
        .openPopup();
      const [geoRes, soilRes] = await Promise.allSettled([
        fetch(
          `https://nominatim.openstreetmap.org/reverse?lat=${lat}&lon=${lng}&format=json&accept-language=en`,
        ).then((r) => r.json()),
        getSoilByPoint(lat, lng),
      ]);
      if (!clickMarkerRef.current) return;
      const addr =
        geoRes.status === "fulfilled" ? geoRes.value.address || {} : {};
      const place =
        addr.village ||
        addr.suburb ||
        addr.town ||
        addr.city ||
        addr.county ||
        addr.state ||
        "Unknown area";
      const dist = addr.county || addr.state_district || "";
      const state = addr.state || "";
      const soil = soilRes.status === "fulfilled" ? soilRes.value?.data?.data?.soil_type : null;
      marker.setPopupContent(`
        <div style="min-width:210px;font-family:system-ui,sans-serif">
          <div style="font-size:14px;font-weight:700;color:#0f172a">${place}</div>
          ${dist ? `<div style="font-size:12px;color:#4b5563;margin-top:2px">📍 ${dist}${state ? ", " + state : ""}</div>` : ""}
          <hr style="margin:8px 0;border:none;border-top:1px solid #e5e7eb"/>
          <div style="background:#f0fdf4;border-radius:8px;padding:8px 10px">
            <div style="font-size:10px;color:#64748b;font-weight:600;text-transform:uppercase;letter-spacing:.5px">Soil Type</div>
            <div style="font-size:13px;font-weight:700;color:#15803d">${soil || "Unavailable"}</div>
          </div>
          <div style="margin-top:6px;font-size:10px;font-family:monospace;color:#9ca3af">${lat.toFixed(5)}, ${lng.toFixed(5)}</div>
        </div>`);
      marker.openPopup();
    });

    // ── Draw mode ──
    map.on(L.Draw.Event.CREATED, async (event) => {
      const layer = event.layer;
      drawnItemsRef.current.addLayer(layer);
      const raw = layer.getLatLngs();
      const ring = Array.isArray(raw[0]) ? raw[0] : raw;
      const coords = ring.map((ll) => [ll.lat, ll.lng]);
      const area = ring.length > 0 ? L.GeometryUtil.geodesicArea(ring) : 0;
      polyCount++;
      const id = `poly-${Date.now()}-${polyCount}`;
      const name = `Polygon ${polyCount}`;
      layerMapRef.current.set(id, layer);

      const centerLat = coords.reduce((s, c) => s + c[0], 0) / coords.length;
      const centerLng = coords.reduce((s, c) => s + c[1], 0) / coords.length;

      layer
        .bindPopup(
          `
        <div style="min-width:220px;font-family:system-ui,sans-serif">
          <b>${name}</b> · ${formatArea(area)}<br/>
          <div style="margin-top:8px;display:flex;align-items:center;gap:8px;color:#64748b;font-size:12px">
            <div style="width:16px;height:16px;border:2px solid #2563eb;border-top-color:transparent;border-radius:50%;animation:spin .8s linear infinite"></div>
            Analysing…
          </div>
          <style>@keyframes spin{to{transform:rotate(360deg)}}</style>
        </div>`,
        )
        .openPopup();

      layer.on("click", () => {
        if (onPolygonSelect) onPolygonSelect(id);
      });
      if (onPolygonCreatedRef.current)
        onPolygonCreatedRef.current({
          id,
          name,
          coordinates: coords,
          area,
          status: "loading",
        });

      setAnalysing(true);
      const [soilRes, farmRes] = await Promise.allSettled([
        getSoilByPolygon(coords),
        analyseFarmland(coords),
      ]);
      setAnalysing(false);
      console.log("soilres: ",soilRes)
      console.log("farmRes:",farmRes)
      const soilData =
        soilRes.status === "fulfilled" ? soilRes.value?.data?.data : null;
      const farmGeoJson =
        farmRes.status === "fulfilled" ? farmRes.value?.data?.data : null;
      const distrib = soilData?.distribution || [];
      const features = farmGeoJson?.features || [];

      lastSoilDataRef.current = soilData;
      lastFarmFeaturesRef.current = features;
      lastCoordsRef.current = coords;
      lastDistribRef.current = distrib;
      lastCenterRef.current = { lat: centerLat, lng: centerLng };
      lastPolyIdRef.current = id;

      window.__clearDWLayers?.();
      setShowLandUse(false);
      renderLayers(false);

      const soilRows = distrib
        .map(
          (d, i) => `
        <div style="display:flex;align-items:center;gap:6px;margin-bottom:4px">
          <div style="width:10px;height:10px;border-radius:3px;background:${SOIL_COLORS[i % SOIL_COLORS.length]};flex-shrink:0"></div>
          <div style="flex:1;font-size:12px;color:#374151">${d.soil_class}</div>
          <div style="font-size:12px;font-weight:600;color:#0f172a">${d.percentage?.toFixed(1)}%</div>
        </div>`,
        )
        .join("");

      const qualityByClass = soilData?.soil_quality_by_class || [];
      const overallQ = soilData?.overall_weighted_quality || null;
      const sqiColor = (sqi) =>
        sqi >= 0.8 ? "#16a34a" : sqi >= 0.5 ? "#d97706" : "#dc2626";
      const sqiLabel = (sqi) =>
        sqi >= 0.8 ? "Good" : sqi >= 0.5 ? "Average" : "Poor";
      const qualityRows = qualityByClass
        .map((cls) => {
          const sqi = cls.properties?.soil_quality_index;
          if (sqi == null) return "";
          const color = sqiColor(sqi);
          return `<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px">
          <div style="font-size:11px;color:#374151">${cls.soil_class}</div>
          <div style="display:flex;align-items:center;gap:5px">
            <span style="font-size:11px;font-weight:700;color:${color}">${sqi.toFixed(2)}</span>
            <span style="font-size:10px;background:${color}20;color:${color};border-radius:4px;padding:1px 5px;font-weight:600">${sqiLabel(sqi)}</span>
          </div>
        </div>`;
        })
        .join("");
      const paramRows = overallQ
        ? `
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:4px;margin-top:6px">
          ${[
          ["pH", overallQ.ph, ""],
          ["Nitrogen", overallQ.nitrogen, " g/kg"],
          ["SOC", overallQ.soc, " %"],
          ["CEC", overallQ.cec, " cmol/kg"],
          ["Bulk Density", overallQ.bulk_density, " g/cm³"],
        ]
          .map(
            ([label, val, unit]) => `
            <div style="background:#f8fafc;border-radius:6px;padding:5px 7px">
              <div style="font-size:9px;color:#94a3b8;font-weight:600;text-transform:uppercase">${label}</div>
              <div style="font-size:11px;font-weight:700;color:#0f172a">${val?.toFixed(3)}${unit}</div>
            </div>`,
          )
          .join("")}
        </div>`
        : "";

      const landCount = features.reduce((acc, f) => {
        const l = f.properties?.class || "unknown";
        acc[l] = (acc[l] || 0) + 1;
        return acc;
      }, {});

      layer.setPopupContent(`
        <div style="min-width:260px;max-height:500px;overflow-y:auto;font-family:system-ui,sans-serif">
          <div style="font-size:14px;font-weight:700;color:#0f172a">${name}</div>
          <div style="font-size:11px;color:#64748b;margin-top:2px">${coords.length} pts · ${formatArea(area)}</div>
          <hr style="margin:10px 0;border:none;border-top:1px solid #e5e7eb"/>
          <div style="font-size:11px;font-weight:700;color:#374151;text-transform:uppercase;letter-spacing:.5px;margin-bottom:8px">🌱 Soil Distribution</div>
          ${distrib.length > 0 ? soilRows : '<div style="font-size:12px;color:#94a3b8">No soil data</div>'}
          <hr style="margin:10px 0;border:none;border-top:1px solid #e5e7eb"/>
          <div style="font-size:11px;font-weight:700;color:#374151;text-transform:uppercase;letter-spacing:.5px;margin-bottom:8px">🧪 Soil Quality</div>
          ${qualityRows}${paramRows}
          <hr style="margin:10px 0;border:none;border-top:1px solid #e5e7eb"/>
          <label style="display:flex;align-items:center;gap:8px;cursor:pointer;padding:6px 0">
            <input type="checkbox" id="landuse-toggle" onchange="window.__toggleLandUse(this.checked)" style="width:15px;height:15px;cursor:pointer;accent-color:#2563eb"/>
            <span style="font-size:12px;font-weight:600;color:#374151">🛰️ Show Land Use</span>
          </label>
          <div id="landuse-details" style="display:none;margin-top:4px;padding:8px 10px;background:#f8fafc;border-radius:8px;border:1px solid #e2e8f0">
            ${Object.entries(landCount)
          .map(
            ([label, count]) => `
              <div style="display:flex;align-items:center;gap:6px;margin-bottom:4px">
                <div style="width:10px;height:10px;border-radius:3px;background:${LAND_COLORS[label] || "#888"};flex-shrink:0"></div>
                <div style="flex:1;font-size:12px;color:#374151;text-transform:capitalize">${label}</div>
                <div style="font-size:11px;color:#64748b">${count} zone${count > 1 ? "s" : ""}</div>
              </div>`,
          )
          .join("")}
          </div>
          <hr style="margin:10px 0;border:none;border-top:1px solid #e5e7eb"/>
          <button id="crop-rec-btn" onclick="window.__showCropModal()" style="width:100%;padding:9px 12px;background:#16a34a;color:#fff;border:none;border-radius:8px;font-size:12px;font-weight:600;cursor:pointer">
            🌾 Show Crop Recommendation
          </button>
          <div id="crop-result-area" style="display:none;margin-top:10px"></div>
        </div>`);
      layer.openPopup();

      if (onPolygonCreatedRef.current)
        onPolygonCreatedRef.current({
          id,
          name,
          coordinates: coords,
          area,
          status: "done",
          soilDistribution: distrib,
          landUse: landCount,
          soilQualityByClass: soilData?.soil_quality_by_class || [],
          overallQuality: soilData?.overall_weighted_quality || null,
          cropRecommendations: null,
          weather: null,
        });
    });

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []); // eslint-disable-line

  useEffect(() => {
    const map = mapRef.current,
      norm = normalLayerRef.current,
      sat = satelliteLayerRef.current,
      label = labelLayerRef.current;
    if (!map || !norm || !sat || !label) return;
    if (mapView === "satellite") {
      if (map.hasLayer(norm)) map.removeLayer(norm);
      if (!map.hasLayer(sat)) {
        sat.addTo(map);
        sat.bringToBack();
      }
      if (!map.hasLayer(label)) label.addTo(map);
    } else {
      if (map.hasLayer(sat)) map.removeLayer(sat);
      if (map.hasLayer(label)) map.removeLayer(label);
      if (!map.hasLayer(norm)) {
        norm.addTo(map);
        norm.bringToBack();
      }
    }
  }, [mapView]);

  useEffect(() => {
    const map = mapRef.current,
      dc = drawControlRef.current;
    if (!map || !dc) return;
    if (mode === "draw") {
      dc.addTo(map);
      map.getContainer().style.cursor = "crosshair";
      if (clickMarkerRef.current) {
        map.removeLayer(clickMarkerRef.current);
        clickMarkerRef.current = null;
      }
    } else {
      document.dispatchEvent(
        new KeyboardEvent("keydown", {
          keyCode: 27,
          key: "Escape",
          bubbles: true,
        }),
      );
      dc.remove();
      map.getContainer().style.cursor = "";
    }
  }, [mode]);

  useEffect(() => {
    layerMapRef.current.forEach((layer, id) => {
      layer.setStyle(
        id === selectedPolygonId
          ? {
            color: "#dc2626",
            fillColor: "#ef4444",
            fillOpacity: 0.3,
            weight: 3,
          }
          : {
            color: "#2563eb",
            fillColor: "#3b82f6",
            fillOpacity: 0.25,
            weight: 2,
          },
      );
    });
  }, [selectedPolygonId]);

  useEffect(() => {
    const ids = new Set(polygons.map((p) => p.id));
    layerMapRef.current.forEach((layer, id) => {
      if (!ids.has(id)) {
        drawnItemsRef.current.removeLayer(layer);
        layerMapRef.current.delete(id);
        analysisLayerRef.current.clearLayers();
        soilLayerRef.current.clearLayers();
        window.__clearDWLayers?.();
      }
    });
  }, [polygons]);

  const btnClass = (isActive) =>
    `p-2 border rounded-xl cursor-pointer transition-all duration-150 shadow-sm
     ${isActive
      ? "bg-green-50 border-green-700 shadow-inner text-white scale-95"
      : "bg-white border-neutral-300 text-neutral-500 hover:bg-neutral-50 hover:border-neutral-400 active:scale-95"
    }`;

  return (
    <div
      className="relative w-full h-full">
      {loading && (
        <div
          className= "animate-fade-in bg-gradient-to-tl from-white to-neutral-300  h-full w-full flex flex-col items-center justify-center gap-4 absolute z-50"
          
        >
          <div
          className= "animate-spin w-12 h-12 border-4 border-neutral-300 border-t-green-800 rounded-full" />
            
          <div className="text-xl font-bold text-neutral-600">Loading map…</div>
          {/* <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style> */}
        </div>
      )}
      {analysing && (
        <div
          style={{
            position: "absolute",
            bottom: 80,
            left: "50%",
            transform: "translateX(-50%)",
            zIndex: 1000,
            background: "#1e293b",
            color: "#fff",
            padding: "8px 18px",
            borderRadius: 999,
            fontSize: 12,
            fontWeight: 600,
            display: "flex",
            alignItems: "center",
            gap: 8,
            boxShadow: "0 4px 12px rgba(0,0,0,.25)",
          }}
        >
          <div
            style={{
              width: 14,
              height: 14,
              border: "2px solid rgba(255,255,255,.3)",
              borderTop: "2px solid #fff",
              borderRadius: "50%",
              animation: "spin .8s linear infinite",
            }}
          />
          Analysing polygon…
        </div>
      )}


      <div className="absolute h-15 w-auto px-5 bg-gradient-to-b flex gap-2 items-center justify-evenly from-white to-neutral-200 rounded-xl shadow-md border border-neutral-300 z-[1000] bottom-8 left-1/2 -translate-x-1/2">
        <div className="flex gap-2 border-r pr-4 r border-neutral-300">
          <Tooltip content="Normal view" placement="top">
            <button
              className={btnClass(activeLeft === "map")}
              onClick={() => {
                setActiveLeft("map")
                setMapView("normal")
              }}
            ><Mapview className="text-neutral-500" /></button>
          </Tooltip>
          <Tooltip content="Satellite view" placement="top">
            <button
              className={btnClass(activeLeft === "satellite")}
              onClick={() => {
                setActiveLeft("satellite")
                setMapView("satellite")
              }}
            ><Satellite className="text-neutral-500" /></button>
          </Tooltip>
        </div>
        <div className="flex gap-2 pl-4">
          <Tooltip content="Click to get soil info" placement="top">
            <button
              className={btnClass(activeRight === "click")}
              onClick={() => {
                setActiveRight("click")
                setMode("click")
              }}
            ><MousePointer2 className="text-neutral-500" /></button>
          </Tooltip>
          <Tooltip content="Draw polygon to analyse area" placement="top">
            <button className={btnClass(activeRight === "draw")}
              onClick={() => {
                setActiveRight("draw")
                setMode("draw")
              }}
            ><Pen className="text-neutral-500" /></button>
          </Tooltip>
        </div>
      </div>

      <div ref={containerRef} className="w-full h-full" />
    </div>
  );
}

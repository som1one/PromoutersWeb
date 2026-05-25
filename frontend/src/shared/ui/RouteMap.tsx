import { useEffect, useMemo, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

import type { PhotoReport, RoutePoint, RouteRecord } from '../api/routes';
import type { GeoPingRecord } from '../api/sessions';
import { formatDateTime, photoStatusLabel, pointTypeLabel } from '../route-utils';

type RouteMapProps = {
  route: RouteRecord;
  photos?: PhotoReport[];
  geoPings?: GeoPingRecord[];
  height?: number;
};

const tileLayers = {
  light: {
    url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  },
  satellite: {
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attribution: 'Tiles &copy; Esri',
  },
};

function makePinIcon(label: string, tone: 'start' | 'finish' | 'checkpoint' | 'photo' | 'live') {
  const cls = `route-map-pin route-map-pin-${tone}`;
  return L.divIcon({
    className: cls,
    html: `<span>${label}</span>`,
    iconSize: tone === 'photo' ? [30, 30] : tone === 'live' ? [22, 22] : [34, 34],
    iconAnchor: tone === 'photo' ? [15, 15] : tone === 'live' ? [11, 11] : [17, 17],
    popupAnchor: [0, -16],
  });
}

const ICONS = {
  start: makePinIcon('S', 'start'),
  finish: makePinIcon('F', 'finish'),
  checkpoint: (n: number) => makePinIcon(String(n), 'checkpoint'),
  stop: (n: number) => makePinIcon(String(n), 'checkpoint'),
  photo: makePinIcon('📷', 'photo'),
  live: makePinIcon('●', 'live'),
};

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function pointPhotos(point: RoutePoint, photos: PhotoReport[]) {
  return photos.filter((photo) => photo.point_id === point.id);
}

function buildPointPopup(point: RoutePoint, photos: PhotoReport[]) {
  const matchingPhotos = pointPhotos(point, photos);
  const header = `<div class="map-popup-head"><strong>${point.sequence}. ${escapeHtml(point.name)}</strong>
    <span class="map-popup-tag">${pointTypeLabel(point.point_type)}</span></div>`;
  const address = point.address
    ? `<div class="map-popup-row">${escapeHtml(point.address)}</div>`
    : '';
  const coords =
    point.latitude !== null && point.longitude !== null
      ? `<div class="map-popup-row map-popup-muted">${Number(point.latitude).toFixed(5)}, ${Number(point.longitude).toFixed(5)}</div>`
      : '';
  const notes = point.notes
    ? `<div class="map-popup-row">${escapeHtml(point.notes)}</div>`
    : '';

  let photoBlock = '';
  if (matchingPhotos.length) {
    const first = matchingPhotos[0];
    photoBlock = `
      <div class="map-popup-photo">
        <img src="${escapeHtml(first.file_url)}" alt="${escapeHtml(point.name)}" />
        <div class="map-popup-row map-popup-muted">${formatDateTime(first.captured_at)} · ${photoStatusLabel(first.status)}</div>
        ${first.notes ? `<div class="map-popup-row">${escapeHtml(first.notes)}</div>` : ''}
        ${matchingPhotos.length > 1 ? `<div class="map-popup-row map-popup-muted">+${matchingPhotos.length - 1} ещё</div>` : ''}
      </div>
    `;
  } else {
    photoBlock = '<div class="map-popup-row map-popup-empty">Фотоотчёт не загружен</div>';
  }

  return `<div class="map-popup">${header}${address}${coords}${notes}${photoBlock}</div>`;
}

function buildPhotoPopup(photo: PhotoReport) {
  return `
    <div class="map-popup">
      <div class="map-popup-head">
        <strong>${escapeHtml(photo.point_name ?? 'Фотоотчёт')}</strong>
        <span class="map-popup-tag">${photoStatusLabel(photo.status)}</span>
      </div>
      <div class="map-popup-photo">
        <img src="${escapeHtml(photo.file_url)}" alt="photo" />
        <div class="map-popup-row map-popup-muted">${formatDateTime(photo.captured_at)}</div>
        ${photo.notes ? `<div class="map-popup-row">${escapeHtml(photo.notes)}</div>` : ''}
      </div>
    </div>
  `;
}

export function RouteMap({ route, photos = [], geoPings = [], height = 480 }: RouteMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<L.Map | null>(null);
  const tileLayerRef = useRef<L.TileLayer | null>(null);
  const layersRef = useRef<{
    points: L.LayerGroup;
    track: L.LayerGroup;
    photos: L.LayerGroup;
    live: L.LayerGroup;
  } | null>(null);
  const [layerName, setLayerName] = useState<keyof typeof tileLayers>('light');
  const [showTrack, setShowTrack] = useState(true);
  const [showPhotos, setShowPhotos] = useState(true);
  const hasCoords = useMemo(
    () => route.points.some((p) => p.latitude !== null && p.longitude !== null),
    [route.points],
  );

  // 1. Инициализируем карту один раз
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = L.map(containerRef.current, {
      zoomControl: true,
      scrollWheelZoom: true,
      attributionControl: true,
      worldCopyJump: true,
    });
    mapRef.current = map;

    const layer = L.tileLayer(tileLayers.light.url, {
      maxZoom: 19,
      attribution: tileLayers.light.attribution,
    }).addTo(map);
    tileLayerRef.current = layer;

    layersRef.current = {
      points: L.layerGroup().addTo(map),
      track: L.layerGroup().addTo(map),
      photos: L.layerGroup().addTo(map),
      live: L.layerGroup().addTo(map),
    };

    return () => {
      map.remove();
      mapRef.current = null;
      tileLayerRef.current = null;
      layersRef.current = null;
    };
  }, []);

  // 2. Переключение слоёв (light/satellite)
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (tileLayerRef.current) {
      tileLayerRef.current.remove();
    }
    const cfg = tileLayers[layerName];
    tileLayerRef.current = L.tileLayer(cfg.url, {
      maxZoom: 19,
      attribution: cfg.attribution,
    }).addTo(map);
  }, [layerName]);

  // 3. Перерисовка маркеров и линий при смене данных
  useEffect(() => {
    const map = mapRef.current;
    const layers = layersRef.current;
    if (!map || !layers) return;

    layers.points.clearLayers();
    layers.track.clearLayers();
    layers.photos.clearLayers();
    layers.live.clearLayers();

    const validPoints = route.points
      .filter((point) => point.latitude !== null && point.longitude !== null)
      .map((point) => ({
        ...point,
        latLng: L.latLng(Number(point.latitude), Number(point.longitude)),
      }));

    if (validPoints.length === 0) {
      return;
    }

    // Точки маршрута
    validPoints.forEach((point) => {
      const icon =
        point.point_type === 'start'
          ? ICONS.start
          : point.point_type === 'finish'
            ? ICONS.finish
            : ICONS.checkpoint(point.sequence);
      const marker = L.marker(point.latLng, { icon, title: point.name });
      marker.bindPopup(buildPointPopup(point, photos), {
        maxWidth: 280,
        className: 'route-map-popup',
      });
      marker.addTo(layers.points);
    });

    // Линия маршрута между точками (плановая)
    if (validPoints.length >= 2) {
      L.polyline(
        validPoints.map((point) => point.latLng),
        { color: '#2f6c52', weight: 4, opacity: 0.85, lineJoin: 'round' },
      ).addTo(layers.points);
    }

    // GPS-трекинг (фактический)
    const trackingPoints = geoPings
      .filter((ping) => ping.latitude !== null && ping.longitude !== null)
      .map((ping) => L.latLng(Number(ping.latitude), Number(ping.longitude)));
    if (trackingPoints.length >= 2) {
      L.polyline(trackingPoints, {
        color: '#1f6feb',
        weight: 3,
        opacity: 0.7,
        dashArray: '6 4',
      }).addTo(layers.track);
    }

    // Live-маркер: последняя зафиксированная GPS-точка
    if (trackingPoints.length > 0) {
      const last = trackingPoints[trackingPoints.length - 1];
      const liveMarker = L.marker(last, { icon: ICONS.live, title: 'Последняя позиция' });
      liveMarker.bindPopup(
        `<div class="map-popup"><div class="map-popup-head"><strong>Последняя позиция</strong></div>
        <div class="map-popup-row map-popup-muted">${last.lat.toFixed(5)}, ${last.lng.toFixed(5)}</div></div>`,
        { maxWidth: 240, className: 'route-map-popup' },
      );
      liveMarker.addTo(layers.live);
      // Пульсирующий радиус
      L.circle(last, {
        radius: 30,
        color: '#1f6feb',
        weight: 2,
        opacity: 0.7,
        fillColor: '#1f6feb',
        fillOpacity: 0.15,
      }).addTo(layers.live);
    }

    // Фотомаркеры (вне точек)
    photos.forEach((photo) => {
      if (
        photo.point_id === null &&
        photo.latitude !== null &&
        photo.longitude !== null
      ) {
        const marker = L.marker(L.latLng(Number(photo.latitude), Number(photo.longitude)), {
          icon: ICONS.photo,
        });
        marker.bindPopup(buildPhotoPopup(photo), {
          maxWidth: 280,
          className: 'route-map-popup',
        });
        marker.addTo(layers.photos);
      }
    });

    // Подгоняем границы карты
    const bounds = L.latLngBounds(validPoints.map((point) => point.latLng));
    trackingPoints.forEach((latLng) => bounds.extend(latLng));
    photos.forEach((photo) => {
      if (photo.latitude !== null && photo.longitude !== null) {
        bounds.extend(L.latLng(Number(photo.latitude), Number(photo.longitude)));
      }
    });
    if (validPoints.length === 1 && trackingPoints.length === 0) {
      map.setView(validPoints[0].latLng, 15);
    } else {
      map.fitBounds(bounds, { padding: [32, 32], maxZoom: 16 });
    }
    setTimeout(() => map.invalidateSize(), 80);
  }, [route, photos, geoPings]);

  // 4. Управляем видимостью слоёв
  useEffect(() => {
    const map = mapRef.current;
    const layers = layersRef.current;
    if (!map || !layers) return;
    if (showTrack) {
      if (!map.hasLayer(layers.track)) map.addLayer(layers.track);
      if (!map.hasLayer(layers.live)) map.addLayer(layers.live);
    } else {
      if (map.hasLayer(layers.track)) map.removeLayer(layers.track);
      if (map.hasLayer(layers.live)) map.removeLayer(layers.live);
    }
  }, [showTrack]);

  useEffect(() => {
    const map = mapRef.current;
    const layers = layersRef.current;
    if (!map || !layers) return;
    if (showPhotos) {
      if (!map.hasLayer(layers.photos)) map.addLayer(layers.photos);
    } else if (map.hasLayer(layers.photos)) {
      map.removeLayer(layers.photos);
    }
  }, [showPhotos]);

  if (!hasCoords) {
    return (
      <div className="route-map-empty">
        Координаты точек маршрута не заданы — карту показать нельзя.
      </div>
    );
  }

  return (
    <div className="route-map-wrap">
      <div className="route-map-toolbar">
        <div className="route-map-toolbar-group">
          <button
            type="button"
            className={`route-map-toggle${layerName === 'light' ? ' is-active' : ''}`}
            onClick={() => setLayerName('light')}
          >
            Карта
          </button>
          <button
            type="button"
            className={`route-map-toggle${layerName === 'satellite' ? ' is-active' : ''}`}
            onClick={() => setLayerName('satellite')}
          >
            Спутник
          </button>
        </div>
        <div className="route-map-toolbar-group">
          <label className="route-map-toggle-label">
            <input
              type="checkbox"
              checked={showTrack}
              onChange={(event) => setShowTrack(event.target.checked)}
            />
            Трек GPS
          </label>
          <label className="route-map-toggle-label">
            <input
              type="checkbox"
              checked={showPhotos}
              onChange={(event) => setShowPhotos(event.target.checked)}
            />
            Фото вне точек
          </label>
        </div>
      </div>
      <div ref={containerRef} className="route-map" style={{ height }} />
      <div className="route-map-legend">
        <span><i className="legend-dot legend-dot-start"></i> Старт</span>
        <span><i className="legend-dot legend-dot-finish"></i> Финиш</span>
        <span><i className="legend-dot legend-dot-checkpoint"></i> Точки</span>
        <span><i className="legend-line legend-line-plan"></i> План</span>
        <span><i className="legend-line legend-line-track"></i> Факт GPS</span>
        <span><i className="legend-dot legend-dot-live"></i> Сейчас</span>
      </div>
    </div>
  );
}

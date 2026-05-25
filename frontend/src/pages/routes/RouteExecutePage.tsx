import { useEffect, useState } from 'react';

import { useAuth } from '../../app/auth/useAuth';
import { fetchSessionPhotos, uploadSessionPhoto } from '../../shared/api/photos';
import { createGeoPing, fetchSessionGeoPings, type GeoPingRecord } from '../../shared/api/sessions';
import {
  fetchRoute,
  fetchRouteSession,
  startRoute,
  type PhotoReport,
  type RouteRecord,
  type SessionSummary,
} from '../../shared/api/routes';
import { useToast } from '../../shared/toast/useToast';
import {
  formatDateTime,
  getLastGeoPing,
  photoStatusLabel,
  photoStatusTone,
  pointTypeLabel,
  routeStatusLabel,
  routeStatusTone,
  sessionStatusLabel,
} from '../../shared/route-utils';
import {
  Accordion,
  AppButton,
  AppLink,
  EmptyState,
  InfoGrid,
  PageIntro,
  SelectField,
  SectionTitle,
  StatusPill,
  Surface,
  TextArea,
  TextInput,
} from '../../shared/ui/AppUI';

function nowForInput() {
  return new Date().toISOString().slice(0, 16);
}

function getBrowserLocation() {
  return new Promise<{ latitude: number; longitude: number }>((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error('Геолокация недоступна на этом устройстве.'));
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (position) => {
        resolve({
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
        });
      },
      () => reject(new Error('Не удалось получить координаты. Разрешите доступ к геолокации.')),
      {
        enableHighAccuracy: true,
        timeout: 8000,
      },
    );
  });
}

export function RouteExecutePage() {
  const routeId = window.location.pathname.split('/')[3] ?? '';
  const { accessToken } = useAuth();
  const { showToast } = useToast();
  const [route, setRoute] = useState<RouteRecord | null>(null);
  const [session, setSession] = useState<SessionSummary | null>(null);
  const [geoPings, setGeoPings] = useState<GeoPingRecord[]>([]);
  const [photos, setPhotos] = useState<PhotoReport[]>([]);
  const [startCoordinates, setStartCoordinates] = useState({ latitude: '', longitude: '' });
  const [geoForm, setGeoForm] = useState({
    capturedAt: nowForInput(),
    latitude: '',
    longitude: '',
    pointId: '',
    source: 'tracking',
  });
  const [photoForm, setPhotoForm] = useState({
    capturedAt: nowForInput(),
    latitude: '',
    longitude: '',
    pointId: '',
    notes: '',
    file: null as File | null,
  });
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (!accessToken || !routeId) {
      return;
    }

    let cancelled = false;
    const token = accessToken;
    const currentRouteId = routeId;

    async function loadState() {
      try {
        const nextRoute = await fetchRoute(token, currentRouteId);
        if (cancelled) {
          return;
        }

        setRoute(nextRoute);

        if (nextRoute.current_session) {
          const [nextSession, nextGeoPings, nextPhotos] = await Promise.all([
            fetchRouteSession(token, currentRouteId),
            fetchSessionGeoPings(token, nextRoute.current_session.id),
            fetchSessionPhotos(token, nextRoute.current_session.id),
          ]);

          if (!cancelled) {
            setSession(nextSession);
            setGeoPings(nextGeoPings);
            setPhotos(nextPhotos);
          }
        }
      } catch (error) {
        if (!cancelled) {
          showToast({
            tone: 'error',
            title: 'Не удалось открыть выполнение',
            description: error instanceof Error ? error.message : undefined,
          });
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    void loadState();

    return () => {
      cancelled = true;
    };
  }, [accessToken, routeId, showToast]);

  async function refreshSessionData(sessionId: string) {
    if (!accessToken || !routeId) {
      return;
    }

    const token = accessToken;
    const currentRouteId = routeId;

    const [nextRoute, nextSession, nextGeoPings, nextPhotos] = await Promise.all([
      fetchRoute(token, currentRouteId),
      fetchRouteSession(token, currentRouteId),
      fetchSessionGeoPings(token, sessionId),
      fetchSessionPhotos(token, sessionId),
    ]);

    setRoute(nextRoute);
    setSession(nextSession);
    setGeoPings(nextGeoPings);
    setPhotos(nextPhotos);
  }

  async function autofillCoordinates(target: 'start' | 'geo' | 'photo') {
    try {
      const position = await getBrowserLocation();

      if (target === 'start') {
        setStartCoordinates({
          latitude: String(position.latitude),
          longitude: String(position.longitude),
        });
      } else if (target === 'geo') {
        setGeoForm((current) => ({
          ...current,
          latitude: String(position.latitude),
          longitude: String(position.longitude),
        }));
      } else {
        setPhotoForm((current) => ({
          ...current,
          latitude: String(position.latitude),
          longitude: String(position.longitude),
        }));
      }
    } catch (error) {
      showToast({
        tone: 'error',
        title: 'Координаты не получены',
        description: error instanceof Error ? error.message : undefined,
      });
    }
  }

  async function handleStartRoute() {
    if (!accessToken || !routeId) {
      return;
    }

    const token = accessToken;
    const currentRouteId = routeId;
    setIsSubmitting(true);
    try {
      const startedSession = await startRoute(token, currentRouteId, {
        captured_at: new Date().toISOString(),
        latitude: Number(startCoordinates.latitude),
        longitude: Number(startCoordinates.longitude),
      });
      await refreshSessionData(startedSession.id);
      showToast({
        tone: 'success',
        title: 'Маршрут начат',
      });
    } catch (error) {
      showToast({
        tone: 'error',
        title: 'Старт не выполнен',
        description: error instanceof Error ? error.message : undefined,
      });
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleAddGeoPing() {
    if (!accessToken || !session) {
      return;
    }

    const token = accessToken;
    setIsSubmitting(true);
    try {
      await createGeoPing(token, session.id, {
        captured_at: new Date(geoForm.capturedAt).toISOString(),
        latitude: Number(geoForm.latitude),
        longitude: Number(geoForm.longitude),
        point_id: geoForm.pointId || null,
        source: geoForm.source as 'tracking' | 'manual' | 'photo' | 'finish' | 'start',
      });
      await refreshSessionData(session.id);
      setGeoForm((current) => ({
        ...current,
        capturedAt: nowForInput(),
        latitude: '',
        longitude: '',
        pointId: '',
      }));
      showToast({
        tone: 'success',
        title: 'GPS сохранен',
      });
    } catch (error) {
      showToast({
        tone: 'error',
        title: 'Не удалось сохранить GPS',
        description: error instanceof Error ? error.message : undefined,
      });
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleUploadPhoto() {
    if (!accessToken || !session || !photoForm.file) {
      return;
    }

    const token = accessToken;
    setIsSubmitting(true);
    try {
      await uploadSessionPhoto(token, session.id, {
        file: photoForm.file,
        capturedAt: new Date(photoForm.capturedAt).toISOString(),
        latitude: Number(photoForm.latitude),
        longitude: Number(photoForm.longitude),
        pointId: photoForm.pointId || null,
        notes: photoForm.notes,
      });
      await refreshSessionData(session.id);
      setPhotoForm({
        capturedAt: nowForInput(),
        latitude: '',
        longitude: '',
        pointId: '',
        notes: '',
        file: null,
      });
      showToast({
        tone: 'success',
        title: 'Фото загружено',
      });
    } catch (error) {
      showToast({
        tone: 'error',
        title: 'Не удалось загрузить фото',
        description: error instanceof Error ? error.message : undefined,
      });
    } finally {
      setIsSubmitting(false);
    }
  }

  if (isLoading) {
    return (
      <Surface>
        <EmptyState title="Загружаем рабочую сессию" />
      </Surface>
    );
  }

  if (!route) {
    return (
      <Surface>
        <EmptyState title="Маршрут не найден" />
      </Surface>
    );
  }

  const lastGeoPing = getLastGeoPing(geoPings);

  return (
    <div className="page-stack">
      <PageIntro
        eyebrow="Выполнение"
        title={route.title}
        description="Старт, GPS и фотоотчеты собраны в короткие раскрывающиеся блоки."
        action={route.status === 'in_progress' ? <AppLink to={`/app/routes/${route.id}/finish`}>Завершить</AppLink> : undefined}
      />

      <Surface>
        <InfoGrid
          items={[
            {
              label: 'Статус маршрута',
              value: <StatusPill tone={routeStatusTone(route.status)}>{routeStatusLabel(route.status)}</StatusPill>,
            },
            {
              label: 'Сессия',
              value: session ? sessionStatusLabel(session.status) : 'Еще не начата',
            },
            {
              label: 'Последний GPS',
              value: lastGeoPing ? formatDateTime(lastGeoPing.captured_at) : 'Нет',
            },
            {
              label: 'Фото',
              value: photos.length,
            },
          ]}
        />
      </Surface>

      {!session ? (
        <Surface>
          <SectionTitle title="Запустить маршрут" subtitle="Сначала зафиксируйте старт" />
          <div className="form-grid">
            <TextInput
              label="Широта"
              value={startCoordinates.latitude}
              onChange={(event) =>
                setStartCoordinates((current) => ({ ...current, latitude: event.target.value }))
              }
              type="number"
              step="0.000001"
              placeholder="53.900000"
            />
            <TextInput
              label="Долгота"
              value={startCoordinates.longitude}
              onChange={(event) =>
                setStartCoordinates((current) => ({ ...current, longitude: event.target.value }))
              }
              type="number"
              step="0.000001"
              placeholder="27.566700"
            />
          </div>
          <div className="action-row">
            <AppButton type="button" variant="ghost" onClick={() => void autofillCoordinates('start')}>
              Определить автоматически
            </AppButton>
            <AppButton type="button" onClick={() => void handleStartRoute()} disabled={isSubmitting}>
              Начать маршрут
            </AppButton>
          </div>
        </Surface>
      ) : (
        <>
          <Surface>
            <Accordion title="Добавить GPS" subtitle="Короткая форма трекинга" defaultOpen>
              <div className="form-grid">
                <TextInput
                  label="Время"
                  type="datetime-local"
                  value={geoForm.capturedAt}
                  onChange={(event) => setGeoForm((current) => ({ ...current, capturedAt: event.target.value }))}
                />
                <SelectField
                  label="Тип точки"
                  value={geoForm.source}
                  onChange={(event) => setGeoForm((current) => ({ ...current, source: event.target.value }))}
                >
                  <option value="tracking">Маршрут</option>
                  <option value="manual">Ручная</option>
                  <option value="photo">Фото</option>
                </SelectField>
                <TextInput
                  label="Широта"
                  type="number"
                  step="0.000001"
                  value={geoForm.latitude}
                  onChange={(event) => setGeoForm((current) => ({ ...current, latitude: event.target.value }))}
                />
                <TextInput
                  label="Долгота"
                  type="number"
                  step="0.000001"
                  value={geoForm.longitude}
                  onChange={(event) => setGeoForm((current) => ({ ...current, longitude: event.target.value }))}
                />
                <SelectField
                  className="field-wide"
                  label="Точка маршрута"
                  value={geoForm.pointId}
                  onChange={(event) => setGeoForm((current) => ({ ...current, pointId: event.target.value }))}
                >
                  <option value="">Без привязки</option>
                  {route.points.map((point) => (
                    <option key={point.id} value={point.id}>
                      {point.sequence}. {point.name} · {pointTypeLabel(point.point_type)}
                    </option>
                  ))}
                </SelectField>
              </div>
              <div className="action-row">
                <AppButton type="button" variant="ghost" onClick={() => void autofillCoordinates('geo')}>
                  Взять координаты
                </AppButton>
                <AppButton type="button" onClick={() => void handleAddGeoPing()} disabled={isSubmitting}>
                  Сохранить GPS
                </AppButton>
              </div>
            </Accordion>

            <Accordion title="Загрузить фото" subtitle="Фото привязывается к сессии">
              <div className="form-grid">
                <TextInput
                  label="Время"
                  type="datetime-local"
                  value={photoForm.capturedAt}
                  onChange={(event) => setPhotoForm((current) => ({ ...current, capturedAt: event.target.value }))}
                />
                <label className="field">
                  <span className="field-label">Файл</span>
                  <input
                    className="field-input"
                    type="file"
                    accept="image/*"
                    onChange={(event) =>
                      setPhotoForm((current) => ({
                        ...current,
                        file: event.target.files?.[0] ?? null,
                      }))
                    }
                  />
                </label>
                <TextInput
                  label="Широта"
                  type="number"
                  step="0.000001"
                  value={photoForm.latitude}
                  onChange={(event) => setPhotoForm((current) => ({ ...current, latitude: event.target.value }))}
                />
                <TextInput
                  label="Долгота"
                  type="number"
                  step="0.000001"
                  value={photoForm.longitude}
                  onChange={(event) => setPhotoForm((current) => ({ ...current, longitude: event.target.value }))}
                />
                <SelectField
                  className="field-wide"
                  label="Точка маршрута"
                  value={photoForm.pointId}
                  onChange={(event) => setPhotoForm((current) => ({ ...current, pointId: event.target.value }))}
                >
                  <option value="">Без привязки</option>
                  {route.points.map((point) => (
                    <option key={point.id} value={point.id}>
                      {point.sequence}. {point.name}
                    </option>
                  ))}
                </SelectField>
                <TextArea
                  className="field-wide"
                  label="Комментарий"
                  value={photoForm.notes}
                  onChange={(event) => setPhotoForm((current) => ({ ...current, notes: event.target.value }))}
                  placeholder="Короткая заметка по фото"
                />
              </div>
              <div className="action-row">
                <AppButton type="button" variant="ghost" onClick={() => void autofillCoordinates('photo')}>
                  Взять координаты
                </AppButton>
                <AppButton
                  type="button"
                  onClick={() => void handleUploadPhoto()}
                  disabled={isSubmitting || !photoForm.file}
                >
                  Загрузить фото
                </AppButton>
              </div>
            </Accordion>
          </Surface>

          <Surface>
            <Accordion title="Последние данные" subtitle="GPS и фото одним списком" defaultOpen>
              <div className="content-grid">
                <div className="list-stack">
                  {geoPings.length ? (
                    geoPings.map((geoPing) => (
                      <article key={geoPing.id} className="list-card list-card-tight">
                        <strong>{geoPing.point_name || 'GPS точка'}</strong>
                        <p>{geoPing.latitude}, {geoPing.longitude}</p>
                        <span>{formatDateTime(geoPing.captured_at)}</span>
                      </article>
                    ))
                  ) : (
                    <EmptyState title="GPS пока нет" />
                  )}
                </div>
                <div className="list-stack">
                  {photos.length ? (
                    photos.map((photo) => (
                      <article key={photo.id} className="list-card list-card-tight">
                        <div className="list-card-top">
                          <strong>{photo.point_name || 'Фото по маршруту'}</strong>
                          <StatusPill tone={photoStatusTone(photo.status)}>
                            {photoStatusLabel(photo.status)}
                          </StatusPill>
                        </div>
                        <p>{photo.notes || 'Без комментария'}</p>
                        <span>{formatDateTime(photo.captured_at)}</span>
                      </article>
                    ))
                  ) : (
                    <EmptyState title="Фото пока нет" />
                  )}
                </div>
              </div>
            </Accordion>
          </Surface>
        </>
      )}
    </div>
  );
}

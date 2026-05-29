import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

import { useAuth } from '../../app/auth/useAuth';
import { fetchRoute, finishRoute, type RouteRecord } from '../../shared/api/routes';
import { useToast } from '../../shared/toast/useToast';
import { formatDateTime, routeStatusLabel, routeStatusTone } from '../../shared/route-utils';
import {
  AppButton,
  AppLink,
  EmptyState,
  InfoGrid,
  PageIntro,
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
      reject(new Error('Геолокация недоступна.'));
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (position) =>
        resolve({
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
        }),
      () => reject(new Error('Не удалось определить координаты.')),
      { enableHighAccuracy: true, timeout: 8000 },
    );
  });
}

export function RouteFinishPage() {
  const routeId = useParams().routeId ?? '';
  const navigate = useNavigate();
  const { accessToken } = useAuth();
  const { showToast } = useToast();
  const [route, setRoute] = useState<RouteRecord | null>(null);
  const [formState, setFormState] = useState({
    capturedAt: nowForInput(),
    latitude: '',
    longitude: '',
    leafletCount: '',
    summary: '',
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

    async function loadRoute() {
      try {
        const nextRoute = await fetchRoute(token, currentRouteId);
        if (!cancelled) {
          setRoute(nextRoute);
        }
      } catch (error) {
        if (!cancelled) {
          showToast({
            tone: 'error',
            title: 'Не удалось открыть завершение',
            description: error instanceof Error ? error.message : undefined,
          });
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    void loadRoute();

    return () => {
      cancelled = true;
    };
  }, [accessToken, routeId, showToast]);

  async function autofillFinishCoordinates() {
    try {
      const position = await getBrowserLocation();
      setFormState((current) => ({
        ...current,
        latitude: String(position.latitude),
        longitude: String(position.longitude),
      }));
    } catch (error) {
      showToast({
        tone: 'error',
        title: 'Координаты не получены',
        description: error instanceof Error ? error.message : undefined,
      });
    }
  }

  async function handleFinishRoute() {
    if (!accessToken || !routeId) {
      return;
    }

    const token = accessToken;
    const currentRouteId = routeId;
    setIsSubmitting(true);
    try {
      await finishRoute(token, currentRouteId, {
        captured_at: new Date(formState.capturedAt).toISOString(),
        latitude: Number(formState.latitude),
        longitude: Number(formState.longitude),
        leaflet_count: Number(formState.leafletCount),
        summary: formState.summary,
      });
      // Перезагружаем маршрут, чтобы получить актуальный статус (completed)
      const updatedRoute = await fetchRoute(token, currentRouteId);
      setRoute(updatedRoute);
      showToast({
        tone: 'success',
        title: 'Маршрут завершен',
      });
      // Даём UI обновиться перед редиректом
      setTimeout(() => navigate(`/app/routes/${routeId}`), 800);
    } catch (error) {
      showToast({
        tone: 'error',
        title: 'Не удалось завершить маршрут',
        description: error instanceof Error ? error.message : undefined,
      });
    } finally {
      setIsSubmitting(false);
    }
  }

  if (isLoading) {
    return (
      <Surface>
        <EmptyState title="Готовим форму завершения" />
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

  return (
    <div className="page-stack">
      <PageIntro
        eyebrow="Финиш"
        title={`Завершение: ${route.title}`}
        description="Короткая форма закрытия смены без визуального перегруза."
        action={<AppLink to={`/app/routes/${route.id}/execute`} variant="ghost">Назад</AppLink>}
      />

      <Surface>
        <InfoGrid
          items={[
            {
              label: 'Статус',
              value: <StatusPill tone={routeStatusTone(route.status)}>{routeStatusLabel(route.status)}</StatusPill>,
            },
            { label: 'Старт сессии', value: formatDateTime(route.current_session?.started_at ?? null) },
            { label: 'Фото', value: route.photo_count },
            { label: 'GPS', value: route.geo_ping_count },
          ]}
        />
      </Surface>

      <Surface>
        <div className="form-grid">
          <TextInput
            label="Время завершения"
            type="datetime-local"
            value={formState.capturedAt}
            onChange={(event) => setFormState((current) => ({ ...current, capturedAt: event.target.value }))}
          />
          <TextInput
            label="Количество листовок"
            type="number"
            min="0"
            value={formState.leafletCount}
            onChange={(event) => setFormState((current) => ({ ...current, leafletCount: event.target.value }))}
          />
          <TextInput
            label="Широта"
            type="number"
            step="0.000001"
            value={formState.latitude}
            onChange={(event) => setFormState((current) => ({ ...current, latitude: event.target.value }))}
          />
          <TextInput
            label="Долгота"
            type="number"
            step="0.000001"
            value={formState.longitude}
            onChange={(event) => setFormState((current) => ({ ...current, longitude: event.target.value }))}
          />
          <TextArea
            className="field-wide"
            label="Краткий итог"
            value={formState.summary}
            onChange={(event) => setFormState((current) => ({ ...current, summary: event.target.value }))}
            placeholder="Например: маршрут закрыт без замечаний, фото приложены, трафик средний."
          />
        </div>

        <div className="action-row">
          <AppButton type="button" variant="ghost" onClick={() => void autofillFinishCoordinates()}>
            Взять координаты
          </AppButton>
          <AppButton type="button" onClick={() => void handleFinishRoute()} disabled={isSubmitting}>
            Завершить маршрут
          </AppButton>
        </div>
      </Surface>
    </div>
  );
}

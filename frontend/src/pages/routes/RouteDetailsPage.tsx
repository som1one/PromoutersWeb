import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';

import { useAuth } from '../../app/auth/useAuth';
import {
  fetchRoute,
  fetchRoutePhotos,
  fetchRouteReport,
  type PhotoReport,
  type RouteRecord,
  type RouteReport,
} from '../../shared/api/routes';
import {
  Accordion,
  AppLink,
  EmptyState,
  InfoGrid,
  PageIntro,
  SectionTitle,
  StatusPill,
  Surface,
} from '../../shared/ui/AppUI';
import {
  formatDate,
  formatDateTime,
  photoStatusLabel,
  photoStatusTone,
  pointTypeLabel,
  routeStatusLabel,
  routeStatusTone,
} from '../../shared/route-utils';
import { useToast } from '../../shared/toast/useToast';

export function RouteDetailsPage() {
  const routeId = useParams().routeId ?? '';
  const { accessToken } = useAuth();
  const { showToast } = useToast();
  const [route, setRoute] = useState<RouteRecord | null>(null);
  const [photos, setPhotos] = useState<PhotoReport[]>([]);
  const [report, setReport] = useState<RouteReport | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!accessToken || !routeId) {
      return;
    }

    let cancelled = false;
    const token = accessToken;
    const currentRouteId = routeId;

    async function loadRoute() {
      try {
        const [nextRoute, nextPhotos] = await Promise.all([
          fetchRoute(token, currentRouteId),
          fetchRoutePhotos(token, currentRouteId),
        ]);

        if (cancelled) {
          return;
        }

        setRoute(nextRoute);
        setPhotos(nextPhotos);

        if (nextRoute.status === 'completed') {
          try {
            const nextReport = await fetchRouteReport(token, currentRouteId);
            if (!cancelled) {
              setReport(nextReport);
            }
          } catch {
            if (!cancelled) {
              setReport(null);
            }
          }
        }
      } catch (error) {
        if (!cancelled) {
          showToast({
            tone: 'error',
            title: 'Не удалось открыть маршрут',
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

  if (isLoading) {
    return (
      <Surface>
        <EmptyState title="Загружаем маршрут" />
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
        eyebrow="Маршрут"
        title={route.title}
        description={route.description || `${formatDate(route.work_date)} · ${route.branch_name}`}
        action={
          <div className="action-row">
            {route.status === 'assigned' ? (
              <AppLink to={`/app/routes/${route.id}/execute`}>Начать</AppLink>
            ) : null}
            {route.status === 'in_progress' ? (
              <>
                <AppLink to={`/app/routes/${route.id}/execute`} variant="ghost">
                  Выполнение
                </AppLink>
                <AppLink to={`/app/routes/${route.id}/finish`}>Завершить</AppLink>
              </>
            ) : null}
          </div>
        }
      />

      <Surface>
        <InfoGrid
          items={[
            {
              label: 'Статус',
              value: <StatusPill tone={routeStatusTone(route.status)}>{routeStatusLabel(route.status)}</StatusPill>,
            },
            { label: 'Промоутер', value: route.promoter_name || 'Не назначен' },
            { label: 'Точек', value: route.points.length },
            { label: 'Плановый старт', value: formatDateTime(route.planned_start_at) },
          ]}
        />
      </Surface>

      <Surface>
        <SectionTitle title="Содержимое маршрута" subtitle="Все спрятано в короткие блоки" />

        <Accordion title="Точки маршрута" subtitle={`${route.points.length} адресов`} defaultOpen>
          <div className="list-stack">
            {route.points.map((point) => (
              <article key={point.id} className="list-card list-card-tight">
                <div className="list-card-top">
                  <strong>{point.sequence}. {point.name}</strong>
                  <StatusPill tone="neutral">{pointTypeLabel(point.point_type)}</StatusPill>
                </div>
                <p>{point.address || 'Адрес не указан'}</p>
                <span>{formatDateTime(point.planned_arrival_at)}</span>
              </article>
            ))}
          </div>
        </Accordion>

        <Accordion title="Фотоотчеты" subtitle={`${photos.length} файлов`}>
          {photos.length ? (
            <div className="gallery-grid">
              {photos.map((photo) => (
                <article key={photo.id} className="media-card">
                  <img src={photo.file_url} alt={photo.point_name || route.title} />
                  <div className="media-card-body">
                    <div className="list-card-top">
                      <strong>{photo.point_name || 'Фото по маршруту'}</strong>
                      <StatusPill tone={photoStatusTone(photo.status)}>
                        {photoStatusLabel(photo.status)}
                      </StatusPill>
                    </div>
                    <p>{photo.notes || 'Без комментария'}</p>
                    <span>{formatDateTime(photo.captured_at)}</span>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <EmptyState title="Фото пока нет" />
          )}
        </Accordion>

        {report ? (
          <Accordion title="Итоговый отчет" subtitle={`${report.total_minutes} минут`}>
            <div className="detail-list">
              <div className="detail-row">
                <span>Листовки</span>
                <strong>{report.leaflet_count}</strong>
              </div>
              <div className="detail-row">
                <span>Фото</span>
                <strong>{report.photo_count}</strong>
              </div>
              <div className="detail-row">
                <span>GPS</span>
                <strong>{report.geo_ping_count}</strong>
              </div>
            </div>
            <p className="support-copy">{report.summary}</p>
          </Accordion>
        ) : null}
      </Surface>
    </div>
  );
}

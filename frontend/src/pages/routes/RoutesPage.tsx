import { useEffect, useMemo, useState } from 'react';

import { useAuth } from '../../app/auth/useAuth';
import { fetchRoutes, type RouteRecord } from '../../shared/api/routes';
import { formatDate, routeStatusLabel, routeStatusTone } from '../../shared/route-utils';
import { useToast } from '../../shared/toast/useToast';
import {
  AppLink,
  EmptyState,
  PageIntro,
  SectionTitle,
  StatusPill,
  Surface,
} from '../../shared/ui/AppUI';

type RouteFilter = 'all' | 'active' | 'completed';

export function RoutesPage() {
  const { accessToken } = useAuth();
  const { showToast } = useToast();
  const [routes, setRoutes] = useState<RouteRecord[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [filter, setFilter] = useState<RouteFilter>('active');

  useEffect(() => {
    if (!accessToken) {
      return;
    }

    let cancelled = false;
    const token = accessToken;

    async function loadRoutes() {
      try {
        const nextRoutes = await fetchRoutes(token);

        if (!cancelled) {
          setRoutes(nextRoutes);
        }
      } catch (error) {
        if (!cancelled) {
          showToast({
            tone: 'error',
            title: 'Не удалось загрузить маршруты',
            description: error instanceof Error ? error.message : undefined,
          });
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    void loadRoutes();

    return () => {
      cancelled = true;
    };
  }, [accessToken, showToast]);

  const visibleRoutes = useMemo(() => {
    if (filter === 'active') {
      return routes.filter((route) => route.status === 'assigned' || route.status === 'in_progress');
    }
    if (filter === 'completed') {
      return routes.filter((route) => route.status === 'completed');
    }
    return routes;
  }, [filter, routes]);

  return (
    <div className="page-stack">
      <PageIntro
        eyebrow="Маршруты"
        title="Компактный список смен"
        description="Только короткие карточки и понятные статусы. Без длинных экранов и лишних блоков."
      />

      <Surface>
        <SectionTitle title="Фильтр" subtitle="Выберите только нужный срез" />
        <div className="segmented">
          <button
            type="button"
            className={`segment${filter === 'active' ? ' segment-active' : ''}`}
            onClick={() => setFilter('active')}
          >
            Активные
          </button>
          <button
            type="button"
            className={`segment${filter === 'all' ? ' segment-active' : ''}`}
            onClick={() => setFilter('all')}
          >
            Все
          </button>
          <button
            type="button"
            className={`segment${filter === 'completed' ? ' segment-active' : ''}`}
            onClick={() => setFilter('completed')}
          >
            Завершенные
          </button>
        </div>
      </Surface>

      <Surface>
        <SectionTitle
          title="Список маршрутов"
          subtitle={isLoading ? 'Загрузка...' : `${visibleRoutes.length} карточек`}
        />

        {isLoading ? (
          <EmptyState title="Собираем маршруты" />
        ) : visibleRoutes.length ? (
          <div className="list-stack">
            {visibleRoutes.map((route) => (
              <article key={route.id} className="list-card">
                <div className="list-card-top">
                  <strong>{route.title}</strong>
                  <StatusPill tone={routeStatusTone(route.status)}>
                    {routeStatusLabel(route.status)}
                  </StatusPill>
                </div>
                <p>{formatDate(route.work_date)} · {route.branch_name}</p>
                <p>{route.promoter_name || 'Промоутер еще не назначен'}</p>
                <div className="mini-stats">
                  <span>{route.points.length} точек</span>
                  <span>{route.photo_count} фото</span>
                  <span>{route.geo_ping_count} GPS</span>
                </div>
                <div className="action-row">
                  <AppLink to={`/app/routes/${route.id}`}>Открыть</AppLink>
                  {route.status === 'assigned' ? (
                    <AppLink to={`/app/routes/${route.id}/execute`} variant="ghost">
                      Начать
                    </AppLink>
                  ) : null}
                  {route.status === 'in_progress' ? (
                    <AppLink to={`/app/routes/${route.id}/finish`} variant="ghost">
                      Завершить
                    </AppLink>
                  ) : null}
                </div>
              </article>
            ))}
          </div>
        ) : (
          <EmptyState title="Маршрутов не найдено" description="Попробуйте другой фильтр." />
        )}
      </Surface>
    </div>
  );
}

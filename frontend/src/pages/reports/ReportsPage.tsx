import { useEffect, useState } from 'react';

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

export function ReportsPage() {
  const { accessToken } = useAuth();
  const { showToast } = useToast();
  const [completedRoutes, setCompletedRoutes] = useState<RouteRecord[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!accessToken) {
      return;
    }

    let cancelled = false;
    const token = accessToken;

    async function loadReports() {
      try {
        const routes = await fetchRoutes(token);
        if (!cancelled) {
          setCompletedRoutes(routes.filter((route) => route.status === 'completed'));
        }
      } catch (error) {
        if (!cancelled) {
          showToast({
            tone: 'error',
            title: 'Не удалось загрузить отчеты',
            description: error instanceof Error ? error.message : undefined,
          });
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    void loadReports();

    return () => {
      cancelled = true;
    };
  }, [accessToken, showToast]);

  return (
    <div className="page-stack">
      <PageIntro
        eyebrow="Отчеты"
        title="Закрытые маршруты"
        description="Только те смены, по которым уже сформирован финальный результат."
      />

      <Surface>
        <SectionTitle
          title="Итоговые карточки"
          subtitle={isLoading ? 'Загрузка...' : `${completedRoutes.length} завершенных маршрутов`}
        />

        {isLoading ? (
          <EmptyState title="Собираем отчеты" />
        ) : completedRoutes.length ? (
          <div className="list-stack">
            {completedRoutes.map((route) => (
              <article key={route.id} className="list-card">
                <div className="list-card-top">
                  <strong>{route.title}</strong>
                  <StatusPill tone={routeStatusTone(route.status)}>
                    {routeStatusLabel(route.status)}
                  </StatusPill>
                </div>
                <p>{formatDate(route.work_date)} · {route.branch_name}</p>
                <div className="mini-stats">
                  <span>{route.photo_count} фото</span>
                  <span>{route.geo_ping_count} GPS</span>
                </div>
                <div className="action-row">
                  <AppLink to={`/app/routes/${route.id}`}>Открыть отчет</AppLink>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <EmptyState title="Завершенных маршрутов пока нет" />
        )}
      </Surface>
    </div>
  );
}

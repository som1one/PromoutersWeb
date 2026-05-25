import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';

import { useAuth } from '../../app/auth/useAuth';
import { fetchBranches, type BranchRecord } from '../../shared/api/branches';
import { fetchRoutes, type RouteRecord } from '../../shared/api/routes';
import {
  formatDate,
  formatDateTime,
  pointTypeLabel,
  routeStatusLabel,
  routeStatusTone,
} from '../../shared/route-utils';
import { useToast } from '../../shared/toast/useToast';
import {
  AppLink,
  EmptyState,
  MetricCard,
  PageIntro,
  SectionTitle,
  StatusPill,
  Surface,
} from '../../shared/ui/AppUI';

type RouteFilter = 'all' | 'draft' | 'active' | 'completed';

export function AdminRoutesPage() {
  const { accessToken } = useAuth();
  const { showToast } = useToast();
  const [searchParams, setSearchParams] = useSearchParams();
  const [routes, setRoutes] = useState<RouteRecord[]>([]);
  const [branches, setBranches] = useState<BranchRecord[]>([]);
  const [filter, setFilter] = useState<RouteFilter>('active');
  const [isLoading, setIsLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const branchFilter = searchParams.get('branchId') ?? '';

  useEffect(() => {
    if (!accessToken) {
      return;
    }

    let cancelled = false;
    const token = accessToken;

    async function loadAll() {
      try {
        const [nextRoutes, nextBranches] = await Promise.all([
          fetchRoutes(token),
          fetchBranches(token).catch(() => [] as BranchRecord[]),
        ]);
        if (!cancelled) {
          setRoutes(nextRoutes);
          setBranches(nextBranches);
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

    void loadAll();

    return () => {
      cancelled = true;
    };
  }, [accessToken, showToast]);

  const branchById = useMemo(
    () => Object.fromEntries(branches.map((b) => [b.id, b])),
    [branches],
  );

  const visibleRoutes = useMemo(() => {
    let result = routes;
    if (branchFilter) {
      result = result.filter((route) => route.branch_id === branchFilter);
    }
    switch (filter) {
      case 'draft':
        return result.filter((route) => route.status === 'draft');
      case 'active':
        return result.filter(
          (route) => route.status === 'assigned' || route.status === 'in_progress',
        );
      case 'completed':
        return result.filter((route) => route.status === 'completed');
      default:
        return result;
    }
  }, [filter, routes, branchFilter]);

  const toggleExpanded = (id: string) =>
    setExpandedId((current) => (current === id ? null : id));

  const clearBranchFilter = () => {
    const next = new URLSearchParams(searchParams);
    next.delete('branchId');
    setSearchParams(next, { replace: true });
  };

  const activeBranch = branchFilter ? branchById[branchFilter] : null;

  return (
    <div className="page-stack">
      <PageIntro
        eyebrow="Маршруты"
        title={activeBranch ? `Маршруты · ${activeBranch.name}` : 'Маршруты филиала'}
        description={
          activeBranch
            ? 'Видны только маршруты выбранного филиала. Снимите фильтр, чтобы увидеть все.'
            : 'Срез по статусам, назначениям и ходу выполнения. Откройте карточку для деталей и точек.'
        }
        action={
          activeBranch ? (
            <button type="button" className="chip-link" onClick={clearBranchFilter}>
              Сбросить филиал
            </button>
          ) : undefined
        }
      />

      <div className="metric-strip">
        <MetricCard label="Всего" value={String(routes.length)} note="Все видимые маршруты" />
        <MetricCard
          label="В работе"
          value={String(routes.filter((route) => route.status === 'in_progress').length)}
          note="Активные сессии"
        />
        <MetricCard
          label="Без промоутера"
          value={String(routes.filter((route) => !route.promoter_id).length)}
          note="Требуют назначения"
        />
      </div>

      <Surface>
        <SectionTitle title="Фильтр" subtitle="Оставьте только нужные карточки" />
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
            className={`segment${filter === 'draft' ? ' segment-active' : ''}`}
            onClick={() => setFilter('draft')}
          >
            Черновики
          </button>
          <button
            type="button"
            className={`segment${filter === 'completed' ? ' segment-active' : ''}`}
            onClick={() => setFilter('completed')}
          >
            Завершенные
          </button>
          <button
            type="button"
            className={`segment${filter === 'all' ? ' segment-active' : ''}`}
            onClick={() => setFilter('all')}
          >
            Все
          </button>
        </div>
      </Surface>

      <Surface>
        <SectionTitle
          title="Маршруты"
          subtitle={isLoading ? 'Загрузка...' : `${visibleRoutes.length} карточек`}
        />

        {isLoading ? (
          <EmptyState title="Собираем данные по маршрутам" />
        ) : visibleRoutes.length ? (
          <div className="list-stack">
            {visibleRoutes.map((route) => {
              const isExpanded = expandedId === route.id;
              return (
                <article key={route.id} className="route-row-card">
                  <button
                    type="button"
                    className="route-row-summary"
                    onClick={() => toggleExpanded(route.id)}
                    aria-expanded={isExpanded}
                  >
                    <div className="route-row-main">
                      <strong>{route.title}</strong>
                      <span>
                        {formatDate(route.work_date)} · {route.branch_name}
                      </span>
                      <span className="route-row-promoter">
                        {route.promoter_name || 'Промоутер не назначен'}
                      </span>
                    </div>
                    <div className="route-row-meta">
                      <StatusPill tone={routeStatusTone(route.status)}>
                        {routeStatusLabel(route.status)}
                      </StatusPill>
                      <span className={`route-row-chevron${isExpanded ? ' is-open' : ''}`}>
                        <svg
                          width="16"
                          height="16"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        >
                          <polyline points="6 9 12 15 18 9" />
                        </svg>
                      </span>
                    </div>
                  </button>

                  {isExpanded ? (
                    <div className="route-row-body">
                      <div className="mini-stats">
                        <span>{route.points.length} точек</span>
                        <span>{route.photo_count} фото</span>
                        <span>{route.geo_ping_count} GPS</span>
                      </div>

                      <div className="detail-list">
                        {route.planned_start_at ? (
                          <div className="detail-row">
                            <span>Запланировано</span>
                            <strong>{formatDateTime(route.planned_start_at)}</strong>
                          </div>
                        ) : null}
                        {route.created_by_name ? (
                          <div className="detail-row">
                            <span>Создан</span>
                            <strong>{route.created_by_name}</strong>
                          </div>
                        ) : null}
                        {route.description ? (
                          <div className="detail-row detail-row-stack">
                            <span>Описание</span>
                            <strong>{route.description}</strong>
                          </div>
                        ) : null}
                      </div>

                      {route.points.length > 0 ? (
                        <div className="route-row-points">
                          <SectionTitle
                            title="Точки маршрута"
                            subtitle={`${route.points.length}`}
                          />
                          <div className="list-stack">
                            {route.points.map((point) => (
                              <div
                                key={point.id}
                                className="list-card list-card-tight"
                              >
                                <div className="list-card-top">
                                  <strong>
                                    {point.sequence}. {point.name}
                                  </strong>
                                  <StatusPill tone="neutral">
                                    {pointTypeLabel(point.point_type)}
                                  </StatusPill>
                                </div>
                                {point.address ? <p>{point.address}</p> : null}
                              </div>
                            ))}
                          </div>
                        </div>
                      ) : null}

                      <div className="action-row route-row-actions">
                        <AppLink to={`/app/admin/routes/${route.id}`}>
                          Подробнее
                        </AppLink>
                      </div>
                    </div>
                  ) : null}
                </article>
              );
            })}
          </div>
        ) : (
          <EmptyState title="Маршруты не найдены" />
        )}
      </Surface>
    </div>
  );
}

import { useEffect, useMemo, useState } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { ClipboardList, Clock, UserMinus, Search, Filter, Plus, ChevronDown } from 'lucide-react';

import './admin-theme.css';

import { useAuth } from '../../app/auth/useAuth';
import { fetchBranches, type BranchRecord } from '../../shared/api/branches';
import { fetchRoutes, type RouteRecord } from '../../shared/api/routes';
import {
  formatDate,
  formatDateTime,
  pointTypeLabel,
} from '../../shared/route-utils';
import { useToast } from '../../shared/toast/useToast';

type RouteFilter = 'all' | 'draft' | 'active' | 'completed';

export function AdminRoutesPage() {
  const { accessToken } = useAuth();
  const { showToast } = useToast();
  const [searchParams] = useSearchParams();
  const [routes, setRoutes] = useState<RouteRecord[]>([]);
  const [, setBranches] = useState<BranchRecord[]>([]);
  const [filter, setFilter] = useState<RouteFilter>('active');
  const [searchQuery, setSearchQuery] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const branchFilter = searchParams.get('branchId') ?? '';

  useEffect(() => {
    if (!accessToken) return;
    let cancelled = false;

    async function loadAll() {
      try {
        const [nextRoutes, nextBranches] = await Promise.all([
          fetchRoutes(accessToken as string),
          fetchBranches(accessToken as string).catch(() => [] as BranchRecord[]),
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
        if (!cancelled) setIsLoading(false);
      }
    }

    void loadAll();
    return () => { cancelled = true; };
  }, [accessToken, showToast]);

  const visibleRoutes = useMemo(() => {
    let result = routes;
    if (branchFilter) {
      result = result.filter((route) => route.branch_id === branchFilter);
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter(route => 
        route.title?.toLowerCase().includes(q) ||
        route.promoter_name?.toLowerCase().includes(q)
      );
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
  }, [filter, routes, branchFilter, searchQuery]);

  const toggleExpanded = (id: string) => setExpandedId((current) => (current === id ? null : id));

  // Stats calculation
  const totalRoutes = routes.length;
  const activeRoutes = routes.filter((r) => r.status === 'in_progress').length;
  const noPromoterRoutes = routes.filter((r) => !r.promoter_id).length;

  const getStatusPillClass = (status: string) => {
    switch(status) {
      case 'draft': return 'admin-pill-neutral';
      case 'assigned': 
      case 'in_progress': return 'admin-pill-accent';
      case 'completed': return 'admin-pill-positive';
      default: return 'admin-pill-neutral';
    }
  };

  const getStatusLabel = (status: string) => {
    switch(status) {
      case 'draft': return 'Черновик';
      case 'assigned': return 'Назначен';
      case 'in_progress': return 'В работе';
      case 'completed': return 'Завершен';
      default: return status;
    }
  };

  return (
    <main className="admin-bg">
      <div className="admin-container">
        {/* Заголовок */}
        <div style={{ marginBottom: '2rem' }}>
          <h1 className="admin-header-title">Панель администратора</h1>
          <p className="admin-header-subtitle">Управление маршрутами</p>
        </div>

        {/* Поиск и фильтры */}
        <div className="admin-toolbar">
          <div className="admin-toolbar-row">
            <div className="admin-search-wrapper">
              <Search className="admin-search-icon" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Поиск по названию или промоутеру..."
                className="admin-search-input"
              />
            </div>
            <div className="admin-btn-group">
              <button className="admin-btn admin-btn-primary">
                <Plus className="admin-btn-icon" />
                <span className="admin-btn-text-hide-sm">Добавить маршрут</span>
                <span className="admin-btn-text-show-sm">Добавить</span>
              </button>
            </div>
          </div>

          {/* Фильтр по статусу */}
          <div className="admin-filter-container">
            <Filter className="admin-filter-icon" />
            <span className="admin-filter-label">Фильтр:</span>
            <button
              onClick={() => setFilter("active")}
              className={`admin-filter-btn ${filter === 'active' ? 'active' : 'inactive'}`}
            >
              Активные
            </button>
            <button
              onClick={() => setFilter("draft")}
              className={`admin-filter-btn ${filter === 'draft' ? 'active' : 'inactive'}`}
            >
              Черновики
            </button>
            <button
              onClick={() => setFilter("completed")}
              className={`admin-filter-btn ${filter === 'completed' ? 'active' : 'inactive'}`}
            >
              Завершенные
            </button>
            <button
              onClick={() => setFilter("all")}
              className={`admin-filter-btn ${filter === 'all' ? 'active' : 'inactive'}`}
            >
              Все
            </button>
          </div>
        </div>

        {/* Статистика */}
        <div className="admin-stats-grid">
          <div className="admin-stat-card">
            <div className="admin-stat-info">
              <p className="admin-stat-label">Всего маршрутов</p>
              <p className="admin-stat-value text-white">{totalRoutes}</p>
            </div>
            <div className="admin-stat-icon-wrapper bg-purple-500-20 text-purple-400">
              <ClipboardList className="admin-stat-icon" />
            </div>
          </div>

          <div className="admin-stat-card">
            <div className="admin-stat-info">
              <p className="admin-stat-label">В работе</p>
              <p className="admin-stat-value text-blue-400">{activeRoutes}</p>
            </div>
            <div className="admin-stat-icon-wrapper bg-blue-500-20 text-blue-400">
              <Clock className="admin-stat-icon" />
            </div>
          </div>

          <div className="admin-stat-card">
            <div className="admin-stat-info">
              <p className="admin-stat-label">Без промоутера</p>
              <p className="admin-stat-value text-yellow-400">{noPromoterRoutes}</p>
            </div>
            <div className="admin-stat-icon-wrapper bg-yellow-500-20 text-yellow-400">
              <UserMinus className="admin-stat-icon" />
            </div>
          </div>
        </div>

        {/* Таблица/Список */}
        <div className="admin-table-container">
          <div className="admin-table-header">
            <h2 className="admin-table-title">Список маршрутов</h2>
            <p className="admin-table-subtitle">
              Найдено: {visibleRoutes.length} из {routes.length}
            </p>
          </div>
          
          {isLoading ? (
            <div className="admin-empty-state">
              <div className="admin-empty-state-icon">⌛</div>
              <h2 className="admin-empty-state-title">Загрузка маршрутов...</h2>
              <p className="admin-empty-state-text">Пожалуйста, подождите.</p>
            </div>
          ) : visibleRoutes.length === 0 ? (
            <div className="admin-empty-state">
              <div className="admin-empty-state-icon">📋</div>
              <h2 className="admin-empty-state-title">Маршруты не найдены</h2>
              <p className="admin-empty-state-text">По выбранному фильтру маршруты не найдены.</p>
            </div>
          ) : (
            <div>
              {visibleRoutes.map((route) => {
                const isExpanded = expandedId === route.id;
                return (
                  <div key={route.id} className="admin-route-row">
                    <button
                      className="admin-route-summary"
                      onClick={() => toggleExpanded(route.id)}
                    >
                      <div className="admin-route-main">
                        <span className="admin-route-title">{route.title}</span>
                        <span className="admin-route-meta">
                          {formatDate(route.work_date)} · {route.branch_name}
                        </span>
                        <span className="admin-route-promoter">
                          {route.promoter_name || 'Промоутер не назначен'}
                        </span>
                      </div>
                      <div className="admin-route-actions">
                        <span className={`admin-pill ${getStatusPillClass(route.status)}`}>
                          {getStatusLabel(route.status)}
                        </span>
                        <span className={`admin-route-chevron ${isExpanded ? 'is-open' : ''}`}>
                          <ChevronDown size={20} />
                        </span>
                      </div>
                    </button>

                    {isExpanded && (
                      <div className="admin-route-body">
                        <div className="admin-route-details-grid">
                          <div>
                            <span>{route.points.length} точек</span>
                            <span style={{ margin: '0 8px' }}>•</span>
                            <span>{route.photo_count} фото</span>
                            <span style={{ margin: '0 8px' }}>•</span>
                            <span>{route.geo_ping_count} GPS</span>
                          </div>
                          
                          {route.planned_start_at && (
                            <div>
                              <span>Запланировано: </span>
                              <strong style={{ color: '#fff' }}>{formatDateTime(route.planned_start_at)}</strong>
                            </div>
                          )}
                          
                          {route.description && (
                            <div>
                              <span>Описание: </span>
                              <strong style={{ color: '#fff' }}>{route.description}</strong>
                            </div>
                          )}
                        </div>

                        {route.points.length > 0 && (
                          <div>
                            <h3 className="admin-route-points-title">Точки маршрута ({route.points.length})</h3>
                            <div>
                              {route.points.map((point) => (
                                <div key={point.id} className="admin-point-card">
                                  <div className="admin-point-card-top">
                                    <span className="admin-point-name">{point.sequence}. {point.name}</span>
                                    <span className="admin-pill admin-pill-neutral" style={{ fontSize: '0.65rem' }}>
                                      {pointTypeLabel(point.point_type)}
                                    </span>
                                  </div>
                                  {point.address && <span className="admin-point-address">{point.address}</span>}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        <div className="admin-route-actions-bottom">
                          <Link to={`/app/admin/routes/${route.id}`} className="admin-route-link">
                            Подробнее
                          </Link>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </main>
  );
}


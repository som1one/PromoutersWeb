import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';

import { useAuth } from '../../app/auth/useAuth';
import { fetchAuditLogs, type AuditLogRecord } from '../../shared/api/audit';
import {
  fetchPayoutSummaryByPromoter,
  fetchPayouts,
  type PayoutRecord,
  type PayoutSummaryRecord,
} from '../../shared/api/finance';
import { fetchNotifications, type NotificationRecord } from '../../shared/api/notifications';
import { fetchRoutes, type RouteRecord } from '../../shared/api/routes';
import {
  formatCurrencyAmount,
  formatDate,
  formatDateTime,
  isManagerRole,
  payoutStatusLabel,
  payoutStatusTone,
  roleCodeLabel,
  routeStatusLabel,
  routeStatusTone,
  sumMoney,
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

export function OverviewPage() {
  const { accessToken, user } = useAuth();
  const { showToast } = useToast();
  const [routes, setRoutes] = useState<RouteRecord[]>([]);
  const [payouts, setPayouts] = useState<PayoutRecord[]>([]);
  const [notifications, setNotifications] = useState<NotificationRecord[]>([]);
  const [payoutSummary, setPayoutSummary] = useState<PayoutSummaryRecord[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLogRecord[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const managerView = user ? isManagerRole(user.roleCode) : false;

  useEffect(() => {
    if (!accessToken || !user) {
      return;
    }

    let cancelled = false;
    const token = accessToken;
    const currentUser = user;

    async function loadData() {
      try {
        const [nextRoutes, nextPayouts, nextNotifications, nextPayoutSummary, nextAuditLogs] =
          await Promise.all([
            fetchRoutes(token),
            fetchPayouts(token),
            fetchNotifications(token),
            managerView
              ? fetchPayoutSummaryByPromoter(token, currentUser.branchId ?? undefined)
              : Promise.resolve([]),
            managerView
              ? fetchAuditLogs(token, {
                  branchId: currentUser.branchId ?? undefined,
                  limit: 4,
                })
              : Promise.resolve([]),
          ]);

        if (cancelled) {
          return;
        }

        setRoutes(nextRoutes);
        setPayouts(nextPayouts);
        setNotifications(nextNotifications);
        setPayoutSummary(nextPayoutSummary);
        setAuditLogs(nextAuditLogs);
      } catch (error) {
        if (!cancelled) {
          showToast({
            tone: 'error',
            title: 'Не удалось загрузить обзор',
            description: error instanceof Error ? error.message : undefined,
          });
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    void loadData();

    return () => {
      cancelled = true;
    };
  }, [accessToken, managerView, showToast, user]);

  const activeRoutes = useMemo(
    () => routes.filter((route) => route.status === 'assigned' || route.status === 'in_progress'),
    [routes],
  );
  const completedRoutes = useMemo(() => routes.filter((route) => route.status === 'completed'), [routes]);
  const unreadNotifications = notifications.filter((item) => item.status !== 'read').length;
  const totalPayouts = formatCurrencyAmount(sumMoney(payouts.map((item) => item.amount)));
  const nextRoute = activeRoutes[0] ?? routes[0] ?? null;
  const recentNotifications = notifications.slice(0, 3);
  const recentPayouts = payouts.slice(0, 3);
  const topPromoters = payoutSummary.slice(0, 3);

  if (!user) {
    return null;
  }

  return (
    <div className="page-stack">
      <PageIntro
        eyebrow={managerView ? 'Операционный контур' : 'Мобильный сценарий'}
        title={managerView ? 'Короткая сводка по филиалу' : 'Все ключевое на одном экране'}
        description={
          managerView
            ? 'Маршруты, выплаты, сигналы и аудит в компактной раскладке без перегруженных таблиц.'
            : 'Текущий маршрут, быстрые действия, выплаты и сигналы собраны так, чтобы ими было удобно пользоваться с телефона.'
        }
        action={<StatusPill tone={managerView ? 'accent' : 'positive'}>{roleCodeLabel(user.roleCode)}</StatusPill>}
      />

      {isLoading ? (
        <Surface>
          <EmptyState title="Загружаем рабочую сводку" description="Секунду, собираем данные." />
        </Surface>
      ) : (
        <>
          <div className="metric-strip">
            <MetricCard
              label={managerView ? 'Всего маршрутов' : 'Активный статус'}
              value={managerView ? String(routes.length) : nextRoute ? routeStatusLabel(nextRoute.status) : 'Нет'}
              note={managerView ? `${activeRoutes.length} активных` : nextRoute?.title ?? 'Маршрут пока не назначен'}
            />
            <MetricCard
              label={managerView ? 'Сигналы' : 'Завершено смен'}
              value={managerView ? String(unreadNotifications) : String(completedRoutes.length)}
              note={managerView ? 'Непрочитанные уведомления' : 'С закрытым отчетом'}
            />
            <MetricCard
              label="Выплаты"
              value={totalPayouts}
              note={managerView ? 'Сумма по видимым начислениям' : 'Доступно в кабинете'}
            />
          </div>

          <div className="content-grid">
            <Surface>
              <SectionTitle
                title={nextRoute ? nextRoute.title : 'На сегодня нет активного маршрута'}
                subtitle={
                  nextRoute
                    ? `${formatDate(nextRoute.work_date)} · ${nextRoute.branch_name}`
                    : 'Когда смена будет назначена, она появится здесь первой.'
                }
                action={
                  nextRoute ? (
                    <AppLink
                      to={
                        managerView ? `/app/admin/routes/${nextRoute.id}` : `/app/routes/${nextRoute.id}`
                      }
                    >
                      Открыть
                    </AppLink>
                  ) : null
                }
              />

              {nextRoute ? (
                <div className="route-spotlight">
                  <div className="detail-list">
                    <div className="detail-row">
                      <span>Статус</span>
                      <StatusPill tone={routeStatusTone(nextRoute.status)}>
                        {routeStatusLabel(nextRoute.status)}
                      </StatusPill>
                    </div>
                    <div className="detail-row">
                      <span>Промоутер</span>
                      <strong>{nextRoute.promoter_name || 'Не назначен'}</strong>
                    </div>
                    <div className="detail-row">
                      <span>Точек</span>
                      <strong>{nextRoute.points.length}</strong>
                    </div>
                    <div className="detail-row">
                      <span>Фото</span>
                      <strong>{nextRoute.photo_count}</strong>
                    </div>
                  </div>

                  <div className="action-row">
                    <AppLink
                      to={
                        managerView ? `/app/admin/routes/${nextRoute.id}` : `/app/routes/${nextRoute.id}`
                      }
                    >
                      Подробнее
                    </AppLink>
                    {!managerView && nextRoute.status === 'assigned' ? (
                      <AppLink to={`/app/routes/${nextRoute.id}/execute`} variant="ghost">
                        Начать
                      </AppLink>
                    ) : null}
                  </div>
                </div>
              ) : (
                <EmptyState
                  title="Пауза без лишнего шума"
                  description="Экран останется коротким даже когда данных мало."
                />
              )}
            </Surface>

            <Surface>
              <SectionTitle
                title={managerView ? 'Свежие события' : 'Новые сигналы'}
                subtitle={managerView ? 'Что изменилось последним' : 'Напоминания и статусы по смене'}
                action={<AppLink to={managerView ? '/app/audit-logs' : '/app/notifications'} variant="ghost">Все</AppLink>}
              />

              {managerView ? (
                auditLogs.length ? (
                  <div className="list-stack">
                    {auditLogs.map((log) => (
                      <article key={log.id} className="list-card">
                        <strong>{log.action}</strong>
                        <p>{log.actor_username || 'system'} · {log.entity_type}</p>
                        <span>{formatDateTime(log.created_at)}</span>
                      </article>
                    ))}
                  </div>
                ) : (
                  <EmptyState title="Аудит пока пуст" />
                )
              ) : recentNotifications.length ? (
                <div className="list-stack">
                  {recentNotifications.map((notification) => (
                    <article key={notification.id} className="list-card">
                      <div className="list-card-top">
                        <strong>{notification.title}</strong>
                        <StatusPill tone={notification.status === 'read' ? 'neutral' : 'accent'}>
                          {notification.status === 'read' ? 'Прочитано' : 'Новое'}
                        </StatusPill>
                      </div>
                      <p>{notification.body}</p>
                      <span>{formatDateTime(notification.created_at)}</span>
                    </article>
                  ))}
                </div>
              ) : (
                <EmptyState title="Новых сигналов нет" />
              )}
            </Surface>
          </div>

          <div className="content-grid">
            <Surface>
              <SectionTitle
                title={managerView ? 'Начисления по людям' : 'Ближайшие выплаты'}
                subtitle={managerView ? 'Короткая выборка по промоутерам' : 'Что уже рассчитано'}
                action={<AppLink to="/app/payouts" variant="ghost">Открыть</AppLink>}
              />

              {managerView ? (
                topPromoters.length ? (
                  <div className="list-stack">
                    {topPromoters.map((summary) => (
                      <article key={summary.promoter_id} className="list-card list-card-tight">
                        <div className="list-card-top">
                          <strong>{summary.promoter_name}</strong>
                          <StatusPill tone="positive">
                            {formatCurrencyAmount(summary.total_amount, summary.currency)}
                          </StatusPill>
                        </div>
                        <p>{summary.payout_count} начислений</p>
                      </article>
                    ))}
                  </div>
                ) : (
                  <EmptyState title="Начислений пока нет" />
                )
              ) : recentPayouts.length ? (
                <div className="list-stack">
                  {recentPayouts.map((payout) => (
                    <article key={payout.id} className="list-card list-card-tight">
                      <div className="list-card-top">
                        <strong>{payout.route_title}</strong>
                        <StatusPill tone={payoutStatusTone(payout.status)}>
                          {payoutStatusLabel(payout.status)}
                        </StatusPill>
                      </div>
                      <p>{formatDate(payout.work_date)}</p>
                      <span>{formatCurrencyAmount(payout.amount, payout.currency)}</span>
                    </article>
                  ))}
                </div>
              ) : (
                <EmptyState title="Выплаты появятся после закрытия первых маршрутов" />
              )}
            </Surface>

            <Surface>
              <SectionTitle
                title={managerView ? 'Быстрые переходы' : 'Что можно сделать сейчас'}
                subtitle="Без перегруженного меню"
              />
              <div className="chip-grid">
                <Link className="chip-link" to={managerView ? '/app/admin/routes' : '/app/routes'}>
                  {managerView ? 'Маршруты филиала' : 'Мои маршруты'}
                </Link>
                <Link className="chip-link" to="/app/payouts">
                  Выплаты
                </Link>
                <Link className="chip-link" to="/app/notifications">
                  Уведомления
                </Link>
                <Link className="chip-link" to="/app/profile">
                  Профиль
                </Link>
              </div>
            </Surface>
          </div>
        </>
      )}
    </div>
  );
}

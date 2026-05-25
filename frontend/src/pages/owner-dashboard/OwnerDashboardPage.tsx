import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';

import { useAuth } from '../../app/auth/useAuth';
import { fetchAuditLogs, type AuditLogRecord } from '../../shared/api/audit';
import { fetchBranches, type BranchRecord } from '../../shared/api/branches';
import { fetchExpensePlans, type ExpensePlanRecord } from '../../shared/api/expense-plans';
import {
  fetchPayoutSummaryByPromoter,
  fetchPayouts,
  type PayoutRecord,
  type PayoutSummaryRecord,
} from '../../shared/api/finance';
import {
  fetchMasterRequests,
  type MasterRequestRecord,
} from '../../shared/api/master-requests';
import { fetchRoutes, type RouteRecord } from '../../shared/api/routes';
import { fetchUsers, type UserRecord } from '../../shared/api/users';
import {
  expensePlanStatusLabel,
  expensePlanStatusTone,
  formatCurrencyAmount,
  formatDateTime,
  masterRequestStatusLabel,
  masterRequestStatusTone,
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

export function OwnerDashboardPage() {
  const { accessToken, user } = useAuth();
  const { showToast } = useToast();
  const [routes, setRoutes] = useState<RouteRecord[]>([]);
  const [branches, setBranches] = useState<BranchRecord[]>([]);
  const [users, setUsers] = useState<UserRecord[]>([]);
  const [payouts, setPayouts] = useState<PayoutRecord[]>([]);
  const [payoutSummary, setPayoutSummary] = useState<PayoutSummaryRecord[]>([]);
  const [plans, setPlans] = useState<ExpensePlanRecord[]>([]);
  const [masterRequests, setMasterRequests] = useState<MasterRequestRecord[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLogRecord[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!accessToken) return;

    let cancelled = false;
    setIsLoading(true);

    Promise.all([
      fetchRoutes(accessToken),
      fetchBranches(accessToken),
      fetchUsers(accessToken),
      fetchPayouts(accessToken),
      fetchPayoutSummaryByPromoter(accessToken),
      fetchExpensePlans(accessToken),
      fetchMasterRequests(accessToken),
      fetchAuditLogs(accessToken, { limit: 8 }),
    ])
      .then(
        ([
          nextRoutes,
          nextBranches,
          nextUsers,
          nextPayouts,
          nextPayoutSummary,
          nextPlans,
          nextMasterRequests,
          nextAuditLogs,
        ]) => {
          if (cancelled) return;
          setRoutes(nextRoutes);
          setBranches(nextBranches);
          setUsers(nextUsers);
          setPayouts(nextPayouts);
          setPayoutSummary(nextPayoutSummary);
          setPlans(nextPlans);
          setMasterRequests(nextMasterRequests);
          setAuditLogs(nextAuditLogs);
        },
      )
      .catch((error) => {
        if (cancelled) return;
        showToast({
          tone: 'error',
          title: 'Не удалось загрузить дашборд',
          description: error instanceof Error ? error.message : undefined,
        });
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [accessToken, showToast]);

  const totalIncome = useMemo(
    () => sumMoney(payouts.map((payout) => payout.amount)),
    [payouts],
  );
  const totalExpenseApproved = useMemo(
    () =>
      sumMoney(
        plans
          .filter((plan) => plan.status === 'approved')
          .map((plan) => plan.total_amount),
      ),
    [plans],
  );
  const totalExpensePending = useMemo(
    () =>
      sumMoney(
        plans
          .filter((plan) => plan.status === 'submitted')
          .map((plan) => plan.total_amount),
      ),
    [plans],
  );
  const pendingPlans = plans.filter((plan) => plan.status === 'submitted');
  const activeRoutes = routes.filter(
    (route) => route.status === 'in_progress' || route.status === 'assigned',
  );
  const activeMasterRequests = masterRequests.filter(
    (request) =>
      request.status === 'on_the_way' || request.status === 'in_progress',
  );

  const usersByRole = useMemo(() => {
    const acc: Record<string, number> = {};
    for (const userItem of users) {
      const code = userItem.role_code ?? 'unknown';
      acc[code] = (acc[code] ?? 0) + 1;
    }
    return acc;
  }, [users]);

  const branchStats = useMemo(() => {
    return branches.map((branch) => {
      const branchRoutes = routes.filter((route) => route.branch_id === branch.id);
      const branchUsers = users.filter((u) => u.branch_id === branch.id);
      const branchPayouts = payouts.filter(
        (p) => branchRoutes.some((r) => r.id === p.route_id),
      );
      const branchPayoutSum = sumMoney(branchPayouts.map((p) => p.amount));
      return {
        branch,
        routes_count: branchRoutes.length,
        active_routes: branchRoutes.filter(
          (r) => r.status === 'in_progress' || r.status === 'assigned',
        ).length,
        users_count: branchUsers.length,
        payouts_total: branchPayoutSum,
      };
    });
  }, [branches, routes, users, payouts]);

  if (!user) return null;

  return (
    <div className="page-stack">
      <PageIntro
        eyebrow="Кабинет собственника"
        title="Сводка по системе"
        description="Финансы, активность, пользователи и согласования по всем филиалам."
        action={<StatusPill tone="positive">{roleCodeLabel(user.roleCode)}</StatusPill>}
      />

      {isLoading ? (
        <Surface>
          <EmptyState title="Собираем данные дашборда" />
        </Surface>
      ) : (
        <>
          {/* Финансовый срез */}
          <div className="metric-strip">
            <MetricCard
              label="Доход (выплаты)"
              value={formatCurrencyAmount(totalIncome)}
              note={`${payouts.length} начислений`}
              to="/app/income-expense"
            />
            <MetricCard
              label="Расход (согласовано)"
              value={formatCurrencyAmount(totalExpenseApproved)}
              note={`${plans.filter((p) => p.status === 'approved').length} планов`}
              to="/app/income-expense"
            />
            <MetricCard
              label="Ждёт согласования"
              value={formatCurrencyAmount(totalExpensePending)}
              note={`${pendingPlans.length} планов`}
              to="/app/income-expense"
            />
          </div>

          {/* Операционный срез */}
          <div className="metric-strip">
            <MetricCard
              label="Маршрутов всего"
              value={String(routes.length)}
              note={`${activeRoutes.length} активных`}
              to="/app/admin/routes"
            />
            <MetricCard
              label="Заявки мастера"
              value={String(masterRequests.length)}
              note={`${activeMasterRequests.length} в работе`}
              to="/app/master-requests"
            />
            <MetricCard
              label="Сотрудников"
              value={String(users.length)}
              note={`${branches.length} филиалов`}
              to="/app/audit-logs"
            />
          </div>

          {/* Планы на согласование */}
          {pendingPlans.length > 0 ? (
            <Surface>
              <SectionTitle
                title="Ждут вашего согласования"
                subtitle={`${pendingPlans.length} планов расходов`}
                action={<AppLink to="/app/income-expense" variant="ghost">Открыть финансы</AppLink>}
              />
              <div className="list-stack">
                {pendingPlans.map((plan) => (
                  <Link
                    key={plan.id}
                    to="/app/income-expense"
                    className="list-card list-card-link"
                  >
                    <div className="list-card-top">
                      <strong>{plan.title}</strong>
                      <StatusPill tone={expensePlanStatusTone(plan.status)}>
                        {expensePlanStatusLabel(plan.status)}
                      </StatusPill>
                    </div>
                    <p>
                      {plan.branch_name} · {plan.created_by_name}
                    </p>
                    <p>
                      Сумма:{' '}
                      <strong>
                        {formatCurrencyAmount(plan.total_amount, plan.currency)}
                      </strong>{' '}
                      ({plan.items.length} позиций)
                    </p>
                  </Link>
                ))}
              </div>
            </Surface>
          ) : null}

          {/* Срез по филиалам */}
          <Surface>
            <SectionTitle
              title="Филиалы"
              subtitle={`${branches.length} филиалов в системе`}
              action={<AppLink to="/app/admin/routes" variant="ghost">Все маршруты</AppLink>}
            />
            <div className="list-stack">
              {branchStats.map((row) => (
                <Link
                  key={row.branch.id}
                  to={`/app/admin/routes?branchId=${row.branch.id}`}
                  className="list-card list-card-link"
                >
                  <div className="list-card-top">
                    <strong>{row.branch.name}</strong>
                    <StatusPill tone={row.branch.is_active ? 'positive' : 'neutral'}>
                      {row.branch.is_active ? 'Активен' : 'Отключён'}
                    </StatusPill>
                  </div>
                  <p>{row.branch.city ?? row.branch.address ?? '—'}</p>
                  <div className="mini-stats">
                    <span>{row.routes_count} маршрутов</span>
                    <span>{row.active_routes} активных</span>
                    <span>{row.users_count} сотрудников</span>
                    <span>{formatCurrencyAmount(row.payouts_total)}</span>
                  </div>
                </Link>
              ))}
            </div>
          </Surface>

          <div className="content-grid">
            {/* Активные маршруты */}
            <Surface>
              <SectionTitle
                title="Активные маршруты"
                subtitle={`${activeRoutes.length} в работе`}
                action={<AppLink to="/app/admin/routes" variant="ghost">Все</AppLink>}
              />
              {activeRoutes.length ? (
                <div className="list-stack">
                  {activeRoutes.slice(0, 5).map((route) => (
                    <Link
                      key={route.id}
                      to={`/app/admin/routes/${route.id}`}
                      className="list-card list-card-tight list-card-link"
                    >
                      <div className="list-card-top">
                        <strong>{route.title}</strong>
                        <StatusPill tone={routeStatusTone(route.status)}>
                          {routeStatusLabel(route.status)}
                        </StatusPill>
                      </div>
                      <p>
                        {route.branch_name} · {route.promoter_name ?? 'Не назначен'}
                      </p>
                    </Link>
                  ))}
                </div>
              ) : (
                <EmptyState title="Активных маршрутов нет" />
              )}
            </Surface>

            {/* Активные заявки мастера */}
            <Surface>
              <SectionTitle
                title="Заявки мастера"
                subtitle={`${activeMasterRequests.length} в работе`}
                action={<AppLink to="/app/master-requests" variant="ghost">Все</AppLink>}
              />
              {activeMasterRequests.length ? (
                <div className="list-stack">
                  {activeMasterRequests.slice(0, 5).map((request) => (
                    <Link
                      key={request.id}
                      to="/app/master-requests"
                      className="list-card list-card-tight list-card-link"
                    >
                      <div className="list-card-top">
                        <strong>{request.title}</strong>
                        <StatusPill tone={masterRequestStatusTone(request.status)}>
                          {masterRequestStatusLabel(request.status)}
                        </StatusPill>
                      </div>
                      <p>
                        {request.branch_name} · {request.assignee_name ?? 'Не назначен'}
                      </p>
                    </Link>
                  ))}
                </div>
              ) : (
                <EmptyState title="Активных заявок нет" />
              )}
            </Surface>
          </div>

          <div className="content-grid">
            {/* Топ промоутеров по выплатам */}
            <Surface>
              <SectionTitle
                title="Промоутеры по выплатам"
                subtitle="Свод по периоду"
                action={<AppLink to="/app/income-expense" variant="ghost">Детали</AppLink>}
              />
              {payoutSummary.length ? (
                <div className="list-stack">
                  {payoutSummary
                    .slice()
                    .sort((a, b) => Number(b.total_amount) - Number(a.total_amount))
                    .slice(0, 5)
                    .map((summary) => (
                      <Link
                        key={summary.promoter_id}
                        to="/app/income-expense"
                        className="list-card list-card-tight list-card-link"
                      >
                        <div className="list-card-top">
                          <strong>{summary.promoter_name}</strong>
                          <StatusPill tone="positive">
                            {formatCurrencyAmount(summary.total_amount, summary.currency)}
                          </StatusPill>
                        </div>
                        <p>{summary.payout_count} начислений</p>
                      </Link>
                    ))}
                </div>
              ) : (
                <EmptyState title="Начислений пока нет" />
              )}
            </Surface>

            {/* Состав команды */}
            <Surface>
              <SectionTitle title="Состав команды" subtitle={`${users.length} человек`} />
              <div className="list-stack">
                {Object.entries(usersByRole).map(([roleCode, count]) => (
                  <div key={roleCode} className="detail-row">
                    <span>{roleCodeLabel(roleCode)}</span>
                    <strong>{count}</strong>
                  </div>
                ))}
              </div>
            </Surface>
          </div>

          {/* Аудит */}
          <Surface>
            <SectionTitle
              title="Последние действия в системе"
              subtitle={`${auditLogs.length} записей`}
              action={<AppLink to="/app/audit-logs" variant="ghost">Полный журнал</AppLink>}
            />
            {auditLogs.length ? (
              <div className="list-stack">
                {auditLogs.map((log) => (
                  <Link
                    key={log.id}
                    to="/app/audit-logs"
                    className="list-card list-card-tight list-card-link"
                  >
                    <div className="list-card-top">
                      <strong>{log.action}</strong>
                      <span>{formatDateTime(log.created_at)}</span>
                    </div>
                    <p>
                      {log.actor_username ?? 'system'} · {log.entity_type}
                    </p>
                  </Link>
                ))}
              </div>
            ) : (
              <EmptyState title="Журнал пуст" />
            )}
          </Surface>
        </>
      )}
    </div>
  );
}

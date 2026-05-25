import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';

import { useAuth } from '../../app/auth/useAuth';
import { fetchBranches, type BranchRecord } from '../../shared/api/branches';
import {
  decideExpensePlan,
  fetchExpensePlans,
  type ExpenseDecision,
  type ExpensePlanRecord,
} from '../../shared/api/expense-plans';
import { fetchPayouts, type PayoutRecord } from '../../shared/api/finance';
import { fetchRoutes, type RouteRecord } from '../../shared/api/routes';
import { fetchUsers, type UserRecord } from '../../shared/api/users';
import {
  expensePlanStatusLabel,
  expensePlanStatusTone,
  formatCurrencyAmount,
  formatDate,
  formatDateTime,
  payoutStatusLabel,
  payoutStatusTone,
  routeStatusLabel,
  sumMoney,
} from '../../shared/route-utils';
import { useToast } from '../../shared/toast/useToast';
import {
  AppButton,
  AppLink,
  EmptyState,
  MetricCard,
  PageIntro,
  SectionTitle,
  StatusPill,
  Surface,
} from '../../shared/ui/AppUI';

type PeriodPreset = 'all' | 'current_month' | 'last_30' | 'last_90';

const PERIOD_LABELS: Record<PeriodPreset, string> = {
  all: 'Всё время',
  current_month: 'Текущий месяц',
  last_30: 'Последние 30 дней',
  last_90: 'Последние 90 дней',
};

function periodStart(period: PeriodPreset): Date | null {
  const now = new Date();
  switch (period) {
    case 'current_month':
      return new Date(now.getFullYear(), now.getMonth(), 1);
    case 'last_30':
      return new Date(now.getTime() - 30 * 24 * 3600 * 1000);
    case 'last_90':
      return new Date(now.getTime() - 90 * 24 * 3600 * 1000);
    default:
      return null;
  }
}

function asNumber(value: string | number | null | undefined): number {
  if (value === null || value === undefined || value === '') return 0;
  const n = typeof value === 'number' ? value : Number.parseFloat(String(value));
  return Number.isFinite(n) ? n : 0;
}

function downloadCsv(filename: string, rows: string[][]) {
  const escape = (cell: string) => {
    const value = String(cell ?? '');
    if (/[",\n;]/.test(value)) return `"${value.replace(/"/g, '""')}"`;
    return value;
  };
  const csv = rows.map((row) => row.map(escape).join(';')).join('\r\n');
  const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function OwnerFinancePage() {
  const { accessToken, user } = useAuth();
  const { showToast } = useToast();

  const [period, setPeriod] = useState<PeriodPreset>('all');
  const [branchId, setBranchId] = useState<string>('');
  const [isLoading, setIsLoading] = useState(true);
  const [busyPlanId, setBusyPlanId] = useState<string | null>(null);
  const [expandedPromoterId, setExpandedPromoterId] = useState<string | null>(null);
  const [expandedPlanId, setExpandedPlanId] = useState<string | null>(null);

  const [branches, setBranches] = useState<BranchRecord[]>([]);
  const [users, setUsers] = useState<UserRecord[]>([]);
  const [routes, setRoutes] = useState<RouteRecord[]>([]);
  const [payouts, setPayouts] = useState<PayoutRecord[]>([]);
  const [plans, setPlans] = useState<ExpensePlanRecord[]>([]);

  const reload = async () => {
    if (!accessToken) return;
    setIsLoading(true);
    try {
      const [b, u, r, p, e] = await Promise.all([
        fetchBranches(accessToken),
        fetchUsers(accessToken),
        fetchRoutes(accessToken),
        fetchPayouts(accessToken),
        fetchExpensePlans(accessToken),
      ]);
      setBranches(b);
      setUsers(u);
      setRoutes(r);
      setPayouts(p);
      setPlans(e);
    } catch (error) {
      showToast({
        tone: 'error',
        title: 'Не удалось загрузить финансы',
        description: error instanceof Error ? error.message : undefined,
      });
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessToken]);

  const startDate = useMemo(() => periodStart(period), [period]);
  const branchById = useMemo(
    () => Object.fromEntries(branches.map((b) => [b.id, b])),
    [branches],
  );
  const promoterByPayout = useMemo(() => {
    const acc: Record<string, UserRecord> = {};
    for (const u of users) acc[u.id] = u;
    return acc;
  }, [users]);

  const filteredRoutes = useMemo(() => {
    return routes.filter((route) => {
      if (branchId && route.branch_id !== branchId) return false;
      if (startDate && new Date(route.work_date) < startDate) return false;
      return true;
    });
  }, [routes, branchId, startDate]);

  const filteredPayouts = useMemo(() => {
    const routeIds = new Set(filteredRoutes.map((r) => r.id));
    return payouts.filter((payout) => routeIds.has(payout.route_id));
  }, [payouts, filteredRoutes]);

  const filteredPlans = useMemo(() => {
    return plans.filter((plan) => {
      if (branchId && plan.branch_id !== branchId) return false;
      if (startDate && new Date(plan.period_end) < startDate) return false;
      return true;
    });
  }, [plans, branchId, startDate]);

  const totalIncome = sumMoney(filteredPayouts.map((p) => p.amount));
  const totalExpenseApproved = sumMoney(
    filteredPlans.filter((p) => p.status === 'approved').map((p) => p.total_amount),
  );
  const totalLeaflets = filteredPayouts
    .filter((p) => p.payout_rate_type === 'per_leaflet')
    .reduce((acc, p) => acc + asNumber(p.units), 0);
  const totalHours = filteredPayouts
    .filter((p) => p.payout_rate_type === 'hourly')
    .reduce((acc, p) => acc + asNumber(p.units), 0);
  const completedRoutes = filteredRoutes.filter((r) => r.status === 'completed').length;

  const branchSummary = useMemo(() => {
    return branches
      .filter((branch) => !branchId || branch.id === branchId)
      .map((branch) => {
        const branchRoutes = filteredRoutes.filter((r) => r.branch_id === branch.id);
        const branchRouteIds = new Set(branchRoutes.map((r) => r.id));
        const branchPayouts = filteredPayouts.filter((p) =>
          branchRouteIds.has(p.route_id),
        );
        const branchPlans = filteredPlans.filter((p) => p.branch_id === branch.id);
        const income = sumMoney(branchPayouts.map((p) => p.amount));
        const expenseApproved = sumMoney(
          branchPlans.filter((p) => p.status === 'approved').map((p) => p.total_amount),
        );
        const avgCheck = branchPayouts.length
          ? income / branchPayouts.length
          : 0;
        return {
          branch,
          income,
          expenseApproved,
          avgCheck,
          completed_routes: branchRoutes.filter((r) => r.status === 'completed').length,
          payouts_count: branchPayouts.length,
        };
      });
  }, [branches, branchId, filteredRoutes, filteredPayouts, filteredPlans]);

  // Сводка по промоутерам с детализацией по маршрутам и количеству листовок
  const promoterSummary = useMemo(() => {
    const map = new Map<
      string,
      {
        promoter_id: string;
        promoter_name: string;
        branch_id: string | null;
        payouts: PayoutRecord[];
        total_amount: number;
        leaflets: number;
        hours: number;
        routes: number;
      }
    >();
    for (const payout of filteredPayouts) {
      const id = payout.promoter_id;
      const promoter = promoterByPayout[id];
      const entry =
        map.get(id) ??
        {
          promoter_id: id,
          promoter_name: payout.promoter_name,
          branch_id: promoter?.branch_id ?? null,
          payouts: [] as PayoutRecord[],
          total_amount: 0,
          leaflets: 0,
          hours: 0,
          routes: 0,
        };
      entry.payouts.push(payout);
      entry.total_amount += asNumber(payout.amount);
      if (payout.payout_rate_type === 'per_leaflet') {
        entry.leaflets += asNumber(payout.units);
      }
      if (payout.payout_rate_type === 'hourly') {
        entry.hours += asNumber(payout.units);
      }
      entry.routes += 1;
      map.set(id, entry);
    }
    return Array.from(map.values()).sort(
      (a, b) => b.total_amount - a.total_amount,
    );
  }, [filteredPayouts, promoterByPayout]);

  // Срез по типам ставок
  const rateBreakdown = useMemo(() => {
    const acc = { hourly: 0, per_leaflet: 0, fixed_shift: 0, none: 0 };
    for (const p of filteredPayouts) {
      const key = (p.payout_rate_type ?? 'none') as keyof typeof acc;
      acc[key] += asNumber(p.amount);
    }
    return acc;
  }, [filteredPayouts]);

  const pendingPlans = filteredPlans.filter((p) => p.status === 'submitted');

  async function handleDecide(planId: string, decision: ExpenseDecision) {
    if (!accessToken) return;
    setBusyPlanId(planId);
    try {
      await decideExpensePlan(accessToken, planId, { decision });
      const label =
        decision === 'approved'
          ? 'согласован'
          : decision === 'needs_revision'
            ? 'отправлен на доработку'
            : 'отклонён';
      showToast({ tone: 'info', title: `План ${label}` });
      await reload();
    } catch (error) {
      showToast({
        tone: 'error',
        title: 'Не удалось зафиксировать решение',
        description: error instanceof Error ? error.message : undefined,
      });
    } finally {
      setBusyPlanId(null);
    }
  }

  function exportPayoutsCsv() {
    const header = [
      'Промоутер',
      'Филиал',
      'Маршрут',
      'Дата',
      'Тип ставки',
      'Кол-во листовок',
      'Часы',
      'Сумма',
      'Валюта',
      'Статус',
    ];
    const rows: string[][] = [header];
    for (const payout of filteredPayouts) {
      const promoter = promoterByPayout[payout.promoter_id];
      const branch = promoter?.branch_id ? branchById[promoter.branch_id] : null;
      rows.push([
        payout.promoter_name,
        branch?.name ?? '—',
        payout.route_title,
        formatDate(payout.work_date),
        payout.payout_rate_type ?? '—',
        payout.payout_rate_type === 'per_leaflet'
          ? String(asNumber(payout.units))
          : '',
        payout.payout_rate_type === 'hourly' ? String(asNumber(payout.units)) : '',
        asNumber(payout.amount).toFixed(2),
        payout.currency,
        payoutStatusLabel(payout.status),
      ]);
    }
    downloadCsv(`payouts-${new Date().toISOString().slice(0, 10)}.csv`, rows);
  }

  function exportPromotersCsv() {
    const header = ['Промоутер', 'Маршрутов', 'Листовок', 'Часов', 'Итого выплата'];
    const rows: string[][] = [header];
    for (const row of promoterSummary) {
      rows.push([
        row.promoter_name,
        String(row.routes),
        String(Math.round(row.leaflets)),
        row.hours.toFixed(2),
        row.total_amount.toFixed(2),
      ]);
    }
    downloadCsv(`promoters-summary-${new Date().toISOString().slice(0, 10)}.csv`, rows);
  }

  if (!user) return null;

  return (
    <div className="page-stack">
      <PageIntro
        eyebrow="Финансы собственника"
        title="Полный финансовый контур"
        description="Доход, расходы, план/факт по филиалам, детализация по промоутерам и согласование планов."
        action={<StatusPill tone="positive">Owner</StatusPill>}
      />

      {/* Фильтры */}
      <Surface>
        <SectionTitle title="Фильтры" subtitle="Период и филиал" />
        <div className="filters-row">
          <div className="segmented">
            {(Object.keys(PERIOD_LABELS) as PeriodPreset[]).map((p) => (
              <button
                key={p}
                type="button"
                className={`segment${period === p ? ' segment-active' : ''}`}
                onClick={() => setPeriod(p)}
              >
                {PERIOD_LABELS[p]}
              </button>
            ))}
          </div>
          <label className="filter-select">
            <span>Филиал</span>
            <select
              value={branchId}
              onChange={(event) => setBranchId(event.target.value)}
            >
              <option value="">Все филиалы</option>
              {branches.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </select>
          </label>
        </div>
      </Surface>

      {isLoading ? (
        <Surface>
          <EmptyState title="Загружаем финансы" />
        </Surface>
      ) : (
        <>
          {/* KPI */}
          <div className="metric-strip">
            <MetricCard
              label="Доход (выплаты)"
              value={formatCurrencyAmount(totalIncome)}
              note={`${filteredPayouts.length} начислений`}
            />
            <MetricCard
              label="Расход (согласовано)"
              value={formatCurrencyAmount(totalExpenseApproved)}
              note={`${filteredPlans.filter((p) => p.status === 'approved').length} планов`}
            />
            <MetricCard
              label="Дельта"
              value={formatCurrencyAmount(totalIncome - totalExpenseApproved)}
              note="Доход минус расход"
            />
          </div>

          <div className="metric-strip">
            <MetricCard
              label="Завершено маршрутов"
              value={String(completedRoutes)}
              note={`${filteredRoutes.length} всего`}
            />
            <MetricCard
              label="Распространено листовок"
              value={String(Math.round(totalLeaflets))}
              note="по фактическим выплатам"
            />
            <MetricCard
              label="Отработано часов"
              value={totalHours.toFixed(1)}
              note="по почасовым ставкам"
            />
          </div>

          {/* Планы расходов на согласовании */}
          {pendingPlans.length > 0 ? (
            <Surface>
              <SectionTitle
                title="Ждут согласования"
                subtitle={`${pendingPlans.length} планов в выбранном периоде`}
              />
              <div className="list-stack">
                {pendingPlans.map((plan) => {
                  const isOpen = expandedPlanId === plan.id;
                  const isBusy = busyPlanId === plan.id;
                  return (
                    <article key={plan.id} className="route-row-card">
                      <button
                        type="button"
                        className="route-row-summary"
                        aria-expanded={isOpen}
                        onClick={() => setExpandedPlanId(isOpen ? null : plan.id)}
                      >
                        <div className="route-row-main">
                          <strong>{plan.title}</strong>
                          <span>
                            {plan.branch_name} · {formatDate(plan.period_start)} —{' '}
                            {formatDate(plan.period_end)}
                          </span>
                          <span className="route-row-promoter">
                            Автор: {plan.created_by_name} · {plan.items.length} позиций
                          </span>
                        </div>
                        <div className="route-row-meta">
                          <StatusPill tone={expensePlanStatusTone(plan.status)}>
                            {expensePlanStatusLabel(plan.status)}
                          </StatusPill>
                          <span className="route-row-amount">
                            {formatCurrencyAmount(plan.total_amount, plan.currency)}
                          </span>
                          <span className={`route-row-chevron${isOpen ? ' is-open' : ''}`}>
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

                      {isOpen ? (
                        <div className="route-row-body">
                          <SectionTitle
                            title="Позиции"
                            subtitle={`${plan.items.length} строк`}
                          />
                          <div className="list-stack">
                            {plan.items.map((item) => (
                              <div key={item.id} className="list-card list-card-tight">
                                <div className="list-card-top">
                                  <strong>
                                    {item.sequence}. {item.name}
                                  </strong>
                                  <span>
                                    {formatCurrencyAmount(item.amount, plan.currency)}
                                  </span>
                                </div>
                                <p>
                                  {item.category ?? 'Без категории'} · {item.quantity} ×{' '}
                                  {formatCurrencyAmount(item.unit_price, plan.currency)}
                                </p>
                              </div>
                            ))}
                          </div>

                          {plan.comment ? (
                            <div className="detail-row detail-row-stack">
                              <span>Комментарий</span>
                              <strong>{plan.comment}</strong>
                            </div>
                          ) : null}

                          <div className="action-row route-row-actions">
                            <AppButton
                              type="button"
                              onClick={() => void handleDecide(plan.id, 'approved')}
                              disabled={isBusy}
                            >
                              Согласовать
                            </AppButton>
                            <AppButton
                              type="button"
                              variant="ghost"
                              onClick={() =>
                                void handleDecide(plan.id, 'needs_revision')
                              }
                              disabled={isBusy}
                            >
                              Вернуть на доработку
                            </AppButton>
                            <AppButton
                              type="button"
                              variant="ghost"
                              onClick={() => void handleDecide(plan.id, 'rejected')}
                              disabled={isBusy}
                            >
                              Отклонить
                            </AppButton>
                          </div>
                        </div>
                      ) : null}
                    </article>
                  );
                })}
              </div>
            </Surface>
          ) : null}

          {/* Срез по филиалам */}
          <Surface>
            <SectionTitle
              title="Срез по филиалам"
              subtitle={`${branchSummary.length} филиалов в фильтре`}
            />
            <div className="list-stack">
              {branchSummary.map((row) => (
                <Link
                  key={row.branch.id}
                  to={`/app/admin/routes?branchId=${row.branch.id}`}
                  className="list-card list-card-link"
                >
                  <div className="list-card-top">
                    <strong>{row.branch.name}</strong>
                    <StatusPill tone="positive">
                      {formatCurrencyAmount(row.income)}
                    </StatusPill>
                  </div>
                  <div className="mini-stats">
                    <span>{row.completed_routes} завершённых</span>
                    <span>{row.payouts_count} выплат</span>
                    <span>средний чек {formatCurrencyAmount(row.avgCheck)}</span>
                    <span>расход {formatCurrencyAmount(row.expenseApproved)}</span>
                  </div>
                </Link>
              ))}
            </div>
          </Surface>

          {/* Срез по типам оплаты */}
          <Surface>
            <SectionTitle
              title="Структура выплат"
              subtitle="По типам ставок"
            />
            <div className="detail-list">
              <div className="detail-row">
                <span>Почасовая</span>
                <strong>{formatCurrencyAmount(rateBreakdown.hourly)}</strong>
              </div>
              <div className="detail-row">
                <span>За листовку</span>
                <strong>{formatCurrencyAmount(rateBreakdown.per_leaflet)}</strong>
              </div>
              <div className="detail-row">
                <span>Фикс за смену</span>
                <strong>{formatCurrencyAmount(rateBreakdown.fixed_shift)}</strong>
              </div>
              {rateBreakdown.none > 0 ? (
                <div className="detail-row">
                  <span>Без ставки</span>
                  <strong>{formatCurrencyAmount(rateBreakdown.none)}</strong>
                </div>
              ) : null}
            </div>
          </Surface>

          {/* Промоутеры с детализацией по маршрутам */}
          <Surface>
            <SectionTitle
              title="Промоутеры — детализация выплат"
              subtitle={`${promoterSummary.length} промоутеров в фильтре`}
              action={
                <button
                  type="button"
                  className="chip-link"
                  onClick={exportPromotersCsv}
                  disabled={promoterSummary.length === 0}
                >
                  Сводка CSV
                </button>
              }
            />
            {promoterSummary.length === 0 ? (
              <EmptyState title="Нет начислений за выбранный период" />
            ) : (
              <div className="list-stack">
                {promoterSummary.map((row) => {
                  const isOpen = expandedPromoterId === row.promoter_id;
                  return (
                    <article key={row.promoter_id} className="route-row-card">
                      <button
                        type="button"
                        className="route-row-summary"
                        aria-expanded={isOpen}
                        onClick={() =>
                          setExpandedPromoterId(isOpen ? null : row.promoter_id)
                        }
                      >
                        <div className="route-row-main">
                          <strong>{row.promoter_name}</strong>
                          <span>
                            {row.routes} маршрутов · {Math.round(row.leaflets)} листовок
                            {row.hours > 0 ? ` · ${row.hours.toFixed(1)} ч` : ''}
                          </span>
                          <span className="route-row-promoter">
                            {row.branch_id && branchById[row.branch_id]?.name
                              ? branchById[row.branch_id].name
                              : 'Филиал не определён'}
                          </span>
                        </div>
                        <div className="route-row-meta">
                          <StatusPill tone="positive">
                            {formatCurrencyAmount(row.total_amount)}
                          </StatusPill>
                          <span className={`route-row-chevron${isOpen ? ' is-open' : ''}`}>
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

                      {isOpen ? (
                        <div className="route-row-body">
                          <SectionTitle
                            title="Маршруты и выплаты"
                            subtitle={`${row.payouts.length} начислений`}
                          />
                          <div className="list-stack">
                            {row.payouts.map((payout) => {
                              const route = filteredRoutes.find(
                                (r) => r.id === payout.route_id,
                              );
                              return (
                                <Link
                                  key={payout.id}
                                  to={
                                    route
                                      ? `/app/admin/routes/${payout.route_id}`
                                      : '#'
                                  }
                                  className="list-card list-card-tight list-card-link"
                                >
                                  <div className="list-card-top">
                                    <strong>{payout.route_title}</strong>
                                    <span>
                                      {formatCurrencyAmount(
                                        payout.amount,
                                        payout.currency,
                                      )}
                                    </span>
                                  </div>
                                  <p>
                                    {formatDate(payout.work_date)} ·{' '}
                                    {payout.payout_rate_name ?? 'Ставка не указана'}
                                  </p>
                                  <div className="mini-stats">
                                    {payout.payout_rate_type === 'per_leaflet' ? (
                                      <span>{Math.round(asNumber(payout.units))} листовок</span>
                                    ) : null}
                                    {payout.payout_rate_type === 'hourly' ? (
                                      <span>{asNumber(payout.units).toFixed(1)} ч</span>
                                    ) : null}
                                    {route ? (
                                      <span>статус: {routeStatusLabel(route.status)}</span>
                                    ) : null}
                                    <span>
                                      <StatusPill tone={payoutStatusTone(payout.status)}>
                                        {payoutStatusLabel(payout.status)}
                                      </StatusPill>
                                    </span>
                                  </div>
                                </Link>
                              );
                            })}
                          </div>
                        </div>
                      ) : null}
                    </article>
                  );
                })}
              </div>
            )}
          </Surface>

          {/* Все начисления (сырая лента) */}
          <Surface>
            <SectionTitle
              title="Все начисления за период"
              subtitle={`${filteredPayouts.length} строк`}
              action={
                <button
                  type="button"
                  className="chip-link"
                  onClick={exportPayoutsCsv}
                  disabled={filteredPayouts.length === 0}
                >
                  Выплаты CSV
                </button>
              }
            />
            {filteredPayouts.length === 0 ? (
              <EmptyState title="Начислений в этом периоде нет" />
            ) : (
              <div className="payout-table">
                <div className="payout-table-row payout-table-head">
                  <span>Промоутер</span>
                  <span>Маршрут</span>
                  <span>Дата</span>
                  <span>Ставка</span>
                  <span>Объём</span>
                  <span>Сумма</span>
                  <span>Статус</span>
                </div>
                {filteredPayouts.slice(0, 50).map((payout) => (
                  <Link
                    key={payout.id}
                    to={`/app/admin/routes/${payout.route_id}`}
                    className="payout-table-row payout-table-link"
                  >
                    <span>{payout.promoter_name}</span>
                    <span>{payout.route_title}</span>
                    <span>{formatDate(payout.work_date)}</span>
                    <span>{payout.payout_rate_name ?? '—'}</span>
                    <span>
                      {payout.payout_rate_type === 'per_leaflet'
                        ? `${Math.round(asNumber(payout.units))} лист.`
                        : payout.payout_rate_type === 'hourly'
                          ? `${asNumber(payout.units).toFixed(1)} ч`
                          : '—'}
                    </span>
                    <span>{formatCurrencyAmount(payout.amount, payout.currency)}</span>
                    <span>
                      <StatusPill tone={payoutStatusTone(payout.status)}>
                        {payoutStatusLabel(payout.status)}
                      </StatusPill>
                    </span>
                  </Link>
                ))}
                {filteredPayouts.length > 50 ? (
                  <div className="payout-table-more">
                    Показаны первые 50 из {filteredPayouts.length}. Скачайте CSV для
                    полного списка.
                  </div>
                ) : null}
              </div>
            )}
          </Surface>

          {/* Все планы расходов */}
          <Surface>
            <SectionTitle
              title="Все планы расходов в периоде"
              subtitle={`${filteredPlans.length} планов`}
              action={
                <AppLink to="/app/expense-plans" variant="ghost">
                  Полный раздел
                </AppLink>
              }
            />
            {filteredPlans.length === 0 ? (
              <EmptyState title="Планов в этом периоде нет" />
            ) : (
              <div className="list-stack">
                {filteredPlans.map((plan) => (
                  <Link
                    key={plan.id}
                    to="/app/expense-plans"
                    className="list-card list-card-tight list-card-link"
                  >
                    <div className="list-card-top">
                      <strong>{plan.title}</strong>
                      <StatusPill tone={expensePlanStatusTone(plan.status)}>
                        {expensePlanStatusLabel(plan.status)}
                      </StatusPill>
                    </div>
                    <p>
                      {plan.branch_name} · {formatDate(plan.period_start)} —{' '}
                      {formatDate(plan.period_end)}
                    </p>
                    <div className="mini-stats">
                      <span>{plan.items.length} позиций</span>
                      <span>{formatCurrencyAmount(plan.total_amount, plan.currency)}</span>
                      {plan.submitted_at ? (
                        <span>отправлен {formatDateTime(plan.submitted_at)}</span>
                      ) : null}
                      {plan.approved_at ? (
                        <span>согласован {formatDateTime(plan.approved_at)}</span>
                      ) : null}
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </Surface>
        </>
      )}
    </div>
  );
}

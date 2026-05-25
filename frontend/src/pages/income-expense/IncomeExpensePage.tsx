import { useEffect, useMemo, useState } from 'react';

import { useAuth } from '../../app/auth/useAuth';
import {
  decideExpensePlan,
  fetchExpensePlans,
  submitExpensePlan,
  type ExpenseDecision,
  type ExpensePlanRecord,
} from '../../shared/api/expense-plans';
import {
  fetchPayoutSummaryByPromoter,
  fetchPayouts,
  type PayoutRecord,
  type PayoutSummaryRecord,
} from '../../shared/api/finance';
import {
  expensePlanStatusLabel,
  expensePlanStatusTone,
  formatCurrencyAmount,
  formatDate,
  formatDateTime,
  payoutStatusLabel,
  payoutStatusTone,
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

export function IncomeExpensePage() {
  const { accessToken, user } = useAuth();
  const { showToast } = useToast();
  const [payouts, setPayouts] = useState<PayoutRecord[]>([]);
  const [summary, setSummary] = useState<PayoutSummaryRecord[]>([]);
  const [plans, setPlans] = useState<ExpensePlanRecord[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [expandedPromoterId, setExpandedPromoterId] = useState<string | null>(null);
  const [expandedPlanId, setExpandedPlanId] = useState<string | null>(null);
  const [busyPlanId, setBusyPlanId] = useState<string | null>(null);

  async function reloadPlans() {
    if (!accessToken) return;
    try {
      const list = await fetchExpensePlans(accessToken);
      setPlans(list);
    } catch (error) {
      showToast({
        tone: 'error',
        title: 'Не удалось обновить планы',
        description: error instanceof Error ? error.message : undefined,
      });
    }
  }

  async function handleSubmitPlan(planId: string) {
    if (!accessToken) return;
    setBusyPlanId(planId);
    try {
      await submitExpensePlan(accessToken, planId);
      showToast({ tone: 'info', title: 'План отправлен собственнику' });
      await reloadPlans();
    } catch (error) {
      showToast({
        tone: 'error',
        title: 'Не удалось отправить план',
        description: error instanceof Error ? error.message : undefined,
      });
    } finally {
      setBusyPlanId(null);
    }
  }

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
      await reloadPlans();
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

  useEffect(() => {
    if (!accessToken || !user) return;

    let cancelled = false;
    setIsLoading(true);

    Promise.all([
      fetchPayouts(accessToken),
      fetchPayoutSummaryByPromoter(accessToken, user.branchId ?? undefined),
      fetchExpensePlans(accessToken),
    ])
      .then(([payoutsList, summaryList, plansList]) => {
        if (cancelled) return;
        setPayouts(payoutsList);
        setSummary(summaryList);
        setPlans(plansList);
      })
      .catch((error) => {
        if (cancelled) return;
        showToast({
          tone: 'error',
          title: 'Не удалось загрузить раздел Доход/Расход',
          description: error instanceof Error ? error.message : undefined,
        });
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [accessToken, user, showToast]);

  const totalIncomePlanned = useMemo(
    () => sumMoney(payouts.map((payout) => payout.amount)),
    [payouts],
  );
  const totalExpensePlanned = useMemo(
    () => sumMoney(plans.filter((plan) => plan.status !== 'rejected').map((plan) => plan.total_amount)),
    [plans],
  );

  if (!user) return null;

  return (
    <div className="page-stack">
      <PageIntro
        eyebrow="Финансы"
        title="Доход и расход"
        description="Свод выплат и планов расходов с детализацией по каждому промоутеру."
      />

      <div className="metric-strip">
        <MetricCard
          label="Сумма выплат"
          value={formatCurrencyAmount(totalIncomePlanned)}
          note={`${payouts.length} начислений`}
        />
        <MetricCard
          label="Сумма расходов"
          value={formatCurrencyAmount(totalExpensePlanned)}
          note={`${plans.length} планов`}
        />
        <MetricCard
          label="Дельта"
          value={formatCurrencyAmount(totalIncomePlanned - totalExpensePlanned)}
          note="Выплаты минус расходы"
        />
      </div>

      <Surface>
        <SectionTitle
          title="Выплаты по промоутерам"
          subtitle={isLoading ? 'Загрузка...' : `${summary.length} промоутеров`}
          action={<AppLink to="/app/payouts" variant="ghost">Все начисления</AppLink>}
        />

        {isLoading ? (
          <EmptyState title="Собираем сводку" />
        ) : summary.length === 0 ? (
          <EmptyState title="Начислений по промоутерам пока нет" />
        ) : (
          <div className="list-stack">
            {summary.map((row) => {
              const isExpanded = expandedPromoterId === row.promoter_id;
              const avg = row.payout_count
                ? Number.parseFloat(String(row.total_amount)) / row.payout_count
                : 0;
              return (
                <article key={row.promoter_id} className="route-row-card">
                  <button
                    type="button"
                    className="route-row-summary"
                    aria-expanded={isExpanded}
                    onClick={() =>
                      setExpandedPromoterId(isExpanded ? null : row.promoter_id)
                    }
                  >
                    <div className="route-row-main">
                      <strong>{row.promoter_name}</strong>
                      <span>
                        {row.payout_count} начислений · средняя{' '}
                        {formatCurrencyAmount(avg, row.currency)}
                      </span>
                    </div>
                    <div className="route-row-meta">
                      <StatusPill tone="positive">
                        {formatCurrencyAmount(row.total_amount, row.currency)}
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
                      <div className="list-stack">
                        {row.payouts.map((payout) => (
                          <div key={payout.id} className="list-card list-card-tight">
                            <div className="list-card-top">
                              <strong>{payout.route_title}</strong>
                              <StatusPill tone={payoutStatusTone(payout.status)}>
                                {payoutStatusLabel(payout.status)}
                              </StatusPill>
                            </div>
                            <p>
                              {formatDate(payout.work_date)} ·{' '}
                              {payout.payout_rate_name ?? 'Ставка не указана'}
                            </p>
                            <p>
                              {payout.units
                                ? `${payout.units} ${
                                    payout.payout_rate_type === 'hourly' ? 'ч' : 'шт'
                                  } · `
                                : ''}
                              {formatCurrencyAmount(payout.amount, payout.currency)}
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : null}
                </article>
              );
            })}
          </div>
        )}
      </Surface>

      <Surface>
        <SectionTitle
          title="Расходы филиала"
          subtitle={isLoading ? 'Загрузка...' : `${plans.length} планов`}
          action={<AppLink to="/app/expense-plans" variant="ghost">Открыть планы</AppLink>}
        />

        {isLoading ? (
          <EmptyState title="Собираем планы" />
        ) : plans.length === 0 ? (
          <EmptyState title="Планов расходов пока нет" />
        ) : (
          <div className="list-stack">
            {plans.map((plan) => {
              const isExpanded = expandedPlanId === plan.id;
              const isOwner = user?.roleCode === 'owner';
              const isBranchManager = user?.roleCode === 'branch_manager';
              const isPlanAuthor = user?.id === plan.created_by_id;

              // Руководитель филиала отправляет свой черновик собственнику
              const canSubmit =
                isBranchManager &&
                isPlanAuthor &&
                (plan.status === 'draft' || plan.status === 'rejected');

              // Собственник принимает решение по планам, ждущим согласования
              const canDecide = isOwner && plan.status === 'submitted';

              // Подсказка руководителю, пока ждём решения собственника
              const waitingForOwner = isBranchManager && plan.status === 'submitted';

              const isBusy = busyPlanId === plan.id;

              return (
                <article key={plan.id} className="route-row-card">
                  <button
                    type="button"
                    className="route-row-summary"
                    aria-expanded={isExpanded}
                    onClick={() => setExpandedPlanId(isExpanded ? null : plan.id)}
                  >
                    <div className="route-row-main">
                      <strong>{plan.title}</strong>
                      <span>
                        {plan.branch_name} · {formatDate(plan.period_start)} —{' '}
                        {formatDate(plan.period_end)}
                      </span>
                      <span className="route-row-promoter">
                        {plan.created_by_name} · {plan.items.length} позиций
                      </span>
                    </div>
                    <div className="route-row-meta">
                      <StatusPill tone={expensePlanStatusTone(plan.status)}>
                        {expensePlanStatusLabel(plan.status)}
                      </StatusPill>
                      <span className="route-row-amount">
                        {formatCurrencyAmount(plan.total_amount, plan.currency)}
                      </span>
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
                      <div className="detail-list">
                        <div className="detail-row">
                          <span>Период</span>
                          <strong>
                            {formatDate(plan.period_start)} — {formatDate(plan.period_end)}
                          </strong>
                        </div>
                        <div className="detail-row">
                          <span>Сумма</span>
                          <strong>
                            {formatCurrencyAmount(plan.total_amount, plan.currency)}
                          </strong>
                        </div>
                        <div className="detail-row">
                          <span>Автор</span>
                          <strong>{plan.created_by_name}</strong>
                        </div>
                        {plan.submitted_at ? (
                          <div className="detail-row">
                            <span>Отправлен</span>
                            <strong>{formatDateTime(plan.submitted_at)}</strong>
                          </div>
                        ) : null}
                        {plan.approved_at ? (
                          <div className="detail-row">
                            <span>Согласован</span>
                            <strong>{formatDateTime(plan.approved_at)}</strong>
                          </div>
                        ) : null}
                        {plan.comment ? (
                          <div className="detail-row detail-row-stack">
                            <span>Комментарий</span>
                            <strong>{plan.comment}</strong>
                          </div>
                        ) : null}
                      </div>

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
                            {item.note ? <p>{item.note}</p> : null}
                          </div>
                        ))}
                      </div>

                      {plan.approvals.length ? (
                        <>
                          <SectionTitle
                            title="Согласование"
                            subtitle={`${plan.approvals.length} записей`}
                          />
                          <div className="list-stack">
                            {plan.approvals.map((approval) => (
                              <div
                                key={approval.id}
                                className="list-card list-card-tight"
                              >
                                <div className="list-card-top">
                                  <strong>{approval.approver_name}</strong>
                                  <StatusPill
                                    tone={
                                      approval.decision === 'approved'
                                        ? 'positive'
                                        : approval.decision === 'rejected'
                                          ? 'warning'
                                          : 'accent'
                                    }
                                  >
                                    {approval.decision}
                                  </StatusPill>
                                </div>
                                {approval.comment ? <p>{approval.comment}</p> : null}
                                <span>
                                  {approval.decided_at
                                    ? formatDateTime(approval.decided_at)
                                    : 'Ожидает решения'}
                                </span>
                              </div>
                            ))}
                          </div>
                        </>
                      ) : null}

                      <div className="action-row route-row-actions">
                        {canSubmit ? (
                          <AppButton
                            type="button"
                            onClick={() => void handleSubmitPlan(plan.id)}
                            disabled={isBusy}
                          >
                            Отправить на согласование
                          </AppButton>
                        ) : null}
                        {canDecide ? (
                          <>
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
                          </>
                        ) : null}
                        {waitingForOwner ? (
                          <span className="status-hint">
                            Ожидает решения собственника
                          </span>
                        ) : null}
                        <AppLink to="/app/expense-plans" variant="ghost">
                          Открыть в планах
                        </AppLink>
                      </div>
                    </div>
                  ) : null}
                </article>
              );
            })}
          </div>
        )}
      </Surface>
    </div>
  );
}

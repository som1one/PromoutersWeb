import { useEffect, useMemo, useState, type FormEvent } from 'react';

import { useAuth } from '../../app/auth/useAuth';
import { fetchBranches, type BranchRecord } from '../../shared/api/branches';
import {
  createExpensePlan,
  decideExpensePlan,
  fetchExpensePlans,
  submitExpensePlan,
  type ExpenseDecision,
  type ExpensePlanItemPayload,
  type ExpensePlanRecord,
} from '../../shared/api/expense-plans';
import {
  expensePlanStatusLabel,
  expensePlanStatusTone,
  formatCurrencyAmount,
  formatDate,
  formatDateTime,
  sumMoney,
} from '../../shared/route-utils';
import { useToast } from '../../shared/toast/useToast';
import {
  AppButton,
  EmptyState,
  MetricCard,
  PageIntro,
  SectionTitle,
  StatusPill,
  Surface,
  TextArea,
  TextInput,
} from '../../shared/ui/AppUI';

type ItemDraft = ExpensePlanItemPayload;

const emptyItem = (): ItemDraft => ({
  name: '',
  category: 'Материалы',
  quantity: 1,
  unit_price: 0,
  note: '',
});

export function ExpensePlansPage() {
  const { accessToken, user } = useAuth();
  const { showToast } = useToast();
  const [plans, setPlans] = useState<ExpensePlanRecord[]>([]);
  const [branches, setBranches] = useState<BranchRecord[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [draftTitle, setDraftTitle] = useState('План расходов на месяц');
  const [draftPeriodStart, setDraftPeriodStart] = useState(() =>
    new Date().toISOString().slice(0, 10),
  );
  const [draftPeriodEnd, setDraftPeriodEnd] = useState(() => {
    const next = new Date();
    next.setMonth(next.getMonth() + 1);
    return next.toISOString().slice(0, 10);
  });
  const [draftBranchId, setDraftBranchId] = useState<string>('');
  const [draftComment, setDraftComment] = useState('');
  const [draftItems, setDraftItems] = useState<ItemDraft[]>([
    { name: 'Аренда офиса', category: 'Аренда', quantity: 1, unit_price: 0 },
    { name: 'Листовки', category: 'Материалы', quantity: 1000, unit_price: 0 },
  ]);

  const isOwner = user?.roleCode === 'owner';
  const isBranchManager = user?.roleCode === 'branch_manager';
  const canCreate = isBranchManager || isOwner;

  const reload = async (token: string) => {
    setIsLoading(true);
    try {
      const records = await fetchExpensePlans(token);
      setPlans(records);
    } catch (error) {
      showToast({
        tone: 'error',
        title: 'Не удалось загрузить планы расходов',
        description: error instanceof Error ? error.message : undefined,
      });
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (!accessToken) return;
    void reload(accessToken);
  }, [accessToken]);

  useEffect(() => {
    if (!accessToken || !canCreate) return;
    fetchBranches(accessToken)
      .then((records) => {
        setBranches(records);
        if (!draftBranchId && user?.branchId) {
          setDraftBranchId(user.branchId);
        } else if (!draftBranchId && records[0]) {
          setDraftBranchId(records[0].id);
        }
      })
      .catch(() => undefined);
  }, [accessToken, canCreate, user?.branchId, draftBranchId]);

  const totalDraftAmount = useMemo(
    () =>
      sumMoney(
        draftItems.map((item) => Number(item.quantity || 0) * Number(item.unit_price || 0)),
      ),
    [draftItems],
  );

  const handleCreate = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!accessToken || !draftBranchId) return;

    setIsSubmitting(true);
    try {
      await createExpensePlan(accessToken, {
        title: draftTitle,
        branch_id: draftBranchId,
        period_start: draftPeriodStart,
        period_end: draftPeriodEnd,
        comment: draftComment || null,
        items: draftItems
          .filter((item) => item.name.trim())
          .map((item, index) => ({
            sequence: index + 1,
            name: item.name.trim(),
            category: item.category || null,
            quantity: Number(item.quantity) || 0,
            unit_price: Number(item.unit_price) || 0,
            note: item.note || null,
          })),
      });
      showToast({ tone: 'info', title: 'План создан' });
      setDraftItems([emptyItem()]);
      setDraftComment('');
      await reload(accessToken);
    } catch (error) {
      showToast({
        tone: 'error',
        title: 'Не удалось создать план',
        description: error instanceof Error ? error.message : undefined,
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSubmitForApproval = async (planId: string) => {
    if (!accessToken) return;
    try {
      await submitExpensePlan(accessToken, planId);
      showToast({ tone: 'info', title: 'План отправлен собственнику' });
      await reload(accessToken);
    } catch (error) {
      showToast({
        tone: 'error',
        title: 'Не удалось отправить план',
        description: error instanceof Error ? error.message : undefined,
      });
    }
  };

  const handleDecide = async (planId: string, decision: ExpenseDecision) => {
    if (!accessToken) return;
    try {
      await decideExpensePlan(accessToken, planId, { decision });
      showToast({ tone: 'info', title: `Решение принято: ${decision}` });
      await reload(accessToken);
    } catch (error) {
      showToast({
        tone: 'error',
        title: 'Не удалось зафиксировать решение',
        description: error instanceof Error ? error.message : undefined,
      });
    }
  };

  if (!user) return null;

  return (
    <div className="page-stack">
      <PageIntro
        eyebrow={isOwner ? 'Согласование расходов' : 'План расходов филиала'}
        title="Планы расходов и согласование"
        description={
          isOwner
            ? 'Согласуйте или верните на доработку планы расходов руководителей филиалов.'
            : 'Сформируйте план расходов и отправьте собственнику на согласование.'
        }
      />

      <div className="metric-strip">
        <MetricCard label="Всего планов" value={String(plans.length)} note="Видимые сейчас" />
        <MetricCard
          label="На согласовании"
          value={String(plans.filter((plan) => plan.status === 'submitted').length)}
          note="Ожидают решения"
        />
        <MetricCard
          label="Согласовано"
          value={String(plans.filter((plan) => plan.status === 'approved').length)}
          note="Можно исполнять"
        />
      </div>

      {canCreate ? (
        <Surface>
          <SectionTitle title="Новый план" subtitle="Сформируйте позиции и отправьте собственнику" />
          <form className="auth-form" onSubmit={handleCreate}>
            <TextInput
              label="Название"
              value={draftTitle}
              onChange={(event) => setDraftTitle(event.target.value)}
            />
            <div className="content-grid">
              <TextInput
                label="Период с"
                value={draftPeriodStart}
                type="date"
                onChange={(event) => setDraftPeriodStart(event.target.value)}
              />
              <TextInput
                label="Период по"
                value={draftPeriodEnd}
                type="date"
                onChange={(event) => setDraftPeriodEnd(event.target.value)}
              />
            </div>
            {isOwner ? (
              <label className="text-input">
                <span className="text-input-label">Филиал</span>
                <select
                  className="text-input-control"
                  value={draftBranchId}
                  onChange={(event) => setDraftBranchId(event.target.value)}
                >
                  {branches.map((branch) => (
                    <option key={branch.id} value={branch.id}>
                      {branch.name}
                    </option>
                  ))}
                </select>
              </label>
            ) : null}

            <SectionTitle title="Позиции" subtitle={`Сумма: ${formatCurrencyAmount(totalDraftAmount)}`} />
            <div className="list-stack">
              {draftItems.map((item, index) => (
                <div key={index} className="list-card">
                  <TextInput
                    label="Название"
                    value={item.name}
                    onChange={(event) =>
                      setDraftItems((prev) =>
                        prev.map((row, idx) =>
                          idx === index ? { ...row, name: event.target.value } : row,
                        ),
                      )
                    }
                  />
                  <TextInput
                    label="Категория"
                    value={item.category ?? ''}
                    onChange={(event) =>
                      setDraftItems((prev) =>
                        prev.map((row, idx) =>
                          idx === index ? { ...row, category: event.target.value } : row,
                        ),
                      )
                    }
                  />
                  <div className="content-grid">
                    <TextInput
                      label="Количество"
                      value={String(item.quantity)}
                      type="number"
                      onChange={(event) =>
                        setDraftItems((prev) =>
                          prev.map((row, idx) =>
                            idx === index
                              ? { ...row, quantity: Number(event.target.value) || 0 }
                              : row,
                          ),
                        )
                      }
                    />
                    <TextInput
                      label="Цена"
                      value={String(item.unit_price)}
                      type="number"
                      onChange={(event) =>
                        setDraftItems((prev) =>
                          prev.map((row, idx) =>
                            idx === index
                              ? { ...row, unit_price: Number(event.target.value) || 0 }
                              : row,
                          ),
                        )
                      }
                    />
                  </div>
                  <AppButton
                    type="button"
                    variant="ghost"
                    onClick={() =>
                      setDraftItems((prev) => prev.filter((_, idx) => idx !== index))
                    }
                  >
                    Удалить позицию
                  </AppButton>
                </div>
              ))}
              <AppButton
                type="button"
                variant="ghost"
                onClick={() => setDraftItems((prev) => [...prev, emptyItem()])}
              >
                Добавить позицию
              </AppButton>
            </div>

            <TextArea
              label="Комментарий"
              value={draftComment}
              onChange={(event) => setDraftComment(event.target.value)}
            />

            <AppButton type="submit" disabled={isSubmitting}>
              {isSubmitting ? 'Создаём...' : 'Создать план'}
            </AppButton>
          </form>
        </Surface>
      ) : null}

      <Surface>
        <SectionTitle
          title={isLoading ? 'Загрузка планов...' : `${plans.length} планов`}
          subtitle="Ваши и сабмиченные планы"
        />

        {isLoading ? (
          <EmptyState title="Собираем планы" />
        ) : plans.length === 0 ? (
          <EmptyState title="Планов расходов пока нет" />
        ) : (
          <div className="list-stack">
            {plans.map((plan) => (
              <article key={plan.id} className="list-card">
                <div className="list-card-top">
                  <strong>{plan.title}</strong>
                  <StatusPill tone={expensePlanStatusTone(plan.status)}>
                    {expensePlanStatusLabel(plan.status)}
                  </StatusPill>
                </div>
                <p>
                  {plan.branch_name} · {formatDate(plan.period_start)} — {formatDate(plan.period_end)}
                </p>
                <p>
                  Сумма: <strong>{formatCurrencyAmount(plan.total_amount, plan.currency)}</strong>
                </p>
                <p>
                  Автор: {plan.created_by_name}
                  {plan.submitted_at ? ` · отправлено ${formatDateTime(plan.submitted_at)}` : ''}
                </p>
                {plan.comment ? <p>{plan.comment}</p> : null}

                <details>
                  <summary>Позиции ({plan.items.length})</summary>
                  <div className="list-stack">
                    {plan.items.map((item) => (
                      <div key={item.id} className="list-card list-card-tight">
                        <strong>
                          {item.sequence}. {item.name}
                        </strong>
                        <p>
                          {item.category ?? '—'} · {item.quantity} ×{' '}
                          {formatCurrencyAmount(item.unit_price, plan.currency)}
                        </p>
                        <span>{formatCurrencyAmount(item.amount, plan.currency)}</span>
                      </div>
                    ))}
                  </div>
                </details>

                <details>
                  <summary>Согласование ({plan.approvals.length})</summary>
                  <div className="list-stack">
                    {plan.approvals.map((approval) => (
                      <div key={approval.id} className="list-card list-card-tight">
                        <strong>{approval.approver_name}</strong>
                        <p>Решение: {approval.decision}</p>
                        {approval.comment ? <p>{approval.comment}</p> : null}
                        <span>
                          {approval.decided_at
                            ? formatDateTime(approval.decided_at)
                            : 'Ожидает'}
                        </span>
                      </div>
                    ))}
                  </div>
                </details>

                <div className="action-row">
                  {(plan.status === 'draft' || plan.status === 'rejected') &&
                  user.roleCode === 'branch_manager' &&
                  plan.created_by_id === user.id ? (
                    <AppButton type="button" onClick={() => handleSubmitForApproval(plan.id)}>
                      Отправить на согласование
                    </AppButton>
                  ) : null}

                  {isOwner && plan.status === 'submitted' ? (
                    <>
                      <AppButton type="button" onClick={() => handleDecide(plan.id, 'approved')}>
                        Согласовать
                      </AppButton>
                      <AppButton
                        type="button"
                        variant="ghost"
                        onClick={() => handleDecide(plan.id, 'needs_revision')}
                      >
                        Вернуть на доработку
                      </AppButton>
                      <AppButton
                        type="button"
                        variant="ghost"
                        onClick={() => handleDecide(plan.id, 'rejected')}
                      >
                        Отклонить
                      </AppButton>
                    </>
                  ) : null}

                  {user.roleCode === 'branch_manager' && plan.status === 'submitted' ? (
                    <span className="status-hint">Ожидает решения собственника</span>
                  ) : null}
                </div>
              </article>
            ))}
          </div>
        )}
      </Surface>
    </div>
  );
}

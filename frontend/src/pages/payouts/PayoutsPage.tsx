import { useEffect, useState } from 'react';

import { useAuth } from '../../app/auth/useAuth';
import { fetchPayouts, type PayoutRecord } from '../../shared/api/finance';
import {
  formatCurrencyAmount,
  formatDate,
  payoutStatusLabel,
  payoutStatusTone,
  sumMoney,
} from '../../shared/route-utils';
import { useToast } from '../../shared/toast/useToast';
import {
  EmptyState,
  MetricCard,
  PageIntro,
  SectionTitle,
  StatusPill,
  Surface,
} from '../../shared/ui/AppUI';

export function PayoutsPage() {
  const { accessToken } = useAuth();
  const { showToast } = useToast();
  const [payouts, setPayouts] = useState<PayoutRecord[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!accessToken) {
      return;
    }

    let cancelled = false;
    const token = accessToken;

    async function loadPayouts() {
      try {
        const nextPayouts = await fetchPayouts(token);
        if (!cancelled) {
          setPayouts(nextPayouts);
        }
      } catch (error) {
        if (!cancelled) {
          showToast({
            tone: 'error',
            title: 'Не удалось загрузить выплаты',
            description: error instanceof Error ? error.message : undefined,
          });
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    void loadPayouts();

    return () => {
      cancelled = true;
    };
  }, [accessToken, showToast]);

  const calculated = payouts.filter((payout) => payout.status === 'calculated' || payout.status === 'approved');
  const paid = payouts.filter((payout) => payout.status === 'paid');

  return (
    <div className="page-stack">
      <PageIntro
        eyebrow="Выплаты"
        title="Все начисления без перегруза"
        description="Сначала короткая сводка, затем плотный список начислений."
      />

      <div className="metric-strip">
        <MetricCard label="Всего" value={formatCurrencyAmount(sumMoney(payouts.map((item) => item.amount)))} />
        <MetricCard label="К выплате" value={formatCurrencyAmount(sumMoney(calculated.map((item) => item.amount)))} />
        <MetricCard label="Уже оплачено" value={formatCurrencyAmount(sumMoney(paid.map((item) => item.amount)))} />
      </div>

      <Surface>
        <SectionTitle
          title="Лента начислений"
          subtitle={isLoading ? 'Загрузка...' : `${payouts.length} записей`}
        />

        {isLoading ? (
          <EmptyState title="Собираем выплаты" />
        ) : payouts.length ? (
          <div className="list-stack">
            {payouts.map((payout) => (
              <article key={payout.id} className="list-card">
                <div className="list-card-top">
                  <strong>{payout.route_title}</strong>
                  <StatusPill tone={payoutStatusTone(payout.status)}>
                    {payoutStatusLabel(payout.status)}
                  </StatusPill>
                </div>
                <p>{formatDate(payout.work_date)} · {payout.promoter_name}</p>
                <div className="mini-stats">
                  <span>{formatCurrencyAmount(payout.amount, payout.currency)}</span>
                  <span>{payout.payout_rate_name || 'Ставка не указана'}</span>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <EmptyState title="Начислений пока нет" />
        )}
      </Surface>
    </div>
  );
}

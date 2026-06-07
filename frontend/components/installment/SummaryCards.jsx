"use client";

import DashboardCard from "./DashboardCard";

export default function SummaryCards({ deal }) {
  const total = Number(deal?.total) || 0;
  const paid = Number(deal?.paid) || 0;
  const rest = Math.max(0, total - paid);

  // Витрина KPI как в макете:
  // - Общая сумма
  // - Первоначальный взнос
  // - Сумма рассрочки (total - initial)
  const initialPayment = Number(deal?.initial_payment) || 0;
  // "По графику" имеет смысл только если график создан (есть срок).
  // Когда срок не задан (term_months=0), показываем 0, чтобы не вводить в заблуждение.
  // На клиенте поле может называться `term` (из маппера), поэтому поддерживаем оба варианта.
  const termMonths = Number(deal?.term_months ?? deal?.term) || 0;
  const hasSchedule = termMonths > 0;
  const installmentSum = hasSchedule
    ? (Number(deal?.installment_amount) || Math.max(0, total - initialPayment))
    : 0;

  // Прогресс по рассрочке (по графику):
  // - initial_payment НЕ вычитаем из paid, т.к. он не является фактом оплаты в нашей модели
  const paidInstallment = hasSchedule
    ? (
        Number(deal?.paid_installment) ||
        Math.min(installmentSum, Math.max(0, paid))
      )
    : 0;
  const restInstallment = hasSchedule
    ? (
        Number(deal?.rest_installment) ||
        Math.max(0, installmentSum - paidInstallment)
      )
    : 0;
  const progressPercent = installmentSum > 0 ? (paidInstallment / installmentSum) * 100 : 0;
  const safePercent = Math.max(0, Math.min(100, Number.isFinite(progressPercent) ? progressPercent : 0));

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
      <DashboardCard
        title="Общая сумма"
        value={`${total.toLocaleString('ru-RU')} ₽`}
        subtitle="По договору"
        icon={<span className="text-xl">💰</span>}
        color="blue"
      />
      <DashboardCard
        title="Первоначальный взнос"
        value={`${initialPayment.toLocaleString('ru-RU')} ₽`}
        subtitle="До рассрочки"
        icon={<span className="text-xl">🟩</span>}
        color="green"
      />
      <DashboardCard
        title="Сумма рассрочки"
        value={`${installmentSum.toLocaleString('ru-RU')} ₽`}
        subtitle="По графику"
        icon={<span className="text-xl">🟫</span>}
        color="orange"
      />

      {/* Виджет прогресса (как на скрине) */}
      <div className="rounded-xl border p-4 sm:p-6 bg-gradient-to-br from-purple-500/20 to-purple-600/20 border-purple-500/30 backdrop-blur-sm transition-all hover:scale-105 hover:shadow-lg">
        <div className="flex items-start justify-between mb-3 sm:mb-4">
          <div className="flex items-center gap-2 sm:gap-3">
            <div className="p-2 sm:p-3 rounded-lg bg-white/5 text-purple-400">
              <span className="text-lg sm:text-xl">🟪</span>
            </div>
            <div>
              <p className="text-xs sm:text-sm text-dashboard-text-muted font-medium">Прогресс</p>
              <p className="text-[10px] sm:text-xs text-dashboard-text-muted/70 mt-0.5 sm:mt-1">Оплачено / остаток</p>
            </div>
          </div>
          <div className="text-xs sm:text-sm font-bold text-white">{Math.round(safePercent)}%</div>
        </div>

        <div className="flex items-center gap-3 sm:gap-4">
          <div className="relative w-12 h-12 sm:w-16 sm:h-16 flex-shrink-0">
            <div
              className="w-full h-full rounded-full"
              style={{
                background: `conic-gradient(#a855f7 ${safePercent}%, rgba(148,163,184,0.22) 0)`,
              }}
            />
            <div className="absolute inset-1 sm:inset-2 rounded-full bg-slate-900/40 flex items-center justify-center border border-white/5">
              <span className="text-[10px] sm:text-xs font-bold text-white">{Math.round(safePercent)}%</span>
            </div>
          </div>

          <div className="flex-1 space-y-1.5 sm:space-y-2 min-w-0">
            <div className="flex items-center justify-between text-xs sm:text-sm">
              <span className="text-dashboard-text-muted truncate mr-2">Оплачено:</span>
              <span className="font-semibold text-white whitespace-nowrap">
                {hasSchedule ? `${paidInstallment.toLocaleString("ru-RU")} ₽` : "—"}
              </span>
            </div>
            <div className="flex items-center justify-between text-xs sm:text-sm">
              <span className="text-dashboard-text-muted truncate mr-2">Осталось:</span>
              <span className="font-semibold text-white whitespace-nowrap">
                {hasSchedule ? `${restInstallment.toLocaleString("ru-RU")} ₽` : "—"}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

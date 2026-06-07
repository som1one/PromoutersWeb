"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useDeal } from "@/modules/admin/deals/hooks";
import AdminPaymentsTable from "@/components/admin/AdminPaymentsTable";
import PaymentLogs from "@/components/admin/PaymentLogs";
import DealDetailsCard from "@/components/admin/DealDetailsCard";
import SummaryCards from "@/components/installment/SummaryCards";
import CashPaymentModal from "@/components/admin/CashPaymentModal";
import DealSettingsModal from "@/components/admin/DealSettingsModal";
import { Loader, ErrorState, EmptyState } from "@/components/ui/State";
import { Wallet, Settings, ArrowLeft, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { deleteDeal } from "@/modules/admin/deals/api";

export default function AdminDealPage() {
  const { id } = useParams();
  const router = useRouter();
  const { deal, loading, error, refetch } = useDeal(id);
  const [showCashModal, setShowCashModal] = useState(false);
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);

  if (loading) {
    return (
      <main className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900/20 to-slate-900">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <Loader text="Загрузка сделки..." />
        </div>
      </main>
    );
  }

  if (error) {
    return (
      <main className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900/20 to-slate-900">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <ErrorState message={error} onRetry={refetch} />
        </div>
      </main>
    );
  }

  if (!deal) {
    return (
      <main className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900/20 to-slate-900">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <EmptyState text="Сделка не найдена" icon="📋" />
        </div>
      </main>
    );
  }

  const remaining = deal.deal?.total_amount - deal.deal?.paid_amount || 0;
  const isFullyPaid = remaining <= 0;
  const hasTotal = (deal.deal?.total_amount || 0) > 0;

  // Приводим данные к формату, который ожидают "клиентские" карточки SummaryCards
  const termMonths = Number(deal.deal?.term_months) || 0;
  const clientLikeDeal = {
    total: Number(deal.deal?.total_amount) || 0,
    paid: Number(deal.deal?.paid_amount) || 0,
    initial_payment: Number(deal.deal?.initial_payment) || 0,
    // "По графику" считаем только если график создан (term_months > 0)
    installment_amount: termMonths > 0 ? (Number(deal.deal?.installment_amount) || 0) : 0,
    term_months: termMonths,
  };

  const payments = Array.isArray(deal.payments) ? deal.payments : [];
  const paidCount = payments.filter((p) => p?.status === "paid").length;
  const totalCount = payments.length;
  const totalSum = payments.reduce((s, p) => s + (Number(p?.amount) || 0), 0);
  const paidSum = payments.reduce((s, p) => {
    const amt = Number(p?.amount) || 0;
    const remainingInMonth = p?.remaining_in_month;
    const paidInMonth = p?.paid_in_month;
    if (typeof remainingInMonth === "number") return s + Math.max(0, amt - remainingInMonth);
    if (typeof paidInMonth === "number") return s + Math.min(amt, Math.max(0, paidInMonth));
    return s + (p?.status === "paid" ? amt : 0);
  }, 0);
  const progress = totalSum > 0 ? (paidSum / totalSum) * 100 : 0;

  const handleDelete = async () => {
    setDeleting(true);
    try {
      await deleteDeal(id);
      router.push("/admin/deals");
    } catch (err) {
      alert(err?.response?.data?.detail || "Ошибка при удалении сделки");
      setDeleting(false);
    }
  };

  return (
    <main className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900/20 to-slate-900">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Заголовок и кнопки */}
        <div className="mb-6">
          <Link 
            href="/admin/deals"
            prefetch={false}
            className="inline-flex items-center gap-2 text-slate-400 hover:text-white mb-4 transition-colors text-sm sm:text-base"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Назад к списку</span>
          </Link>
          <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-4">
            <div>
              <h1 className="text-2xl sm:text-3xl font-bold text-white mb-1 sm:mb-2">Детали рассрочки</h1>
              <p className="text-xs sm:text-sm text-slate-400">ID: #{id}</p>
            </div>
            <div className="flex flex-col sm:flex-row gap-2 sm:gap-3 w-full sm:w-auto">
              <button
                onClick={() => setShowSettingsModal(true)}
                className="w-full sm:w-auto px-4 py-2.5 bg-slate-700 hover:bg-slate-600 text-white rounded-lg transition-colors flex items-center justify-center gap-2 border border-slate-600 text-sm sm:text-base"
              >
                <Settings className="w-4 h-4" />
                <span>Настройки</span>
              </button>
              {!isFullyPaid && hasTotal && (
                <button
                  onClick={() => setShowCashModal(true)}
                  className="w-full sm:w-auto px-4 py-2.5 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors flex items-center justify-center gap-2 text-sm sm:text-base"
                >
                  <Wallet className="w-4 h-4" />
                  <span>Наличный расчет</span>
                </button>
              )}
              <button
                onClick={() => setShowDeleteConfirm(true)}
                disabled={deleting}
                className="w-full sm:w-auto px-4 py-2.5 bg-red-600 hover:bg-red-700 text-white rounded-lg transition-colors flex items-center justify-center gap-2 text-sm sm:text-base disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Trash2 className="w-4 h-4" />
                <span>Удалить</span>
              </button>
              {!hasTotal && (
                <div className="text-xs sm:text-sm text-slate-400 flex items-center justify-center sm:justify-start px-2 py-2">
                  Сначала задайте сумму в настройках
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="space-y-4 sm:space-y-6">
          {/* Как у клиента: заголовок сделки + местоположение */}
          <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl p-4 sm:p-6">
            <h2 className="text-xl sm:text-2xl font-bold text-white mb-2">
              {deal.deal?.title || `Сделка #${deal.deal?.contract_number || id}`}
            </h2>
            {deal.deal?.object_location && (
              <div className="flex items-center gap-2 text-xs sm:text-sm text-slate-400">
                <span className="text-purple-400">📍</span>
                <span>{deal.deal.object_location}</span>
              </div>
            )}
          </div>

          {/* KPI как у клиента */}
          <SummaryCards deal={clientLikeDeal} />
          
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 sm:gap-6">
            <div className="lg:col-span-2 space-y-4 sm:space-y-6">
              <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl overflow-hidden">
                <div className="px-4 sm:px-6 py-3 sm:py-4 border-b border-slate-700">
                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 sm:gap-6">
                    <div>
                      <h2 className="text-base sm:text-lg font-semibold text-white">График платежей</h2>
                      <p className="text-xs sm:text-sm text-slate-400 mt-1">
                        {paidCount} из {totalCount} платежей выполнено
                      </p>
                    </div>
                    <div className="text-left sm:text-right">
                      <div className="text-xl sm:text-2xl font-bold text-white">{Math.round(progress)}%</div>
                      <div className="text-xs text-slate-400">Прогресс</div>
                    </div>
                  </div>
                </div>
                <div className="px-4 sm:px-6 pt-3 sm:pt-4">
                  <div className="h-2 bg-slate-700/50 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-purple-500 to-purple-600 transition-all duration-500"
                      style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
                    />
                  </div>
                </div>
                <AdminPaymentsTable payments={deal.payments} />
              </div>
              
              <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl overflow-hidden">
                <div className="px-4 sm:px-6 py-3 sm:py-4 border-b border-slate-700">
                  <h2 className="text-base sm:text-lg font-semibold text-white">История платежей</h2>
                </div>
                <PaymentLogs dealId={id} />
              </div>
            </div>
            
            <div className="lg:col-span-1">
              <DealDetailsCard deal={deal} />
            </div>
          </div>
        </div>

        {showCashModal && (
          <CashPaymentModal
            dealId={id}
            onClose={() => setShowCashModal(false)}
            onSuccess={() => {
              refetch();
              setShowCashModal(false);
            }}
          />
        )}

        {showSettingsModal && deal.deal && (
          <DealSettingsModal
            deal={deal.deal}
            dealId={id}
            onClose={() => setShowSettingsModal(false)}
            onSuccess={() => {
              refetch();
              setShowSettingsModal(false);
            }}
          />
        )}

        {showDeleteConfirm && (
          <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
            <div className="bg-slate-800 border border-slate-700 rounded-xl p-6 max-w-md w-full">
              <h3 className="text-xl font-semibold text-white mb-2">Подтверждение удаления</h3>
              <p className="text-slate-300 mb-6">
                Вы уверены, что хотите удалить сделку <strong className="text-white">#{id}</strong>? 
                Это действие нельзя отменить. Все связанные данные будут удалены.
              </p>
              <div className="flex gap-3 justify-end">
                <button
                  onClick={() => setShowDeleteConfirm(false)}
                  disabled={deleting}
                  className="px-4 py-2 border border-slate-600 text-slate-300 rounded-lg hover:bg-slate-700 disabled:opacity-50 transition-colors"
                >
                  Отмена
                </button>
                <button
                  onClick={handleDelete}
                  disabled={deleting}
                  className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 flex items-center gap-2 transition-colors"
                >
                  {deleting ? (
                    <>
                      <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                      Удаление...
                    </>
                  ) : (
                    "Удалить"
                  )}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}

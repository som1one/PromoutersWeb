"use client";

import { useDeals } from "@/modules/admin/deals/hooks";
import DealsTable from "@/components/admin/DealsTable";
import CreateDealModal from "@/components/admin/CreateDealModal";
import { Loader, ErrorState, EmptyState } from "@/components/ui/State";
import { ClipboardList, DollarSign, Wallet, Banknote, Search, Trash2, Filter, Plus } from "lucide-react";
import { useMemo, useState } from "react";
import { clearDatabase } from "@/modules/admin/deals/api";

export default function AdminDealsPage() {
  const { deals, loading, error, refetch } = useDeals();
  const [searchQuery, setSearchQuery] = useState("");
  const [filterType, setFilterType] = useState("open"); // "open", "closed"
  const [showClearConfirm, setShowClearConfirm] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);

  // Все сделки (для статистики)
  const allInstallmentDeals = useMemo(() => {
    if (!deals) return [];
    return deals;
  }, [deals]);

  const installmentDeals = useMemo(() => {
    if (!deals) return [];
    
    const totalAmount = (d) => Number(d.total_amount) || 0;
    const paidAmount = (d) => Number(d.paid_amount) || 0;
    const initialPayment = (d) => Number(d.initial_payment) || 0;
    const installmentAmount = (d) => Math.max(0, totalAmount(d) - initialPayment(d));
    const paidInstallment = (d) => Math.min(installmentAmount(d), Math.max(0, paidAmount(d)));
    const isClosed = (d) => installmentAmount(d) > 0 && paidInstallment(d) >= installmentAmount(d);
    
    switch (filterType) {
      case "closed":
        // Закрытые (полностью оплаченные)
        return deals.filter(d => isClosed(d));
      case "open":
      default:
        // Открытые (не полностью оплаченные)
        return deals.filter(d => !isClosed(d));
    }
  }, [deals, filterType]);

  const filteredDeals = useMemo(() => {
    if (!installmentDeals) return [];
    if (!searchQuery.trim()) return installmentDeals;
    
    const query = searchQuery.toLowerCase();
    return installmentDeals.filter(d => {
      const title = (d.title || "").toLowerCase();
      const email = (d.email || "").toLowerCase();
      const dealId = (d.deal_id || "").toLowerCase();
      const projectNumber = ((d.project_number || "").toLowerCase());
      return title.includes(query) || email.includes(query) || dealId.includes(query) || projectNumber.includes(query);
    });
  }, [installmentDeals, searchQuery]);

  const stats = useMemo(() => {
    // Статистика всегда считается из всех сделок со статусом "Рассрочка", независимо от фильтра
    if (!allInstallmentDeals || allInstallmentDeals.length === 0) {
      return {
        installmentsCount: 0,
        installmentTotal: 0,
        installmentPaid: 0,
        installmentRemaining: 0,
      };
    }

    // Метрики считаем по сумме РАССРОЧКИ (total_amount - initial_payment), а не по общей сумме сделки
    const normalized = allInstallmentDeals.map((d) => {
      const totalAmount = Number(d.total_amount) || 0;
      const paidAmount = Number(d.paid_amount) || 0;
      const initialPayment = Number(d.initial_payment) || 0;
      const termMonths = Number(d.term_months) || 0;

      const installmentAmount = Math.max(0, totalAmount - initialPayment);
      // initial_payment не является фактом оплаты => оплачено по графику = paid_amount (с ограничением суммой рассрочки)
      const paidInstallment = Math.min(installmentAmount, Math.max(0, paidAmount));
      const remainingInstallment = Math.max(0, installmentAmount - paidInstallment);

      return {
        installmentAmount,
        paidInstallment,
        remainingInstallment,
      };
    });

    // Считаем все сделки со статусом "Рассрочка"
    const installmentsCount = normalized.length;
    const installmentTotal = normalized.reduce((sum, x) => sum + x.installmentAmount, 0);
    const installmentPaid = normalized.reduce((sum, x) => sum + x.paidInstallment, 0);
    const installmentRemaining = normalized.reduce((sum, x) => sum + x.remainingInstallment, 0);

    return {
      installmentsCount,
      installmentTotal,
      installmentPaid,
      installmentRemaining,
    };
  }, [allInstallmentDeals]);

  const handleClearDatabase = async () => {
    setClearing(true);
    try {
      await clearDatabase();
      alert("База данных успешно очищена!");
      setShowClearConfirm(false);
      refetch();
    } catch (error) {
      alert(`Ошибка при очистке базы данных: ${error.message || "Неизвестная ошибка"}`);
    } finally {
      setClearing(false);
    }
  };

  if (loading) {
    return (
      <main className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900/20 to-slate-900">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <Loader text="Загрузка сделок..." />
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

  if (!deals || deals.length === 0) {
    return (
      <>
        <main className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900/20 to-slate-900">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
            <div className="mb-8">
              <h1 className="text-4xl font-bold text-white mb-2">Панель администратора</h1>
              <p className="text-slate-400 text-lg">Управление рассрочками</p>
            </div>
            <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl p-12 text-center">
              <div className="text-6xl mb-4">📋</div>
              <h2 className="text-2xl font-semibold text-white mb-2">Сделки не найдены</h2>
              <p className="text-slate-400 mb-6">База данных пуста. Создайте первую сделку.</p>
              <button 
                onClick={() => setShowCreateModal(true)}
                className="px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors flex items-center gap-2 font-medium mx-auto"
              >
                <Plus className="w-5 h-5" />
                Добавить первую сделку
              </button>
            </div>
          </div>
        </main>
        {showCreateModal && (
          <CreateDealModal
            onClose={() => setShowCreateModal(false)}
            onSuccess={() => {
              setShowCreateModal(false);
              refetch();
            }}
          />
        )}
      </>
    );
  }

  // По умолчанию показываем только рассрочки: если их нет — выводим пустое состояние
  if (installmentDeals.length === 0) {
    return (
      <>
        <main className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900/20 to-slate-900">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
            <div className="mb-8">
              <h1 className="text-4xl font-bold text-white mb-2">Панель администратора</h1>
              <p className="text-slate-400 text-lg">Управление рассрочками</p>
            </div>
            <div className="mb-6">
              <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between">
                <div className="relative flex-1 w-full sm:max-w-md">
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-slate-400" />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Поиск по имени, email или номеру проекта..."
                    className="w-full pl-10 pr-4 py-3 bg-slate-800/50 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent text-sm sm:text-base"
                  />
                </div>
                <div className="flex flex-wrap gap-3">
                  <button 
                    onClick={() => setShowCreateModal(true)}
                    className="px-4 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors flex items-center gap-2 font-medium"
                  >
                    <Plus className="w-4 h-4" />
                    <span className="hidden sm:inline">Добавить сделку</span>
                    <span className="sm:hidden">Добавить</span>
                  </button>
                  <button 
                    onClick={() => setShowClearConfirm(true)}
                    className="px-4 py-3 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors flex items-center gap-2 font-medium"
                  >
                    <Trash2 className="w-4 h-4" />
                    <span className="hidden sm:inline">Очистить БД</span>
                    <span className="sm:hidden">Очистить</span>
                  </button>
                </div>
              </div>
            </div>
            <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl p-12 text-center">
              <div className="text-6xl mb-4">📋</div>
              <h2 className="text-2xl font-semibold text-white mb-2">Рассрочки не найдены</h2>
              <p className="text-slate-400 mb-6">По выбранному фильтру рассрочки не найдены.</p>
              <button 
                onClick={() => setShowCreateModal(true)}
                className="px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors flex items-center gap-2 font-medium mx-auto"
              >
                <Plus className="w-5 h-5" />
                Добавить сделку
              </button>
            </div>
          </div>
        </main>
        {showCreateModal && (
          <CreateDealModal
            onClose={() => setShowCreateModal(false)}
            onSuccess={() => {
              setShowCreateModal(false);
              refetch();
            }}
          />
        )}
        {showClearConfirm && (
          <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50">
            <div className="bg-slate-800 border border-red-500/50 rounded-xl p-6 max-w-md w-full mx-4 shadow-2xl">
              <div className="flex items-center gap-3 mb-4">
                <div className="p-2 bg-red-500/20 rounded-lg">
                  <Trash2 className="w-6 h-6 text-red-400" />
                </div>
                <h2 className="text-xl font-semibold text-white">Очистка базы данных</h2>
              </div>
              
              <div className="mb-6">
                <p className="text-slate-300 mb-2">
                  Вы уверены, что хотите очистить всю базу данных?
                </p>
                <p className="text-sm text-red-400 font-medium">
                  ⚠️ Это действие удалит:
                </p>
                <ul className="text-sm text-slate-400 mt-2 ml-4 list-disc space-y-1">
                  <li>Все сделки (deals)</li>
                  <li>Все логи платежей (payment_logs)</li>
                  <li>Все распределения платежей (cash_allocations)</li>
                </ul>
                <p className="text-sm text-red-400 font-medium mt-4">
                  Это действие нельзя отменить!
                </p>
              </div>

              <div className="flex gap-3 justify-end">
                <button
                  onClick={() => setShowClearConfirm(false)}
                  disabled={clearing}
                  className="px-4 py-2 border border-slate-600 text-slate-300 rounded-lg hover:bg-slate-700 disabled:opacity-50 transition-colors"
                >
                  Отмена
                </button>
                <button
                  onClick={handleClearDatabase}
                  disabled={clearing}
                  className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 flex items-center gap-2 transition-colors"
                >
                  {clearing ? (
                    <>
                      <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                      Очистка...
                    </>
                  ) : (
                    <>
                      <Trash2 className="w-4 h-4" />
                      Очистить БД
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        )}
      </>
    );
  }

  return (
    <>
    <main className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900/20 to-slate-900">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Заголовок */}
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-white mb-2">Панель администратора</h1>
          <p className="text-slate-400 text-lg">Управление рассрочками</p>
        </div>

        {/* Поиск и фильтры */}
        <div className="mb-6 space-y-4">
          <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between">
            <div className="relative flex-1 w-full sm:max-w-md">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-slate-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Поиск по имени, email или номеру проекта..."
                className="w-full pl-10 pr-4 py-3 bg-slate-800/50 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent text-sm sm:text-base"
              />
            </div>
            <div className="flex flex-wrap gap-3">
              <button 
                onClick={() => setShowCreateModal(true)}
                className="px-4 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors flex items-center gap-2 font-medium"
              >
                <Plus className="w-4 h-4" />
                <span className="hidden sm:inline">Добавить сделку</span>
                <span className="sm:hidden">Добавить</span>
              </button>
              <button 
                onClick={() => setShowClearConfirm(true)}
                className="px-4 py-3 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors flex items-center gap-2 font-medium"
              >
                <Trash2 className="w-4 h-4" />
                <span className="hidden sm:inline">Очистить БД</span>
                <span className="sm:hidden">Очистить</span>
              </button>
            </div>
          </div>
          
          {/* Фильтр по статусу */}
          <div className="flex items-center gap-2 flex-wrap">
            <Filter className="w-5 h-5 text-slate-400" />
            <span className="text-sm text-slate-400 font-medium">Фильтр:</span>
            <button
              onClick={() => setFilterType("open")}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                filterType === "open"
                  ? "bg-purple-600 text-white"
                  : "bg-slate-800/50 text-slate-300 hover:bg-slate-700 border border-slate-700"
              }`}
            >
              Открытые
            </button>
            <button
              onClick={() => setFilterType("closed")}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                filterType === "closed"
                  ? "bg-purple-600 text-white"
                  : "bg-slate-800/50 text-slate-300 hover:bg-slate-700 border border-slate-700"
              }`}
            >
              Закрытые
            </button>
          </div>
        </div>

        {/* Статистика */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6 mb-6 sm:mb-8">
          <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl p-6 hover:bg-slate-800/70 transition-all hover:border-purple-500/50">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-slate-400 mb-1">Рассрочек</p>
                <p className="text-3xl font-bold text-white">{stats.installmentsCount}</p>
              </div>
              <div className="p-3 bg-purple-500/20 rounded-lg">
                <ClipboardList className="w-6 h-6 text-purple-400" />
              </div>
            </div>
          </div>

          <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl p-6 hover:bg-slate-800/70 transition-all hover:border-purple-500/50">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-slate-400 mb-1">Оплачено</p>
                <p className="text-3xl font-bold text-emerald-400">
                  {stats.installmentPaid.toLocaleString('ru-RU')} ₽
                </p>
              </div>
              <div className="p-3 bg-emerald-500/20 rounded-lg">
                <Wallet className="w-6 h-6 text-emerald-400" />
              </div>
            </div>
          </div>

          <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl p-6 hover:bg-slate-800/70 transition-all hover:border-purple-500/50">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-slate-400 mb-1">Осталось оплатить</p>
                <p className="text-3xl font-bold text-blue-400">
                  {stats.installmentRemaining.toLocaleString('ru-RU')} ₽
                </p>
              </div>
              <div className="p-3 bg-blue-500/20 rounded-lg">
                <Banknote className="w-6 h-6 text-blue-400" />
              </div>
            </div>
          </div>

          <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl p-6 hover:bg-slate-800/70 transition-all hover:border-purple-500/50">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-slate-400 mb-1">Общая сумма рассрочки</p>
                <p className="text-3xl font-bold text-white">
                  {stats.installmentTotal.toLocaleString('ru-RU')} ₽
                </p>
              </div>
              <div className="p-3 bg-purple-500/20 rounded-lg">
                <DollarSign className="w-6 h-6 text-purple-400" />
              </div>
            </div>
          </div>
        </div>

        {/* Таблица */}
        <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl overflow-hidden">
          <div className="px-4 sm:px-6 py-4 border-b border-slate-700">
            <h2 className="text-base sm:text-lg font-semibold text-white">Список рассрочек</h2>
            <p className="text-xs sm:text-sm text-slate-400 mt-1">
              Найдено: {filteredDeals.length} из {installmentDeals.length}
            </p>
          </div>
          <DealsTable deals={filteredDeals} onRefresh={refetch} />
        </div>
      </div>

      {/* Модальное окно подтверждения очистки БД */}
      {showClearConfirm && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-slate-800 border border-red-500/50 rounded-xl p-6 max-w-md w-full mx-4 shadow-2xl">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 bg-red-500/20 rounded-lg">
                <Trash2 className="w-6 h-6 text-red-400" />
              </div>
              <h2 className="text-xl font-semibold text-white">Очистка базы данных</h2>
            </div>
            
            <div className="mb-6">
              <p className="text-slate-300 mb-2">
                Вы уверены, что хотите очистить всю базу данных?
              </p>
              <p className="text-sm text-red-400 font-medium">
                ⚠️ Это действие удалит:
              </p>
              <ul className="text-sm text-slate-400 mt-2 ml-4 list-disc space-y-1">
                <li>Все сделки (deals)</li>
                <li>Все логи платежей (payment_logs)</li>
                <li>Все распределения платежей (cash_allocations)</li>
              </ul>
              <p className="text-sm text-red-400 font-medium mt-4">
                Это действие нельзя отменить!
              </p>
            </div>

            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setShowClearConfirm(false)}
                disabled={clearing}
                className="px-4 py-2 border border-slate-600 text-slate-300 rounded-lg hover:bg-slate-700 disabled:opacity-50 transition-colors"
              >
                Отмена
              </button>
              <button
                onClick={handleClearDatabase}
                disabled={clearing}
                className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 flex items-center gap-2 transition-colors"
              >
                {clearing ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                    Очистка...
                  </>
                ) : (
                  <>
                    <Trash2 className="w-4 h-4" />
                    Очистить БД
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
      {showCreateModal && (
        <CreateDealModal
          onClose={() => setShowCreateModal(false)}
          onSuccess={() => {
            setShowCreateModal(false);
            refetch();
          }}
        />
      )}
    </main>
    </>
  );
}

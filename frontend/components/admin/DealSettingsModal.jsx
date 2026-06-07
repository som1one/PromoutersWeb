"use client";

import { useState } from "react";
import { updateDealSettings } from "@/modules/admin/deals/api";
import { Settings, X } from "lucide-react";

export default function DealSettingsModal({ deal, dealId, onClose, onSuccess }) {
  const [formData, setFormData] = useState({
    total_amount: deal?.total_amount || 0,
    // Не подставляем "6" по умолчанию — если срок не задан, пусть админ явно укажет
    term_months: typeof deal?.term_months === "number" ? deal.term_months : 0,
    initial_payment: deal?.initial_payment || 0,
    title: deal?.title || "",
    project_number: deal?.project_number || "",
    schedule_day: deal?.schedule_day || null,  // День месяца для платежей (1-31)
    // Информация о проекте
    client_name: deal?.client_name || "",
    project_type: deal?.project_type || "",
    project_start_date: deal?.project_start_date || "",
    object_location: deal?.object_location || ""
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      await updateDealSettings(dealId, {
        total_amount: formData.total_amount > 0 ? formData.total_amount : undefined,
        term_months: formData.term_months >= 0 ? formData.term_months : undefined,
        initial_payment: formData.initial_payment >= 0 ? formData.initial_payment : undefined,
        title: formData.title || undefined,
        project_number: formData.project_number || undefined,
        schedule_day: formData.schedule_day && formData.schedule_day >= 1 && formData.schedule_day <= 31 ? formData.schedule_day : undefined,
        // Информация о проекте
        client_name: formData.client_name || undefined,
        project_type: formData.project_type || undefined,
        project_start_date: formData.project_start_date || undefined,
        object_location: formData.object_location || undefined
      });
      onSuccess?.();
    } catch (err) {
      setError(err.message || "Ошибка при обновлении настроек");
      console.error("settings_update_error", err);
    } finally {
      setLoading(false);
    }
  };

  const formatAmount = (value) => {
    const numbers = value.replace(/\D/g, "");
    return numbers.replace(/\B(?=(\d{3})+(?!\d))/g, " ");
  };

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-slate-800 border border-slate-700 rounded-xl max-w-2xl w-full shadow-2xl max-h-[90vh] overflow-y-auto custom-scrollbar">
        <div className="sticky top-0 bg-slate-800 border-b border-slate-700 px-6 py-4 flex justify-between items-center">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-purple-500/20 rounded-lg">
              <Settings className="w-5 h-5 text-purple-400" />
            </div>
            <h2 className="text-xl font-semibold text-white">Настройки рассрочки</h2>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-slate-700 rounded-lg transition-colors"
          >
            <X className="w-5 h-5 text-slate-400" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Общая сумма (₽)
              </label>
              <input
                type="text"
                value={formData.total_amount ? formatAmount(formData.total_amount.toString()) : ""}
                onChange={(e) => {
                  const num = parseInt(e.target.value.replace(/\s/g, "")) || 0;
                  setFormData({ ...formData, total_amount: num });
                }}
                placeholder="0"
                className="w-full px-4 py-3 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                required
                disabled={loading}
              />
              <p className="text-xs text-slate-400 mt-1">
                Текущая оплаченная сумма: {deal?.paid_amount?.toLocaleString('ru-RU') || 0} ₽
              </p>
            </div>

            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="block text-sm font-medium text-slate-300">
                  Срок рассрочки (месяцев)
                </label>
                {formData.term_months > 0 && (
                  <button
                    type="button"
                    onClick={() => setFormData({ ...formData, term_months: 0 })}
                    disabled={loading}
                    className="text-xs text-red-400 hover:text-red-300 underline disabled:opacity-50 transition-colors"
                  >
                    Сбросить срок
                  </button>
                )}
              </div>
              <input
                type="number"
                value={formData.term_months}
                onChange={(e) => setFormData({ ...formData, term_months: parseInt(e.target.value) || 0 })}
                min="0"
                max="120"
                className="w-full px-4 py-3 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                required
                disabled={loading}
              />
              <p className="text-xs text-slate-400 mt-1">
                {formData.term_months === 0 ? "0 = график не настроен" : "От 1 до 120 месяцев"}
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Первоначальный взнос (₽)
              </label>
              <input
                type="text"
                value={formatAmount(String(formData.initial_payment ?? 0))}
                onChange={(e) => {
                  const num = parseInt(e.target.value.replace(/\s/g, "")) || 0;
                  setFormData({ ...formData, initial_payment: num });
                }}
                placeholder="0"
                className="w-full px-4 py-3 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                disabled={loading}
              />
              <p className="text-xs text-slate-400 mt-1">
                Это засчитывается как оплата 1-го месяца и увеличивает «Оплачено».
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Число оплаты (день месяца)
              </label>
              <input
                type="number"
                value={formData.schedule_day || ""}
                onChange={(e) => {
                  const val = e.target.value === "" ? null : parseInt(e.target.value);
                  if (val === null || (val >= 1 && val <= 31)) {
                    setFormData({ ...formData, schedule_day: val });
                  }
                }}
                min="1"
                max="31"
                placeholder="10"
                className="w-full px-4 py-3 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                disabled={loading}
              />
              <p className="text-xs text-slate-400 mt-1">
                День месяца, когда должен производиться платёж (1-31). По умолчанию: {new Date().getDate()}
              </p>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Название сделки
            </label>
            <input
              type="text"
              value={formData.title}
              onChange={(e) => setFormData({ ...formData, title: e.target.value })}
              placeholder="Название сделки"
              className="w-full px-4 py-3 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
              disabled={loading}
            />
          </div>

          {/* Информация о проекте */}
          <div className="pt-4 border-t border-slate-700">
            <h3 className="text-base font-semibold text-white mb-4">Информация о проекте</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">
                  Клиент
                </label>
                <input
                  type="text"
                  value={formData.client_name}
                  onChange={(e) => setFormData({ ...formData, client_name: e.target.value })}
                  placeholder="Имя клиента"
                  className="w-full px-4 py-3 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                  disabled={loading}
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">
                  Телефон
                </label>
                <input
                  type="text"
                  value={formData.project_number}
                  onChange={(e) => setFormData({ ...formData, project_number: e.target.value })}
                  placeholder="+7 (999) 123-45-67"
                  className="w-full px-4 py-3 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                  disabled={loading}
                />
                <p className="text-xs text-slate-400 mt-1">
                  По этому номеру клиент сможет войти в систему
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">
                  Тип проекта
                </label>
                <input
                  type="text"
                  value={formData.project_type}
                  onChange={(e) => setFormData({ ...formData, project_type: e.target.value })}
                  placeholder="Например, Дом, Квартира"
                  className="w-full px-4 py-3 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                  disabled={loading}
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">
                  Дата начала проекта
                </label>
                <input
                  type="text"
                  value={formData.project_start_date}
                  onChange={(e) => setFormData({ ...formData, project_start_date: e.target.value })}
                  placeholder="Например, 01.01.2026"
                  className="w-full px-4 py-3 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                  disabled={loading}
                />
              </div>

              <div className="md:col-span-2">
                <label className="block text-sm font-medium text-slate-300 mb-2">
                  Адрес объекта
                </label>
                <input
                  type="text"
                  value={formData.object_location}
                  onChange={(e) => setFormData({ ...formData, object_location: e.target.value })}
                  placeholder="Полный адрес объекта"
                  className="w-full px-4 py-3 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                  disabled={loading}
                />
              </div>
            </div>
          </div>

          {error && (
            <div className="bg-red-500/20 border border-red-500/30 text-red-400 px-4 py-3 rounded-lg">
              {error}
            </div>
          )}

          <div className="flex gap-3 justify-end pt-4 border-t border-slate-700">
            <button
              type="button"
              onClick={onClose}
              disabled={loading}
              className="px-4 py-2 border border-slate-600 text-slate-300 rounded-lg hover:bg-slate-700 disabled:opacity-50 transition-colors"
            >
              Отмена
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 flex items-center gap-2 transition-colors"
            >
              {loading ? (
                <>
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                  Сохранение...
                </>
              ) : (
                "Сохранить изменения"
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}


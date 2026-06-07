"use client";

import { useState } from "react";
import { createDeal } from "@/modules/admin/deals/api";
import { Plus, X } from "lucide-react";

export default function CreateDealModal({ onClose, onSuccess }) {
  const [formData, setFormData] = useState({
    deal_id: "",
    title: "",
    email: "",
    project_number: "",
    total_amount: "",
    term_months: "",
    initial_payment: "",
    schedule_day: new Date().getDate()
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      await createDeal({
        deal_id: formData.deal_id.trim(),
        title: formData.title.trim() || "Новая сделка",
        email: formData.email.trim() || null,
        project_number: formData.project_number.trim() || null,
        total_amount: parseInt(formData.total_amount.replace(/\s/g, "")) || 0,
        term_months: parseInt(formData.term_months) || 0,
        initial_payment: parseInt(formData.initial_payment.replace(/\s/g, "")) || 0,
        schedule_day: formData.schedule_day && formData.schedule_day >= 1 && formData.schedule_day <= 31 ? formData.schedule_day : null
      });
      onSuccess?.();
      onClose();
    } catch (err) {
      setError(err.message || "Ошибка при создании сделки");
      console.error("create_deal_error", err);
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
            <div className="p-2 bg-green-500/20 rounded-lg">
              <Plus className="w-5 h-5 text-green-400" />
            </div>
            <h2 className="text-xl font-semibold text-white">Создать новую сделку</h2>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-slate-700 rounded-lg transition-colors"
          >
            <X className="w-5 h-5 text-slate-400" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-6">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              ID сделки <span className="text-red-400">*</span>
            </label>
            <input
              type="text"
              value={formData.deal_id}
              onChange={(e) => setFormData({ ...formData, deal_id: e.target.value })}
              placeholder="DEAL-001"
              className="w-full px-4 py-3 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:ring-2 focus:ring-green-500 focus:border-green-500"
              required
              disabled={loading}
            />
            <p className="text-xs text-slate-400 mt-1">
              Уникальный идентификатор сделки
            </p>
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
              className="w-full px-4 py-3 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:ring-2 focus:ring-green-500 focus:border-green-500"
              disabled={loading}
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Общая сумма (₽) <span className="text-red-400">*</span>
              </label>
              <input
                type="text"
                value={formData.total_amount ? formatAmount(formData.total_amount.toString()) : ""}
                onChange={(e) => {
                  const num = e.target.value.replace(/\s/g, "");
                  setFormData({ ...formData, total_amount: num });
                }}
                placeholder="0"
                className="w-full px-4 py-3 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:ring-2 focus:ring-green-500 focus:border-green-500"
                required
                disabled={loading}
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Срок рассрочки (месяцев) <span className="text-red-400">*</span>
              </label>
              <input
                type="number"
                value={formData.term_months}
                onChange={(e) => setFormData({ ...formData, term_months: parseInt(e.target.value) || 0 })}
                min="0"
                max="120"
                placeholder="6"
                className="w-full px-4 py-3 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:ring-2 focus:ring-green-500 focus:border-green-500"
                required
                disabled={loading}
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Первоначальный взнос (₽)
              </label>
              <input
                type="text"
                value={formData.initial_payment ? formatAmount(formData.initial_payment.toString()) : ""}
                onChange={(e) => {
                  const num = e.target.value.replace(/\s/g, "");
                  setFormData({ ...formData, initial_payment: num });
                }}
                placeholder="0"
                className="w-full px-4 py-3 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:ring-2 focus:ring-green-500 focus:border-green-500"
                disabled={loading}
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Число оплаты (день месяца)
              </label>
              <input
                type="number"
                value={formData.schedule_day}
                onChange={(e) => {
                  const val = parseInt(e.target.value);
                  if (val >= 1 && val <= 31) {
                    setFormData({ ...formData, schedule_day: val });
                  }
                }}
                min="1"
                max="31"
                className="w-full px-4 py-3 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:ring-2 focus:ring-green-500 focus:border-green-500"
                disabled={loading}
              />
              <p className="text-xs text-slate-400 mt-1">
                День месяца для платежей (1-31). По умолчанию: {new Date().getDate()}
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Email клиента
              </label>
              <input
                type="email"
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                placeholder="email@example.com"
                className="w-full px-4 py-3 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:ring-2 focus:ring-green-500 focus:border-green-500"
                disabled={loading}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Номер проекта <span className="text-red-400">*</span>
              </label>
              <input
                type="text"
                value={formData.project_number}
                onChange={(e) => setFormData({ ...formData, project_number: e.target.value })}
                placeholder="Например, ПРО-001"
                className="w-full px-4 py-3 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:ring-2 focus:ring-green-500 focus:border-green-500"
                required
                disabled={loading}
              />
              <p className="text-xs text-slate-400 mt-1">
                По этому номеру клиент сможет войти в систему
              </p>
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
              className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 flex items-center gap-2 transition-colors"
            >
              {loading ? (
                <>
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                  Создание...
                </>
              ) : (
                <>
                  <Plus className="w-4 h-4" />
                  Создать сделку
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

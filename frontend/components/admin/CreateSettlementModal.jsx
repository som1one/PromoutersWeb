"use client";

import { useState, useEffect, useMemo } from "react";
import { X, Calculator, Clock, Package } from "lucide-react";
import { createSettlement, fetchPromoters } from "@/lib/api/settlements";

const RATE_TYPES = [
  { value: "hourly", label: "Почасовая", icon: Clock, unitLabel: "Часы" },
  { value: "per_leaflet", label: "Поштучно", icon: Package, unitLabel: "Штуки" },
];

export default function CreateSettlementModal({ isOpen, onClose, onSuccess }) {
  const [promoters, setPromoters] = useState([]);
  const [loadingPromoters, setLoadingPromoters] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const [promoterId, setPromoterId] = useState("");
  const [rateType, setRateType] = useState("hourly");
  const [amountPerUnit, setAmountPerUnit] = useState("");
  const [units, setUnits] = useState("");
  const [notes, setNotes] = useState("");

  useEffect(() => {
    if (!isOpen) return;
    setLoadingPromoters(true);
    fetchPromoters()
      .then((data) => {
        // Filter to show only promoter-role users, or all if role filtering isn't strict
        const list = Array.isArray(data) ? data : [];
        setPromoters(list);
      })
      .catch(() => setPromoters([]))
      .finally(() => setLoadingPromoters(false));
  }, [isOpen]);

  const totalAmount = useMemo(() => {
    const rate = parseFloat(amountPerUnit);
    const qty = parseFloat(units);
    if (isNaN(rate) || isNaN(qty) || rate <= 0 || qty <= 0) return null;
    return (rate * qty).toFixed(2);
  }, [amountPerUnit, units]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!promoterId || !amountPerUnit || !units) return;

    setSubmitting(true);
    setError(null);

    try {
      await createSettlement({
        promoter_id: promoterId,
        rate_type: rateType,
        amount_per_unit: parseFloat(amountPerUnit),
        units: parseFloat(units),
        notes: notes.trim() || null,
      });
      // Reset form
      setPromoterId("");
      setRateType("hourly");
      setAmountPerUnit("");
      setUnits("");
      setNotes("");
      onSuccess?.();
    } catch (err) {
      setError(err.message || "Ошибка при создании расчёта");
    } finally {
      setSubmitting(false);
    }
  };

  if (!isOpen) return null;

  const currentRateType = RATE_TYPES.find((r) => r.value === rateType);

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-slate-800 border border-slate-700 rounded-xl w-full max-w-md shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-700">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-purple-500/20 rounded-lg">
              <Calculator className="w-5 h-5 text-purple-400" />
            </div>
            <h2 className="text-lg font-semibold text-white">Новый расчёт</h2>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-700 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-5">
          {/* Promoter select */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Промоутер
            </label>
            {loadingPromoters ? (
              <div className="px-4 py-3 bg-slate-900/50 border border-slate-700 rounded-lg text-slate-500 text-sm">
                Загрузка...
              </div>
            ) : (
              <select
                value={promoterId}
                onChange={(e) => setPromoterId(e.target.value)}
                required
                className="w-full px-4 py-3 bg-slate-900/50 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
              >
                <option value="">Выберите промоутера</option>
                {promoters.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.first_name} {p.last_name}
                    {p.role_code ? ` (${p.role_code})` : ""}
                  </option>
                ))}
              </select>
            )}
          </div>

          {/* Rate type */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Тип оплаты
            </label>
            <div className="grid grid-cols-2 gap-3">
              {RATE_TYPES.map((type) => {
                const Icon = type.icon;
                const isSelected = rateType === type.value;
                return (
                  <button
                    key={type.value}
                    type="button"
                    onClick={() => setRateType(type.value)}
                    className={`flex items-center gap-2 px-4 py-3 rounded-lg border text-sm font-medium transition-colors ${
                      isSelected
                        ? "bg-purple-600 border-purple-500 text-white"
                        : "bg-slate-900/50 border-slate-700 text-slate-300 hover:bg-slate-700"
                    }`}
                  >
                    <Icon className="w-4 h-4" />
                    {type.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Amount per unit */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Ставка (₽/{rateType === "hourly" ? "час" : "шт."})
            </label>
            <input
              type="number"
              step="0.01"
              min="0.01"
              value={amountPerUnit}
              onChange={(e) => setAmountPerUnit(e.target.value)}
              required
              placeholder="0.00"
              className="w-full px-4 py-3 bg-slate-900/50 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
            />
          </div>

          {/* Units */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              {currentRateType?.unitLabel || "Количество"}
            </label>
            <input
              type="number"
              step="0.01"
              min="0.01"
              value={units}
              onChange={(e) => setUnits(e.target.value)}
              required
              placeholder={rateType === "hourly" ? "Количество часов" : "Количество штук"}
              className="w-full px-4 py-3 bg-slate-900/50 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
            />
          </div>

          {/* Total preview */}
          {totalAmount && (
            <div className="bg-slate-900/50 border border-slate-700 rounded-lg px-4 py-3">
              <p className="text-sm text-slate-400">Итого к выплате:</p>
              <p className="text-2xl font-bold text-emerald-400">
                {Number(totalAmount).toLocaleString("ru-RU")} ₽
              </p>
            </div>
          )}

          {/* Notes */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Комментарий (необязательно)
            </label>
            <input
              type="text"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Дополнительная информация"
              className="w-full px-4 py-3 bg-slate-900/50 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
            />
          </div>

          {/* Error */}
          {error && (
            <div className="px-4 py-3 bg-red-500/10 border border-red-500/30 rounded-lg">
              <p className="text-sm text-red-400">{error}</p>
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={submitting}
              className="flex-1 px-4 py-3 border border-slate-600 text-slate-300 rounded-lg hover:bg-slate-700 disabled:opacity-50 transition-colors font-medium"
            >
              Отмена
            </button>
            <button
              type="submit"
              disabled={submitting || !promoterId || !amountPerUnit || !units}
              className="flex-1 px-4 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 transition-colors font-medium flex items-center justify-center gap-2"
            >
              {submitting ? (
                <>
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  Создание...
                </>
              ) : (
                <>
                  <Calculator className="w-4 h-4" />
                  Создать
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

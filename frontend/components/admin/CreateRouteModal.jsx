"use client";

import { useState, useEffect } from "react";
import { createRoute, fetchAvailablePromoters } from "@/lib/api/routes";
import { Plus, X, MapPin } from "lucide-react";

export default function CreateRouteModal({ isOpen, onClose, onSuccess }) {
  const [formData, setFormData] = useState({
    title: "",
    work_date: "",
    address: "",
    description: "",
    promoter_id: "",
  });
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [promoters, setPromoters] = useState([]);
  const [promotersLoading, setPromotersLoading] = useState(false);

  useEffect(() => {
    if (isOpen) {
      loadPromoters();
    }
  }, [isOpen]);

  const loadPromoters = async () => {
    setPromotersLoading(true);
    try {
      const data = await fetchAvailablePromoters();
      setPromoters(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error("fetch_promoters_error", err);
      setPromoters([]);
    } finally {
      setPromotersLoading(false);
    }
  };

  const validate = () => {
    const newErrors = {};

    if (!formData.title.trim()) {
      newErrors.title = "Название маршрута обязательно";
    } else if (formData.title.trim().length > 255) {
      newErrors.title = "Название не должно превышать 255 символов";
    }

    if (!formData.work_date) {
      newErrors.work_date = "Дата обязательна";
    }

    if (!formData.address.trim()) {
      newErrors.address = "Адрес обязателен";
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);

    if (!validate()) {
      return;
    }

    setLoading(true);

    try {
      const payload = {
        title: formData.title.trim(),
        work_date: formData.work_date,
        address: formData.address.trim(),
      };

      if (formData.description.trim()) {
        payload.description = formData.description.trim();
      }

      if (formData.promoter_id) {
        payload.promoter_id = parseInt(formData.promoter_id, 10);
      }

      await createRoute(payload);
      onSuccess?.();
      handleClose();
    } catch (err) {
      setError(err.message || "Ошибка при создании маршрута");
      console.error("create_route_error", err);
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    setFormData({
      title: "",
      work_date: "",
      address: "",
      description: "",
      promoter_id: "",
    });
    setErrors({});
    setError(null);
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-slate-800 border border-slate-700 rounded-xl max-w-2xl w-full shadow-2xl max-h-[90vh] overflow-y-auto custom-scrollbar">
        <div className="sticky top-0 bg-slate-800 border-b border-slate-700 px-6 py-4 flex justify-between items-center">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-green-500/20 rounded-lg">
              <MapPin className="w-5 h-5 text-green-400" />
            </div>
            <h2 className="text-xl font-semibold text-white">Создать новый маршрут</h2>
          </div>
          <button
            onClick={handleClose}
            className="p-2 hover:bg-slate-700 rounded-lg transition-colors"
          >
            <X className="w-5 h-5 text-slate-400" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-6">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Название маршрута <span className="text-red-400">*</span>
            </label>
            <input
              type="text"
              value={formData.title}
              onChange={(e) => {
                setFormData({ ...formData, title: e.target.value });
                if (errors.title) setErrors({ ...errors, title: null });
              }}
              placeholder="Например, Раздача листовок ТЦ Мега"
              maxLength={255}
              className={`w-full px-4 py-3 bg-slate-700 border rounded-lg text-white placeholder-slate-500 focus:ring-2 focus:ring-green-500 focus:border-green-500 ${
                errors.title ? "border-red-500" : "border-slate-600"
              }`}
              disabled={loading}
            />
            {errors.title && (
              <p className="text-xs text-red-400 mt-1">{errors.title}</p>
            )}
            <p className="text-xs text-slate-400 mt-1">
              {formData.title.length}/255 символов
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Дата <span className="text-red-400">*</span>
              </label>
              <input
                type="date"
                value={formData.work_date}
                onChange={(e) => {
                  setFormData({ ...formData, work_date: e.target.value });
                  if (errors.work_date) setErrors({ ...errors, work_date: null });
                }}
                className={`w-full px-4 py-3 bg-slate-700 border rounded-lg text-white placeholder-slate-500 focus:ring-2 focus:ring-green-500 focus:border-green-500 ${
                  errors.work_date ? "border-red-500" : "border-slate-600"
                }`}
                disabled={loading}
              />
              {errors.work_date && (
                <p className="text-xs text-red-400 mt-1">{errors.work_date}</p>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Промоутер
              </label>
              <select
                value={formData.promoter_id}
                onChange={(e) => setFormData({ ...formData, promoter_id: e.target.value })}
                className="w-full px-4 py-3 bg-slate-700 border border-slate-600 rounded-lg text-white focus:ring-2 focus:ring-green-500 focus:border-green-500"
                disabled={loading || promotersLoading}
              >
                <option value="">Не назначен (черновик)</option>
                {promotersLoading ? (
                  <option disabled>Загрузка...</option>
                ) : (
                  promoters.map((promoter) => (
                    <option key={promoter.id} value={promoter.id}>
                      {promoter.full_name || promoter.name || `Промоутер #${promoter.id}`}
                    </option>
                  ))
                )}
              </select>
              <p className="text-xs text-slate-400 mt-1">
                {formData.promoter_id
                  ? "Маршрут будет создан со статусом «назначен»"
                  : "Маршрут будет создан со статусом «черновик»"}
              </p>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Адрес <span className="text-red-400">*</span>
            </label>
            <input
              type="text"
              value={formData.address}
              onChange={(e) => {
                setFormData({ ...formData, address: e.target.value });
                if (errors.address) setErrors({ ...errors, address: null });
              }}
              placeholder="г. Москва, ул. Примерная, д. 1"
              className={`w-full px-4 py-3 bg-slate-700 border rounded-lg text-white placeholder-slate-500 focus:ring-2 focus:ring-green-500 focus:border-green-500 ${
                errors.address ? "border-red-500" : "border-slate-600"
              }`}
              disabled={loading}
            />
            {errors.address && (
              <p className="text-xs text-red-400 mt-1">{errors.address}</p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Описание
            </label>
            <textarea
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              placeholder="Дополнительная информация о маршруте..."
              rows={3}
              className="w-full px-4 py-3 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:ring-2 focus:ring-green-500 focus:border-green-500 resize-none"
              disabled={loading}
            />
          </div>

          {error && (
            <div className="bg-red-500/20 border border-red-500/30 text-red-400 px-4 py-3 rounded-lg">
              {error}
            </div>
          )}

          <div className="flex gap-3 justify-end pt-4 border-t border-slate-700">
            <button
              type="button"
              onClick={handleClose}
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
                  Создать маршрут
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

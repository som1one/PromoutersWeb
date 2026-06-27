"use client";

import { useState, useEffect, useCallback } from "react";
import { fetchRoutes } from "@/lib/api/routes";
import CreateRouteModal from "@/components/admin/CreateRouteModal";
import { Loader, ErrorState } from "@/components/ui/State";
import { Plus, MapPin, ChevronLeft, ChevronRight } from "lucide-react";

const PAGE_SIZE = 50;

const STATUS_LABELS = {
  draft: "Черновик",
  assigned: "Назначен",
  in_progress: "В работе",
  completed: "Завершён",
  cancelled: "Отменён",
};

const STATUS_COLORS = {
  draft: "bg-slate-500/20 text-slate-300",
  assigned: "bg-blue-500/20 text-blue-300",
  in_progress: "bg-yellow-500/20 text-yellow-300",
  completed: "bg-green-500/20 text-green-300",
  cancelled: "bg-red-500/20 text-red-300",
};

function formatDate(dateStr) {
  if (!dateStr) return "—";
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return dateStr;
  return d.toLocaleDateString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

function RouteStatusBadge({ status }) {
  const label = STATUS_LABELS[status] || status;
  const color = STATUS_COLORS[status] || "bg-slate-500/20 text-slate-300";

  return (
    <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium ${color}`}>
      {label}
    </span>
  );
}

function RoutesTable({ routes, page }) {
  if (!routes || routes.length === 0) {
    return (
      <div className="p-12 text-center">
        <div className="text-5xl mb-4">🗺️</div>
        <p className="text-slate-400 text-lg">Маршруты не найдены</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="border-b border-slate-700">
            <th className="px-4 sm:px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
              №
            </th>
            <th className="px-4 sm:px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
              Дата
            </th>
            <th className="px-4 sm:px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
              Название
            </th>
            <th className="px-4 sm:px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
              Промоутер
            </th>
            <th className="px-4 sm:px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
              Статус
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-700/50">
          {routes.map((route, index) => (
            <tr
              key={route.id}
              className="hover:bg-slate-700/30 transition-colors"
            >
              <td className="px-4 sm:px-6 py-4 text-sm text-slate-300">
                {(page - 1) * PAGE_SIZE + index + 1}
              </td>
              <td className="px-4 sm:px-6 py-4 text-sm text-slate-300">
                {formatDate(route.work_date)}
              </td>
              <td className="px-4 sm:px-6 py-4 text-sm text-white font-medium">
                {route.title || "—"}
              </td>
              <td className="px-4 sm:px-6 py-4 text-sm text-slate-300">
                {route.promoter?.full_name || route.promoter?.name || "Не назначен"}
              </td>
              <td className="px-4 sm:px-6 py-4">
                <RouteStatusBadge status={route.status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Pagination({ page, totalPages, onPageChange }) {
  if (totalPages <= 1) return null;

  return (
    <div className="flex items-center justify-between px-4 sm:px-6 py-4 border-t border-slate-700">
      <p className="text-sm text-slate-400">
        Страница {page} из {totalPages}
      </p>
      <div className="flex items-center gap-2">
        <button
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
          className="p-2 rounded-lg border border-slate-700 text-slate-300 hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <ChevronLeft className="w-4 h-4" />
        </button>
        <button
          onClick={() => onPageChange(page + 1)}
          disabled={page >= totalPages}
          className="p-2 rounded-lg border border-slate-700 text-slate-300 hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}

export default function AdminRoutesPage() {
  const [routes, setRoutes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [showCreateModal, setShowCreateModal] = useState(false);

  const loadRoutes = useCallback(async (currentPage = 1) => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchRoutes({ page: currentPage, pageSize: PAGE_SIZE });

      // Handle paginated response (items + total) or plain array
      if (data && typeof data === "object" && Array.isArray(data.items)) {
        setRoutes(data.items);
        const total = data.total || data.items.length;
        setTotalPages(Math.max(1, Math.ceil(total / PAGE_SIZE)));
      } else if (Array.isArray(data)) {
        // Sort by date descending on client side if backend doesn't sort
        const sorted = [...data].sort((a, b) => {
          const dateA = new Date(a.work_date || 0);
          const dateB = new Date(b.work_date || 0);
          return dateB - dateA;
        });
        // Client-side pagination fallback
        const start = (currentPage - 1) * PAGE_SIZE;
        const pageItems = sorted.slice(start, start + PAGE_SIZE);
        setRoutes(pageItems);
        setTotalPages(Math.max(1, Math.ceil(sorted.length / PAGE_SIZE)));
      } else {
        setRoutes([]);
        setTotalPages(1);
      }
    } catch (err) {
      setError(err.message || "Ошибка загрузки маршрутов");
      setRoutes([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadRoutes(page);
  }, [page, loadRoutes]);

  const handlePageChange = (newPage) => {
    setPage(newPage);
  };

  const handleCreateSuccess = () => {
    setShowCreateModal(false);
    setPage(1);
    loadRoutes(1);
  };

  if (loading) {
    return (
      <main className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900/20 to-slate-900">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <Loader text="Загрузка маршрутов..." />
        </div>
      </main>
    );
  }

  if (error) {
    return (
      <main className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900/20 to-slate-900">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <ErrorState message={error} onRetry={() => loadRoutes(page)} />
        </div>
      </main>
    );
  }

  return (
    <>
      <main className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900/20 to-slate-900">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          {/* Header */}
          <div className="mb-8 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div>
              <h1 className="text-4xl font-bold text-white mb-2">Маршруты</h1>
              <p className="text-slate-400 text-lg">Управление маршрутами промоутеров</p>
            </div>
            <button
              onClick={() => setShowCreateModal(true)}
              className="px-4 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors flex items-center gap-2 font-medium"
            >
              <Plus className="w-4 h-4" />
              Создать новый маршрут
            </button>
          </div>

          {/* Routes Table */}
          <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl overflow-hidden">
            <div className="px-4 sm:px-6 py-4 border-b border-slate-700">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-purple-500/20 rounded-lg">
                  <MapPin className="w-5 h-5 text-purple-400" />
                </div>
                <div>
                  <h2 className="text-base sm:text-lg font-semibold text-white">
                    Список маршрутов
                  </h2>
                  <p className="text-xs sm:text-sm text-slate-400 mt-0.5">
                    Всего: {routes.length} на странице
                  </p>
                </div>
              </div>
            </div>
            <RoutesTable routes={routes} page={page} />
            <Pagination
              page={page}
              totalPages={totalPages}
              onPageChange={handlePageChange}
            />
          </div>
        </div>
      </main>

      <CreateRouteModal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        onSuccess={handleCreateSuccess}
      />
    </>
  );
}

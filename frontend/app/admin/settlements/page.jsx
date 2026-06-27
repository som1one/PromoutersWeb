"use client";

import { useState, useEffect, useCallback } from "react";
import { fetchSettlements } from "@/lib/api/settlements";
import { getUser } from "@/lib/auth";
import SettlementsTable from "@/components/admin/SettlementsTable";
import SettlementFilters from "@/components/admin/SettlementFilters";
import { Loader, ErrorState } from "@/components/ui/State";
import { Calculator, ChevronLeft, ChevronRight, FileX2 } from "lucide-react";

const PAGE_SIZE = 50;

export default function AdminSettlementsPage() {
  const [settlements, setSettlements] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [filters, setFilters] = useState({ status: null, search: "" });
  const [userRole, setUserRole] = useState(null);

  useEffect(() => {
    const user = getUser();
    if (user?.role) {
      setUserRole(user.role);
    }
  }, []);

  const loadSettlements = useCallback(
    async (currentPage = 1, currentFilters = filters) => {
      setLoading(true);
      setError(null);
      try {
        const data = await fetchSettlements({
          status: currentFilters.status,
          search: currentFilters.search,
          page: currentPage,
          pageSize: PAGE_SIZE,
        });

        // Handle paginated response { items, total, page, page_size } or plain array
        if (data && typeof data === "object" && Array.isArray(data.items)) {
          setSettlements(data.items);
          const total = data.total || data.items.length;
          setTotalPages(Math.max(1, Math.ceil(total / PAGE_SIZE)));
        } else if (Array.isArray(data)) {
          // Client-side pagination fallback
          const start = (currentPage - 1) * PAGE_SIZE;
          const pageItems = data.slice(start, start + PAGE_SIZE);
          setSettlements(pageItems);
          setTotalPages(Math.max(1, Math.ceil(data.length / PAGE_SIZE)));
        } else {
          setSettlements([]);
          setTotalPages(1);
        }
      } catch (err) {
        setError(err.message || "Ошибка загрузки расчётов");
        setSettlements([]);
      } finally {
        setLoading(false);
      }
    },
    [filters]
  );

  useEffect(() => {
    loadSettlements(page, filters);
  }, [page, filters, loadSettlements]);

  const handleFilterChange = (newFilters) => {
    setFilters(newFilters);
    setPage(1);
  };

  const handlePageChange = (newPage) => {
    setPage(newPage);
  };

  const handleRefresh = () => {
    loadSettlements(page, filters);
  };

  if (loading) {
    return (
      <main className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900/20 to-slate-900">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <Loader text="Загрузка расчётов..." />
        </div>
      </main>
    );
  }

  if (error) {
    return (
      <main className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900/20 to-slate-900">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <ErrorState message={error} onRetry={handleRefresh} />
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900/20 to-slate-900">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-white mb-2">Расчёты</h1>
          <p className="text-slate-400 text-lg">Управление выплатами промоутерам</p>
        </div>

        {/* Filters */}
        <div className="mb-6">
          <SettlementFilters onFilterChange={handleFilterChange} />
        </div>

        {/* Table */}
        <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl overflow-hidden">
          <div className="px-4 sm:px-6 py-4 border-b border-slate-700">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-purple-500/20 rounded-lg">
                <Calculator className="w-5 h-5 text-purple-400" />
              </div>
              <div>
                <h2 className="text-base sm:text-lg font-semibold text-white">
                  Список расчётов
                </h2>
                <p className="text-xs sm:text-sm text-slate-400 mt-0.5">
                  {settlements.length > 0
                    ? `Показано: ${settlements.length} на странице`
                    : "Нет записей"}
                </p>
              </div>
            </div>
          </div>

          {settlements.length === 0 ? (
            <div className="flex flex-col items-center justify-center p-12 text-slate-400">
              <FileX2 className="w-12 h-12 mb-4 text-slate-500" />
              <p className="text-lg text-center">Расчёты не найдены</p>
            </div>
          ) : (
            <>
              <SettlementsTable
                settlements={settlements}
                startIndex={(page - 1) * PAGE_SIZE}
                onRefresh={handleRefresh}
                userRole={userRole}
              />
              {totalPages > 1 && (
                <div className="flex items-center justify-between px-4 sm:px-6 py-4 border-t border-slate-700">
                  <p className="text-sm text-slate-400">
                    Страница {page} из {totalPages}
                  </p>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handlePageChange(page - 1)}
                      disabled={page <= 1}
                      className="p-2 rounded-lg border border-slate-700 text-slate-300 hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                      <ChevronLeft className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => handlePageChange(page + 1)}
                      disabled={page >= totalPages}
                      className="p-2 rounded-lg border border-slate-700 text-slate-300 hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                      <ChevronRight className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </main>
  );
}

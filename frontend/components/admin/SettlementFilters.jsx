"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { Search } from "lucide-react";

const STATUS_TABS = [
  { key: "all", label: "Все" },
  { key: "calculated", label: "Завершён" },
  { key: "paid", label: "Выплачено" },
];

export default function SettlementFilters({ onFilterChange }) {
  const [activeStatus, setActiveStatus] = useState("all");
  const [searchValue, setSearchValue] = useState("");
  const debounceTimer = useRef(null);

  const emitFilterChange = useCallback(
    (status, search) => {
      onFilterChange?.({
        status: status === "all" ? null : status,
        search: search.length >= 2 ? search : "",
      });
    },
    [onFilterChange]
  );

  const handleStatusChange = (statusKey) => {
    setActiveStatus(statusKey);
    emitFilterChange(statusKey, searchValue.length >= 2 ? searchValue : "");
  };

  const handleSearchChange = (e) => {
    const value = e.target.value;
    setSearchValue(value);

    if (debounceTimer.current) {
      clearTimeout(debounceTimer.current);
    }

    debounceTimer.current = setTimeout(() => {
      emitFilterChange(activeStatus, value.length >= 2 ? value : "");
    }, 300);
  };

  useEffect(() => {
    return () => {
      if (debounceTimer.current) {
        clearTimeout(debounceTimer.current);
      }
    };
  }, []);

  return (
    <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between">
      {/* Status filter tabs */}
      <div className="flex items-center gap-2 flex-wrap">
        {STATUS_TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => handleStatusChange(tab.key)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              activeStatus === tab.key
                ? "bg-purple-600 text-white"
                : "bg-slate-800/50 text-slate-300 hover:bg-slate-700 border border-slate-700"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Search input */}
      <div className="relative flex-1 w-full sm:max-w-md">
        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-slate-400" />
        <input
          type="text"
          value={searchValue}
          onChange={handleSearchChange}
          placeholder="Поиск по промоутеру или адресу..."
          className="w-full pl-10 pr-4 py-3 bg-slate-800/50 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent text-sm sm:text-base"
        />
      </div>
    </div>
  );
}

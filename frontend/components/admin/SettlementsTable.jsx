"use client";

import SettlementStatusBadge from "./SettlementStatusBadge";
import PayButton from "./PayButton";

/**
 * Format a date string to DD.MM.YYYY format.
 * @param {string} dateStr - ISO date string or YYYY-MM-DD
 * @returns {string} Formatted date
 */
function formatDate(dateStr) {
  if (!dateStr) return "—";
  const date = new Date(dateStr);
  const day = String(date.getDate()).padStart(2, "0");
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const year = date.getFullYear();
  return `${day}.${month}.${year}`;
}

/**
 * Format rate type for display.
 * @param {object} settlement - Settlement record
 * @returns {string} Formatted rate type
 */
function formatRateType(settlement) {
  const rateType = settlement.calculation_details?.rate_type || settlement.payout_rate_type || settlement.rate_type;
  switch (rateType) {
    case "hourly":
      return "Почасовая";
    case "per_leaflet":
      return "Поштучно";
    case "fixed_shift":
      return "За смену";
    default:
      return rateType || "—";
  }
}

/**
 * Format quantity based on rate type.
 * For hourly/fixed_shift: "Xч Yмин" (derived from total_minutes)
 * For per_leaflet: "X шт."
 * @param {object} settlement - Settlement record
 * @returns {string} Formatted quantity string
 */
function formatQuantity(settlement) {
  const rateType = settlement.calculation_details?.rate_type || settlement.rate_type;

  if (rateType === "per_leaflet") {
    const count =
      settlement.calculation_details?.leaflet_count ??
      settlement.units ??
      0;
    return `${count} шт.`;
  }

  // hourly or fixed_shift — display time as "Xч Yмін"
  const totalMinutes =
    settlement.calculation_details?.total_minutes ??
    settlement.total_minutes ??
    0;
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  return `${hours}ч ${minutes}мин`;
}

/**
 * Format amount with ₽ currency symbol.
 * @param {number|string} amount
 * @returns {JSX.Element}
 */
function formatAmount(amount) {
  if (amount == null || amount === 0) {
    return <span className="text-slate-500">—</span>;
  }
  const numAmount = Number(amount);
  return (
    <span className="font-semibold text-white">
      {numAmount.toLocaleString("ru-RU", {
        minimumFractionDigits: 0,
        maximumFractionDigits: 2,
      })}{" "}
      ₽
    </span>
  );
}

/**
 * SettlementsTable — displays settlement records in a styled table.
 *
 * @param {Object} props
 * @param {Array} props.settlements - Array of settlement/payout records
 * @param {number} [props.startIndex=0] - Starting index for sequential row numbering (for pagination)
 * @param {Function} [props.onRefresh] - Callback to refresh data after payment action
 * @param {string} [props.userRole] - Current user role for permission checks
 */
export default function SettlementsTable({
  settlements = [],
  startIndex = 0,
  onRefresh,
  userRole,
}) {
  if (!settlements.length) {
    return null;
  }

  return (
    <div className="overflow-hidden">
      <div className="overflow-x-auto custom-scrollbar">
        <table className="w-full text-xs sm:text-sm">
          <thead className="bg-slate-900/50 border-b border-slate-700">
            <tr>
              <th className="px-3 sm:px-6 py-3 sm:py-4 text-left text-xs font-bold uppercase text-slate-400 tracking-wider">
                №
              </th>
              <th className="px-3 sm:px-6 py-3 sm:py-4 text-left text-xs font-bold uppercase text-slate-400 tracking-wider">
                ДАТА
              </th>
              <th className="px-3 sm:px-6 py-3 sm:py-4 text-left text-xs font-bold uppercase text-slate-400 tracking-wider">
                ПРОМОУТЕР
              </th>
              <th className="px-3 sm:px-6 py-3 sm:py-4 text-left text-xs font-bold uppercase text-slate-400 tracking-wider hidden md:table-cell">
                РЕКВИЗИТЫ
              </th>
              <th className="px-3 sm:px-6 py-3 sm:py-4 text-left text-xs font-bold uppercase text-slate-400 tracking-wider hidden sm:table-cell">
                ТИП
              </th>
              <th className="px-3 sm:px-6 py-3 sm:py-4 text-left text-xs font-bold uppercase text-slate-400 tracking-wider hidden sm:table-cell">
                КОЛИЧЕСТВО
              </th>
              <th className="px-3 sm:px-6 py-3 sm:py-4 text-left text-xs font-bold uppercase text-slate-400 tracking-wider hidden sm:table-cell">
                СТАТУС
              </th>
              <th className="px-3 sm:px-6 py-3 sm:py-4 text-left text-xs font-bold uppercase text-slate-400 tracking-wider">
                СУММА К ВЫПЛАТЕ
              </th>
              <th className="px-3 sm:px-6 py-3 sm:py-4 text-left text-xs font-bold uppercase text-slate-400 tracking-wider">
                ДЕЙСТВИЕ
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-700/50">
            {settlements.map((settlement, index) => (
              <tr
                key={settlement.id || settlement.payout_id || index}
                className="hover:bg-slate-800/30 transition-all duration-200 group border-b border-slate-700/30"
              >
                <td className="px-3 sm:px-6 py-3 sm:py-4 text-slate-300 font-medium">
                  {startIndex + index + 1}
                </td>
                <td className="px-3 sm:px-6 py-3 sm:py-4 whitespace-nowrap text-slate-300">
                  {formatDate(settlement.session_date || settlement.calculated_at)}
                </td>
                <td className="px-3 sm:px-6 py-3 sm:py-4 text-white">
                  {settlement.promoter_name || "—"}
                </td>
                <td className="px-3 sm:px-6 py-3 sm:py-4 text-slate-300 hidden md:table-cell">
                  {settlement.promoter_phone ? (
                    <div className="text-xs space-y-0.5">
                      <div className="flex items-center gap-1">
                        <span className="text-slate-500">📱</span>
                        <span>{settlement.promoter_phone}</span>
                      </div>
                      {settlement.promoter_bank && (
                        <div className="flex items-center gap-1">
                          <span className="text-slate-500">🏦</span>
                          <span>{settlement.promoter_bank}</span>
                        </div>
                      )}
                      {settlement.promoter_card_holder && (
                        <div className="flex items-center gap-1">
                          <span className="text-slate-500">👤</span>
                          <span>{settlement.promoter_card_holder}</span>
                        </div>
                      )}
                    </div>
                  ) : (
                    <span className="text-slate-500 text-xs">Не указаны</span>
                  )}
                </td>
                <td className="px-3 sm:px-6 py-3 sm:py-4 whitespace-nowrap text-slate-300 hidden sm:table-cell">
                  {formatRateType(settlement)}
                </td>
                <td className="px-3 sm:px-6 py-3 sm:py-4 whitespace-nowrap text-slate-300 hidden sm:table-cell">
                  {formatQuantity(settlement)}
                </td>
                <td className="px-3 sm:px-6 py-3 sm:py-4 whitespace-nowrap hidden sm:table-cell">
                  <SettlementStatusBadge status={settlement.status} />
                </td>
                <td className="px-3 sm:px-6 py-3 sm:py-4 whitespace-nowrap">
                  {formatAmount(settlement.amount)}
                </td>
                <td className="px-3 sm:px-6 py-3 sm:py-4 whitespace-nowrap">
                  <PayButton
                    settlement={settlement}
                    onSuccess={onRefresh}
                    userRole={userRole}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

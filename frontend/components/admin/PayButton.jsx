"use client";

import { useState } from "react";
import { approveAndPaySettlement, paySettlement } from "@/lib/api/settlements";

/**
 * Format a paid_at timestamp to a readable string (DD.MM.YYYY HH:MM).
 * @param {string} paidAt - ISO timestamp
 * @returns {string}
 */
function formatPaidAt(paidAt) {
  if (!paidAt) return "";
  const date = new Date(paidAt);
  const day = String(date.getDate()).padStart(2, "0");
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const year = date.getFullYear();
  const hours = String(date.getHours()).padStart(2, "0");
  const minutes = String(date.getMinutes()).padStart(2, "0");
  return `${day}.${month}.${year} ${hours}:${minutes}`;
}

/**
 * PayButton — payment action button for settlement rows.
 *
 * Behavior by status:
 * - `calculated`: renders «Подтвердить и выплатить» button (approve + pay in one action)
 * - `approved`: renders «Выплатить» button
 * - `paid`: renders non-interactive «Выплачено» label with paid_at timestamp
 * - `draft`/`cancelled`: renders nothing
 *
 * Role check: button is hidden if userRole is not `owner` or `branch_manager`.
 *
 * Props:
 *   settlement: object — the settlement/payout record (has status, id/payout_id, paid_at)
 *   onSuccess: function — callback after successful payment (refreshes data)
 *   userRole: string — current user role for permission checks
 */
export default function PayButton({ settlement, onSuccess, userRole }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const status = settlement?.status;
  const payoutId = settlement?.payout_id || settlement?.id;
  const paidAt = settlement?.paid_at;

  // For `paid` status, show non-interactive label regardless of role
  if (status === "paid") {
    return (
      <span className="inline-flex items-center gap-1.5 text-xs text-emerald-400 font-medium">
        <svg
          className="w-3.5 h-3.5"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M5 13l4 4L19 7"
          />
        </svg>
        <span>Выплачено</span>
        {paidAt && (
          <span className="text-slate-500 ml-1">{formatPaidAt(paidAt)}</span>
        )}
      </span>
    );
  }

  // For draft/cancelled — render nothing
  if (status === "draft" || status === "cancelled") {
    return null;
  }

  // Role check — hide button if not owner or branch_manager
  const allowedRoles = ["owner", "branch_manager"];
  if (!allowedRoles.includes(userRole)) {
    return null;
  }

  // Only `calculated` and `approved` statuses get action buttons
  if (status !== "calculated" && status !== "approved") {
    return null;
  }

  const handleClick = async () => {
    if (loading) return;

    setLoading(true);
    setError(null);

    try {
      if (status === "calculated") {
        await approveAndPaySettlement(payoutId);
      } else if (status === "approved") {
        await paySettlement(payoutId);
      }
      onSuccess?.();
    } catch (err) {
      setError(err.message || "Ошибка при выплате");
      // Auto-clear error after 5 seconds
      setTimeout(() => {
        setError(null);
      }, 5000);
    } finally {
      setLoading(false);
    }
  };

  const buttonLabel =
    status === "calculated" ? "Подтвердить и выплатить" : "Выплатить";

  return (
    <div className="inline-flex flex-col items-start gap-1">
      <button
        type="button"
        onClick={handleClick}
        disabled={loading}
        className="px-3 py-1.5 text-xs font-medium rounded-lg bg-purple-600 text-white hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 transition-colors whitespace-nowrap"
      >
        {loading && (
          <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
        )}
        {buttonLabel}
      </button>
      {error && (
        <span className="text-xs text-red-400 max-w-[180px] leading-tight">
          {error}
        </span>
      )}
    </div>
  );
}

"use client";

import { useState, useRef } from "react";
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
 * - `paid`: renders non-interactive «Выплачено» label with paid_at timestamp + proof link
 * - `draft`/`cancelled`: renders nothing
 *
 * IMPORTANT: Payment requires uploading a screenshot of the bank transfer.
 * Without the screenshot, payment cannot be completed.
 *
 * Props:
 *   settlement: object — the settlement/payout record
 *   onSuccess: function — callback after successful payment
 *   userRole: string — current user role for permission checks
 */
export default function PayButton({ settlement, onSuccess, userRole }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const fileInputRef = useRef(null);

  const status = settlement?.status;
  const payoutId = settlement?.payout_id || settlement?.id;
  const paidAt = settlement?.paid_at;
  const proofUrl = settlement?.payment_proof_url;

  // For `paid` status, show non-interactive label with proof link
  if (status === "paid") {
    return (
      <div className="inline-flex flex-col items-start gap-1">
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
        {proofUrl && (
          <a
            href={proofUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300 transition-colors"
          >
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
            Скрин перевода
          </a>
        )}
      </div>
    );
  }

  // For draft/cancelled — render nothing
  if (status === "draft" || status === "cancelled") {
    return null;
  }

  // Role check — hide button if not owner, branch_manager, or ad_director
  const allowedRoles = ["owner", "branch_manager", "ad_director"];
  if (!allowedRoles.includes(userRole)) {
    return null;
  }

  // Only `calculated` and `approved` statuses get action buttons
  if (status !== "calculated" && status !== "approved") {
    return null;
  }

  const handleFileSelected = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Validate file type
    const allowedTypes = ["image/jpeg", "image/png", "image/webp", "image/gif"];
    if (!allowedTypes.includes(file.type)) {
      setError("Допустимы только изображения (JPG, PNG, WebP)");
      setTimeout(() => setError(null), 5000);
      return;
    }

    // Validate file size (max 10MB)
    if (file.size > 10 * 1024 * 1024) {
      setError("Максимальный размер файла — 10 МБ");
      setTimeout(() => setError(null), 5000);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      if (status === "calculated") {
        await approveAndPaySettlement(payoutId, file);
      } else if (status === "approved") {
        await paySettlement(payoutId, file);
      }
      onSuccess?.();
    } catch (err) {
      setError(err.message || "Ошибка при выплате");
      setTimeout(() => setError(null), 5000);
    } finally {
      setLoading(false);
      // Reset file input
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  const handleClick = () => {
    if (loading) return;
    // Trigger file picker
    fileInputRef.current?.click();
  };

  const buttonLabel =
    status === "calculated" ? "Оплатить (+ скрин)" : "Оплатить (+ скрин)";

  return (
    <div className="inline-flex flex-col items-start gap-1">
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={handleFileSelected}
      />
      <button
        type="button"
        onClick={handleClick}
        disabled={loading}
        className="px-3 py-1.5 text-xs font-medium rounded-lg bg-purple-600 text-white hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 transition-colors whitespace-nowrap"
        title="Прикрепите скриншот перевода для подтверждения выплаты"
      >
        {loading ? (
          <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
        ) : (
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
          </svg>
        )}
        {buttonLabel}
      </button>
      <span className="text-[10px] text-slate-500 max-w-[160px] leading-tight">
        Скриншот перевода обязателен
      </span>
      {error && (
        <span className="text-xs text-red-400 max-w-[180px] leading-tight">
          {error}
        </span>
      )}
    </div>
  );
}

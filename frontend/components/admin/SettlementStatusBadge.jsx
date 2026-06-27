"use client";

/**
 * SettlementStatusBadge — displays a colored badge for settlement (payout) status.
 *
 * Props:
 *   status: string — one of "calculated", "approved", "paid", "draft", "cancelled"
 */
export default function SettlementStatusBadge({ status }) {
  const statusMap = {
    calculated: {
      text: "Завершён",
      class: "bg-amber-500/20 text-amber-400 border border-amber-500/30",
    },
    approved: {
      text: "Подтверждён",
      class: "bg-blue-500/20 text-blue-400 border border-blue-500/30",
    },
    paid: {
      text: "Выплачено",
      class: "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30",
    },
    draft: {
      text: "Черновик",
      class: "bg-slate-700 text-slate-400 border border-slate-600",
    },
    cancelled: {
      text: "Отменён",
      class: "bg-red-500/20 text-red-400 border border-red-500/30",
    },
  };

  const statusInfo = statusMap[status] || {
    text: status || "—",
    class: "bg-slate-700 text-slate-400 border border-slate-600",
  };

  return (
    <span
      className={`px-3 py-1 text-xs font-medium rounded-full ${statusInfo.class}`}
    >
      {statusInfo.text}
    </span>
  );
}

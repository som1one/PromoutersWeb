"use client";

import { useEffect, useState } from "react";
import { getPaymentLogs } from "@/modules/admin/payments/api";
import { Copy, Check } from "lucide-react";

export default function PaymentLogs({ dealId }) {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [copiedId, setCopiedId] = useState(null);

  useEffect(() => {
    loadLogs();
  }, [dealId]);

  const loadLogs = async () => {
    setLoading(true);
    try {
      const data = await getPaymentLogs(dealId);
      setLogs(data);
    } catch (error) {
      console.error("Error loading payment logs:", error);
    } finally {
      setLoading(false);
    }
  };

  // Очистка комментария от номеров месяцев и сумм (например, "#5:20" или "#5:20 | текст")
  const cleanComment = (comment) => {
    if (!comment) return "—";
    
    // Убираем паттерны типа "#5:20" или "#5:20 |" в начале строки
    let cleaned = comment.replace(/^#\d+:\d+\s*\|\s*/, ""); // Убираем "#5:20 | "
    cleaned = cleaned.replace(/^#\d+:\d+\s*/, ""); // Убираем "#5:20 "
    
    // Если после очистки осталась пустая строка, возвращаем "—"
    return cleaned.trim() || "—";
  };

  // Копирование Payment ID в буфер обмена
  const copyPaymentId = async (paymentId) => {
    try {
      await navigator.clipboard.writeText(paymentId);
      setCopiedId(paymentId);
      setTimeout(() => setCopiedId(null), 2000);
    } catch (error) {
      console.error("Failed to copy:", error);
    }
  };

  if (loading) {
    return <div className="text-slate-400 p-4">Загрузка истории платежей...</div>;
  }

  if (logs.length === 0) {
    return <div className="text-slate-400 p-4">История платежей пуста</div>;
  }

  return (
    <div className="overflow-hidden">
      <div className="overflow-x-auto custom-scrollbar">
        <table className="w-full text-sm">
          <thead className="bg-slate-900/50 border-b border-slate-700">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-bold uppercase text-slate-400 tracking-wider">Дата</th>
              <th className="px-6 py-3 text-left text-xs font-bold uppercase text-slate-400 tracking-wider">Сумма</th>
              <th className="px-6 py-3 text-left text-xs font-bold uppercase text-slate-400 tracking-wider">Статус</th>
              <th className="px-6 py-3 text-left text-xs font-bold uppercase text-slate-400 tracking-wider">Источник</th>
              <th className="px-6 py-3 text-left text-xs font-bold uppercase text-slate-400 tracking-wider">Комментарий</th>
              <th className="px-6 py-3 text-left text-xs font-bold uppercase text-slate-400 tracking-wider">Payment ID</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-700/50">
            {logs.map((log) => (
              <tr key={log.id} className="hover:bg-slate-800/30 transition-colors">
                <td className="px-6 py-4 text-slate-300">
                  {new Date(log.created_at).toLocaleDateString('ru-RU')}
                </td>
                <td className="px-6 py-4 font-semibold text-emerald-400">
                  {log.amount.toLocaleString('ru-RU')} ₽
                </td>
                <td className="px-6 py-4">
                  <span className={`px-3 py-1 text-xs font-medium rounded-full border ${
                    log.status === "paid" 
                      ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/30" 
                      : log.status === "pending"
                      ? "bg-yellow-500/20 text-yellow-400 border-yellow-500/30"
                      : "bg-red-500/20 text-red-400 border-red-500/30"
                  }`}>
                    {log.status === "paid" ? "Оплачено" : log.status === "pending" ? "В обработке" : "Ошибка"}
                  </span>
                </td>
                <td className="px-6 py-4 text-slate-400">
                  {log.source === "admin_cash" ? "наличные" : log.source}
                </td>
                <td className="px-6 py-4 text-slate-400">
                  {cleanComment(log.comment)}
                </td>
                <td className="px-6 py-4">
                  <div className="flex items-center gap-2 max-w-[200px]">
                    <span className="text-xs text-slate-500 font-mono truncate">
                      {log.payment_id.length > 12 ? `${log.payment_id.substring(0, 12)}...` : log.payment_id}
                    </span>
                    <button
                      onClick={() => copyPaymentId(log.payment_id)}
                      className="flex-shrink-0 p-1 hover:bg-slate-700 rounded transition-colors"
                      title="Копировать Payment ID"
                    >
                      {copiedId === log.payment_id ? (
                        <Check className="w-3 h-3 text-emerald-400" />
                      ) : (
                        <Copy className="w-3 h-3 text-slate-400 hover:text-slate-300" />
                      )}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}


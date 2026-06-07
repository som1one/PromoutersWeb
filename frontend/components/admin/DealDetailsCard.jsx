"use client";

import { Calendar, User, Tag, Home, MapPin, Phone, CreditCard } from "lucide-react";

export default function DealDetailsCard({ deal }) {
  if (!deal) return null;

  // Единая точка правды: raw из маппера (dto.deal) или вложенное deal (админка), или сам объект
  const dealInfo = deal.raw || deal.deal || deal;
  // Телефон может быть в project_number или в старых полях для обратной совместимости
  const clientPhone = dealInfo.project_number || deal.client_phone || dealInfo.client_phone || dealInfo.CONTACT_PHONE || dealInfo.contact_phone || "";

  return (
    <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl p-6">
      <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
        <Tag className="w-5 h-5 text-purple-400" />
        Информация о проекте
      </h3>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6 pb-6 border-b border-slate-700">
        <div className="flex items-start gap-3">
          <User className="w-5 h-5 text-purple-400 mt-0.5 flex-shrink-0" />
          <div>
            <p className="text-xs text-slate-400 mb-1">Клиент</p>
            <p className="text-sm font-medium text-white">{deal.client_name || dealInfo.client_name || "—"}</p>
          </div>
        </div>

        <div className="flex items-start gap-3">
          <Phone className="w-5 h-5 text-purple-400 mt-0.5 flex-shrink-0" />
          <div>
            <p className="text-xs text-slate-400 mb-1">Телефон</p>
            <p className="text-sm font-medium text-white">{clientPhone || "—"}</p>
          </div>
        </div>

        <div className="flex items-start gap-3">
          <Home className="w-5 h-5 text-purple-400 mt-0.5 flex-shrink-0" />
          <div>
            <p className="text-xs text-slate-400 mb-1">Тип проекта</p>
            <p className="text-sm font-medium text-white">{dealInfo.project_type || "—"}</p>
          </div>
        </div>

        <div className="flex items-start gap-3">
          <Calendar className="w-5 h-5 text-purple-400 mt-0.5 flex-shrink-0" />
          <div>
            <p className="text-xs text-slate-400 mb-1">Дата начала проекта</p>
            <p className="text-sm font-medium text-white">{dealInfo.project_start_date || "—"}</p>
          </div>
        </div>

        <div className="flex items-start gap-3 md:col-span-2">
          <MapPin className="w-5 h-5 text-purple-400 mt-0.5 flex-shrink-0" />
          <div>
            <p className="text-xs text-slate-400 mb-1">Адрес объекта</p>
            <p className="text-sm font-medium text-white">{dealInfo.object_location || "—"}</p>
          </div>
        </div>
      </div>

      {/* Число оплаты - показываем если есть график платежей */}
      {(dealInfo.term_months > 0 || dealInfo.schedule_day) && (
        <div className="pt-4 border-t border-slate-700">
          <div className="flex items-start gap-3">
            <CreditCard className="w-5 h-5 text-purple-400 mt-0.5 flex-shrink-0" />
            <div>
              <p className="text-xs text-slate-400 mb-1">Число оплаты</p>
              <p className="text-sm font-medium text-white">
                {dealInfo.schedule_day ? (
                  <>
                    {dealInfo.schedule_day} {dealInfo.schedule_day === 1 ? "число" : dealInfo.schedule_day < 5 ? "числа" : "число"} каждого месяца
                  </>
                ) : (
                  <>
                    {new Date().getDate()} {new Date().getDate() === 1 ? "число" : new Date().getDate() < 5 ? "числа" : "число"} каждого месяца <span className="text-slate-500 text-xs">(по умолчанию)</span>
                  </>
                )}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}


"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";

export default function LoginPage() {
  const [phone, setPhone] = useState("");
  const [acceptedOffer, setAcceptedOffer] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [message, setMessage] = useState(null);
  const router = useRouter();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setMessage(null);

    try {
      // Нормализуем телефон (убираем пробелы для отправки)
      const normalizedPhone = phone.replace(/\s/g, "");
      
      // Отправляем телефон
      let response;
      try {
        response = await fetch(`/api/auth/magic-link?phone=${encodeURIComponent(normalizedPhone)}`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
        });
      } catch (e) {
        // Если query параметр не работает, пробуем body
        response = await fetch("/api/auth/magic-link", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ phone: normalizedPhone }),
        });
      }

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || data.message || "Ошибка запроса");
      }

      // Если в development режиме, автоматически переходим по ссылке
      if (data.link) {
        setMessage("Ссылка для входа отправлена. Перенаправление...");
        // Автоматически переходим по ссылке
        setTimeout(() => {
          window.location.href = data.link;
        }, 1500);
      } else {
        setMessage("Ссылка для входа отправлена");
      }
    } catch (err) {
      setError(err.message || "Ошибка при запросе ссылки для входа");
    } finally {
      setLoading(false);
    }
  };

  // Форматирование телефона при вводе
  const handlePhoneChange = (e) => {
    const input = e.target.value;
    const cursorPosition = e.target.selectionStart;
    
    // Извлекаем только цифры из ввода
    let digits = input.replace(/\D/g, '');
    
    // Если пользователь стирает (backspace)
    if (input.length < phone.length) {
      // Если курсор на символе форматирования, удаляем предыдущую цифру
      const beforeCursor = input.slice(0, cursorPosition);
      const digitsBefore = beforeCursor.replace(/\D/g, '');
      
      // Если удалили форматирующий символ, удаляем последнюю цифру перед ним
      if (digitsBefore.length < phone.replace(/\D/g, '').length) {
        digits = digitsBefore;
      } else {
        digits = input.replace(/\D/g, '');
      }
    }
    
    // Если начинается с 8, заменяем на 7 (без добавления 8)
    if (digits.startsWith("8")) {
      digits = "7" + digits.slice(1);
    }
    
    // Если пусто или не начинается с 7, начинаем с 7
    if (digits.length === 0) {
      setPhone("");
      return;
    }
    
    if (!digits.startsWith("7")) {
      digits = "7" + digits;
    }
    
    // Ограничиваем длину до 11 цифр (7 + 10)
    if (digits.length > 11) {
      digits = digits.slice(0, 11);
    }
    
    // Форматируем: +7 (XXX) XXX-XX-XX
    let formatted = "+7";
    if (digits.length > 1) {
      const rest = digits.slice(1);
      formatted += " (" + rest.slice(0, 3);
      if (rest.length > 3) {
        formatted += ") " + rest.slice(3, 6);
        if (rest.length > 6) {
          formatted += "-" + rest.slice(6, 8);
          if (rest.length > 8) {
            formatted += "-" + rest.slice(8, 10);
          }
        }
      } else if (rest.length > 0) {
        formatted += ")";
      }
    }
    
    setPhone(formatted);
    
    // Восстанавливаем позицию курсора
    setTimeout(() => {
      const digitCount = digits.length;
      let newPos = formatted.length;
      
      if (digitCount <= 1) {
        newPos = formatted.length;
      } else if (digitCount <= 4) {
        newPos = formatted.indexOf('(') + digitCount;
      } else if (digitCount <= 7) {
        newPos = formatted.indexOf(')') + 1 + (digitCount - 3);
      } else if (digitCount <= 9) {
        const firstDash = formatted.indexOf('-');
        newPos = firstDash + 1 + (digitCount - 7);
      }
      
      e.target.setSelectionRange(newPos, newPos);
    }, 0);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="bg-dashboard-card rounded-2xl border border-slate-700/50 p-8 backdrop-blur-sm shadow-2xl">
          <div className="text-center mb-8">
            <div className="w-16 h-16 bg-slate-900/40 border border-slate-700/60 rounded-full flex items-center justify-center mx-auto mb-4 overflow-hidden">
              <Image
                src="/logo.png"
                alt="Логотип"
                width={40}
                height={40}
                priority
              />
            </div>
            <h1 className="text-3xl font-bold text-white mb-2">Вход в систему</h1>
            <p className="text-dashboard-text-muted">
              Введите ваш номер телефона для получения ссылки для входа
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label htmlFor="phone" className="block text-sm font-medium text-white mb-2">
                Номер телефона
              </label>
              <input
                id="phone"
                type="tel"
                value={phone}
                onChange={handlePhoneChange}
                required
                className="w-full px-4 py-3 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                placeholder="+7 (XXX) XXX-XX-XX"
                disabled={loading}
                maxLength={18}
              />
            </div>

            <div className="flex items-start gap-3">
              <input
                id="accept-offer"
                type="checkbox"
                checked={acceptedOffer}
                onChange={(e) => setAcceptedOffer(e.target.checked)}
                className="mt-1 h-4 w-4 rounded border-slate-600 bg-slate-800 text-purple-600 focus:ring-purple-500"
              />
              <label htmlFor="accept-offer" className="text-sm text-slate-300">
                Я принимаю условия{" "}
                <a
                  href="/offer"
                  target="_blank"
                  rel="noreferrer"
                  className="text-purple-400 hover:text-purple-300 underline"
                >
                  оферты
                </a>
              </label>
            </div>

            {error && (
              <div className="bg-red-500/10 border border-red-500/50 rounded-lg p-4">
                <p className="text-red-400 text-sm">{error}</p>
              </div>
            )}

            {message && (
              <div className="bg-green-500/10 border border-green-500/50 rounded-lg p-4">
                <p className="text-green-400 text-sm">{message}</p>
              </div>
            )}

            <button
              type="submit"
              disabled={loading || !phone || phone.length < 10 || !acceptedOffer}
              className="w-full bg-purple-600 hover:bg-purple-700 disabled:bg-slate-700 disabled:cursor-not-allowed text-white font-semibold py-3 px-4 rounded-lg transition-colors"
            >
              {loading ? "Отправка..." : "Получить ссылку для входа"}
            </button>
          </form>

          <div className="mt-6 text-center text-sm text-dashboard-text-muted">
            <p>
              Если у вас нет рассрочки или возникли проблемы,{" "}
              <span className="text-purple-400">обратитесь к администратору</span>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}


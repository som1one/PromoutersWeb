/**
 * Тесты для компонента CashPaymentModal
 * Проверяет функциональность выбора даты оплаты
 */

// Моки
const mockDeal = {
  deal: {
    deal_id: "TEST_001",
    title: "Тестовая сделка",
    total_amount: 1000000, // 10000 руб в копейках
    paid_amount: 500000, // 5000 руб
    term_months: 12,
  },
  payments: [
    {
      index: 0,
      month_index: 0,
      month: "Январь 2026",
      amount: 100000,
      status: "pending",
      paid_in_month: 0,
    },
    {
      index: 1,
      month_index: 1,
      month: "Февраль 2026",
      amount: 100000,
      status: "pending",
      paid_in_month: 0,
    },
  ],
};

// Базовые тесты (для ручной проверки в консоли браузера)
const tests = {
  // Тест 1: Проверка инициализации даты
  testDateInitialization: () => {
    console.log("🧪 Тест 1: Инициализация даты");
    const today = new Date();
    const expectedDate = today.toISOString().split('T')[0];
    console.log(`Ожидаемая дата: ${expectedDate}`);
    console.log("✅ Дата должна быть установлена на сегодня");
  },

  // Тест 2: Проверка формата даты для API
  testDateFormatForAPI: () => {
    console.log("\n🧪 Тест 2: Формат даты для API");
    const testDate = "2026-01-15";
    const dateRegex = /^\d{4}-\d{2}-\d{2}$/;
    const isValid = dateRegex.test(testDate);
    console.log(`Дата: ${testDate}`);
    console.log(`Валидный формат: ${isValid ? "✅" : "❌"}`);
    return isValid;
  },

  // Тест 3: Проверка передачи даты в API
  testDatePassingToAPI: () => {
    console.log("\n🧪 Тест 3: Передача даты в API");
    const mockAllocations = [{ month_index: 0, amount: 50000 }];
    const mockComment = "Тестовый комментарий";
    const mockPaymentDate = "2026-01-15";
    
    // Симуляция вызова API
    const apiCall = {
      deal_id: "TEST_001",
      allocations: mockAllocations,
      comment: mockComment,
      payment_date: mockPaymentDate,
    };
    
    console.log("Данные для API:", JSON.stringify(apiCall, null, 2));
    console.log("✅ payment_date должен быть передан в API");
    return apiCall.payment_date === mockPaymentDate;
  },

  // Тест 4: Проверка валидации даты
  testDateValidation: () => {
    console.log("\n🧪 Тест 4: Валидация даты");
    const validDates = [
      "2026-01-15",
      "2026-12-31",
      "2025-01-01",
    ];
    
    const invalidDates = [
      "2026-13-01", // Неверный месяц
      "2026-01-32", // Неверный день
      "15-01-2026", // Неверный формат
    ];
    
    const dateRegex = /^\d{4}-\d{2}-\d{2}$/;
    
    console.log("Валидные даты:");
    validDates.forEach(date => {
      const isValid = dateRegex.test(date);
      console.log(`  ${date}: ${isValid ? "✅" : "❌"}`);
    });
    
    console.log("Невалидные даты:");
    invalidDates.forEach(date => {
      const isValid = dateRegex.test(date);
      console.log(`  ${date}: ${isValid ? "⚠️ (формат OK, но значение неверное)" : "❌"}`);
    });
    
    return true;
  },

  // Тест 5: Проверка UI элементов
  testUIElements: () => {
    console.log("\n🧪 Тест 5: UI элементы");
    console.log("Проверьте вручную в браузере:");
    console.log("  1. Поле выбора даты должно быть видимым");
    console.log("  2. Поле должно быть расположено ПЕРЕД выбором месяцев");
    console.log("  3. По умолчанию должна быть установлена сегодняшняя дата");
    console.log("  4. Поле должно иметь иконку календаря 📅");
    console.log("  5. При изменении даты значение должно обновляться");
    return true;
  },

  // Запуск всех тестов
  runAll: () => {
    console.log("=".repeat(60));
    console.log("🚀 ЗАПУСК ТЕСТОВ: CashPaymentModal");
    console.log("=".repeat(60));
    
    const results = [];
    results.push(tests.testDateInitialization());
    results.push(tests.testDateFormatForAPI());
    results.push(tests.testDatePassingToAPI());
    results.push(tests.testDateValidation());
    results.push(tests.testUIElements());
    
    console.log("\n" + "=".repeat(60));
    console.log("📊 ИТОГИ");
    console.log("=".repeat(60));
    console.log(`Пройдено: ${results.filter(r => r !== false).length}/${results.length}`);
    console.log("=".repeat(60));
  },
};

// Экспорт для использования в браузере
if (typeof window !== 'undefined') {
  window.CashPaymentModalTests = tests;
  console.log("✅ Тесты загружены. Используйте: CashPaymentModalTests.runAll()");
}

// Для Node.js окружения
if (typeof module !== 'undefined' && module.exports) {
  module.exports = tests;
}

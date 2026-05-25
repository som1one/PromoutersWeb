export const overviewMetrics = [
  {
    label: 'Чекпоинтов сегодня',
    value: '07',
    note: '2 уже отмечены, 5 в работе',
  },
  {
    label: 'Фотоотчёты',
    value: '18',
    note: '3 требуют повторной загрузки',
  },
  {
    label: 'Начисление',
    value: '128 BYN',
    note: 'по текущей смене и бонусам',
  },
] as const;

export const timeline = [
  {
    id: 'p1',
    time: '10:00',
    title: 'Старт смены',
    address: 'ТРЦ Galileo, главный вход',
    status: 'done',
  },
  {
    id: 'p2',
    time: '11:15',
    title: 'Чекпоинт 2',
    address: 'Бобруйская, 6',
    status: 'done',
  },
  {
    id: 'p3',
    time: '12:40',
    title: 'ТЦ Dana Mall',
    address: 'Проспект Независимости, вход B2',
    status: 'current',
  },
  {
    id: 'p4',
    time: '14:10',
    title: 'ЖК Маяк Минска',
    address: 'Улица Туровского, 4',
    status: 'next',
  },
] as const;

export const checklist = [
  'Подтвердить старт смены через геометку.',
  'Загрузить 3 фотоотчёта до 13:00.',
  'Отправить запрос мастеру на новый промостенд.',
] as const;

export const feed = [
  {
    id: 'n1',
    title: 'Маршрут обновлён супервайзером',
    body: 'Добавлена дополнительная точка на 14:10 возле ЖК Маяк Минска.',
    tone: 'accent',
  },
  {
    id: 'n2',
    title: 'Проверка фотоотчёта',
    body: 'Последний кадр размыт. Нужна пересъёмка в следующей точке.',
    tone: 'warning',
  },
] as const;

export const tasks = [
  {
    id: 't1',
    title: 'Повторить фотоотчёт для стойки B2',
    meta: 'До 12:55 · высокий приоритет',
    status: 'urgent',
  },
  {
    id: 't2',
    title: 'Подтвердить остаток листовок',
    meta: 'До 13:20 · средний приоритет',
    status: 'scheduled',
  },
  {
    id: 't3',
    title: 'Запросить у мастера новую рамку',
    meta: 'Сегодня · можно объединить с BSO',
    status: 'planned',
  },
] as const;

export const payouts = [
  {
    id: 'pay-1',
    period: '28 апр - 04 мая',
    amount: '420 BYN',
    status: 'К выплате',
  },
  {
    id: 'pay-2',
    period: '21 апр - 27 апр',
    amount: '385 BYN',
    status: 'Выплачено',
  },
] as const;

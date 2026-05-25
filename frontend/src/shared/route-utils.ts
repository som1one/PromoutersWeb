import type { ExpensePlanRecord } from './api/expense-plans';
import type { PayoutRecord } from './api/finance';
import type { MasterRequestStatus } from './api/master-requests';
import type { GeoPingRecord } from './api/sessions';
import type { PhotoStatus, RoutePoint, RouteStatus, SessionStatus } from './api/routes';

export function isManagerRole(roleCode: string) {
  return ['owner', 'branch_manager', 'ad_director', 'dispatcher'].includes(roleCode);
}

export function roleCodeLabel(roleCode: string) {
  switch (roleCode) {
    case 'owner':
      return 'Собственник';
    case 'branch_manager':
      return 'Руководитель филиала';
    case 'ad_director':
      return 'Директор по рекламе';
    case 'dispatcher':
      return 'Диспетчер';
    case 'director':
      return 'Директор';
    case 'master':
      return 'Мастер';
    case 'promoter':
      return 'Промоутер';
    default:
      return roleCode;
  }
}

export function routeStatusLabel(status: RouteStatus) {
  switch (status) {
    case 'draft':
      return 'Черновик';
    case 'assigned':
      return 'Назначен';
    case 'in_progress':
      return 'В работе';
    case 'completed':
      return 'Завершен';
    case 'cancelled':
      return 'Отменен';
    default:
      return status;
  }
}

export function routeStatusTone(status: RouteStatus): 'neutral' | 'positive' | 'warning' | 'accent' {
  switch (status) {
    case 'completed':
      return 'positive';
    case 'in_progress':
      return 'accent';
    case 'cancelled':
      return 'warning';
    default:
      return 'neutral';
  }
}

export function sessionStatusLabel(status: SessionStatus) {
  switch (status) {
    case 'planned':
      return 'Ожидает старта';
    case 'active':
      return 'Активна';
    case 'completed':
      return 'Завершена';
    case 'cancelled':
      return 'Отменена';
    case 'paused':
      return 'На паузе';
    default:
      return status;
  }
}

export function photoStatusLabel(status: PhotoStatus) {
  switch (status) {
    case 'accepted':
      return 'Принято';
    case 'rejected':
      return 'Отклонено';
    case 'pending':
      return 'На проверке';
    default:
      return status;
  }
}

export function photoStatusTone(status: PhotoStatus): 'neutral' | 'positive' | 'warning' | 'accent' {
  switch (status) {
    case 'accepted':
      return 'positive';
    case 'rejected':
      return 'warning';
    case 'pending':
      return 'accent';
    default:
      return 'neutral';
  }
}

export function pointTypeLabel(pointType: RoutePoint['point_type']) {
  switch (pointType) {
    case 'start':
      return 'Старт';
    case 'finish':
      return 'Финиш';
    case 'stop':
      return 'Остановка';
    case 'checkpoint':
      return 'Точка';
    default:
      return pointType;
  }
}

export function formatDateTime(value: string | null) {
  if (!value) {
    return '—';
  }

  return new Intl.DateTimeFormat('ru-RU', {
    dateStyle: 'short',
    timeStyle: 'short',
  }).format(new Date(value));
}

export function formatDate(value: string | null) {
  if (!value) {
    return '—';
  }

  return new Intl.DateTimeFormat('ru-RU', {
    dateStyle: 'medium',
  }).format(new Date(value));
}

export function formatTime(value: string | null) {
  if (!value) {
    return '—';
  }

  return new Intl.DateTimeFormat('ru-RU', {
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value));
}

export function formatCurrencyAmount(value: string | number, currency = 'RUB') {
  const amount = typeof value === 'number' ? value : Number.parseFloat(value);
  const safeAmount = Number.isFinite(amount) ? amount : 0;

  return new Intl.NumberFormat('ru-RU', {
    style: 'currency',
    currency,
    maximumFractionDigits: 2,
  }).format(safeAmount);
}

export function getLastGeoPing(geoPings: GeoPingRecord[]) {
  return geoPings.length ? geoPings[geoPings.length - 1] : null;
}

export function payoutStatusTone(status: PayoutRecord['status']): 'neutral' | 'positive' | 'warning' | 'accent' {
  switch (status) {
    case 'paid':
      return 'positive';
    case 'cancelled':
      return 'warning';
    case 'approved':
    case 'calculated':
      return 'accent';
    default:
      return 'neutral';
  }
}

export function payoutStatusLabel(status: PayoutRecord['status']) {
  switch (status) {
    case 'draft':
      return 'Черновик';
    case 'calculated':
      return 'Рассчитано';
    case 'approved':
      return 'Подтверждено';
    case 'paid':
      return 'Выплачено';
    case 'cancelled':
      return 'Отменено';
    default:
      return status;
  }
}

export function formatPersonName(firstName: string, lastName: string) {
  return `${firstName} ${lastName}`.trim();
}

export function sumMoney(values: Array<string | number>) {
  return values.reduce<number>((total, value) => {
    const nextValue = typeof value === 'number' ? value : Number.parseFloat(value);
    return total + (Number.isFinite(nextValue) ? nextValue : 0);
  }, 0);
}

export function masterRequestStatusLabel(status: MasterRequestStatus) {
  switch (status) {
    case 'new':
      return 'Новая';
    case 'accepted':
      return 'Принял';
    case 'on_the_way':
      return 'В пути';
    case 'in_progress':
      return 'В работе';
    case 'completed':
      return 'Готово';
    case 'handed_over':
      return 'Забрал на СД';
    case 'cancelled':
      return 'Отменена';
    default:
      return status;
  }
}

export function masterRequestStatusTone(
  status: MasterRequestStatus,
): 'neutral' | 'positive' | 'warning' | 'accent' {
  switch (status) {
    case 'completed':
    case 'handed_over':
      return 'positive';
    case 'on_the_way':
    case 'in_progress':
      return 'accent';
    case 'cancelled':
      return 'warning';
    default:
      return 'neutral';
  }
}

export function expensePlanStatusLabel(status: ExpensePlanRecord['status']) {
  switch (status) {
    case 'draft':
      return 'Черновик';
    case 'submitted':
      return 'На согласовании';
    case 'approved':
      return 'Согласован';
    case 'rejected':
      return 'Отклонён';
    case 'cancelled':
      return 'Отменён';
    default:
      return status;
  }
}

export function expensePlanStatusTone(
  status: ExpensePlanRecord['status'],
): 'neutral' | 'positive' | 'warning' | 'accent' {
  switch (status) {
    case 'approved':
      return 'positive';
    case 'submitted':
      return 'accent';
    case 'rejected':
    case 'cancelled':
      return 'warning';
    default:
      return 'neutral';
  }
}

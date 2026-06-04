import { Link, Outlet, useLocation } from 'react-router-dom';

import { useAuth } from '../../app/auth/useAuth';
import { isManagerRole, roleCodeLabel } from '../route-utils';
import { BottomNav, StatusPill } from '../ui/AppUI';

type NavItem = {
  to: string;
  label: string;
  icon: string;
};

const promoterItems: NavItem[] = [
  { to: '/app', label: 'Главная', icon: 'home' },
  { to: '/app/routes', label: 'Маршруты', icon: 'routes' },
  { to: '/app/notifications', label: 'Сигналы', icon: 'signals' },
  { to: '/app/profile', label: 'Профиль', icon: 'profile' },
];

const masterItems: NavItem[] = [
  { to: '/app', label: 'Главная', icon: 'home' },
  { to: '/app/master-requests', label: 'Заявки', icon: 'tasks' },
  { to: '/app/notifications', label: 'Сигналы', icon: 'signals' },
  { to: '/app/profile', label: 'Профиль', icon: 'profile' },
];

const branchManagerItems: NavItem[] = [
  { to: '/app', label: 'Обзор', icon: 'home' },
  { to: '/app/admin/routes', label: 'Маршруты', icon: 'routes' },
  { to: '/app/master-requests', label: 'Заявки', icon: 'tasks' },
  { to: '/app/profile', label: 'Профиль', icon: 'profile' },
];

// Диспетчер видит ту же навигацию, что руководитель филиала.
const dispatcherItems: NavItem[] = branchManagerItems;

const adDirectorItems: NavItem[] = [
  { to: '/app', label: 'Обзор', icon: 'home' },
  { to: '/app/admin/routes', label: 'Маршруты', icon: 'routes' },
  { to: '/app/master-requests', label: 'Заявки', icon: 'tasks' },
  { to: '/app/reports', label: 'Отчеты', icon: 'reports' },
  { to: '/app/profile', label: 'Профиль', icon: 'profile' },
];

const ownerItems: NavItem[] = [
  { to: '/app', label: 'Обзор', icon: 'home' },
  { to: '/app/admin/routes', label: 'Маршруты', icon: 'routes' },
  { to: '/app/audit-logs', label: 'Аудит', icon: 'audit' },
  { to: '/app/profile', label: 'Профиль', icon: 'profile' },
];

function getNavItems(roleCode: string): NavItem[] {
  switch (roleCode) {
    case 'owner':
      return ownerItems;
    case 'branch_manager':
      return branchManagerItems;
    case 'ad_director':
      return adDirectorItems;
    case 'dispatcher':
      return dispatcherItems;
    case 'master':
      return masterItems;
    default:
      return promoterItems;
  }
}

function getSectionTitle(pathname: string, managerView: boolean) {
  if (pathname.includes('/admin/routes/')) {
    return 'Карточка маршрута';
  }
  if (pathname.includes('/admin/routes')) {
    return 'Контроль маршрутов';
  }
  if (pathname.includes('/master-requests')) {
    return 'Заявки мастера';
  }
  if (pathname.includes('/expense-plans')) {
    return 'План расходов';
  }
  if (pathname.includes('/income-expense')) {
    return 'Доход и расход';
  }
  if (pathname.includes('/routes/') && pathname.includes('/execute')) {
    return 'Выполнение маршрута';
  }
  if (pathname.includes('/routes/') && pathname.includes('/finish')) {
    return 'Завершение смены';
  }
  if (pathname.includes('/routes/')) {
    return 'Маршрут';
  }
  if (pathname.includes('/routes')) {
    return managerView ? 'Все маршруты' : 'Мои маршруты';
  }
  if (pathname.includes('/notifications')) {
    return 'Уведомления';
  }
  if (pathname.includes('/reports')) {
    return 'Отчеты';
  }
  if (pathname.includes('/audit-logs')) {
    return 'Журнал действий';
  }
  if (pathname.includes('/profile')) {
    return 'Профиль';
  }
  return managerView ? 'Операционный обзор' : 'Рабочая смена';
}

function getInitials(firstName: string, lastName: string, username: string) {
  const f = firstName?.trim()?.[0] ?? '';
  const l = lastName?.trim()?.[0] ?? '';
  const initials = `${f}${l}`.toUpperCase();
  if (initials) return initials;
  return (username || '?').slice(0, 2).toUpperCase();
}

export function PromoterLayout() {
  const { user } = useAuth();
  const location = useLocation();

  if (!user) {
    return null;
  }

  const managerView = isManagerRole(user.roleCode);
  const navItems = getNavItems(user.roleCode);
  const sectionTitle = getSectionTitle(location.pathname, managerView);
  const initials = getInitials(user.firstName, user.lastName, user.username);
  const fullName = [user.lastName, user.firstName].filter(Boolean).join(' ').trim() || user.username;

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar-row">
          <div className="brand-block">
            <div className="brand-mark">СУ</div>
            <div>
              <span className="eyebrow">СУУПР</span>
              <h1 className="shell-title">{sectionTitle}</h1>
            </div>
          </div>
          <Link to="/app/profile" className="user-chip" aria-label="Открыть профиль">
            <span className="user-chip-avatar" aria-hidden="true">
              {initials}
            </span>
          </Link>
        </div>

        <div className="topbar-row topbar-row-compact">
          <div className="shell-meta">
            <strong>{fullName}</strong>
            <span>
              {user.branch}
              {user.city ? ` · ${user.city}` : ''}
            </span>
          </div>
          <StatusPill tone={managerView ? 'accent' : 'positive'}>
            {roleCodeLabel(user.roleCode)}
          </StatusPill>
        </div>
      </header>

      <main className="layout-main">
        <Outlet />
      </main>

      <BottomNav items={navItems} />
    </div>
  );
}

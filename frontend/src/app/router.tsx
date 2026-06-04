import { createBrowserRouter, Navigate } from 'react-router-dom';

import { AdminRouteDetailsPage } from '../pages/admin-routes/AdminRouteDetailsPage';
import { AdminRoutesPage } from '../pages/admin-routes/AdminRoutesPage';
import { AuditLogPage } from '../pages/audit/AuditLogPage';
import { ExpensePlansPage } from '../pages/expense-plans/ExpensePlansPage';
import { LoginPage } from '../pages/login/LoginPage';
import { MasterRequestsPage } from '../pages/master-requests/MasterRequestsPage';
import { NotificationsPage } from '../pages/notifications/NotificationsPage';
import { HomePage } from '../pages/owner-dashboard/HomePage';
import { FinanceRoutePage } from '../pages/owner-finance/FinanceRoutePage';
import { ProfilePage } from '../pages/profile/ProfilePage';
import { ReportsPage } from '../pages/reports/ReportsPage';
import { RouteDetailsPage } from '../pages/routes/RouteDetailsPage';
import { RouteExecutePage } from '../pages/routes/RouteExecutePage';
import { RouteFinishPage } from '../pages/routes/RouteFinishPage';
import { RoutesPage } from '../pages/routes/RoutesPage';
import { AuthGuard } from '../shared/guards/AuthGuard';
import { GuestGuard } from '../shared/guards/GuestGuard';
import { RoleGuard } from '../shared/guards/RoleGuard';
import { PromoterLayout } from '../shared/layouts/PromoterLayout';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <Navigate to="/app" replace />,
  },
  {
    path: '/auth/login',
    element: (
      <GuestGuard>
        <LoginPage />
      </GuestGuard>
    ),
  },
  {
    path: '/app',
    element: (
      <AuthGuard>
        <PromoterLayout />
      </AuthGuard>
    ),
    children: [
      {
        index: true,
        element: <HomePage />,
      },
      {
        path: 'routes',
        element: <RoutesPage />,
      },
      {
        path: 'routes/:routeId',
        element: <RouteDetailsPage />,
      },
      {
        path: 'routes/:routeId/execute',
        element: <RouteExecutePage />,
      },
      {
        path: 'routes/:routeId/finish',
        element: <RouteFinishPage />,
      },
      {
        path: 'admin/routes',
        element: (
          <RoleGuard allowedRoleCodes={['owner', 'branch_manager', 'ad_director']}>
            <AdminRoutesPage />
          </RoleGuard>
        ),
      },
      {
        path: 'admin/routes/:routeId',
        element: (
          <RoleGuard allowedRoleCodes={['owner', 'branch_manager', 'ad_director']}>
            <AdminRouteDetailsPage />
          </RoleGuard>
        ),
      },
      {
        path: 'master-requests',
        element: (
          <RoleGuard
            allowedRoleCodes={['owner', 'branch_manager', 'ad_director', 'master']}
          >
            <MasterRequestsPage />
          </RoleGuard>
        ),
      },
      {
        path: 'expense-plans',
        element: (
          <RoleGuard allowedRoleCodes={['owner', 'branch_manager']}>
            <ExpensePlansPage />
          </RoleGuard>
        ),
      },
      {
        path: 'income-expense',
        element: (
          <RoleGuard allowedRoleCodes={['owner', 'branch_manager']}>
            <FinanceRoutePage />
          </RoleGuard>
        ),
      },
      {
        path: 'reports',
        element: <ReportsPage />,
      },
      {
        path: 'payouts',
        element: <Navigate to="/app/routes" replace />,
      },
      {
        path: 'notifications',
        element: <NotificationsPage />,
      },
      {
        path: 'audit-logs',
        element: (
          <RoleGuard allowedRoleCodes={['owner', 'branch_manager', 'ad_director']}>
            <AuditLogPage />
          </RoleGuard>
        ),
      },
      {
        path: 'profile',
        element: <ProfilePage />,
      },
      {
        path: 'shifts',
        element: <Navigate to="/app/routes" replace />,
      },
      {
        path: 'tasks',
        element: <Navigate to="/app/routes" replace />,
      },
    ],
  },
  {
    path: '*',
    element: <Navigate to="/app" replace />,
  },
]);

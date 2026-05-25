import type { PropsWithChildren } from 'react';
import { Navigate } from 'react-router-dom';

import { useAuth } from '../../app/auth/useAuth';

type RoleGuardProps = PropsWithChildren<{
  allowedRoleCodes: string[];
  fallbackPath?: string;
}>;

export function RoleGuard({
  children,
  allowedRoleCodes,
  fallbackPath = '/app/routes',
}: RoleGuardProps) {
  const { isReady, isAuthenticated, user } = useAuth();

  if (!isReady) {
    return null;
  }

  if (!isAuthenticated || !user) {
    return <Navigate to="/auth/login" replace />;
  }

  if (!allowedRoleCodes.includes(user.roleCode)) {
    return <Navigate to={fallbackPath} replace />;
  }

  return children;
}

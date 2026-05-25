import type { PropsWithChildren } from 'react';
import { Navigate } from 'react-router-dom';

import { useAuth } from '../../app/auth/useAuth';

export function GuestGuard({ children }: PropsWithChildren) {
  const { isAuthenticated, isReady } = useAuth();

  if (!isReady) {
    return <div className="app-loader">Проверяем доступ...</div>;
  }

  if (isAuthenticated) {
    return <Navigate to="/app" replace />;
  }

  return <>{children}</>;
}

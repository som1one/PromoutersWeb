import type { PropsWithChildren } from 'react';
import { Navigate } from 'react-router-dom';

import { useAuth } from '../../app/auth/useAuth';

export function AuthGuard({ children }: PropsWithChildren) {
  const { isAuthenticated, isReady } = useAuth();

  if (!isReady) {
    return <div className="app-loader">Готовим кабинет...</div>;
  }

  if (!isAuthenticated) {
    return <Navigate to="/auth/login" replace />;
  }

  return <>{children}</>;
}

import type { PropsWithChildren } from 'react';

import { ToastProvider } from '../shared/toast/ToastProvider';
import { AuthProvider } from './auth/AuthContext';

export function AppProviders({ children }: PropsWithChildren) {
  return (
    <ToastProvider>
      <AuthProvider>{children}</AuthProvider>
    </ToastProvider>
  );
}

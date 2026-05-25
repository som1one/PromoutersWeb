import { createContext } from 'react';

export type ToastTone = 'success' | 'error' | 'info';

export type ToastInput = {
  title: string;
  description?: string;
  tone?: ToastTone;
};

export type ToastRecord = ToastInput & {
  id: string;
};

export type ToastContextValue = {
  toasts: ToastRecord[];
  showToast: (toast: ToastInput) => void;
  dismissToast: (id: string) => void;
};

export const ToastContext = createContext<ToastContextValue | null>(null);

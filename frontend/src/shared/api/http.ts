import { dispatchUnauthorized, tryRefreshAccessToken } from './session';

const rawApiUrl = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000/api/v1';

export const apiUrl = rawApiUrl.replace(/\/$/, '');

type ApiRequestOptions = RequestInit & {
  accessToken?: string;
  /** Internal flag to prevent infinite refresh loops. */
  _retried?: boolean;
};

type ApiErrorPayload = {
  detail?: string;
};

const errorTranslations: Record<string, string> = {
  'Invalid phone or password': 'Неверный номер телефона или пароль.',
  'User is not active': 'Пользователь деактивирован.',
  'User not found': 'Пользователь не найден.',
  'Challenge not found': 'Код подтверждения не найден.',
  'Challenge is no longer active': 'Код подтверждения больше не активен.',
  'Challenge has expired': 'Срок действия кода истёк.',
  'Too many invalid attempts': 'Превышено число попыток ввода кода.',
  'Invalid verification code': 'Неверный код подтверждения.',
  'Authentication credentials were not provided': 'Требуется авторизация.',
  'Token has expired': 'Сессия истекла. Войдите снова.',
  'Invalid token': 'Сессия недействительна. Войдите снова.',
  'Refresh token has expired': 'Сессия истекла. Войдите снова.',
  'Invalid refresh token': 'Сессия недействительна. Войдите снова.',
};

function normalizeErrorMessage(message: string) {
  return errorTranslations[message] ?? message;
}

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

const REFRESHABLE_PATHS_DENYLIST = ['/auth/login', '/auth/refresh', '/auth/verify-sms'];

function isRefreshable(path: string, options: ApiRequestOptions) {
  if (options._retried) return false;
  if (!options.accessToken) return false;
  return !REFRESHABLE_PATHS_DENYLIST.some((deny) => path.startsWith(deny));
}

export async function apiRequest<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
  const { accessToken, headers, body, _retried, ...restOptions } = options;
  const isFormData = typeof FormData !== 'undefined' && body instanceof FormData;

  const response = await fetch(`${apiUrl}${path}`, {
    ...restOptions,
    body,
    headers: {
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
      ...headers,
    },
  });

  const isJsonResponse = response.headers.get('content-type')?.includes('application/json');
  const payload = isJsonResponse ? ((await response.json()) as ApiErrorPayload | T) : null;

  if (!response.ok) {
    const detail =
      payload && typeof payload === 'object' && 'detail' in payload ? payload.detail : null;

    if (response.status === 401 && isRefreshable(path, options)) {
      const newToken = await tryRefreshAccessToken();
      if (newToken) {
        return apiRequest<T>(path, { ...options, accessToken: newToken, _retried: true });
      }
      dispatchUnauthorized();
    }

    throw new ApiError(normalizeErrorMessage(detail ?? 'Не удалось выполнить запрос.'), response.status);
  }

  return payload as T;
}

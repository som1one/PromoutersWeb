import { useEffect, useRef, useState, type PropsWithChildren } from 'react';

import {
  getCurrentUser,
  loginRequest,
  refreshSession,
  updateMe,
  verifySmsCode,
  type AuthSession,
} from '../../shared/api/auth';
import {
  clearSessionHandlers,
  registerSessionHandlers,
} from '../../shared/api/session';
import {
  AuthContext,
  type LoginChallenge,
  type LoginPayload,
  type UpdateProfilePayload,
  type VerifyCodePayload,
} from './auth-context';

const SESSION_STORAGE_KEY = 'promouters.auth-session';
const CHALLENGE_STORAGE_KEY = 'promouters.auth-challenge';

function readSessionFromStorage() {
  if (typeof window === 'undefined') {
    return null;
  }

  const rawSession = window.localStorage.getItem(SESSION_STORAGE_KEY);
  return rawSession ? (JSON.parse(rawSession) as AuthSession) : null;
}

function readChallengeFromStorage() {
  if (typeof window === 'undefined') {
    return null;
  }

  const rawChallenge = window.localStorage.getItem(CHALLENGE_STORAGE_KEY);
  return rawChallenge ? (JSON.parse(rawChallenge) as LoginChallenge) : null;
}

export function AuthProvider({ children }: PropsWithChildren) {
  const [session, setSession] = useState<AuthSession | null>(() => readSessionFromStorage());
  const [pendingChallenge, setPendingChallenge] = useState<LoginChallenge | null>(() =>
    readChallengeFromStorage(),
  );
  const [isReady, setIsReady] = useState(false);
  const sessionRef = useRef<AuthSession | null>(session);

  useEffect(() => {
    sessionRef.current = session;
  }, [session]);

  useEffect(() => {
    let isCancelled = false;

    async function bootstrapSession() {
      const storedSession = readSessionFromStorage();

      if (!storedSession) {
        if (!isCancelled) {
          setIsReady(true);
        }
        return;
      }

      try {
        const user = await getCurrentUser(storedSession.accessToken);
        const validatedSession = { ...storedSession, user };
        window.localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(validatedSession));

        if (!isCancelled) {
          setSession(validatedSession);
        }
      } catch {
        try {
          const refreshedSession = await refreshSession(storedSession.refreshToken);
          window.localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(refreshedSession));

          if (!isCancelled) {
            setSession(refreshedSession);
          }
        } catch {
          window.localStorage.removeItem(SESSION_STORAGE_KEY);

          if (!isCancelled) {
            setSession(null);
          }
        }
      } finally {
        if (!isCancelled) {
          setIsReady(true);
        }
      }
    }

    void bootstrapSession();

    return () => {
      isCancelled = true;
    };
  }, []);

  const persistSession = (nextSession: AuthSession) => {
    window.localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(nextSession));
    setSession(nextSession);
  };

  const clearSession = () => {
    window.localStorage.removeItem(SESSION_STORAGE_KEY);
    setSession(null);
  };

  const persistChallenge = (challenge: LoginChallenge) => {
    window.localStorage.setItem(CHALLENGE_STORAGE_KEY, JSON.stringify(challenge));
    setPendingChallenge(challenge);
  };

  const clearPendingChallenge = () => {
    window.localStorage.removeItem(CHALLENGE_STORAGE_KEY);
    setPendingChallenge(null);
  };

  const login = async ({ phone, password }: LoginPayload) => {
    if (!phone.trim() || !password.trim()) {
      throw new Error('Введите номер телефона и пароль.');
    }

    const result = await loginRequest({ phone, password });

    if (result.requiresSmsVerification && result.challenge) {
      clearSession();
      persistChallenge(result.challenge);
      return { requiresSmsVerification: true } as const;
    }

    if (!result.session) {
      throw new Error('Не удалось завершить вход. Попробуйте ещё раз.');
    }

    clearPendingChallenge();
    persistSession(result.session);
    return { requiresSmsVerification: false } as const;
  };

  const verifyCode = async ({ code }: VerifyCodePayload) => {
    if (!pendingChallenge?.challengeId) {
      throw new Error('Сессия подтверждения истекла. Начните вход заново.');
    }

    if (!code.trim()) {
      throw new Error('Введите код из SMS.');
    }

    const nextSession = await verifySmsCode(pendingChallenge.challengeId, code);
    clearPendingChallenge();
    persistSession(nextSession);
  };

  const logout = () => {
    clearSession();
    clearPendingChallenge();
  };

  useEffect(() => {
    registerSessionHandlers({
      refresh: async () => {
        const current = sessionRef.current;
        if (!current?.refreshToken) {
          return null;
        }
        try {
          const refreshed = await refreshSession(current.refreshToken);
          window.localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(refreshed));
          sessionRef.current = refreshed;
          setSession(refreshed);
          return refreshed.accessToken;
        } catch {
          window.localStorage.removeItem(SESSION_STORAGE_KEY);
          sessionRef.current = null;
          setSession(null);
          return null;
        }
      },
      logout: () => {
        window.localStorage.removeItem(SESSION_STORAGE_KEY);
        window.localStorage.removeItem(CHALLENGE_STORAGE_KEY);
        sessionRef.current = null;
        setSession(null);
        setPendingChallenge(null);
      },
    });

    return () => {
      clearSessionHandlers();
    };
  }, []);

  const updateProfile = async (payload: UpdateProfilePayload) => {
    if (!session?.accessToken) {
      throw new Error('Сессия не найдена. Войдите заново.');
    }

    const updatedUser = await updateMe(session.accessToken, payload);
    persistSession({ ...session, user: updatedUser });
  };

  return (
    <AuthContext.Provider
      value={{
        isAuthenticated: Boolean(session?.accessToken),
        isReady,
        accessToken: session?.accessToken ?? null,
        user: session?.user ?? null,
        pendingChallenge,
        login,
        verifyCode,
        clearPendingChallenge,
        logout,
        updateProfile,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

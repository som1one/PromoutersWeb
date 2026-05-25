import { createContext } from 'react';

export type PromoterUser = {
  id: string;
  username: string;
  email: string;
  firstName: string;
  lastName: string;
  middleName: string | null;
  status: string;
  roleId: string;
  roleCode: string;
  branchId: string | null;
  role: string;
  branch: string;
  city: string;
  phone: string;
};

export type LoginPayload = {
  phone: string;
  password: string;
};

export type VerifyCodePayload = {
  code: string;
};

export type LoginChallenge = {
  challengeId: string;
  expiresAt: string | null;
};

export type LoginResult = {
  requiresSmsVerification: boolean;
};

export type UpdateProfilePayload = {
  firstName?: string;
  lastName?: string;
  middleName?: string | null;
  email?: string;
  phone?: string | null;
  password?: string;
};

export type AuthContextValue = {
  isAuthenticated: boolean;
  isReady: boolean;
  accessToken: string | null;
  user: PromoterUser | null;
  pendingChallenge: LoginChallenge | null;
  login: (payload: LoginPayload) => Promise<LoginResult>;
  verifyCode: (payload: VerifyCodePayload) => Promise<void>;
  clearPendingChallenge: () => void;
  logout: () => void;
  updateProfile: (payload: UpdateProfilePayload) => Promise<void>;
};

export const AuthContext = createContext<AuthContextValue | null>(null);

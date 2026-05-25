import type {
  LoginChallenge,
  LoginPayload,
  PromoterUser,
} from '../../app/auth/auth-context';
import { apiRequest } from './http';

type UserResponse = {
  id: string;
  username: string;
  email: string;
  phone: string | null;
  first_name: string;
  last_name: string;
  middle_name: string | null;
  status: string;
  role_id: string;
  role_code: string | null;
  branch_id: string | null;
  role_name: string | null;
  branch_name: string | null;
  branch_city: string | null;
};

type TokenPairResponse = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: UserResponse;
};

type LoginChallengeResponse = {
  requires_sms_verification: boolean;
  challenge_id: string | null;
  expires_at: string | null;
  access_token: string | null;
  refresh_token: string | null;
  token_type: string | null;
  user: UserResponse | null;
};

export type AuthSession = {
  accessToken: string;
  refreshToken: string;
  tokenType: string;
  user: PromoterUser;
};

export function mapUser(user: UserResponse): PromoterUser {
  return {
    id: user.id,
    username: user.username,
    email: user.email,
    phone: user.phone ?? '',
    firstName: user.first_name,
    lastName: user.last_name,
    middleName: user.middle_name,
    status: user.status,
    roleId: user.role_id,
    roleCode: user.role_code ?? 'promoter',
    branchId: user.branch_id,
    role: user.role_name ?? 'Промоутер',
    branch: user.branch_name ?? 'Филиал не указан',
    city: user.branch_city ?? 'Город не указан',
  };
}

function mapSession(response: TokenPairResponse): AuthSession {
  return {
    accessToken: response.access_token,
    refreshToken: response.refresh_token,
    tokenType: response.token_type,
    user: mapUser(response.user),
  };
}

export async function loginRequest(payload: LoginPayload) {
  const response = await apiRequest<LoginChallengeResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify(payload),
  });

  if (response.requires_sms_verification) {
    const challenge: LoginChallenge = {
      challengeId: response.challenge_id ?? '',
      expiresAt: response.expires_at,
    };

    return {
      requiresSmsVerification: true,
      challenge,
      session: null,
    } as const;
  }

  if (!response.access_token || !response.refresh_token || !response.token_type || !response.user) {
    throw new Error('Не удалось завершить вход. Попробуйте ещё раз.');
  }

  return {
    requiresSmsVerification: false,
    challenge: null,
    session: mapSession({
      access_token: response.access_token,
      refresh_token: response.refresh_token,
      token_type: response.token_type,
      user: response.user,
    }),
  } as const;
}

export async function verifySmsCode(challengeId: string, code: string) {
  const response = await apiRequest<TokenPairResponse>('/auth/verify-sms', {
    method: 'POST',
    body: JSON.stringify({
      challenge_id: challengeId,
      code,
    }),
  });

  return mapSession(response);
}

export async function refreshSession(refreshToken: string) {
  const response = await apiRequest<TokenPairResponse>('/auth/refresh', {
    method: 'POST',
    body: JSON.stringify({
      refresh_token: refreshToken,
    }),
  });

  return mapSession(response);
}

export async function getCurrentUser(accessToken: string) {
  const response = await apiRequest<UserResponse>('/auth/me', {
    method: 'GET',
    accessToken,
  });

  return mapUser(response);
}

export type UpdateMePayload = {
  firstName?: string;
  lastName?: string;
  middleName?: string | null;
  email?: string;
  phone?: string | null;
  password?: string;
};

export async function updateMe(accessToken: string, payload: UpdateMePayload) {
  const body: Record<string, unknown> = {};
  if (payload.firstName !== undefined) body.first_name = payload.firstName;
  if (payload.lastName !== undefined) body.last_name = payload.lastName;
  if (payload.middleName !== undefined) body.middle_name = payload.middleName;
  if (payload.email !== undefined) body.email = payload.email;
  if (payload.phone !== undefined) body.phone = payload.phone;
  if (payload.password) body.password = payload.password;

  const response = await apiRequest<UserResponse>('/users/me', {
    method: 'PATCH',
    accessToken,
    body: JSON.stringify(body),
  });

  return mapUser(response);
}

import { apiFetch } from '../../lib/apiClient'
import type {
  LoginRequest,
  LogoutRequest,
  LogoutResponse,
  SignupRequest,
  SignupResponse,
  TokenPairResponse,
} from '../../lib/types'

export function signup(payload: SignupRequest): Promise<SignupResponse> {
  return apiFetch<SignupResponse>('/auth/signup/', {
    method: 'POST',
    body: payload,
    skipAuth: true,
  })
}

export function login(payload: LoginRequest): Promise<TokenPairResponse> {
  return apiFetch<TokenPairResponse>('/auth/login/', {
    method: 'POST',
    body: payload,
    skipAuth: true,
  })
}

export function logout(payload: LogoutRequest): Promise<LogoutResponse> {
  return apiFetch<LogoutResponse>('/auth/logout/', {
    method: 'POST',
    body: payload,
  })
}

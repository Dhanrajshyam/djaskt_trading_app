import { apiFetch } from '../../lib/apiClient'
import type {
  BrokerageLinkCreateRequest,
  BrokerageLinkResponse,
  BrokerLoginRequest,
  BrokerLoginResponse,
  BrokerLogoutRequest,
  BrokerLogoutResponse,
} from '../../lib/types'

/**
 * Brokerages this frontend knows how to link/log in to — mirrors the
 * backend's `BROKER_STRATEGIES` registry (brokerage/strategies/registry.py),
 * which today only has a single registered strategy. There's no
 * `GET /brokerages/` catalog endpoint, so this list is hand-kept in sync;
 * adding a new broker means adding a strategy on the backend and a row here.
 */
export const KNOWN_BROKERAGES: { name: string; displayName: string }[] = [
  { name: 'angel_one', displayName: 'Angel One' },
]

export function fetchBrokerageLinks(): Promise<BrokerageLinkResponse[]> {
  return apiFetch<BrokerageLinkResponse[]>('/brokerage/links/')
}

export function createBrokerageLink(
  payload: BrokerageLinkCreateRequest,
): Promise<BrokerageLinkResponse> {
  return apiFetch<BrokerageLinkResponse>('/brokerage/links/', { method: 'POST', body: payload })
}

export function deleteBrokerageLink(linkId: string): Promise<void> {
  return apiFetch<void>(`/brokerage/links/${linkId}/`, { method: 'DELETE' })
}

export function brokerageLogin(payload: BrokerLoginRequest): Promise<BrokerLoginResponse> {
  return apiFetch<BrokerLoginResponse>('/brokerage/login/', { method: 'POST', body: payload })
}

export function brokerageLogout(payload: BrokerLogoutRequest): Promise<BrokerLogoutResponse> {
  return apiFetch<BrokerLogoutResponse>('/brokerage/logout/', { method: 'POST', body: payload })
}

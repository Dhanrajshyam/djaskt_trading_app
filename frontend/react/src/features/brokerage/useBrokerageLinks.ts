import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  brokerageLogin,
  brokerageLogout,
  createBrokerageLink,
  deleteBrokerageLink,
  fetchBrokerageLinks,
} from './brokerageApi'

/** Centralized so the Dashboard and Brokerage Setup page share one cache
 * entry — a login/logout/link change on either page is reflected on both. */
export const brokerageLinksQueryKey = ['brokerage', 'links'] as const

export function useBrokerageLinks() {
  return useQuery({
    queryKey: brokerageLinksQueryKey,
    queryFn: fetchBrokerageLinks,
  })
}

export function useCreateBrokerageLink() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: createBrokerageLink,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: brokerageLinksQueryKey })
    },
  })
}

export function useDeleteBrokerageLink() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: deleteBrokerageLink,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: brokerageLinksQueryKey })
    },
  })
}

export function useBrokerageLogin() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: brokerageLogin,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: brokerageLinksQueryKey })
    },
  })
}

export function useBrokerageLogout() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: brokerageLogout,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: brokerageLinksQueryKey })
    },
  })
}

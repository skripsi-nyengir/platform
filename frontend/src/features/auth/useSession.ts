import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getSession, login, logout } from '../../api/auth'
import { ApiError } from '../../api/errors'
import type { LoginRequest, SessionResponse } from '../../contracts/auth'

export const sessionQueryKey = ['auth', 'session'] as const

export function isUnauthenticated(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401
}

export function useSession() {
  return useQuery<SessionResponse>({
    queryKey: sessionQueryKey,
    queryFn: ({ signal }) => getSession(signal),
    // A 401 is the answer, not a failure worth retrying, and retrying would delay
    // every redirect to the login page by the backoff.
    retry: (failureCount, error) => failureCount < 2 && !isUnauthenticated(error),
    staleTime: 60_000,
  })
}

/**
 * The session as the router should read it.
 *
 * React Query keeps the last successful data after a failed refetch, so a lapsed
 * session would otherwise still look valid. Both the route guard and the login page
 * have to agree on that, or they redirect at each other forever.
 */
export function useSessionState() {
  const query = useSession()
  const rejected = isUnauthenticated(query.error)
  return {
    session: rejected ? undefined : query.data,
    isPending: query.isPending,
    error: query.error,
    rejected,
  }
}

export function useLogin() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: LoginRequest) => login(body),
    onSuccess: (session) => {
      // Seed the cache from the login response so the guard admits the user without
      // a second round trip.
      queryClient.setQueryData(sessionQueryKey, session)
    },
  })
}

export function useLogout(onSignedOut: () => void) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => logout(),
    onSettled: () => {
      // Clear everything: cached telemetry and alerts belong to the session that
      // just ended and must not survive into the next one. Runs on failure too, so a
      // logout the server never saw still ends the session in the browser.
      queryClient.clear()
      onSignedOut()
    },
  })
}

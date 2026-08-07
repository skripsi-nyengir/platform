import { MutationCache, QueryCache, QueryClient, type Query } from '@tanstack/react-query'
import { ApiError } from '../api/errors'
import { sessionQueryKey } from '../features/auth/useSession'

declare module '@tanstack/react-query' {
  interface Register {
    defaultError: ApiError
  }
}

function isUnauthorized(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401
}

// A session can lapse mid-visit, and every route would then fail on its own. Asking
// the session query to refetch in one place lets the route guard do the redirecting,
// so no page component needs to know that authentication exists.
function revalidateSessionOn401(
  error: unknown,
  query: Query<unknown, unknown, unknown, readonly unknown[]>,
) {
  // The session query's own 401 is the signal the guard reads. Reacting to it here
  // would refetch, fail again, and spin forever without ever resolving.
  if (!isUnauthorized(error) || query.queryKey[0] === sessionQueryKey[0]) return
  void queryClient.invalidateQueries({ queryKey: sessionQueryKey })
}

export const queryClient: QueryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Retrying a 401 cannot turn it into a 200, and onError only fires once the
      // retries are exhausted, which would leave an expired session sitting on a
      // dead page for several seconds before the redirect.
      retry: (failureCount, error) => failureCount < 3 && !isUnauthorized(error),
    },
  },
  queryCache: new QueryCache({ onError: revalidateSessionOn401 }),
  mutationCache: new MutationCache({
    onError: (error) => {
      if (isUnauthorized(error)) {
        void queryClient.invalidateQueries({ queryKey: sessionQueryKey })
      }
    },
  }),
})

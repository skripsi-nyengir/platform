import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ComponentType, PropsWithChildren } from 'react'

export interface QueryTestHarness {
  queryClient: QueryClient
  wrapper: ComponentType<PropsWithChildren>
  restore: () => void
}

export function createQueryTestHarness(): QueryTestHarness {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  const originalFetch = globalThis.fetch
  const relativeFetch: typeof fetch = (input, init) => {
    const resolvedInput =
      typeof input === 'string' || input instanceof URL
        ? new URL(String(input), window.location.origin)
        : input
    return originalFetch(resolvedInput, init)
  }
  globalThis.fetch = relativeFetch

  function QueryTestProvider({ children }: PropsWithChildren) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  }

  return {
    queryClient,
    wrapper: QueryTestProvider,
    restore: () => {
      queryClient.clear()
      globalThis.fetch = originalFetch
    },
  }
}

import { QueryClient } from '@tanstack/react-query'
import type { ApiError } from '../api/errors'

declare module '@tanstack/react-query' {
  interface Register {
    defaultError: ApiError
  }
}

export const queryClient = new QueryClient()

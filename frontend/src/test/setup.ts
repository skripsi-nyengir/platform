import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterAll, afterEach, beforeAll } from 'vitest'
import { queryClient } from '../app/queryClient'
import { server } from '../mocks/node'
import { resetMockState } from '../mocks/state'

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(cleanup)
afterEach(() => {
  server.resetHandlers()
  resetMockState()
  // AppProviders shares one module-level client, so a cached session would other-
  // wise let a signed-in test admit the next one straight past the route guard.
  queryClient.clear()
})
afterAll(() => server.close())

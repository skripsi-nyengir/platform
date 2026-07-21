import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterAll, afterEach, beforeAll } from 'vitest'
import { server } from '../mocks/node'
import { resetMockState } from '../mocks/state'

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(cleanup)
afterEach(() => {
  server.resetHandlers()
  resetMockState()
})
afterAll(() => server.close())

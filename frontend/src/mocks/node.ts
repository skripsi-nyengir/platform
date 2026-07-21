import { setupServer } from 'msw/node'
import { createHandlers } from './handlers'
import { mockState } from './state'

export const server = setupServer(...createHandlers(mockState))

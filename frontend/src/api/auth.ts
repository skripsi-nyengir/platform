import {
  LogoutResponseSchema,
  SessionResponseSchema,
  type LoginRequest,
  type LogoutResponse,
  type SessionResponse,
} from '../contracts/auth'
import { requestJson } from './http'

// The session cookie is HttpOnly and same-origin, so fetch sends it without any
// configuration here and nothing in this module ever holds a token.

export function getSession(signal?: AbortSignal): Promise<SessionResponse> {
  return requestJson('/api/auth/session', SessionResponseSchema, { signal })
}

export function login(
  body: LoginRequest,
  signal?: AbortSignal,
): Promise<SessionResponse> {
  return requestJson('/api/auth/login', SessionResponseSchema, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  })
}

export function logout(signal?: AbortSignal): Promise<LogoutResponse> {
  return requestJson('/api/auth/logout', LogoutResponseSchema, {
    method: 'POST',
    signal,
  })
}

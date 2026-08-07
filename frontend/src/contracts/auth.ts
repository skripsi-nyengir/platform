import { z } from 'zod'
import { OperationalInstantSchema } from './common'

export const LoginRequestSchema = z.strictObject({
  username: z.string().min(1).max(200),
  password: z.string().min(1).max(1024),
})
export type LoginRequest = z.infer<typeof LoginRequestSchema>

export const SessionResponseSchema = z.strictObject({
  request_id: z.string(),
  username: z.string(),
  display_name: z.string(),
  expires_at: OperationalInstantSchema,
})
export type SessionResponse = z.infer<typeof SessionResponseSchema>

export const LogoutResponseSchema = z.strictObject({
  request_id: z.string(),
})
export type LogoutResponse = z.infer<typeof LogoutResponseSchema>

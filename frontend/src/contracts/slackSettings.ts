import { z } from 'zod'
import { OperationalInstantSchema } from './common'

const ChannelIdSchema = z.string().trim().min(1).max(255)
const BotTokenSchema = z.string().min(1).max(4096)

export const SlackSettingsResponseSchema = z.strictObject({
  request_id: z.string(),
  enabled: z.boolean(),
  channel_id: ChannelIdSchema.nullable(),
  bot_token_configured: z.boolean(),
  updated_at: OperationalInstantSchema,
  updated_by_username: z.string().nullable(),
})
export type SlackSettingsResponse = z.infer<typeof SlackSettingsResponseSchema>

export const UpdateSlackSettingsRequestSchema = z.strictObject({
  enabled: z.boolean(),
  channel_id: ChannelIdSchema.nullable(),
  bot_token: BotTokenSchema.nullable().optional(),
})
export type UpdateSlackSettingsRequest = z.infer<typeof UpdateSlackSettingsRequestSchema>

export const TestSlackSettingsRequestSchema = z.strictObject({
  channel_id: ChannelIdSchema,
  bot_token: BotTokenSchema.optional(),
})
export type TestSlackSettingsRequest = z.infer<typeof TestSlackSettingsRequestSchema>

export const TestSlackSettingsResponseSchema = z.strictObject({
  request_id: z.string(),
  status: z.literal('sent'),
  sent_at: OperationalInstantSchema,
})
export type TestSlackSettingsResponse = z.infer<typeof TestSlackSettingsResponseSchema>

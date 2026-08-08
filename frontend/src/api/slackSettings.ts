import {
  SlackSettingsResponseSchema,
  TestSlackSettingsRequestSchema,
  TestSlackSettingsResponseSchema,
  UpdateSlackSettingsRequestSchema,
  type SlackSettingsResponse,
  type TestSlackSettingsRequest,
  type TestSlackSettingsResponse,
  type UpdateSlackSettingsRequest,
} from '../contracts/slackSettings'
import { requestJson } from './http'

const slackSettingsPath = '/api/settings/slack' as const

export function getSlackSettings(signal?: AbortSignal): Promise<SlackSettingsResponse> {
  return requestJson(slackSettingsPath, SlackSettingsResponseSchema, { signal })
}

export function updateSlackSettings(
  body: UpdateSlackSettingsRequest,
  signal?: AbortSignal,
): Promise<SlackSettingsResponse> {
  const payload = UpdateSlackSettingsRequestSchema.parse(body)
  return requestJson(slackSettingsPath, SlackSettingsResponseSchema, {
    method: 'PUT',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(payload),
    signal,
  })
}

export function testSlackSettings(
  body: TestSlackSettingsRequest,
  signal?: AbortSignal,
): Promise<TestSlackSettingsResponse> {
  const payload = TestSlackSettingsRequestSchema.parse(body)
  return requestJson(`${slackSettingsPath}/test`, TestSlackSettingsResponseSchema, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(payload),
    signal,
    // Slack transport allows 15 seconds; keep the browser deadline above it so
    // a real delivery cannot be reported as a client-side timeout.
    timeoutMs: 20_000,
  })
}

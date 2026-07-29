import { CorpusDeviceIdSchema, type CorpusDeviceId } from '../contracts/common'
import {
  InjectionEventsResponseSchema,
  type InjectionEventsResponse,
} from '../contracts/injection'
import { requestJson } from './http'

export function getInjectionEvents(
  deviceId: CorpusDeviceId,
  signal?: AbortSignal,
): Promise<InjectionEventsResponse> {
  const id = CorpusDeviceIdSchema.parse(deviceId)
  return requestJson(
    `/api/injection-events?device_id=${encodeURIComponent(id)}`,
    InjectionEventsResponseSchema,
    { signal },
  )
}

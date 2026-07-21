import type { ZodType } from 'zod'
import {
  ProblemDetailsSchema,
  type ApiPath,
} from '../contracts/common'
import { ApiError } from './errors'

export type RequestJsonOptions = Omit<RequestInit, 'signal'> & {
  signal?: AbortSignal
  timeoutMs?: number
}

function rawRequestId(body: unknown): string | undefined {
  if (
    typeof body === 'object' &&
    body !== null &&
    'request_id' in body &&
    typeof body.request_id === 'string'
  ) {
    return body.request_id
  }
  return undefined
}

export async function requestJson<T>(
  path: ApiPath,
  schema: ZodType<T>,
  options: RequestJsonOptions = {},
): Promise<T> {
  const { signal: callerSignal, timeoutMs = 8_000, ...requestOptions } = options
  callerSignal?.throwIfAborted()

  const timeoutController = new AbortController()
  const timeout = globalThis.setTimeout(() => {
    timeoutController.abort(new DOMException('Request timed out', 'TimeoutError'))
  }, timeoutMs)
  const signal = callerSignal
    ? AbortSignal.any([callerSignal, timeoutController.signal])
    : timeoutController.signal
  const headers = new Headers(requestOptions.headers)
  headers.set('accept', 'application/json')

  try {
    const response = await fetch(path, { ...requestOptions, headers, signal })
    let body: unknown
    try {
      body = await response.json()
    } catch (error) {
      if (callerSignal?.aborted) throw callerSignal.reason
      if (timeoutController.signal.aborted) {
        throw new ApiError('timeout', `Request timed out after ${timeoutMs} ms`)
      }
      if (!(error instanceof SyntaxError)) throw error
      body = undefined
    }

    if (!response.ok) {
      const parsedProblem = ProblemDetailsSchema.safeParse(body)
      if (parsedProblem.success) {
        throw new ApiError(
          'problem',
          parsedProblem.data.detail,
          response.status,
          parsedProblem.data.request_id,
          parsedProblem.data,
        )
      }
      throw new ApiError(
        'problem',
        `HTTP ${response.status}`,
        response.status,
        rawRequestId(body),
      )
    }

    const parsed = schema.safeParse(body)
    if (!parsed.success) {
      throw new ApiError('schema', parsed.error.message, undefined, rawRequestId(body))
    }
    return parsed.data
  } catch (error) {
    if (error instanceof ApiError) throw error
    if (callerSignal?.aborted) throw callerSignal.reason
    if (timeoutController.signal.aborted) {
      throw new ApiError('timeout', `Request timed out after ${timeoutMs} ms`)
    }
    throw new ApiError(
      'network',
      error instanceof Error ? error.message : 'Network request failed',
    )
  } finally {
    globalThis.clearTimeout(timeout)
  }
}

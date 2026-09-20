/**
 * Lightweight axios mock for `@/lib/api`.
 *
 * Why not MSW? `msw/node` under `jest-environment-jsdom` requires the
 * `jest-fixed-jsdom` environment (or a pile of fetch/Request/Response/
 * ReadableStream/TextEncoder polyfills) plus `customExportConditions`
 * overrides, and still proved fragile across jsdom versions. Every API
 * call in this codebase funnels through the axios instance in
 * `src/lib/api.ts`, so mocking that module covers the same surface with
 * zero extra dependencies.
 *
 * Usage in a test file:
 *
 *   import { apiMock, mockApiResponse, mockApiError } from '../../../tests/mocks/api-mock'
 *
 *   jest.mock('@/lib/api', () => ({
 *     __esModule: true,
 *     default: apiMock,
 *   }))
 *
 *   it('loads patients', async () => {
 *     mockApiResponse('get', [{ id: 'p1' }])
 *     ...
 *   })
 */

export type HttpMethod = 'get' | 'post' | 'put' | 'patch' | 'delete'

/**
 * Shape-compatible subset of the axios instance returned by
 * `axios.create()` in `src/lib/api.ts`.
 */
export const apiMock = {
  get: jest.fn(),
  post: jest.fn(),
  put: jest.fn(),
  patch: jest.fn(),
  delete: jest.fn(),
  request: jest.fn(),
  defaults: { headers: { common: {} as Record<string, string> } },
  interceptors: {
    request: { use: jest.fn(), eject: jest.fn() },
    response: { use: jest.fn(), eject: jest.fn() },
  },
}

/** Queue a successful axios-style response for the next `api.<method>()` call. */
export function mockApiResponse(
  method: HttpMethod,
  data: unknown,
  status = 200
) {
  apiMock[method].mockResolvedValueOnce({
    data,
    status,
    statusText: 'OK',
    headers: {},
    config: {},
  })
}

/** Queue an axios-style error (with `response` populated) for the next call. */
export function mockApiError(
  method: HttpMethod,
  status = 500,
  data: unknown = { detail: 'Server error' },
  message = `Request failed with status code ${status}`
) {
  const error = Object.assign(new Error(message), {
    isAxiosError: true,
    response: {
      data,
      status,
      statusText: '',
      headers: {},
      config: {},
    },
    config: {},
  })
  apiMock[method].mockRejectedValueOnce(error)
  return error
}

/** Reset all HTTP verb mocks — call in `beforeEach`/`afterEach` as needed. */
export function resetApiMock() {
  const methods: HttpMethod[] = ['get', 'post', 'put', 'patch', 'delete']
  for (const m of methods) {
    apiMock[m].mockReset()
  }
  apiMock.request.mockReset()
}

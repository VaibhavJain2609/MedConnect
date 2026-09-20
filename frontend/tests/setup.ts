/**
 * Jest Test Setup
 * Configures testing environment for all tests
 */

import 'whatwg-fetch'
import '@testing-library/jest-dom'

// Axios in src/lib/api.ts builds an absolute baseURL from this env var at
// module-load time; pin it so tests see a deterministic origin.
process.env.NEXT_PUBLIC_API_URL =
  process.env.NEXT_PUBLIC_API_URL || 'http://localhost'

// ---------------------------------------------------------------------------
// API mocking strategy
// ---------------------------------------------------------------------------
// MSW v2 (tests/mocks/server.ts + handlers.ts) is intentionally DISABLED:
// under jest-environment-jsdom it needs jest-fixed-jsdom (or a set of
// fetch/Request/Response/ReadableStream/TextEncoder polyfills) on top of
// the customExportConditions override already set in jest.config.js, and
// proved too fragile to keep green.
//
// Use the axios-level mock instead — see tests/mocks/api-mock.ts:
//   jest.mock('@/lib/api', () => ({ __esModule: true, default: apiMock }))
//
// The MSW handlers are retained (paths wildcarded to match any origin) so
// MSW can be re-enabled later by uncommenting the block below once a
// jest-fixed-jsdom environment is adopted.
//
// import { server } from './mocks/server'
// beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
// afterEach(() => server.resetHandlers())
// afterAll(() => server.close())
// ---------------------------------------------------------------------------

// Mock next/router
jest.mock('next/router', () => require('next-router-mock'))

// Mock next/navigation
jest.mock('next/navigation', () => ({
  ...require('next-router-mock'),
  useSearchParams: () => ({
    get: jest.fn(),
  }),
}))

// Mock keycloak-js so importing @/lib/auth / @/stores/auth-store in tests
// never constructs a real Keycloak client against jsdom.
jest.mock('keycloak-js')

// Mock window.matchMedia
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: jest.fn().mockImplementation((query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: jest.fn(), // deprecated
    removeListener: jest.fn(), // deprecated
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
    dispatchEvent: jest.fn(),
  })),
})

// Mock IntersectionObserver
global.IntersectionObserver = class IntersectionObserver {
  constructor() {}
  disconnect() {}
  observe() {}
  takeRecords() {
    return []
  }
  unobserve() {}
} as any

// Suppress console errors in tests (optional)
const originalError = console.error
beforeAll(() => {
  console.error = jest.fn((...args) => {
    if (
      typeof args[0] === 'string' &&
      (args[0].includes('Warning: ReactDOM.render') ||
        args[0].includes('Warning: useLayoutEffect') ||
        args[0].includes('Not implemented: HTMLFormElement'))
    ) {
      return
    }
    originalError.call(console, ...args)
  })
})

afterAll(() => {
  console.error = originalError
})

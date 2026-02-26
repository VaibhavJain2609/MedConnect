/**
 * Jest Test Setup
 * Configures testing environment for all tests
 */

import 'whatwg-fetch'
import '@testing-library/jest-dom'
// import { server } from './mocks/server'

// TODO: Configure MSW v2 with Jest (ESM compatibility issue)
// For now, API mocking will be done with manual mocks

// Establish API mocking before all tests
// beforeAll(() => {
//   server.listen({ onUnhandledRequest: 'error' })
// })

// Reset any request handlers that we may add during the tests
// afterEach(() => {
//   server.resetHandlers()
// })

// Clean up after the tests are finished
// afterAll(() => {
//   server.close()
// })

// Mock next/router
jest.mock('next/router', () => require('next-router-mock'))

// Mock next/navigation
jest.mock('next/navigation', () => ({
  ...require('next-router-mock'),
  useSearchParams: () => ({
    get: jest.fn(),
  }),
}))

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

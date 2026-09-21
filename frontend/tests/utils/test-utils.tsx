/**
 * Test Utilities
 * Custom render functions, auth-store seeding, and router helpers.
 */

import React, { ReactElement } from 'react'
import { render, RenderOptions } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouterProvider } from 'next-router-mock/MemoryRouterProvider'
import mockRouter from 'next-router-mock'
import { NextIntlClientProvider } from 'next-intl'

import { useAuthStore } from '@/stores/auth-store'
import type { User } from '@/lib/auth'
import enMessages from '../../messages/en.json'

// ---------------------------------------------------------------------------
// Auth fixtures — match the `User` shape in src/lib/auth.ts
// ---------------------------------------------------------------------------

export const patientUser: User = {
  id: 'user-patient-1',
  email: 'patient@test.com',
  phone: '+919000000001',
  full_name: 'Test Patient',
  role: 'patient',
  language_pref: 'en',
}

export const doctorUser: User = {
  id: 'user-doctor-1',
  email: 'doctor@test.com',
  phone: '+919000000002',
  full_name: 'Dr. Test Doctor',
  role: 'doctor',
  language_pref: 'en',
}

export const adminUser: User = {
  id: 'user-admin-1',
  email: 'admin@test.com',
  phone: '+919000000003',
  full_name: 'Test Admin',
  role: 'admin',
  language_pref: 'en',
}

/** Seed the Zustand auth store as an authenticated user (or signed out). */
export function seedAuth(user: User | null = patientUser) {
  useAuthStore.setState({
    user,
    loading: false,
    initialized: true,
    error: null,
  })
}

/** Reset the auth store to its signed-out, initialized state. */
export function clearAuth() {
  useAuthStore.setState({
    user: null,
    loading: false,
    initialized: true,
    error: null,
  })
}

// ---------------------------------------------------------------------------
// Providers
// ---------------------------------------------------------------------------

function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false, // Disable retries in tests
        gcTime: 0, // React Query v5: gcTime replaces cacheTime
      },
    },
  })
}

interface AllTheProvidersProps {
  children: React.ReactNode
}

function AllTheProviders({ children }: AllTheProvidersProps) {
  const testQueryClient = createTestQueryClient()

  return (
    // Components under test call useTranslations/useFormatter — provide the
    // en bundle so assertions match real English output.
    <NextIntlClientProvider locale="en" messages={enMessages}>
      <QueryClientProvider client={testQueryClient}>
        {/* Provides router context for components using next-router-mock
            (both next/router and next/navigation are mapped to it in setup). */}
        <MemoryRouterProvider>{children}</MemoryRouterProvider>
      </QueryClientProvider>
    </NextIntlClientProvider>
  )
}

interface CustomRenderOptions extends Omit<RenderOptions, 'wrapper'> {
  /** Seed the auth store before rendering. Defaults to leaving it untouched. */
  auth?: User | null
  /** Push an initial route onto next-router-mock before rendering. */
  route?: string
}

function customRender(ui: ReactElement, options?: CustomRenderOptions) {
  const { auth, route, ...renderOptions } = options ?? {}

  if (auth !== undefined) {
    seedAuth(auth)
  }
  if (route) {
    mockRouter.setCurrentUrl(route)
  }

  return render(ui, { wrapper: AllTheProviders, ...renderOptions })
}

// Reset auth state between tests so seeded users don't leak.
afterEach(() => {
  useAuthStore.setState({
    user: null,
    loading: true,
    initialized: false,
    error: null,
  })
})

// Re-export everything
export * from '@testing-library/react'
export { customRender as render }
export { mockRouter }

// Helper functions
export function waitForLoadingToFinish() {
  return new Promise((resolve) => setTimeout(resolve, 0))
}

export function createMockRouter(props: Partial<any> = {}) {
  return {
    push: jest.fn(),
    replace: jest.fn(),
    prefetch: jest.fn(),
    back: jest.fn(),
    pathname: '/',
    route: '/',
    query: {},
    asPath: '/',
    ...props,
  }
}

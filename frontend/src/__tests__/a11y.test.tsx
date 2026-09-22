/**
 * Accessibility (jest-axe) tests for the highest-traffic pages.
 *
 * Renders the login page, patient appointments (list + booking modal),
 * doctor appointments, and admin settings under jsdom and runs axe-core
 * on the rendered container.
 *
 * Mocking follows the repo pattern: the axios instance in `@/lib/api` is
 * replaced by `apiMock` (tests/mocks/api-mock.ts); the typed sub-modules
 * (`@/lib/api/appointments`, `availability`, `clinics`, `platform-settings`)
 * stay real and funnel through it.
 *
 * jsdom caveats:
 *  - `region` is disabled: these tests render page *content* only — the
 *    landmark scaffolding (`<main>`, header, sidebar nav) lives in the
 *    portal layouts, which are intentionally out of scope.
 *  - `color-contrast` is disabled: jsdom never loads the compiled Tailwind
 *    stylesheet, so axe cannot compute real foreground/background colors.
 *    Any contrast concerns on brand colors must be audited in a real
 *    browser (e.g. Playwright + axe) instead.
 */

import { axe, toHaveNoViolations } from 'jest-axe'
import userEvent from '@testing-library/user-event'
import {
  render,
  screen,
  waitFor,
  patientUser,
} from '../../tests/utils/test-utils'
import { apiMock, resetApiMock } from '../../tests/mocks/api-mock'
import type { Appointment } from '@/lib/api/appointments'
import type { PlatformSetting } from '@/lib/api/platform-settings'

// Lazy require inside the factory: `@/lib/api` is first pulled in by
// test-utils (auth-store → lib/auth → api/users) before `apiMock`'s import
// binding has initialized, so a direct reference would hit the TDZ.
jest.mock('@/lib/api', () => ({
  __esModule: true,
  default: require('../../tests/mocks/api-mock').apiMock,
}))

// The login page calls loginRedirect() on mount; the keycloak-js automock
// doesn't stub instance methods, so intercept the auth entry points instead.
jest.mock('@/lib/auth', () => ({
  __esModule: true,
  ...jest.requireActual('@/lib/auth'),
  loginRedirect: jest.fn(),
  signupRedirect: jest.fn(),
  logout: jest.fn(),
}))

import LoginPage from '@/app/login/page'
import PatientAppointmentsPage from '@/app/patient/appointments/page'
import DoctorAppointmentsPage from '@/app/doctor/appointments/page'
import AdminSettingsPage from '@/app/admin/settings/page'

expect.extend(toHaveNoViolations)

/** Axe options for page-fragment scans — see file header for why. */
const AXE_OPTIONS = {
  rules: {
    region: { enabled: false },
    'color-contrast': { enabled: false },
  },
}

const runAxe = (container: HTMLElement) => axe(container, AXE_OPTIONS)

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const FUTURE_ISO = new Date(Date.now() + 48 * 60 * 60 * 1000).toISOString()
const PAST_ISO = new Date(Date.now() - 48 * 60 * 60 * 1000).toISOString()

const patientAppointments: Appointment[] = [
  {
    id: 'appt-1',
    patient_id: 'user-patient-1',
    patient_name: 'Test Patient',
    doctor_id: 'doc-1',
    doctor_name: 'Dr. Sarah Smith',
    clinic_id: 'clinic-1',
    clinic_name: 'City Clinic',
    branch_id: null,
    branch_name: null,
    scheduled_at: FUTURE_ISO,
    duration_minutes: 30,
    type: 'in-person',
    status: 'scheduled',
    chief_complaint: 'Fever for 2 days',
    notes: null,
    cancelled_reason: null,
    meeting_url: null,
    teleconsult_url: null,
    created_by: 'user-patient-1',
    created_at: PAST_ISO,
    updated_at: PAST_ISO,
  },
]

const doctorAppointments: Appointment[] = [
  {
    ...patientAppointments[0],
    id: 'appt-2',
    type: 'teleconsult',
    is_provisional: false,
  },
]

const adminSettings: PlatformSetting[] = [
  {
    key: 'maintenance_mode',
    value: false,
    description: 'Lock out non-admin API traffic',
    updated_by: 'admin',
    updated_at: PAST_ISO,
  },
  {
    key: 'registration_enabled',
    value: true,
    description: null,
    updated_by: null,
    updated_at: null,
  },
  {
    key: 'max_upload_mb',
    value: 10,
    description: 'Maximum upload size in MB',
    updated_by: null,
    updated_at: PAST_ISO,
  },
  {
    key: 'reminder_channels_enabled',
    value: { in_app: true, email: true, sms: false, whatsapp: false },
    description: 'Channels used for appointment reminders',
    updated_by: null,
    updated_at: PAST_ISO,
  },
]

function ok(data: unknown) {
  return Promise.resolve({
    data,
    status: 200,
    statusText: 'OK',
    headers: {},
    config: {},
  })
}

/** Route-style mock for every GET the pages under test issue. */
function stubApiGet(appointments: Appointment[] = []) {
  apiMock.get.mockImplementation((url: string) => {
    if (url.startsWith('/api/v1/appointments')) {
      return ok({ data: appointments, total: appointments.length })
    }
    if (url === '/api/v1/admin/settings') {
      return ok({ data: adminSettings })
    }
    if (url === '/api/v1/doctors/profile') {
      return ok({ id: 'doctor-1' })
    }
    if (url === '/api/v1/patients/clinic-links') {
      return ok({ data: [] })
    }
    if (url.includes('/slots')) {
      return ok({ slots: [] })
    }
    // /api/v1/clinics/my, /api/v1/clinics/:id/doctors, doctor search, etc.
    return ok({ data: [] })
  })
}

beforeEach(() => {
  resetApiMock()
  apiMock.post.mockResolvedValue({ data: {}, status: 200 })
  apiMock.put.mockResolvedValue({ data: {}, status: 200 })
  apiMock.delete.mockResolvedValue({ data: {}, status: 204 })
})

// ---------------------------------------------------------------------------
// Login
// ---------------------------------------------------------------------------

describe('a11y: /login', () => {
  it('has no violations on the redirect spinner state', async () => {
    const { container } = render(<LoginPage />)
    expect(await runAxe(container)).toHaveNoViolations()
  })
})

// ---------------------------------------------------------------------------
// Patient appointments
// ---------------------------------------------------------------------------

describe('a11y: /patient/appointments', () => {
  it('has no violations on the empty state', async () => {
    stubApiGet([])
    const { container } = render(<PatientAppointmentsPage />, {
      auth: patientUser,
    })
    await waitFor(() =>
      expect(screen.getByText('No upcoming appointments')).toBeInTheDocument()
    )
    expect(await runAxe(container)).toHaveNoViolations()
  })

  it('has no violations on the appointment list', async () => {
    stubApiGet(patientAppointments)
    const { container } = render(<PatientAppointmentsPage />, {
      auth: patientUser,
    })
    await waitFor(() =>
      expect(screen.getByText('Dr. Sarah Smith')).toBeInTheDocument()
    )
    expect(await runAxe(container)).toHaveNoViolations()
  })

  it('has no violations on the booking modal', async () => {
    stubApiGet(patientAppointments)
    const { container } = render(<PatientAppointmentsPage />, {
      auth: patientUser,
    })
    await userEvent.click(
      await screen.findByRole('button', { name: /book appointment/i })
    )
    expect(
      await screen.findByRole('dialog', { name: /book appointment/i })
    ).toBeInTheDocument()
    expect(await runAxe(container)).toHaveNoViolations()
  })
})

// ---------------------------------------------------------------------------
// Doctor appointments
// ---------------------------------------------------------------------------

describe('a11y: /doctor/appointments', () => {
  it('has no violations on the schedule view', async () => {
    stubApiGet(doctorAppointments)
    const { container } = render(<DoctorAppointmentsPage />, {
      auth: patientUser,
    })
    await waitFor(() =>
      expect(screen.getByText('Test Patient')).toBeInTheDocument()
    )
    expect(await runAxe(container)).toHaveNoViolations()
  })

  it('has no violations on the new-appointment modal', async () => {
    stubApiGet(doctorAppointments)
    const { container } = render(<DoctorAppointmentsPage />, {
      auth: patientUser,
    })
    await userEvent.click(
      await screen.findByRole('button', { name: /new appointment/i })
    )
    await screen.findByRole('dialog', { name: /new appointment/i })
    expect(await runAxe(container)).toHaveNoViolations()
  })

  it('has no violations on the edit-appointment modal', async () => {
    stubApiGet(doctorAppointments)
    const { container } = render(<DoctorAppointmentsPage />, {
      auth: patientUser,
    })
    await waitFor(() =>
      expect(screen.getByText('Test Patient')).toBeInTheDocument()
    )
    await userEvent.click(screen.getByRole('button', { name: /^edit$/i }))
    await screen.findByRole('dialog', { name: /edit appointment/i })
    expect(await runAxe(container)).toHaveNoViolations()
  })

  it('has no violations on the cancel-appointment modal', async () => {
    stubApiGet(doctorAppointments)
    const { container } = render(<DoctorAppointmentsPage />, {
      auth: patientUser,
    })
    await waitFor(() =>
      expect(screen.getByText('Test Patient')).toBeInTheDocument()
    )
    await userEvent.click(screen.getByRole('button', { name: /^cancel$/i }))
    await screen.findByRole('dialog', { name: /cancel appointment/i })
    expect(await runAxe(container)).toHaveNoViolations()
  })
})

// ---------------------------------------------------------------------------
// Admin settings
// ---------------------------------------------------------------------------

describe('a11y: /admin/settings', () => {
  it('has no violations on the settings grid', async () => {
    stubApiGet()
    const { container } = render(<AdminSettingsPage />, { auth: patientUser })
    await waitFor(() =>
      expect(screen.getByText('Maintenance Mode')).toBeInTheDocument()
    )
    expect(await runAxe(container)).toHaveNoViolations()
  })
})

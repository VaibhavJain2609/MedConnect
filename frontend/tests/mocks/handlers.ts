/**
 * MSW Request Handlers
 * Mock API responses for testing
 */

import { http, HttpResponse } from 'msw'

// Mock data factories
export const mockPatient = (id: string = 'P-001') => ({
  id,
  name: 'John Doe',
  photo: null,
  age: 45,
  gender: 'Male',
  bloodType: 'A+',
  phone: '+1 (555) 123-4567',
  email: 'john.doe@example.com',
  address: '123 Main Street',
  city: 'New York',
  state: 'NY',
  zipCode: '10001',
})

export const mockDoctor = (id: string = 'D-001') => ({
  id,
  name: 'Dr. Sarah Smith',
  photo: null,
  specialty: 'Cardiology',
  experience: 15,
  appointmentsCount: 1234,
  email: 'sarah.smith@medconnect.com',
  phone: '+1 (555) 123-4567',
})

export const mockAppointment = (id: string = 'A-001') => ({
  id,
  patientId: 'P-001',
  patientName: 'John Doe',
  patientPhoto: null,
  doctorName: 'Dr. Sarah Smith',
  doctorPhoto: null,
  department: 'Cardiology',
  appointmentDate: '2026-02-28',
  appointmentTime: '10:00 AM',
  status: 'upcoming',
})

// API request handlers
export const handlers = [
  // Auth endpoints
  http.post('/api/v1/auth/login', () => {
    return HttpResponse.json({
      access_token: 'mock-token',
      user: {
        id: '1',
        email: 'test@example.com',
        full_name: 'Test User',
        role: 'admin',
      },
    })
  }),

  http.post('/api/v1/auth/logout', () => {
    return HttpResponse.json({ success: true })
  }),

  http.get('/api/v1/users/me', () => {
    return HttpResponse.json({
      id: '1',
      email: 'test@example.com',
      full_name: 'Test User',
      role: 'admin',
    })
  }),

  // Patients endpoints
  http.get('/api/v1/admin/patients', () => {
    return HttpResponse.json([
      mockPatient('P-001'),
      mockPatient('P-002'),
      mockPatient('P-003'),
    ])
  }),

  http.get('/api/v1/patients/:id', ({ params }) => {
    return HttpResponse.json(mockPatient(params.id as string))
  }),

  // Doctors endpoints
  http.get('/api/v1/admin/doctors', () => {
    return HttpResponse.json([
      mockDoctor('D-001'),
      mockDoctor('D-002'),
    ])
  }),

  // Appointments endpoints
  http.get('/api/v1/admin/appointments', () => {
    return HttpResponse.json([
      mockAppointment('A-001'),
      mockAppointment('A-002'),
    ])
  }),

  // Dashboard stats
  http.get('/api/v1/admin/stats', () => {
    return HttpResponse.json({
      total_patients: 108,
      patient_trend: 20,
      total_appointments: 42,
      appointment_trend: 12,
      total_doctors: 24,
      doctor_trend: 8,
      total_transactions: 156,
      transaction_trend: 15,
    })
  }),

  // Notifications
  http.get('/api/v1/notifications', () => {
    return HttpResponse.json([
      {
        id: '1',
        type: 'appointment',
        title: 'Upcoming Appointment',
        message: 'Appointment tomorrow at 10:00 AM',
        timestamp: '2 hours ago',
        read: false,
      },
    ])
  }),

  // Search
  http.get('/api/v1/search', ({ request }) => {
    const url = new URL(request.url)
    const query = url.searchParams.get('q')

    return HttpResponse.json([
      {
        id: 'P-001',
        type: 'patient',
        title: 'John Doe',
        subtitle: 'Age 45 • Male',
        url: '/patient/P-001',
      },
    ])
  }),
]

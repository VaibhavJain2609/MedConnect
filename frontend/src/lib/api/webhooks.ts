import api from '@/lib/api'

// ── Clinic outbound webhooks (owner|admin membership required) ────────────

// Keep in sync with app.models.webhook.WEBHOOK_EVENT_TYPES.
export const WEBHOOK_EVENT_TYPES = [
  'appointment.booked',
  'appointment.status_changed',
  'prescription.issued',
] as const

export type WebhookEventType = (typeof WEBHOOK_EVENT_TYPES)[number]

export interface WebhookEndpoint {
  id: string
  clinic_id: string
  url: string
  event_types: string[]
  is_active: boolean
  secret_masked: string
  created_at: string
}

// Create-only shape — the only response that carries the full signing secret.
export interface WebhookEndpointCreated extends WebhookEndpoint {
  secret: string
}

export type WebhookDeliveryStatus = 'pending' | 'sent' | 'failed'

export interface WebhookDelivery {
  id: string
  endpoint_id: string
  event_type: string
  payload: Record<string, unknown>
  status: WebhookDeliveryStatus
  attempts: number
  last_error: string | null
  created_at: string
  delivered_at: string | null
}

export interface WebhookDeliveryList {
  data: WebhookDelivery[]
  total: number
  page: number
  limit: number
  totalPages: number
}

export interface RedeliverFailedResponse {
  redelivered: number
  delivery_ids: string[]
}

export async function listWebhookEndpoints(clinicId: string): Promise<WebhookEndpoint[]> {
  const res = await api.get(`/api/v1/clinics/${clinicId}/webhooks`)
  return res.data.data ?? []
}

export async function createWebhookEndpoint(
  clinicId: string,
  data: { url: string; event_types: string[]; is_active?: boolean }
): Promise<WebhookEndpointCreated> {
  const res = await api.post(`/api/v1/clinics/${clinicId}/webhooks`, data)
  return res.data
}

export async function updateWebhookEndpoint(
  clinicId: string,
  endpointId: string,
  data: Partial<{ url: string; event_types: string[]; is_active: boolean }>
): Promise<WebhookEndpoint> {
  const res = await api.patch(`/api/v1/clinics/${clinicId}/webhooks/${endpointId}`, data)
  return res.data
}

export async function deleteWebhookEndpoint(
  clinicId: string,
  endpointId: string
): Promise<void> {
  await api.delete(`/api/v1/clinics/${clinicId}/webhooks/${endpointId}`)
}

export async function listWebhookDeliveries(
  clinicId: string,
  params?: {
    status?: WebhookDeliveryStatus
    endpoint_id?: string
    page?: number
    limit?: number
  }
): Promise<WebhookDeliveryList> {
  const res = await api.get(`/api/v1/clinics/${clinicId}/webhooks/deliveries`, { params })
  return res.data
}

export async function redeliverWebhookDelivery(
  clinicId: string,
  deliveryId: string
): Promise<WebhookDelivery> {
  const res = await api.post(
    `/api/v1/clinics/${clinicId}/webhooks/deliveries/${deliveryId}/redeliver`
  )
  return res.data
}

export async function redeliverFailedDeliveries(
  clinicId: string,
  endpointId: string
): Promise<RedeliverFailedResponse> {
  const res = await api.post(
    `/api/v1/clinics/${clinicId}/webhooks/${endpointId}/redeliver-failed`
  )
  return res.data
}

/**
 * Generated-contract API helpers (proof of concept).
 *
 * These helpers derive their types from `schema.d.ts`, which is generated
 * from the backend's OpenAPI spec — so if the backend changes a response
 * shape or parameter name, the type error surfaces HERE at compile time,
 * not at runtime in production.
 *
 * Migration pattern for existing modules in this directory:
 *   1. Delete the hand-written interface (e.g. `NotificationsListResponse`).
 *   2. Alias the generated type: `type X = ResponseBody<"/api/v1/...", "get">`
 *      or use `components["schemas"]["X"]` directly.
 *   3. Keep the axios call — only the annotations change.
 *
 * Regenerate after backend contract changes:
 *   cd backend && python scripts/export_openapi.py
 *   cd frontend && npm run gen:api-types
 */

import api from "../api";
import type { components, paths } from "./schema";

// ---------------------------------------------------------------------------
// Type-level plumbing — extract request/response/query shapes from the spec.
// ---------------------------------------------------------------------------

/** JSON body of the 200 response for `paths[P][M]`. */
export type ResponseBody<
  P extends keyof paths,
  M extends keyof paths[P],
> = paths[P][M] extends {
  responses: { 200: { content: { "application/json": infer B } } };
}
  ? B
  : never;

/** JSON request body for `paths[P][M]` (`never` when the op takes no body). */
export type RequestBody<
  P extends keyof paths,
  M extends keyof paths[P],
> = paths[P][M] extends {
  requestBody: { content: { "application/json": infer B } };
}
  ? B
  : never;

/** Query parameters for `paths[P][M]` (`never` when the op takes none). */
export type QueryParams<
  P extends keyof paths,
  M extends keyof paths[P],
> = paths[P][M] extends { parameters: { query?: infer Q } } ? Q : never;

/** Direct access to generated component schemas (request/response models). */
export type Schema<Name extends keyof components["schemas"]> =
  components["schemas"][Name];

// ---------------------------------------------------------------------------
// POC endpoints — three representative call shapes.
// ---------------------------------------------------------------------------

export type MeResponse = ResponseBody<"/api/v1/auth/me", "get">;

/** GET /api/v1/auth/me — no params, response_model-backed response. */
export async function getMeTyped(): Promise<MeResponse> {
  const { data } = await api.get<MeResponse>("/api/v1/auth/me");
  return data;
}

export type Notification = Schema<"NotificationResponse">;
export type NotificationListResponse = ResponseBody<
  "/api/v1/notifications",
  "get"
>;
export type NotificationListParams = QueryParams<
  "/api/v1/notifications",
  "get"
>;

/** GET /api/v1/notifications — query params typed from the spec. */
export async function getNotificationsTyped(
  params?: NotificationListParams,
): Promise<NotificationListResponse> {
  const { data } = await api.get<NotificationListResponse>(
    "/api/v1/notifications",
    { params },
  );
  return data;
}

/** POST /api/v1/notifications/{id}/read — path param + typed response. */
export async function markNotificationReadTyped(
  notificationId: string,
): Promise<Notification> {
  const { data } = await api.post<Notification>(
    `/api/v1/notifications/${notificationId}/read`,
  );
  return data;
}

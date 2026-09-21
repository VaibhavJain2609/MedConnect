/**
 * Shared locations of the saved Keycloak sessions written by the
 * *.setup.ts files and consumed by authenticated specs via
 * `test.use({ storageState })`.
 *
 * Each constant lives in its own module-level export on purpose: importing
 * a `*.setup.ts` file directly would re-register its setup test inside
 * whatever spec imported it.
 *
 *   authFile       — generic "test user" session (E2E_TEST_*), written by
 *                    auth.setup.ts; assumed to be a patient account
 *   doctorAuthFile — doctor session (E2E_DOCTOR_*), auth.doctor.setup.ts
 *   adminAuthFile  — admin session (E2E_ADMIN_*), auth.admin.setup.ts
 */
export const authFile = "e2e/.auth/user.json";
export const doctorAuthFile = "e2e/.auth/doctor.json";
export const adminAuthFile = "e2e/.auth/admin.json";

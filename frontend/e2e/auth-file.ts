/**
 * Shared location of the saved Keycloak session written by auth.setup.ts
 * and consumed by authenticated specs via `test.use({ storageState })`.
 *
 * Kept in its own module on purpose: importing `auth.setup.ts` directly
 * would re-register its setup test inside whatever spec imported it.
 */
export const authFile = "e2e/.auth/user.json";

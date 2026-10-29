/**
 * Typed client for the public API. `schema.d.ts` is GENERATED from openapi.json (pnpm --filter @lozhka/api-client refresh);
 * never edit it by hand. Mutating calls carry the CSRF token the API hands out at /auth/csrf.
 */
import createClient, { type Middleware } from "openapi-fetch";
import type { components, paths } from "./schema";

export type { components, paths };
export type Schemas = components["schemas"];

let csrfToken: string | null = null;

async function ensureCsrf(baseUrl: string): Promise<string> {
  if (csrfToken) return csrfToken;
  const res = await fetch(`${baseUrl}/api/v1/auth/csrf`, { credentials: "include" });
  csrfToken = ((await res.json()) as { csrf: string }).csrf;
  return csrfToken;
}

/** Call after login/logout/register: Django rotates the CSRF token when the session changes. */
export function resetCsrf(): void {
  csrfToken = null;
}

export function createApi(baseUrl = "") {
  const client = createClient<paths>({ baseUrl, credentials: "include" });
  const csrf: Middleware = {
    async onRequest({ request }) {
      if (!["GET", "HEAD", "OPTIONS"].includes(request.method)) {
        request.headers.set("X-CSRFToken", await ensureCsrf(baseUrl));
      }
      return request;
    },
  };
  client.use(csrf);
  return client;
}

/** The API answers errors as {code, detail, extra}. */
export type ApiProblem = { code: string; detail?: string; extra?: Record<string, unknown> };
export function problemOf(error: unknown): ApiProblem {
  if (error && typeof error === "object" && "code" in error) return error as ApiProblem;
  return { code: "unknown" };
}

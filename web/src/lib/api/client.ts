import createClient, { type Middleware } from "openapi-fetch";
import type { components, paths } from "./schema";

export type Schemas = components["schemas"];

let csrfToken: string | null = null;

/** Set from GET /api/v1/me; sent back as X-CSRF-Token on every state-changing request. */
export function setCsrfToken(token: string | null) {
  csrfToken = token;
}

export function csrfHeaders(): Record<string, string> {
  return csrfToken ? { "X-CSRF-Token": csrfToken } : {};
}

const csrf: Middleware = {
  onRequest({ request }) {
    if (request.method !== "GET" && request.method !== "HEAD" && csrfToken) {
      request.headers.set("X-CSRF-Token", csrfToken);
    }
    return request;
  },
};

/** Typed API client; paths and payloads come from the generated OpenAPI schema (`npm run gen:api`). */
export const api = createClient<paths>({ baseUrl: "/", credentials: "same-origin" });
api.use(csrf);

/** FastAPI error bodies are `{detail: string}` or `{detail: [{msg}]}` (validation). */
export function errorMessage(error: unknown, fallback = "Có lỗi xảy ra, thử lại sau."): string {
  const detail = (error as { detail?: unknown } | undefined)?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length) {
    return detail.map((d: { msg?: string; loc?: unknown[] }) => `${d.loc?.at(-1) ?? ""}: ${d.msg ?? ""}`).join("; ");
  }
  return fallback;
}

import createClient from "openapi-fetch";
import type { paths } from "./schema";

/** Typed API client; paths and payloads come from the generated OpenAPI schema (`npm run gen:api`). */
export const api = createClient<paths>({ baseUrl: "/" });

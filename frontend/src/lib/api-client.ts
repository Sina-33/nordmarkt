import type { ApiError } from "./types";

/**
 * Browser-side API client.
 *
 * Kept apart from `api.ts` on purpose: that module reaches for `next/headers`,
 * which only exists on the server. Importing it from a client component pulls
 * the server-only module into the browser bundle and the build fails, so the
 * two halves cannot share a file.
 */
const PUBLIC = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export class ApiRequestError extends Error {
  constructor(
    readonly status: number,
    readonly body: ApiError | null
  ) {
    super(body?.error.detail ?? `API request failed with ${status}`);
    this.name = "ApiRequestError";
  }

  /** Translation key so the UI renders the message in the shopper's language. */
  get messageKey(): string {
    return this.body?.error.message_key ?? "errors.generic";
  }
}

export async function browserFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const locale =
    typeof document !== "undefined" ? document.documentElement.lang || "sv" : "sv";

  const response = await fetch(`${PUBLIC}${path}`, {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", "X-Locale": locale, ...init?.headers }
  });

  if (!response.ok) {
    let body: ApiError | null = null;
    try {
      body = (await response.json()) as ApiError;
    } catch {
      body = null;
    }
    throw new ApiRequestError(response.status, body);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

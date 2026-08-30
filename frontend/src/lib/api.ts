import { cookies, headers } from "next/headers";
import type { ApiError } from "./types";

/**
 * Server-side API client.
 *
 * Two base URLs on purpose: inside Docker the browser cannot resolve `api`,
 * and outside it the container cannot resolve `localhost`. Server components
 * use the internal name and skip a hop through the public ingress.
 */
const INTERNAL = process.env.INTERNAL_API_URL ?? "http://localhost:8000/api/v1";
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

type FetchOptions = RequestInit & {
  locale: string;
  /** Seconds. Omit for uncached (personalised) requests. */
  revalidate?: number;
  tags?: string[];
};

export async function apiFetch<T>(path: string, options: FetchOptions): Promise<T> {
  const { locale, revalidate, tags, ...init } = options;
  const cookieStore = await cookies();
  const cartCookie = cookieStore.get("nm_cart");

  const response = await fetch(`${INTERNAL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-Locale": locale,
      ...(cartCookie ? { Cookie: `nm_cart=${cartCookie.value}` } : {}),
      ...init.headers
    },
    // Catalogue reads are shared and cacheable; anything carrying a cart or a
    // session must not be, or one shopper is served another's basket.
    cache: revalidate === undefined ? "no-store" : undefined,
    next: revalidate === undefined ? undefined : { revalidate, tags }
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

/** Browser-side client used by interactive components. */
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

export async function requestOrigin(): Promise<string> {
  const h = await headers();
  return h.get("origin") ?? "http://localhost:3000";
}

import { cookies, headers } from "next/headers";
import { ApiRequestError } from "./api-client";
import type { ApiError } from "./types";

export { ApiRequestError } from "./api-client";

/**
 * Server-side API client.
 *
 * Two base URLs on purpose: inside Docker the browser cannot resolve `api`,
 * and outside it the container cannot resolve `localhost`. Server components
 * use the internal name here and skip a hop through the public ingress; the
 * public one lives in `api-client.ts` with the browser half.
 */
const INTERNAL = process.env.INTERNAL_API_URL ?? "http://localhost:8000/api/v1";

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

export async function requestOrigin(): Promise<string> {
  const h = await headers();
  return h.get("origin") ?? "http://localhost:3000";
}

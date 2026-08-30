import { apiFetch } from "./api";
import type { Category, ProductDetail, ProductList } from "./types";

export type ListParams = {
  q?: string;
  category?: string;
  brand?: string[];
  sort?: string;
  minPrice?: number;
  maxPrice?: number;
  cursor?: string;
  limit?: number;
};

function toQuery(params: ListParams): string {
  const search = new URLSearchParams();
  if (params.q) search.set("q", params.q);
  if (params.category) search.set("category", params.category);
  if (params.sort) search.set("sort", params.sort);
  if (params.cursor) search.set("cursor", params.cursor);
  if (params.limit) search.set("limit", String(params.limit));
  if (params.minPrice !== undefined) search.set("min_price", String(params.minPrice));
  if (params.maxPrice !== undefined) search.set("max_price", String(params.maxPrice));
  for (const slug of params.brand ?? []) search.append("brand", slug);
  const query = search.toString();
  return query ? `?${query}` : "";
}

export function listProducts(locale: string, params: ListParams = {}) {
  return apiFetch<ProductList>(`/catalog/products${toQuery(params)}`, {
    locale,
    revalidate: 60,
    tags: ["catalog"]
  });
}

export function getProduct(locale: string, slug: string) {
  return apiFetch<ProductDetail>(`/catalog/products/${slug}`, {
    locale,
    revalidate: 30,
    tags: ["catalog", `product:${slug}`]
  });
}

export function getCategories(locale: string) {
  return apiFetch<Category[]>("/catalog/categories", {
    locale,
    revalidate: 600,
    tags: ["catalog"]
  });
}

export type Money = {
  amount: string;
  minor_units: number;
  currency: string;
  /** Server-rendered, locale-correct string. The client never re-formats it. */
  formatted: string;
};

export type Image = {
  url: string;
  alt: string;
  width?: number | null;
  height?: number | null;
};

export type Variant = {
  id: string;
  sku: string;
  options: Record<string, string>;
  price: Money;
  compare_at?: Money | null;
  is_active: boolean;
  sellable?: number | null;
};

export type ProductSummary = {
  id: string;
  slug: string;
  title: string;
  brand: string | null;
  price_from: Money;
  compare_at: Money | null;
  image: Image | null;
  rating_average: string;
  rating_count: number;
  tags: string[];
};

export type ProductDetail = ProductSummary & {
  description: string;
  highlights: string[];
  category_path: string;
  images: Image[];
  variants: Variant[];
};

export type BrandFacet = { slug: string; name: string; count: number };

export type ProductList = {
  data: ProductSummary[];
  facets: { brands: BrandFacet[]; price_min: Money; price_max: Money };
  meta: { next_cursor: string | null; total: number; locale: string };
};

export type Category = {
  slug: string;
  path: string;
  name: string;
  depth: number;
  children: Category[];
};

export type CartLine = {
  variant_id: string;
  sku: string;
  title: string;
  options: Record<string, string>;
  image_url: string | null;
  quantity: number;
  unit_price: Money;
  line_total: Money;
  price_changed: boolean;
};

export type Cart = {
  id: string;
  currency: string;
  item_count: number;
  lines: CartLine[];
  subtotal: Money;
  vat_included: Money;
  shipping: Money;
  total: Money;
  free_shipping_remaining: Money | null;
};

export type ApiError = {
  error: { code: string; message_key: string; detail: string; context: Record<string, unknown> };
  request_id: string | null;
};

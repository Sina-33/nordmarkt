import { ProductCard } from "./product-card";
import type { ProductSummary } from "@/lib/types";

export function ProductGrid({ products }: { products: ProductSummary[] }) {
  return (
    <ul className="grid grid-cols-2 gap-x-5 gap-y-10 lg:grid-cols-4">
      {products.map((product, index) => (
        <li key={product.id}>
          {/* Only the first row is eagerly loaded; below the fold, priority
              hints compete with the LCP image rather than helping it. */}
          <ProductCard product={product} priority={index < 4} />
        </li>
      ))}
    </ul>
  );
}

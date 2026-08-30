"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useOptimistic,
  useState,
  useTransition
} from "react";
import { ApiRequestError, browserFetch } from "@/lib/api-client";
import type { Cart } from "@/lib/types";

type CartContextValue = {
  cart: Cart | null;
  itemCount: number;
  pending: boolean;
  lastErrorKey: string | null;
  refresh: () => Promise<void>;
  addItem: (variantId: string, quantity?: number) => Promise<void>;
  setQuantity: (variantId: string, quantity: number) => Promise<void>;
};

const CartContext = createContext<CartContextValue | null>(null);

export function CartProvider({ children }: { children: React.ReactNode }) {
  const [cart, setCart] = useState<Cart | null>(null);
  const [lastErrorKey, setLastErrorKey] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  // The badge updates the instant the button is pressed; the server response
  // replaces the guess when it lands. A cart badge that waits on a round trip
  // is the most-noticed latency in a storefront.
  const [optimisticCount, addOptimisticCount] = useOptimistic(
    cart?.item_count ?? 0,
    (current: number, delta: number) => Math.max(0, current + delta)
  );

  const run = useCallback(async (work: () => Promise<Cart>) => {
    setLastErrorKey(null);
    try {
      setCart(await work());
    } catch (error) {
      if (error instanceof ApiRequestError) setLastErrorKey(error.messageKey);
      else setLastErrorKey("errors.generic");
      // Re-sync so the optimistic guess cannot linger after a failure.
      try {
        setCart(await browserFetch<Cart>("/cart"));
      } catch {
        /* leave the previous state in place */
      }
      throw error;
    }
  }, []);

  const refresh = useCallback(async () => {
    await run(() => browserFetch<Cart>("/cart"));
  }, [run]);

  const addItem = useCallback(
    async (variantId: string, quantity = 1) => {
      startTransition(() => addOptimisticCount(quantity));
      await run(() =>
        browserFetch<Cart>("/cart/items", {
          method: "POST",
          body: JSON.stringify({ variant_id: variantId, quantity })
        })
      );
    },
    [addOptimisticCount, run]
  );

  const setQuantity = useCallback(
    async (variantId: string, quantity: number) => {
      const current = cart?.lines.find((l) => l.variant_id === variantId)?.quantity ?? 0;
      startTransition(() => addOptimisticCount(quantity - current));
      await run(() =>
        browserFetch<Cart>(`/cart/items/${variantId}`, {
          method: "PATCH",
          body: JSON.stringify({ quantity })
        })
      );
    },
    [addOptimisticCount, cart, run]
  );

  const value = useMemo(
    () => ({
      cart,
      itemCount: optimisticCount,
      pending,
      lastErrorKey,
      refresh,
      addItem,
      setQuantity
    }),
    [cart, optimisticCount, pending, lastErrorKey, refresh, addItem, setQuantity]
  );

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

export function useCart(): CartContextValue {
  const context = useContext(CartContext);
  if (!context) throw new Error("useCart must be used inside CartProvider");
  return context;
}

"use client";

import { useRouter } from "@/i18n/routing";
import { useState } from "react";

export function SearchField({ placeholder }: { placeholder: string }) {
  const router = useRouter();
  const [value, setValue] = useState("");

  return (
    <div className="flex">
      <input
        type="search"
        value={value}
        placeholder={placeholder}
        aria-label={placeholder}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && value.trim()) {
            router.push(`/search?q=${encodeURIComponent(value.trim())}`);
          }
        }}
        className="w-full border border-[var(--color-rule)] bg-[var(--color-paper-raised)] px-3 py-2 text-sm placeholder:text-[var(--color-ink-muted)]"
      />
    </div>
  );
}

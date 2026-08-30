"use client";

export default function ErrorBoundary({
  error,
  reset
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="mx-auto max-w-[40rem] px-4 py-28 text-center">
      <h1 className="font-[family-name:var(--font-display)] text-3xl font-semibold tracking-[-0.02em]">
        Något gick fel hos oss.
      </h1>
      <p className="mt-3 text-[var(--color-ink-muted)]">
        Försök igen. Om det upprepas, uppge referensen nedan när du kontaktar oss.
      </p>
      {error.digest ? (
        <p className="mt-4 font-mono text-xs uppercase tracking-[0.08em]">
          Ref {error.digest}
        </p>
      ) : null}
      <button
        type="button"
        onClick={reset}
        className="mt-7 border border-[var(--color-ink)] px-7 py-3 hover:bg-[var(--color-sand)]"
      >
        Försök igen
      </button>
    </div>
  );
}

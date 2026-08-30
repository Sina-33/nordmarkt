import { Link } from "@/i18n/routing";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-[40rem] px-4 py-28 text-center">
      <p className="font-mono text-[0.6875rem] uppercase tracking-[0.12em] text-[var(--color-ink-muted)]">
        404
      </p>
      <h1 className="mt-3 font-[family-name:var(--font-display)] text-3xl font-semibold tracking-[-0.02em]">
        Sidan finns inte kvar.
      </h1>
      <p className="mt-3 text-[var(--color-ink-muted)]">
        Artikeln kan ha utgått ur sortimentet. Sortimentet står kvar där det stod.
      </p>
      <Link
        href="/"
        className="mt-7 inline-block bg-[var(--color-ink)] px-7 py-3 text-[var(--color-paper)]"
      >
        Till startsidan
      </Link>
    </div>
  );
}

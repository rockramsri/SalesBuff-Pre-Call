/** SalesBuff brand mark — people + chat bubbles; colors follow the active theme via CSS vars. */
export function BrandMark({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 48 48" role="img" aria-label="SalesBuff" fill="none">
      <rect width="48" height="48" rx="12" fill="var(--brand-tile, #141414)" />
      <path
        d="M11 9h12a4 4 0 0 1 4 4v3a4 4 0 0 1-4 4h-2.5l-3.2 3v-3H11a4 4 0 0 1-4-4v-3a4 4 0 0 1 4-4z"
        fill="var(--salesbuff-yellow)"
      />
      <circle cx="12.6" cy="14.5" r="1.15" fill="var(--brand-ink, #141414)" />
      <circle cx="16.8" cy="14.5" r="1.15" fill="var(--brand-ink, #141414)" />
      <circle cx="21" cy="14.5" r="1.15" fill="var(--brand-ink, #141414)" />
      <path
        d="M29 12h7a3 3 0 0 1 3 3v2.5a3 3 0 0 1-3 3h-.5v2.2l-2.4-2.2H29a3 3 0 0 1-3-3V15a3 3 0 0 1 3-3z"
        fill="var(--brand-figure-alt, #ffffff)"
      />
      <circle cx="31" cy="16.3" r="0.95" fill="var(--brand-ink, #141414)" />
      <circle cx="34.2" cy="16.3" r="0.95" fill="var(--brand-ink, #141414)" />
      <circle cx="13" cy="30" r="3.1" fill="var(--salesbuff-yellow)" />
      <path d="M8 41c0-5 10-5 10 0z" fill="var(--salesbuff-yellow)" />
      <circle cx="24" cy="29" r="3.6" fill="var(--brand-figure-mid, #ffffff)" />
      <path d="M18 41c0-5.8 12-5.8 12 0z" fill="var(--brand-figure-mid, #ffffff)" />
      <circle cx="35" cy="30" r="3.1" fill="var(--salesbuff-yellow)" />
      <path d="M30 41c0-5 10-5 10 0z" fill="var(--salesbuff-yellow)" />
    </svg>
  );
}

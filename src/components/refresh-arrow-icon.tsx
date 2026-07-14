export function RefreshArrowIcon({ className = "" }: { className?: string }) {
  return (
    <svg
      className={`refresh-arrow-icon ${className}`.trim()}
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <path d="M19 8a7.5 7.5 0 1 0 .55 7" />
      <path d="M19 3v5h-5" />
    </svg>
  );
}

export function Logo({ size = 28 }: { size?: number }) {
  return (
    <span className="flex items-center gap-2">
      <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden>
        <rect width="32" height="32" rx="8" fill="#121A2B" stroke="#24314A" />
        <circle cx="16" cy="16" r="9" fill="none" stroke="#6275FF" strokeWidth="2.5" />
        <path d="M16 7a9 9 0 0 1 9 9h-9z" fill="#F26B75" />
      </svg>
      <span className="text-[15px] font-semibold tracking-tight">Blindspot <span className="text-accent">AI</span></span>
    </span>
  );
}

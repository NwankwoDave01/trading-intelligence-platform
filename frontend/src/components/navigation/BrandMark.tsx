export function BrandMark({ collapsed = false }: { collapsed?: boolean }) {
  return (
    <div className="flex items-center gap-3">
      <svg
        width="32"
        height="32"
        viewBox="0 0 32 32"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="shrink-0"
        aria-hidden="true"
      >
        <rect x="1" y="1" width="30" height="30" rx="8" fill="#111A25" stroke="rgba(241,243,245,0.14)" />
        <path
          d="M7 21L13 15L17.5 18.5L25 10"
          stroke="#52D6A0"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <circle cx="25" cy="10" r="2.25" fill="#8B7CFF" />
        <path d="M7 24H25" stroke="rgba(241,243,245,0.16)" strokeWidth="1" strokeLinecap="round" />
      </svg>
      {!collapsed && (
        <div className="min-w-0">
          <div className="font-display truncate text-sm font-semibold tracking-tight text-[#F1F3F5]">
            Trading Intelligence
          </div>
          <div className="text-[10px] font-medium tracking-[0.18em] text-[#8B9BB0] uppercase">
            Research Desk
          </div>
        </div>
      )}
    </div>
  );
}

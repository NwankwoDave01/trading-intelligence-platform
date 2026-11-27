import React from "react";
import { AlertTriangle, Inbox, RefreshCw, X } from "lucide-react";

export function SectionHeader({
  index,
  eyebrow,
  title,
  subtitle,
  action,
}: {
  index?: string;
  eyebrow: string;
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-4 border-b border-white/[0.08] pb-6 md:flex-row md:items-end md:justify-between">
      <div className="space-y-2">
        <div className="flex items-center gap-2.5 text-[11px] font-medium tracking-[0.18em] text-[#8B9BB0] uppercase">
          {index && <span className="font-mono-num text-[#8B7CFF]">{index}</span>}
          {index && <span className="h-px w-5 bg-white/15" />}
          <span>{eyebrow}</span>
        </div>
        <h1 className="font-display text-3xl font-semibold tracking-tight text-[#F1F3F5] sm:text-4xl">
          {title}
        </h1>
        {subtitle && <p className="max-w-2xl text-sm leading-relaxed text-[#8B9BB0]">{subtitle}</p>}
      </div>
      {action && <div className="flex flex-wrap items-center gap-2.5">{action}</div>}
    </div>
  );
}

export function Surface({
  children,
  className = "",
  elevated = false,
}: {
  children: React.ReactNode;
  className?: string;
  elevated?: boolean;
}) {
  return (
    <div
      className={`rounded-xl border border-white/[0.08] ${
        elevated ? "bg-[#172431]/90" : "bg-[#111A25]/90"
      } ${className}`}
    >
      {children}
    </div>
  );
}

export type BadgeTone = "mint" | "bearish" | "amber" | "violet" | "neutral";

const TONE_MAP: Record<BadgeTone, string> = {
  mint: "border-[#52D6A0]/30 bg-[#52D6A0]/10 text-[#52D6A0]",
  bearish: "border-[#F06470]/30 bg-[#F06470]/10 text-[#F06470]",
  amber: "border-[#F5B74F]/30 bg-[#F5B74F]/10 text-[#F5B74F]",
  violet: "border-[#8B7CFF]/30 bg-[#8B7CFF]/10 text-[#8B7CFF]",
  neutral: "border-white/15 bg-white/[0.04] text-[#8B9BB0]",
};

export function StatusBadge({
  children,
  tone = "neutral",
  className = "",
}: {
  children: React.ReactNode;
  tone?: BadgeTone;
  className?: string;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-md border px-2.5 py-0.5 text-[11px] font-medium tracking-wider uppercase ${TONE_MAP[tone]} ${className}`}
    >
      {children}
    </span>
  );
}

export function MetricBlock({
  label,
  value,
  subvalue,
  tone = "neutral",
  className = "",
}: {
  label: string;
  value: string;
  subvalue?: string;
  tone?: "neutral" | "mint" | "bearish" | "violet" | "amber";
  className?: string;
}) {
  const valueColor =
    tone === "mint"
      ? "text-[#52D6A0]"
      : tone === "bearish"
      ? "text-[#F06470]"
      : tone === "violet"
      ? "text-[#8B7CFF]"
      : tone === "amber"
      ? "text-[#F5B74F]"
      : "text-[#F1F3F5]";

  return (
    <div className={`space-y-1 ${className}`}>
      <div className="text-[11px] font-medium tracking-[0.14em] text-[#8B9BB0] uppercase">{label}</div>
      <div className={`font-mono-num text-xl font-semibold tracking-tight sm:text-2xl ${valueColor}`}>
        {value}
      </div>
      {subvalue && <div className="font-mono-num text-xs text-[#8B9BB0]">{subvalue}</div>}
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
  icon,
}: {
  title: string;
  description: string;
  action?: React.ReactNode;
  icon?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-white/[0.12] bg-[#111A25]/50 px-6 py-12 text-center">
      <div className="mb-3 flex h-11 w-11 items-center justify-center rounded-lg border border-white/10 bg-[#172431] text-[#8B9BB0]">
        {icon ?? <Inbox className="h-5 w-5" />}
      </div>
      <h3 className="font-display text-base font-medium text-[#F1F3F5]">{title}</h3>
      <p className="mt-1.5 max-w-md text-sm text-[#8B9BB0]">{description}</p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function ErrorState({
  title = "Unable to load data",
  message,
  onRetry,
}: {
  title?: string;
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="flex flex-col items-start justify-between gap-4 rounded-xl border border-[#F06470]/30 bg-[#F06470]/[0.06] p-5 sm:flex-row sm:items-center">
      <div className="flex items-start gap-3">
        <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-[#F06470]" />
        <div>
          <h3 className="font-display text-sm font-semibold text-[#F1F3F5]">{title}</h3>
          <p className="mt-1 text-xs leading-relaxed text-[#8B9BB0]">{message}</p>
        </div>
      </div>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-white/15 bg-[#172431] px-3 py-1.5 text-xs font-medium text-[#F1F3F5] transition hover:border-white/30"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Retry
        </button>
      )}
    </div>
  );
}

export function SkeletonBlock({ className = "h-24" }: { className?: string }) {
  return <div className={`animate-pulse rounded-xl bg-[#172431]/60 ${className}`} />;
}

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = "Confirm",
  confirmTone = "mint",
  isPending = false,
  onConfirm,
  onCancel,
  children,
}: {
  open: boolean;
  title: string;
  description: string;
  confirmLabel?: string;
  confirmTone?: "mint" | "bearish";
  isPending?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  children?: React.ReactNode;
}) {
  if (!open) return null;

  const confirmClasses =
    confirmTone === "bearish"
      ? "bg-[#F06470] text-[#090D13] hover:bg-[#F06470]/90"
      : "bg-[#52D6A0] text-[#090D13] hover:bg-[#52D6A0]/90";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-xl border border-white/15 bg-[#111A25] p-6 shadow-2xl">
        <div className="flex items-start justify-between gap-4">
          <div>
            <StatusBadge tone="amber" className="mb-2">
              Paper Trading Simulation
            </StatusBadge>
            <h3 className="font-display text-lg font-semibold text-[#F1F3F5]">{title}</h3>
          </div>
          <button
            type="button"
            onClick={onCancel}
            className="rounded-lg p-1 text-[#8B9BB0] transition hover:bg-white/5 hover:text-[#F1F3F5]"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <p className="mt-2 text-sm text-[#8B9BB0]">{description}</p>
        {children && <div className="mt-4">{children}</div>}
        <div className="mt-6 flex items-center justify-end gap-3">
          <button
            type="button"
            onClick={onCancel}
            disabled={isPending}
            className="rounded-lg border border-white/15 px-4 py-2 text-xs font-medium text-[#F1F3F5] transition hover:bg-white/5 disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={isPending}
            className={`rounded-lg px-4 py-2 text-xs font-semibold transition disabled:opacity-50 ${confirmClasses}`}
          >
            {isPending ? "Executing..." : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

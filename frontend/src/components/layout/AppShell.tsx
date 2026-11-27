import { useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import {
  Activity,
  BookOpen,
  CandlestickChart,
  ChevronLeft,
  ChevronRight,
  LayoutGrid,
  Menu,
  Radio,
  ShieldCheck,
  Wallet,
  X,
} from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { BrandMark } from "@/components/navigation/BrandMark";
import { StatusBadge } from "@/components/ui/Primitives";
import { useMarketContext } from "@/hooks/useMarketContext";

const NAV_ITEMS = [
  { to: "/overview", label: "Overview", index: "01", icon: LayoutGrid },
  { to: "/market-analysis", label: "Market Analysis", index: "02", icon: CandlestickChart },
  { to: "/signal-intelligence", label: "Signal Intelligence", index: "03", icon: Activity },
  { to: "/risk-management", label: "Risk Management", index: "04", icon: ShieldCheck },
  { to: "/paper-trading", label: "Paper Trading", index: "05", icon: Wallet },
  { to: "/trade-journal", label: "Trade Journal", index: "06", icon: BookOpen },
];

export function AppShell() {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();
  const { provider, providerLoading, providerError, symbol, setSymbol, timeframe, setTimeframe, supportedTimeframes, watchlist } =
    useMarketContext();

  const renderNavLinks = (isCollapsed: boolean, onNavigate?: () => void) => (
    <nav className="flex flex-1 flex-col gap-1 px-3 py-4">
      {NAV_ITEMS.map((item) => {
        const Icon = item.icon;
        return (
          <NavLink
            key={item.to}
            to={item.to}
            end
            onClick={onNavigate}
            className={({ isActive }) =>
              `group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                isActive
                  ? "bg-[#172431] text-[#F1F3F5]"
                  : "text-[#8B9BB0] hover:bg-white/[0.04] hover:text-[#F1F3F5]"
              }`
            }
          >
            {({ isActive }) => (
              <>
                {isActive && (
                  <span className="absolute left-0 top-1.5 bottom-1.5 w-0.5 rounded-r bg-[#52D6A0]" />
                )}
                <Icon
                  className={`h-4 w-4 shrink-0 ${
                    isActive ? "text-[#52D6A0]" : "text-[#8B9BB0] group-hover:text-[#F1F3F5]"
                  }`}
                />
                {!isCollapsed && (
                  <>
                    <span className="flex-1 truncate">{item.label}</span>
                    <span className="font-mono-num text-[10px] text-[#8B9BB0]/60">{item.index}</span>
                  </>
                )}
              </>
            )}
          </NavLink>
        );
      })}
    </nav>
  );

  return (
    <div className="min-h-screen bg-[#090D13] bg-studio-grid text-[#F1F3F5] flex">
      {/* Desktop Sidebar */}
      <aside
        className={`hidden md:flex flex-col shrink-0 border-r border-white/[0.08] bg-[#090D13]/95 backdrop-blur-md transition-all duration-200 ${
          collapsed ? "w-[72px]" : "w-[252px]"
        }`}
      >
        <div className="flex h-16 items-center justify-between border-b border-white/[0.08] px-4">
          <BrandMark collapsed={collapsed} />
          <button
            type="button"
            onClick={() => setCollapsed((c) => !c)}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            className="rounded-md p-1.5 text-[#8B9BB0] transition hover:bg-white/[0.06] hover:text-[#F1F3F5]"
          >
            {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
          </button>
        </div>

        {renderNavLinks(collapsed)}

        {!collapsed && (
          <div className="m-3 rounded-xl border border-white/[0.08] bg-[#111A25] p-3.5">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-medium tracking-[0.16em] text-[#8B9BB0] uppercase">
                Environment
              </span>
              <StatusBadge tone="amber">Paper</StatusBadge>
            </div>
            <p className="mt-2 text-xs leading-relaxed text-[#8B9BB0]">
              Public market feeds only. No live exchange orders or private credentials.
            </p>
          </div>
        )}
      </aside>

      {/* Mobile Drawer */}
      <AnimatePresence>
        {mobileOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex md:hidden"
          >
            <div className="fixed inset-0 bg-black/70 backdrop-blur-sm" onClick={() => setMobileOpen(false)} />
            <motion.aside
              initial={{ x: -260 }}
              animate={{ x: 0 }}
              exit={{ x: -260 }}
              transition={{ type: "spring", stiffness: 320, damping: 32 }}
              className="relative z-10 flex w-[264px] flex-col border-r border-white/[0.08] bg-[#090D13]"
            >
              <div className="flex h-16 items-center justify-between border-b border-white/[0.08] px-4">
                <BrandMark />
                <button
                  type="button"
                  onClick={() => setMobileOpen(false)}
                  className="rounded-md p-1.5 text-[#8B9BB0] hover:bg-white/[0.06] hover:text-[#F1F3F5]"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
              {renderNavLinks(false, () => setMobileOpen(false))}
            </motion.aside>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Main Column */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Top Bar */}
        <header className="sticky top-0 z-30 flex h-16 items-center justify-between gap-3 border-b border-white/[0.08] bg-[#090D13]/90 px-4 backdrop-blur-md sm:px-6 lg:px-8">
          <div className="flex items-center gap-3 min-w-0">
            <button
              type="button"
              onClick={() => setMobileOpen(true)}
              aria-label="Open navigation"
              className="rounded-lg border border-white/[0.08] bg-[#111A25] p-2 text-[#8B9BB0] hover:text-[#F1F3F5] md:hidden"
            >
              <Menu className="h-4 w-4" />
            </button>

            {/* Market & Timeframe Quick Controls */}
            <div className="flex items-center gap-2">
              <select
                value={symbol}
                onChange={(e) => setSymbol(e.target.value)}
                aria-label="Select market pair"
                className="font-mono-num rounded-lg border border-white/[0.1] bg-[#111A25] px-2.5 py-1.5 text-xs font-medium text-[#F1F3F5] outline-none focus:border-[#8B7CFF]"
              >
                {watchlist.map((pair) => (
                  <option key={pair} value={pair}>
                    {pair}
                  </option>
                ))}
              </select>

              <select
                value={timeframe}
                onChange={(e) => setTimeframe(e.target.value)}
                aria-label="Select timeframe"
                className="font-mono-num rounded-lg border border-white/[0.1] bg-[#111A25] px-2.5 py-1.5 text-xs font-medium text-[#F1F3F5] outline-none focus:border-[#8B7CFF]"
              >
                {supportedTimeframes.map((tf) => (
                  <option key={tf} value={tf}>
                    {tf}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="flex items-center gap-2.5">
            <StatusBadge
              tone={providerError ? "bearish" : providerLoading ? "neutral" : "mint"}
              className="hidden sm:inline-flex"
            >
              <Radio className="h-3 w-3" />
              {providerLoading
                ? "Connecting..."
                : providerError
                ? "Provider Offline"
                : `${provider?.exchange ?? "Exchange"} · ${provider?.status ?? "ready"}`}
            </StatusBadge>
            <StatusBadge tone="amber" className="hidden lg:inline-flex">
              Paper Trading
            </StatusBadge>
          </div>
        </header>

        {/* Page Content */}
        <main className="mx-auto w-full max-w-[1440px] flex-1 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <motion.div
            key={location.pathname}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.22, ease: "easeOut" }}
          >
            <Outlet />
          </motion.div>
        </main>
      </div>
    </div>
  );
}

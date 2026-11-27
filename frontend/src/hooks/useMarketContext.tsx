import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { tradingApi } from "@/services/trading-api";
import type { ProviderMetadata } from "@/types/api";

interface MarketContextValue {
  provider: ProviderMetadata | undefined;
  providerLoading: boolean;
  providerError: Error | null;
  symbol: string;
  setSymbol: (symbol: string) => void;
  timeframe: string;
  setTimeframe: (timeframe: string) => void;
  watchlist: string[];
  supportedTimeframes: string[];
  maxCandleLimit: number;
}

const MarketContext = createContext<MarketContextValue | null>(null);

export function MarketProvider({ children }: { children: React.ReactNode }) {
  const {
    data: provider,
    isLoading: providerLoading,
    error: providerError,
  } = useQuery({
    queryKey: ["provider"],
    queryFn: tradingApi.getProvider,
    staleTime: 60_000,
    retry: 1,
  });

  const [symbol, setSymbol] = useState<string>("");
  const [timeframe, setTimeframe] = useState<string>("1h");

  useEffect(() => {
    if (provider?.default_symbol && !symbol) {
      setSymbol(provider.default_symbol);
    }
    if (provider?.supported_timeframes?.length && !provider.supported_timeframes.includes(timeframe)) {
      setTimeframe(provider.supported_timeframes.includes("1h") ? "1h" : provider.supported_timeframes[0]);
    }
  }, [provider, symbol, timeframe]);

  const resolvedSymbol = symbol || provider?.default_symbol || "BTC/USD";

  const watchlist = useMemo(() => {
    const quote = resolvedSymbol.includes("/") ? resolvedSymbol.split("/")[1] : "USD";
    const basePairs = [`BTC/${quote}`, `ETH/${quote}`, `SOL/${quote}`, `AVAX/${quote}`];
    return basePairs.includes(resolvedSymbol) ? basePairs : [resolvedSymbol, ...basePairs.slice(0, 3)];
  }, [resolvedSymbol]);

  const value: MarketContextValue = {
    provider,
    providerLoading,
    providerError: providerError as Error | null,
    symbol: resolvedSymbol,
    setSymbol: (next) => setSymbol(next.trim().toUpperCase()),
    timeframe,
    setTimeframe,
    watchlist,
    supportedTimeframes: provider?.supported_timeframes ?? ["1m", "5m", "15m", "30m", "1h", "4h", "1d"],
    maxCandleLimit: provider?.max_candle_limit ?? 720,
  };

  return <MarketContext.Provider value={value}>{children}</MarketContext.Provider>;
}

export function useMarketContext() {
  const ctx = useContext(MarketContext);
  if (!ctx) throw new Error("useMarketContext must be used inside MarketProvider");
  return ctx;
}

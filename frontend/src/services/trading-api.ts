import { apiRequest } from "@/lib/api-client";
import type {
  AccountCreateRequest,
  CandlesResponse,
  ClosePositionRequest,
  HealthResponse,
  IndicatorResponse,
  MarketStructureResponse,
  MarkPriceRequest,
  OpenPositionRequest,
  PaperAccountSummary,
  PaperLedgerEntry,
  PaperPosition,
  ProviderMetadata,
  RiskPreviewRequest,
  RiskPreviewResponse,
  SignalResponse,
  TickerResponse,
} from "@/types/api";

function buildQuery(params: Record<string, string | number | undefined | null>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  }
  const str = search.toString();
  return str ? `?${str}` : "";
}

export const tradingApi = {
  getHealth: () => apiRequest<HealthResponse>("/health"),

  getProvider: () => apiRequest<ProviderMetadata>("/api/v1/market/provider"),

  getTicker: (symbol?: string) =>
    apiRequest<TickerResponse>(`/api/v1/market/ticker${buildQuery({ symbol })}`),

  getCandles: (params: { symbol?: string; timeframe?: string; limit?: number }) =>
    apiRequest<CandlesResponse>(`/api/v1/market/candles${buildQuery(params)}`),

  getIndicators: (params: { symbol?: string; timeframe?: string; limit?: number }) =>
    apiRequest<IndicatorResponse>(`/api/v1/analysis/indicators${buildQuery(params)}`),

  getMarketStructure: (params: {
    symbol?: string;
    timeframe?: string;
    limit?: number;
    left_bars?: number;
    right_bars?: number;
    break_buffer?: number;
    level_tolerance?: number;
  }) => apiRequest<MarketStructureResponse>(`/api/v1/analysis/market-structure${buildQuery(params)}`),

  getSignal: (params: { symbol?: string; timeframe?: string; limit?: number }) =>
    apiRequest<SignalResponse>(`/api/v1/analysis/signal${buildQuery(params)}`),

  previewRisk: (payload: RiskPreviewRequest) =>
    apiRequest<RiskPreviewResponse>("/api/v1/risk/preview", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  createPaperAccount: (payload: AccountCreateRequest) =>
    apiRequest<PaperAccountSummary>("/api/v1/paper/account", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  getPaperAccount: () => apiRequest<PaperAccountSummary>("/api/v1/paper/account"),

  previewPaperRisk: (payload: OpenPositionRequest) =>
    apiRequest<RiskPreviewResponse>("/api/v1/paper/risk-preview", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  openPaperPosition: (payload: OpenPositionRequest) =>
    apiRequest<PaperPosition>("/api/v1/paper/positions", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  listPaperPositions: () => apiRequest<PaperPosition[]>("/api/v1/paper/positions"),

  getPaperPosition: (positionId: string) =>
    apiRequest<PaperPosition>(`/api/v1/paper/positions/${encodeURIComponent(positionId)}`),

  markPaperPosition: (
    positionId: string,
    payload: MarkPriceRequest,
    candle?: { low?: string; high?: string }
  ) =>
    apiRequest<PaperPosition>(
      `/api/v1/paper/positions/${encodeURIComponent(positionId)}/mark${buildQuery({
        low: candle?.low,
        high: candle?.high,
      })}`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      }
    ),

  closePaperPosition: (positionId: string, payload: ClosePositionRequest) =>
    apiRequest<PaperPosition>(`/api/v1/paper/positions/${encodeURIComponent(positionId)}/close`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  getPaperHistory: () => apiRequest<PaperPosition[]>("/api/v1/paper/history"),

  getPaperPerformance: () => apiRequest<PaperAccountSummary>("/api/v1/paper/performance"),

  getPaperLedger: (positionId: string) =>
    apiRequest<PaperLedgerEntry[]>(`/api/v1/paper/positions/${encodeURIComponent(positionId)}/ledger`),
};

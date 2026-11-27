export interface HealthResponse {
  status: string;
}

export interface ProviderMetadata {
  exchange: string;
  status: string;
  default_symbol: string;
  supported_timeframes: string[];
  max_candle_limit: number;
  rate_limit_enabled: boolean;
  public_api_url?: string;
}

export interface TickerResponse {
  exchange: string;
  symbol: string;
  timestamp: string | null;
  last_price: number | null;
  bid: number | null;
  ask: number | null;
  high_24h: number | null;
  low_24h: number | null;
  volume_24h: number | null;
  price_change_percentage: number | null;
}

export interface Candle {
  timestamp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface CandlesResponse {
  exchange: string;
  symbol: string;
  timeframe: string;
  count: number;
  candles: Candle[];
}

export interface MACDValues {
  line: number | null;
  signal: number | null;
  histogram: number | null;
}

export interface BollingerBandValues {
  upper: number | null;
  middle: number | null;
  lower: number | null;
}

export interface LatestIndicators {
  sma_20: number | null;
  sma_50: number | null;
  ema_20: number | null;
  ema_50: number | null;
  rsi_14: number | null;
  macd: MACDValues;
  bollinger_bands: BollingerBandValues;
  atr_14: number | null;
}

export interface CandleIndicatorRow {
  timestamp: number;
  close: number;
  sma_20: number | null;
  sma_50: number | null;
  ema_20: number | null;
  ema_50: number | null;
  rsi_14: number | null;
  macd: MACDValues;
  bollinger_bands: BollingerBandValues;
  atr_14: number | null;
}

export interface IndicatorResponse {
  exchange: string;
  symbol: string;
  timeframe: string;
  candle_count: number;
  latest: LatestIndicators;
  series: CandleIndicatorRow[];
}

export type SwingClassification = "HH" | "HL" | "LH" | "LL";
export type TrendClassification = "bullish" | "bearish" | "ranging" | "undetermined";
export type BreakType = "BOS" | "CHoCH";
export type BreakDirection = "bullish" | "bearish";

export interface SwingPoint {
  id: string;
  swing_type: "high" | "low";
  timestamp: number;
  price: number;
  confirmation_candle_timestamp: number;
  available_at: number;
  confirmation_delay_bars: number;
  classification: SwingClassification | null;
  reference_swing_id: string | null;
}

export interface TrendState {
  classification: TrendClassification;
  as_of: number;
}

export interface BreakEvent {
  id: string;
  event_type: BreakType;
  direction: BreakDirection;
  broken_level: number;
  source_swing_id: string;
  source_swing_timestamp: number;
  confirmation_candle_timestamp: number;
  confirmation_close: number;
  available_at: number;
}

export interface PotentialBreak {
  id: string;
  event_type: BreakType;
  direction: BreakDirection;
  broken_level: number;
  source_swing_id: string;
  source_swing_timestamp: number;
  observation_candle_timestamp: number;
  observation_close: number;
  wick_extreme: number;
  available_at: number;
  status: "unconfirmed";
}

export interface StructureZone {
  zone_type: "support" | "resistance";
  lower_bound: number;
  upper_bound: number;
  midpoint: number;
  tolerance: number;
  contributing_swings: number;
  source_swing_ids: string[];
  source_timestamps: number[];
  confirmation_timestamps: number[];
  first_available_at: number;
  last_available_at: number;
}

export interface MarketStructureConfiguration {
  left_bars: number;
  right_bars: number;
  break_buffer: number;
  level_tolerance: number;
  break_confirmation: "candle_close";
  tie_handling: string;
}

export interface MarketStructureResponse {
  exchange: string;
  symbol: string;
  timeframe: string;
  candle_count: number;
  as_of: number;
  trend: TrendState;
  confirmed_swings: SwingPoint[];
  break_events: BreakEvent[];
  potential_breaks: PotentialBreak[];
  zones: StructureZone[];
  configuration: MarketStructureConfiguration;
}

export interface SignalResponse {
  symbol: string;
  timeframe: string;
  signal: "BUY" | "SELL" | "WAIT";
  direction: "BULLISH" | "BEARISH" | "NEUTRAL";
  score: number;
  score_scale: [number, number];
  strength: string;
  evaluation_timestamp: number;
  generated_at: number;
  trend: string;
  indicator_observations: {
    close?: number;
    ema_20?: number | null;
    ema_50?: number | null;
    rsi_14?: number | null;
    macd?: MACDValues;
    support_resistance_zones?: StructureZone[];
  };
  structural_observations: {
    recent_breaks?: BreakEvent[];
    confirmed_swings?: SwingPoint[];
  };
  reason_codes: string[];
  explanation: string;
}

export interface RiskPreviewRequest {
  direction: "long" | "short";
  entry: string;
  stop_loss: string;
  take_profit: string;
  equity: string;
  available_cash: string;
  risk_percent: string;
  min_risk_reward?: string;
  open_positions?: number;
  aggregate_open_risk?: string;
  max_open_positions?: number;
  max_aggregate_risk_percent?: string;
  fee_rate?: string;
  max_notional?: string | null;
  leverage?: string;
}

export interface RiskPreviewResponse {
  accepted: boolean;
  reason_code: string;
  message: string;
  symbol?: string;
  direction?: "long" | "short";
  entry?: string | number;
  stop_loss?: string | number;
  take_profit?: string | number;
  risk_per_unit?: string | number;
  cash_risk_budget?: string | number;
  position_quantity?: string | number;
  notional_exposure?: string | number;
  expected_reward?: string | number;
  risk_reward_ratio?: string | number;
  estimated_entry_fee?: string | number;
  estimated_exit_fee?: string | number;
  estimated_total_fees?: string | number;
  available_buying_power?: string | number;
  estimated_max_loss_including_fees?: string | number;
}

export interface PaperPosition {
  id: string;
  symbol: string;
  direction: "long";
  entry_price: string;
  quantity: string;
  stop_loss: string;
  take_profit: string;
  entry_fee: string;
  exit_fee: string | null;
  slippage_rate: string;
  opened_at: string;
  mark_price: string;
  status: "OPEN" | "CLOSED";
  exit_price: string | null;
  realised_pnl: string | null;
  close_reason: "manual" | "stop_loss" | "take_profit" | null;
  idempotency_key: string;
}

export interface PaperAccountSummary {
  account_id: number;
  starting_balance: string | number;
  available_cash: string | number;
  equity: string | number;
  realised_pnl: string | number;
  unrealised_pnl: string | number;
  total_fees: string | number;
  total_return_percent: string | number;
  quote_currency: string;
  risk_percent: string | number;
  open_positions: PaperPosition[];
  open_position_count: number;
  aggregate_open_risk: string | number;
}

export interface PaperLedgerEntry {
  id: number;
  position_id: string;
  kind: "OPEN" | "CLOSE";
  amount: string;
  details: string;
  created_at: string;
}

export interface AccountCreateRequest {
  starting_balance: string;
  quote_currency: string;
  risk_percent: string;
}

export interface OpenPositionRequest {
  symbol: string;
  direction: "long";
  entry: string;
  stop_loss: string;
  take_profit: string;
  risk_percent?: string | null;
  idempotency_key: string;
}

export interface MarkPriceRequest {
  mark_price: string;
}

export interface ClosePositionRequest {
  exit_price: string;
  close_reason: "manual" | "stop_loss" | "take_profit";
}

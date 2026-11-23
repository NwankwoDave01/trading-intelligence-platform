# Trading Intelligence Platform

A modular cryptocurrency market data and algorithmic trading intelligence platform built with FastAPI and CCXT.

---

## Architecture Overview

The market data layer is decoupled from specific cryptocurrency exchanges using an **Adapter Pattern**:

- **`BaseMarketDataProvider` (`backend/app/data/providers/base.py`)**: Abstract base provider defining the contract for ticker, candlestick (OHLCV) fetching, parameter validation, and sanitized error mapping.
- **`KrakenMarketData` (`backend/app/data/providers/kraken.py`)**: Active default provider utilizing CCXT public market data endpoints. Requires **no API keys**. Default trading pair: `BTC/USD`.
- **`BinanceMarketData` (`backend/app/data/providers/binance.py`)**: Secondary provider preserved for multi-exchange flexibility. Default trading pair: `BTC/USDT`.
- **`Provider Factory` (`backend/app/data/providers/factory.py`)**: Dynamically resolves and caches providers based on application configuration. Injected into FastAPI routes via `Depends(get_active_provider)`.
- **Domain Exceptions (`backend/app/data/providers/exceptions.py`)**: Sanitizes and decouples low-level CCXT exchange exceptions into domain errors (`ProviderNetworkError`, `ProviderSymbolNotFoundError`, `ProviderRateLimitError`, `ProviderUnavailableError`, `ProviderInvalidParameterError`). Ensures internal stack traces, URLs, and secrets are never exposed to API clients.

```
                         +--------------------+
                         | FastAPI Endpoints  |
                         |  (market.py)       |
                         +---------+----------+
                                   |
                       (Dependency Injection)
                                   v
                      +-------------------------+
                      | BaseMarketDataProvider  |  <--- Base Interface
                      +------------+------------+
                                   |
                 +-----------------+-----------------+
                 |                                   |
                 v                                   v
      +--------------------+               +--------------------+
      |  KrakenMarketData  | (Default)     | BinanceMarketData  |
      |  (Pair: BTC/USD)   |               | (Pair: BTC/USDT)   |
      +--------------------+               +--------------------+
                 |                                   |
           (Public CCXT)                       (Public CCXT)
                 v                                   v
            Kraken API                          Binance API
```

---

## Exchange Provider Specifications

| Feature | Kraken (Default) | Binance (Optional) |
| :--- | :--- | :--- |
| **Default Trading Pair** | `BTC/USD` | `BTC/USDT` |
| **Public API Authentication** | None (public endpoints) | None (public endpoints) |
| **Max Candlestick Limit** | **720 candles** (Kraken API limit) | **1000 candles** |
| **Supported Timeframes** | `1m`, `5m`, `15m`, `30m`, `1h`, `4h`, `1d`, `1w`, `2w` | `1m`, `5m`, `15m`, `30m`, `1h`, `4h`, `1d` |
| **Rate Limiter** | Enabled (`ccxt.kraken({"enableRateLimit": True})`) | Enabled (`ccxt.binance({"enableRateLimit": True})`) |

> **Kraken OHLC Limit Note**: Kraken's public OHLC endpoint (`/0/public/OHLC`) strictly returns a maximum of the 720 most recent intervals. Requesting limits above 720 returns a `400 Bad Request` with a clear explanation.

---

## Configuration

Provider selection is configured via environment variables or a `.env` file at the repository root:

```ini
# Active provider: 'kraken' (default) or 'binance'
DEFAULT_PROVIDER=kraken
# Alternatively:
MARKET_DATA_PROVIDER=kraken

# Exchange request timeout in milliseconds (default: 15000)
EXCHANGE_TIMEOUT_MS=15000
```

---

## Installation & Setup

### 1. Prerequisites
- Python 3.10+ (tested on Python 3.13)
- Virtual environment tool (`venv`)

### 2. Create and Activate Virtual Environment
```bash
# Windows
python -m venv .venv
.\.venv\Scripts\activate

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r backend/requirements.txt
```

---

## Running the Application

Start the FastAPI application with Uvicorn:

```bash
# From repository root:
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

Interactive documentation is available at:
- **Swagger UI**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

## API Endpoints

### 1. Application Health
- **Endpoint**: `GET /health`
- **Response**:
```json
{
  "status": "healthy"
}
```

### 2. Active Provider Metadata
- **Endpoint**: `GET /api/v1/market/provider`
- **Description**: Returns capabilities and limits of the configured active provider without making any external network requests.
- **Response**:
```json
{
  "exchange": "Kraken",
  "status": "ready",
  "default_symbol": "BTC/USD",
  "supported_timeframes": ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w", "2w"],
  "max_candle_limit": 720,
  "rate_limit_enabled": true
}
```

### 3. Market Ticker
- **Endpoint**: `GET /api/v1/market/ticker`
- **Query Parameters**:
  - `symbol` (optional): Trading pair (e.g., `BTC/USD` for Kraken, `BTC/USDT` for Binance). Defaults to the active exchange's default symbol.
- **Normalized Response**:
```json
{
  "exchange": "Kraken",
  "symbol": "BTC/USD",
  "timestamp": "2026-11-20T08:00:00.000Z",
  "last_price": 94250.0,
  "bid": 94240.0,
  "ask": 94260.0,
  "high_24h": 95100.0,
  "low_24h": 92300.0,
  "volume_24h": 1820.45,
  "price_change_percentage": 2.1
}
```

### 4. Historical Candlesticks (OHLCV)
- **Endpoint**: `GET /api/v1/market/candles`
- **Query Parameters**:
  - `symbol` (optional): Trading pair. Defaults to active provider's default pair.
  - `timeframe` (optional, default `"1h"`): Candlestick interval (`1m`, `5m`, `15m`, `30m`, `1h`, `4h`, `1d`).
  - `limit` (optional, default `100`, max `720` for Kraken, `1000` for Binance): Number of candles to return.
- **Normalized Response**:
```json
{
  "exchange": "Kraken",
  "symbol": "BTC/USD",
  "timeframe": "1h",
  "count": 2,
  "candles": [
    {
      "timestamp": 1700000000000,
      "open": 93000.0,
      "high": 93500.0,
      "low": 92800.0,
      "close": 93400.0,
      "volume": 80.0
    },
    {
      "timestamp": 1700003600000,
      "open": 93400.0,
      "high": 94300.0,
      "low": 93350.0,
      "close": 94250.0,
      "volume": 95.5
    }
  ]
}
```

### 5. Technical Analysis Indicators
- **Endpoint**: `GET /api/v1/analysis/indicators`
- **Query parameters**: `symbol` (provider default if omitted), `timeframe` (default `1h`), and `limit` (default `200`; provider limits apply).
- The endpoint validates every candle's OHLCV fields, finite numeric values, candle price bounds, non-negative volume, and strictly increasing unique integer timestamps. Invalid data receives HTTP 422; insufficient individual indicator warm-up history is represented by `null`, without inventing market data.
- **Features**: SMA(20/50), EMA(20/50), Wilder RSI(14), MACD(12,26,9), Bollinger Bands(20,2), and Wilder ATR(14).
- **Calculation conventions**:
  - EMA is seeded with the SMA of its first N observations, first valid at index N−1, then uses alpha = 2/(N+1).
  - RSI uses the first 14 price changes to seed average gains/losses, first valid at index 14, and Wilder recurrence (previous average × 13 + current change)/14. No gain and no loss maps to neutral RSI 50.
  - MACD uses 12- and 26-period SMA-seeded EMAs. Its signal is a 9-period SMA-seeded EMA of valid MACD values only; histogram = line − signal. First MACD line is at index 25 and first signal at index 33.
  - Bollinger middle is SMA(20); upper/lower are middle ± 2 population standard deviations (ddof=0).
  - ATR uses Wilder smoothing, seeded by 14 true ranges at index 14.
- **Example response** (values abbreviated):
```json
{
  "exchange": "Kraken",
  "symbol": "BTC/USD",
  "timeframe": "1h",
  "candle_count": 100,
  "latest": {
    "sma_20": 94000.0,
    "sma_50": 93800.0,
    "ema_20": 94010.0,
    "ema_50": 93900.0,
    "rsi_14": 55.2,
    "macd": {"line": 12.5, "signal": 10.2, "histogram": 2.3},
    "bollinger_bands": {"upper": 95000.0, "middle": 94000.0, "lower": 93000.0},
    "atr_14": 450.0
  },
  "series": [{"timestamp": 1700000000000, "close": 93400.0, "sma_20": null, "sma_50": null, "ema_20": null, "ema_50": null, "rsi_14": null, "macd": {"line": null, "signal": null, "histogram": null}, "bollinger_bands": {"upper": null, "middle": null, "lower": null}, "atr_14": null}]
}
```

### 6. Market Structure Analysis

- **Endpoint**: `GET /api/v1/analysis/market-structure`
- **Query parameters**: `symbol` (optional; defaults to provider default), `timeframe` (default `1h`), `limit` (default `200`; must not exceed the active provider maximum), `left_bars` and `right_bars` (defaults `3`, each `1–50`), `break_buffer` (default `0`, absolute price units), and `level_tolerance` (default `0`, absolute price units).
- The route uses the existing provider dependency and excludes a final candle whose interval has not closed yet. It returns HTTP 400 for unsupported timeframes or provider-limit violations and HTTP 422 for invalid OHLCV/configuration.

#### Methodology and confirmation timing

- A swing high/low must be strictly higher/lower than every neighbor in the configured left and right windows. Equal highs/lows disqualify tied candidates. A swing is emitted only once all right-side candles are closed; its `timestamp` is the pivot candle open time, `confirmation_candle_timestamp` identifies the final confirming candle, and `available_at` is that candle's estimated close time.
- Each high is compared only with the preceding high, and each low only with the preceding low. The first comparable pivot has no classification. Subsequent highs are HH/LH; subsequent lows are HL/LL. `reference_swing_id` identifies the prior point used.
- Trend uses confirmed swings only. It is bullish when the latest classified high is HH and latest classified low is HL; bearish when they are LH and LL. Once both sides have comparable pivots but do not agree, the state is ranging; before that it is undetermined. A single higher high is not sufficient for a bullish trend.
- A structural level is the latest confirmed swing high/low, available before the break candle. A candle close crossing that level plus/minus `break_buffer` produces BOS when aligned with established trend and CHoCH when opposed. No BOS/CHoCH is emitted while trend is ranging or undetermined. A level/direction pair emits at most one event; a new confirmed pivot creates a new level. The latest candle's wick-only crossing is returned separately as an `unconfirmed` potential break, never as a confirmed event.
- Support uses confirmed swing lows and resistance uses confirmed swing highs. Clustering uses an absolute price tolerance from the first pivot in each cluster; each new pivot joins the nearest matching anchor (ties choose the earliest cluster). Zones expose bounds, source pivots, confirmation/availability times, and contributing-point count; the count is not a strength score.
- Historical results never make a pivot available before its right-side confirmation or a break before its closing candle. The route discards an unfinished latest candle; results assume earlier provider candles are closed. `available_at` is estimated from the fixed timeframe duration.

#### Example request

```http
GET /api/v1/analysis/market-structure?symbol=BTC%2FUSD&timeframe=1h&limit=200&left_bars=3&right_bars=3&break_buffer=0&level_tolerance=50
```

#### Example response (abbreviated)

```json
{
  "exchange": "Kraken",
  "symbol": "BTC/USD",
  "timeframe": "1h",
  "candle_count": 200,
  "as_of": 1700003600000,
  "trend": {"classification": "bullish", "as_of": 1700003600000},
  "confirmed_swings": [{
    "id": "high:42", "swing_type": "high", "timestamp": 1699990000000,
    "price": 94000.0, "confirmation_candle_timestamp": 1699996400000,
    "available_at": 1700000000000, "confirmation_delay_bars": 3,
    "classification": "HH", "reference_swing_id": "high:35"
  }],
  "break_events": [{
    "id": "bos:high:42:47", "event_type": "BOS", "direction": "bullish",
    "broken_level": 94000.0, "source_swing_id": "high:42",
    "source_swing_timestamp": 1699990000000,
    "confirmation_candle_timestamp": 1700000000000,
    "confirmation_close": 94100.0, "available_at": 1700003600000
  }],
  "potential_breaks": [],
  "zones": [{
    "zone_type": "support", "lower_bound": 92000.0, "upper_bound": 92025.0,
    "midpoint": 92012.5, "tolerance": 50.0, "contributing_swings": 2,
    "source_swing_ids": ["low:30", "low:38"],
    "source_timestamps": [1699940000000, 1699968800000],
    "confirmation_timestamps": [1699950800000, 1699979600000],
    "first_available_at": 1699954400000, "last_available_at": 1699983200000
  }],
  "configuration": {
    "left_bars": 3, "right_bars": 3, "break_buffer": 0.0,
    "level_tolerance": 50.0, "break_confirmation": "candle_close",
    "tie_handling": "equal neighboring highs/lows disqualify a pivot"
  }
}
```

---

## Error Handling & Status Codes

All exchange errors are translated into standard HTTP status codes with clean, descriptive client messages:

| HTTP Status | Condition | Example Client Detail |
| :--- | :--- | :--- |
| `400 Bad Request` | Unsupported timeframe or invalid limit | `"Requested limit 800 exceeds maximum allowed of 720 for Kraken."` |
| `404 Not Found` | Symbol not found on exchange | `"Symbol 'UNKNOWN/PAIR' not found or unsupported on Kraken."` |
| `429 Too Many Requests` | Exchange rate limit exceeded | `"Rate limit exceeded while contacting Kraken. Please retry later."` |
| `502 Bad Gateway` | Exchange error / API failure | `"Unable to retrieve market data from Kraken."` |
| `503 Service Unavailable` | Exchange undergoing maintenance | `"Kraken is temporarily unavailable or undergoing maintenance."` |
| `504 Gateway Timeout` | Network timeout reaching exchange | `"Network timeout or connectivity failure while communicating with Kraken."` |

---

## Automated Testing

The automated test suite runs completely offline with **zero external network requests** using mocked exchange responses:

```bash
# Run the entire test suite
.venv/bin/python -m pytest backend/tests/ -v

# Run tests with short summary
.venv/bin/python -m pytest backend/tests/ -q
```

### Test Coverage Areas:
1. **`test_kraken_provider.py`**:
   - Initialization and non-network metadata.
   - Default (`BTC/USD`) and custom pair ticker fetching and response normalization.
   - OHLCV fetching, timeframe validation, and 720 candle limit enforcement.
   - CCXT error translation (`BadSymbol`, `NetworkError`, `RateLimitExceeded`, `ExchangeNotAvailable`).
2. **`test_binance_provider.py`**:
   - Backward compatibility preservation (including `market_data` singleton).
   - Normalized ticker and OHLCV responses for Binance (`BTC/USDT`).
3. **`test_factory_and_config.py`**:
   - Default provider resolution (`Kraken`).
   - Case-insensitive provider selection.
   - Error handling for unsupported providers.
   - Pydantic configuration alias precedence (`MARKET_DATA_PROVIDER` / `DEFAULT_PROVIDER`).
4. **`test_market_api.py`**:
   - FastAPI `/health` and root endpoints.
   - `/api/v1/market/provider` metadata endpoint.
   - `/api/v1/market/ticker` and `/api/v1/market/candles` request routing.
   - Parameter validation (timeframe and candle limits).
   - HTTP status code mapping (400, 404, 429, 502, 503, 504).
   - Dynamic exchange switching via dependency injection.
5. **`test_market_structure.py`** and **`test_market_structure_api.py`**:
   - Pivot ties and confirmation delays, HH/HL/LH/LL labels, all trend states.
   - Close-confirmed BOS/CHoCH, wick-only potential breaks, buffers, and duplicate prevention.
   - Zone clustering, malformed OHLCV/timestamps, provider injection, candle caps, and unfinished-candle exclusion.

---

## Live Connectivity Check (Host Machine)

In containerized or sandboxed development environments, external DNS resolution for public cryptocurrency exchanges may be restricted. On an unrestricted Windows host, you can verify live public Kraken connectivity with:

```bash
python -c "import urllib.request, json; res = urllib.request.urlopen('https://api.kraken.com/0/public/Time', timeout=5); print('Kraken Public Time:', json.loads(res.read()))"
```

---

## Signal, Risk, and Paper Trading APIs

The backend now layers three systems over the existing indicator and market-structure services. No private exchange credentials, live orders, margin, or real-money execution are used.

### Signal rules

`GET /api/v1/analysis/signal?symbol=BTC/USD&timeframe=1h&limit=200` returns BUY/SELL/WAIT with weighted factor values, observations, timestamped structure, and reason codes. Weights are structure ±3, EMA20/EMA50 alignment ±2, close relative to EMA20 ±1, MACD line/signal/histogram ±2, RSI context ±1, recent confirmed structural break ±2, and nearby support/resistance context ±1. Zone proximity is within 1% of close; nearby opposing zones subtract one point and favorable context adds one. Zones never trigger a signal by themselves. Recent breaks mean available within 12 completed timeframe bars. Direction requires a bullish/bearish trend, score of at least +6 or at most -6, three aligned non-trend factors, and no opposing scored factor. Ranging/undetermined trends, fewer than 50 completed bars, or missing warm-up values return WAIT. Scores describe rule alignment, not win probability. Signal evaluation excludes the currently unfinished candle and filters structure events by `available_at`.

### Risk preview

`POST /api/v1/risk/preview` accepts direction, entry, stop, target, equity, available cash, and optional risk/exposure limits. Defaults are 1% equity risk, minimum 1.5:1 reward/risk, five open positions, 5% maximum aggregate open risk, 0.1% fee per side, and 1x leverage only. Quantity is rounded down to eight decimal places; estimated entry and exit fees are both included in the loss budget. The service returns a structured rejection reason instead of changing proposed prices.

### Paper account and positions

- `POST /api/v1/paper/account` creates the one local virtual account (subsequent creates retrieve the existing account); `GET /api/v1/paper/account` retrieves it.
- `POST /api/v1/paper/risk-preview` previews a long proposal against the account and current open risk.
- `POST /api/v1/paper/positions` opens a long position. Include a unique `idempotency_key` (at least 8 characters) for retry safety.
- `GET /api/v1/paper/positions` lists open positions; `GET /api/v1/paper/positions/{id}` retrieves one.
- `POST /api/v1/paper/positions/{id}/mark` updates mark price. Optional `low` and `high` query values supply an OHLC range for stop/target handling.
- `POST /api/v1/paper/positions/{id}/close` closes once; repeat requests return the existing close record.
- `GET /api/v1/paper/history`, `/api/v1/paper/performance`, and `/api/v1/paper/positions/{id}/ledger` expose closed trades, reconciled account metrics, and audit entries.

The virtual account stores quote cash in SQLite at `var/paper_trading.sqlite3` (override with `PAPER_TRADING_DB`). SQLite transactions serialize account mutations; the database is local to the application instance and is not a shared/distributed production store. Entry and exit fills apply adverse 0.05% slippage and 0.1% fees. Opening debits unleveraged notional plus entry fee; equity is cash plus marked position value. Net realized P&L includes both fees exactly once. If a supplied candle crosses both protective levels, stop loss wins. Paper trading intentionally supports long positions only; short exposure and leveraged trading are rejected/out of scope until a complete liability and buying-power model exists. Market marks are updated by the caller through the mark endpoint; there is no background polling job.

Example risk request:

```json
{
  "direction": "long", "entry": "100", "stop_loss": "95",
  "take_profit": "110", "equity": "10000", "available_cash": "10000"
}
```

Example paper account request:

```json
{"starting_balance": "10000", "quote_currency": "USD", "risk_percent": "1"}
```

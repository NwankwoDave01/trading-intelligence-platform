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

---

## Live Connectivity Check (Host Machine)

In containerized or sandboxed development environments, external DNS resolution for public cryptocurrency exchanges may be restricted. On an unrestricted Windows host, you can verify live public Kraken connectivity with:

```bash
python -c "import urllib.request, json; res = urllib.request.urlopen('https://api.kraken.com/0/public/Time', timeout=5); print('Kraken Public Time:', json.loads(res.read()))"
```

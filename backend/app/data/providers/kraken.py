"""
Kraken public market data provider implementation using CCXT.
Fetches ticker and OHLCV candlestick data without requiring API keys.
"""

from typing import Any, Dict, List, Optional
import ccxt

from backend.app.data.providers.base import BaseMarketDataProvider
from backend.app.data.providers.exceptions import ProviderError, ProviderInvalidParameterError


class KrakenMarketData(BaseMarketDataProvider):
    """
    Public Kraken market data provider.
    No API keys are required for ticker and OHLCV market data operations.
    """

    NAME = "Kraken"
    DEFAULT_SYMBOL = "BTC/USD"
    MAX_CANDLE_LIMIT = 720  # Kraken public OHLC API returns a maximum of 720 candles per request.
    SUPPORTED_TIMEFRAMES = [
        "1m", "5m", "15m", "30m",
        "1h", "4h", "1d", "1w", "2w"
    ]

    def __init__(self, exchange: Optional[ccxt.kraken] = None, timeout_ms: int = 15000):
        self.exchange = exchange or ccxt.kraken({
            "enableRateLimit": True,
            "timeout": timeout_ms,
        })

    @property
    def name(self) -> str:
        return self.NAME

    @property
    def default_symbol(self) -> str:
        return self.DEFAULT_SYMBOL

    @property
    def supported_timeframes(self) -> List[str]:
        return list(self.SUPPORTED_TIMEFRAMES)

    @property
    def max_candle_limit(self) -> int:
        return self.MAX_CANDLE_LIMIT

    def get_ticker(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """
        Fetch public 24-hour ticker for Kraken.
        Default pair: BTC/USD.
        """
        target_symbol = self.validate_symbol(symbol)
        try:
            ticker = self.exchange.fetch_ticker(target_symbol)
            return {
                "exchange": self.name,
                "symbol": target_symbol,
                "timestamp": ticker.get("datetime"),
                "last_price": ticker.get("last"),
                "bid": ticker.get("bid"),
                "ask": ticker.get("ask"),
                "high_24h": ticker.get("high"),
                "low_24h": ticker.get("low"),
                "volume_24h": ticker.get("baseVolume"),
                "price_change_percentage": ticker.get("percentage"),
            }
        except (ProviderError, ProviderInvalidParameterError):
            raise
        except Exception as e:
            raise self.translate_ccxt_error(e, symbol=target_symbol) from e

    def get_candles(
        self,
        symbol: Optional[str] = None,
        timeframe: str = "1h",
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Fetch public OHLCV candles from Kraken.
        Kraken caps single-request OHLC results at 720 intervals.
        """
        target_symbol = self.validate_symbol(symbol)
        target_timeframe = self.validate_timeframe(timeframe)
        target_limit = self.validate_limit(limit)

        try:
            candles = self.exchange.fetch_ohlcv(
                target_symbol,
                timeframe=target_timeframe,
                limit=target_limit,
            )

            # Limit output to requested count if exchange returns extra
            sliced_candles = candles[-target_limit:] if candles and len(candles) > target_limit else (candles or [])

            return [
                {
                    "timestamp": candle[0],
                    "open": candle[1],
                    "high": candle[2],
                    "low": candle[3],
                    "close": candle[4],
                    "volume": candle[5],
                }
                for candle in sliced_candles
            ]
        except (ProviderError, ProviderInvalidParameterError):
            raise
        except Exception as e:
            raise self.translate_ccxt_error(e, symbol=target_symbol) from e

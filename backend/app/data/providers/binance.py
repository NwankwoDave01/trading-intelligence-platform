"""
Public Binance market data provider implementation.
Preserves existing functionality while adhering to the BaseMarketDataProvider adapter.
No API keys are required for these operations.
"""

from typing import Any, Dict, List, Optional
import ccxt

from backend.app.data.providers.base import BaseMarketDataProvider
from backend.app.data.providers.exceptions import ProviderError, ProviderInvalidParameterError


class BinanceMarketData(BaseMarketDataProvider):
    """
    Public Binance market data provider.
    No API keys are required for these operations.
    """

    NAME = "Binance"
    DEFAULT_SYMBOL = "BTC/USDT"
    MAX_CANDLE_LIMIT = 1000
    SUPPORTED_TIMEFRAMES = [
        "1m", "5m", "15m", "30m",
        "1h", "4h", "1d"
    ]

    def __init__(self, exchange: Optional[ccxt.binance] = None, timeout_ms: int = 15000):
        self.exchange = exchange or ccxt.binance({
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

    def get_ticker(self, symbol: Optional[str] = "BTC/USDT") -> Dict[str, Any]:
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
        symbol: Optional[str] = "BTC/USDT",
        timeframe: str = "1h",
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        target_symbol = self.validate_symbol(symbol)
        target_timeframe = self.validate_timeframe(timeframe)
        target_limit = self.validate_limit(limit)

        try:
            candles = self.exchange.fetch_ohlcv(
                target_symbol,
                timeframe=target_timeframe,
                limit=target_limit,
            )

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


# Retain global instance for backward compatibility
market_data = BinanceMarketData()

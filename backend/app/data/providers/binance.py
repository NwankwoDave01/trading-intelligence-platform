
import ccxt

class BinanceMarketData:
    """
    Public Binance market data provider.
    No API keys are required for these operations.
    """

    def __init__(self):
        self.exchange = ccxt.binance({
            "enableRateLimit": True,
            "timeout": 15000,
        })

    def get_ticker(self, symbol: str = "BTC/USDT"):
        ticker = self.exchange.fetch_ticker(symbol)

        return {
            "exchange": "Binance",
            "symbol": symbol,
            "timestamp": ticker.get("datetime"),
            "last_price": ticker.get("last"),
            "bid": ticker.get("bid"),
            "ask": ticker.get("ask"),
            "high_24h": ticker.get("high"),
            "low_24h": ticker.get("low"),
            "volume_24h": ticker.get("baseVolume"),
            "price_change_percentage": ticker.get("percentage"),
        }

    def get_candles(
        self,
        symbol: str = "BTC/USDT",
        timeframe: str = "1h",
        limit: int = 100,
    ):
        candles = self.exchange.fetch_ohlcv(
            symbol,
            timeframe=timeframe,
            limit=limit,
        )

        return [
            {
                "timestamp": candle[0],
                "open": candle[1],
                "high": candle[2],
                "low": candle[3],
                "close": candle[4],
                "volume": candle[5],
            }
            for candle in candles
        ]

market_data = BinanceMarketData()
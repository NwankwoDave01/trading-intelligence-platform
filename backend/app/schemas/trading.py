"""Request and response schemas for signal, risk, and virtual portfolio APIs."""
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict


class SignalResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    symbol: str
    timeframe: str
    signal: Literal["BUY", "SELL", "WAIT"]
    direction: Literal["BULLISH", "BEARISH", "NEUTRAL"]
    score: int
    score_scale: list[int]
    strength: str
    evaluation_timestamp: int
    generated_at: int
    trend: str
    indicator_observations: dict
    structural_observations: dict
    reason_codes: list[str]
    explanation: str


class RiskRequest(BaseModel):
    direction: Literal["long", "short"]
    entry: Decimal = Field(gt=0)
    stop_loss: Decimal = Field(gt=0)
    take_profit: Decimal = Field(gt=0)
    equity: Decimal = Field(gt=0)
    available_cash: Decimal = Field(ge=0)
    risk_percent: Decimal = Field(default=Decimal("1"), gt=0, le=Decimal("100"))
    min_risk_reward: Decimal = Field(default=Decimal("1.5"), gt=0)
    open_positions: int = Field(default=0, ge=0)
    aggregate_open_risk: Decimal = Field(default=Decimal("0"), ge=0)
    max_open_positions: int = Field(default=5, ge=1)
    max_aggregate_risk_percent: Decimal = Field(default=Decimal("5"), gt=0, le=Decimal("100"))
    fee_rate: Decimal = Field(default=Decimal("0.001"), ge=0, lt=Decimal("1"))
    max_notional: Decimal | None = Field(default=None, gt=0)
    leverage: Decimal = Field(default=Decimal("1"), gt=0)


class AccountCreate(BaseModel):
    starting_balance: Decimal = Field(default=Decimal("10000"), gt=0, max_digits=20, decimal_places=8)
    quote_currency: str = Field(default="USD", min_length=3, max_length=10, pattern=r"^[A-Z]{3,10}$")
    risk_percent: Decimal = Field(default=Decimal("1"), gt=0, le=Decimal("100"))


class OpenPositionRequest(BaseModel):
    symbol: str = Field(min_length=3, max_length=32)
    direction: Literal["long"] = "long"
    entry: Decimal = Field(gt=0, max_digits=20, decimal_places=8)
    stop_loss: Decimal = Field(gt=0, max_digits=20, decimal_places=8)
    take_profit: Decimal = Field(gt=0, max_digits=20, decimal_places=8)
    risk_percent: Decimal | None = Field(default=None, gt=0, le=Decimal("100"))
    idempotency_key: str = Field(min_length=8, max_length=128)


class ClosePositionRequest(BaseModel):
    exit_price: Decimal = Field(gt=0, max_digits=20, decimal_places=8)
    close_reason: Literal["manual", "stop_loss", "take_profit"] = "manual"


class MarkPriceRequest(BaseModel):
    mark_price: Decimal = Field(gt=0, max_digits=20, decimal_places=8)

"""Versioned signal, risk, and paper-trading endpoints."""
import time
from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from backend.app.analysis.service import calculate_indicators
from backend.app.analysis.signals import generate_signal
from backend.app.analysis.market_structure import calculate_market_structure
from backend.app.analysis.market_structure.service import timeframe_to_milliseconds
from backend.app.api.v1.analysis import _handle_provider_exception
from backend.app.data.providers.base import BaseMarketDataProvider
from backend.app.data.providers.factory import get_active_provider
from backend.app.paper import service as paper
from backend.app.risk.service import preview_trade
from backend.app.schemas.trading import SignalResponse, RiskRequest, AccountCreate, OpenPositionRequest, ClosePositionRequest, MarkPriceRequest

router = APIRouter(tags=["Trading Intelligence"])


@router.get("/analysis/signal", response_model=SignalResponse, summary="Generate an explainable trading signal")
def signal(symbol: Optional[str] = None, timeframe: str = "1h", limit: int = Query(default=200, ge=50, le=1000), provider: BaseMarketDataProvider = Depends(get_active_provider)):
    target = symbol or provider.default_symbol
    if timeframe not in provider.supported_timeframes: raise HTTPException(400, f"Unsupported timeframe '{timeframe}' for {provider.name}.")
    if limit > provider.max_candle_limit: raise HTTPException(400, f"Requested limit {limit} exceeds maximum allowed of {provider.max_candle_limit} for {provider.name}.")
    try:
        candles = provider.get_candles(symbol=target, timeframe=timeframe, limit=limit)
        duration = timeframe_to_milliseconds(timeframe)
        now = time.time_ns() // 1_000_000
        if candles and int(candles[-1]["timestamp"]) + duration > now: candles = candles[:-1]
        if len(candles) < 2:
            indicators = {"latest": {}, "series": [], "candle_count": len(candles)}
            structure = {"trend": {"classification":"undetermined"}, "confirmed_swings":[], "break_events":[], "zones":[]}
        else:
            indicators = calculate_indicators(candles)
            structure = calculate_market_structure(candles, timeframe=timeframe)
        result = generate_signal(symbol=target, timeframe=timeframe, candles=candles, indicators=indicators, structure=structure, generated_at=now)
        return SignalResponse(**result)
    except HTTPException: raise
    except Exception as exc:
        if isinstance(exc, (KeyError, TypeError, ValueError)): raise HTTPException(422, str(exc)) from exc
        _handle_provider_exception(exc, provider.name)


@router.post("/risk/preview")
def risk_preview(request: RiskRequest):
    return preview_trade(**request.model_dump())


@router.post("/paper/account")
def create_paper_account(request: AccountCreate):
    try: return paper.create_account(request.starting_balance, request.quote_currency, request.risk_percent)
    except Exception as exc: raise HTTPException(500, "Unable to initialize paper account.") from exc


@router.get("/paper/account")
def get_paper_account():
    account = paper.get_account()
    if not account: raise HTTPException(404, "Paper account not found; create one first.")
    return account


@router.post("/paper/risk-preview")
def paper_risk_preview(request: OpenPositionRequest):
    return paper.preview_position(request.symbol, request.direction, request.entry, request.stop_loss, request.take_profit, request.risk_percent)


@router.post("/paper/positions", status_code=201)
def open_paper_position(request: OpenPositionRequest):
    try: return paper.open_position(request.symbol, request.entry, request.stop_loss, request.take_profit, request.idempotency_key, request.risk_percent)
    except ValueError as exc: raise HTTPException(422, str(exc)) from exc


@router.get("/paper/positions")
def list_paper_positions(): return paper.list_positions()


@router.get("/paper/positions/{position_id}")
def get_paper_position(position_id: str):
    position = paper.get_position(position_id)
    if not position: raise HTTPException(404, "Paper position not found.")
    return position


@router.post("/paper/positions/{position_id}/mark")
def mark_paper_position(position_id: str, request: MarkPriceRequest, low: Decimal | None = Query(default=None, gt=0), high: Decimal | None = Query(default=None, gt=0)):
    if not request.mark_price.is_finite() or request.mark_price <= 0:
        raise HTTPException(422, "Mark price must be finite and positive.")
    if (low is None) != (high is None):
        raise HTTPException(422, "Both candle low and candle high must be supplied together.")
    if low is not None and high is not None:
        if not low.is_finite() or low <= 0 or not high.is_finite() or high <= 0:
            raise HTTPException(422, "Candle low and candle high must be finite and positive.")
        if low > high:
            raise HTTPException(422, "Candle low cannot exceed candle high.")
        if not (low <= request.mark_price <= high):
            raise HTTPException(422, "Mark price must be between candle low and candle high, inclusive.")
    try:
        position = paper.mark_position(position_id, request.mark_price, low, high)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if not position: raise HTTPException(404, "Paper position not found.")
    return position


@router.post("/paper/positions/{position_id}/close")
def close_paper_position(position_id: str, request: ClosePositionRequest):
    position = paper.close_position(position_id, request.exit_price, request.close_reason)
    if not position: raise HTTPException(404, "Paper position not found.")
    return position


@router.get("/paper/history")
def paper_history(): return paper.history()


@router.get("/paper/performance")
def paper_performance():
    account = paper.get_account()
    if not account: raise HTTPException(404, "Paper account not found; create one first.")
    return account


@router.get("/paper/positions/{position_id}/ledger")
def paper_ledger(position_id: str):
    if not paper.get_position(position_id): raise HTTPException(404, "Paper position not found.")
    return paper.ledger(position_id)

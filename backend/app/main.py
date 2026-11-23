
from fastapi import FastAPI

from backend.app.api.v1.market import router as market_router
from backend.app.api.v1.analysis import router as analysis_router
from backend.app.api.v1.trading import router as trading_router

app = FastAPI(
    title="Trading Intelligence Platform",
    description="Algorithmic trading and market intelligence API",
    version="0.3.0"
)

app.include_router(market_router, prefix="/api/v1")
app.include_router(analysis_router, prefix="/api/v1")
app.include_router(trading_router, prefix="/api/v1")


@app.get("/")
def root():
    return {
        "application": "Trading Intelligence Platform",
        "status": "running",
        "version": "0.3.0"
    }


@app.get("/health")
def health():
    return {"status": "healthy"}

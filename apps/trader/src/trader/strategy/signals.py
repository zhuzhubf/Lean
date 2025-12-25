"""Signal engine for 1h/4h swing features."""

from __future__ import annotations

from dataclasses import dataclass

from trader.schemas import MarketSnapshot


@dataclass
class SignalFeatures:
    """Derived features used for trading intents."""

    symbol: str
    trend_1h: float
    trend_4h: float
    atr_pct: float
    spread_bps: float
    volume_ratio: float
    agreement: float


class SignalEngine:
    """Compute lightweight technical features for swing horizons."""

    def __init__(self, bullish_threshold: float = 0.0015, bearish_threshold: float = -0.0015):
        self.bullish_threshold = bullish_threshold
        self.bearish_threshold = bearish_threshold

    def compute(self, snapshot: MarketSnapshot) -> SignalFeatures:
        price = snapshot.price
        ohlcv_1h = snapshot.ohlcv_1h
        ohlcv_4h = snapshot.ohlcv_4h
        trend_1h = (ohlcv_1h.close - ohlcv_1h.open) / ohlcv_1h.open if ohlcv_1h.open else 0.0
        trend_4h = (ohlcv_4h.close - ohlcv_4h.open) / ohlcv_4h.open if ohlcv_4h.open else 0.0
        atr_pct = (snapshot.atr / price) if snapshot.atr and price else 0.0
        volume_ratio = (ohlcv_1h.volume / ohlcv_4h.volume) if ohlcv_4h.volume else 0.0
        agreement = (trend_1h + trend_4h) / 2
        return SignalFeatures(
            symbol=snapshot.symbol,
            trend_1h=trend_1h,
            trend_4h=trend_4h,
            atr_pct=atr_pct,
            spread_bps=snapshot.spread_bps,
            volume_ratio=volume_ratio,
            agreement=agreement,
        )

    def classify(self, features: SignalFeatures) -> str:
        if features.agreement >= self.bullish_threshold:
            return "bullish"
        if features.agreement <= self.bearish_threshold:
            return "bearish"
        return "neutral"

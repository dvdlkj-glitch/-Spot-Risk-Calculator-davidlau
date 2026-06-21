"""
Market data helpers — daily OHLC + ATR(10) auto-grab (spec §4).

Uses yfinance. All network access is wrapped: on any failure the caller gets a
(None, message) tuple and the UI falls back to manual entry without breaking.
"""

from __future__ import annotations

from spot_risk_core import wilder_atr

try:
    import yfinance as yf
except Exception:  # pragma: no cover
    yf = None


def auto_grab_atr(ticker: str, period: int = 10) -> tuple[float | None, dict | None, str]:
    """
    Fetch recent daily bars for `ticker` and compute Wilder ATR(period).

    Returns (atr, last_bar, message):
      * atr      — float, or None on failure
      * last_bar — {"date","high","low","close"} of the most recent bar, or None
      * message  — human-readable status (success detail or failure reason)
    """
    ticker = (ticker or "").strip().upper()
    if not ticker:
        return None, None, "請先輸入 Ticker"
    if yf is None:
        return None, None, "yfinance 未安裝，請手動輸入 ATR"

    try:
        df = yf.Ticker(ticker).history(period="3mo", interval="1d", auto_adjust=False)
    except Exception as e:  # network / lookup error
        return None, None, f"抓取失敗（{type(e).__name__}）— 請手動輸入 ATR"

    if df is None or df.empty or len(df) < period + 1:
        return None, None, f"{ticker} 資料不足（停牌或代碼錯誤）— 請手動輸入 ATR"

    highs = df["High"].tolist()
    lows = df["Low"].tolist()
    closes = df["Close"].tolist()

    try:
        atr = wilder_atr(highs, lows, closes, period=period)
    except ValueError as e:
        return None, None, f"ATR 計算失敗：{e}"

    last_idx = df.index[-1]
    last_bar = {
        "date": last_idx.strftime("%Y-%m-%d"),
        "high": float(highs[-1]),
        "low": float(lows[-1]),
        "close": float(closes[-1]),
    }
    msg = (
        f"已自動填入 {ticker} 的 ATR({period}): {atr:.2f} · "
        f"最新日線 {last_bar['date']} "
        f"高 {last_bar['high']:.2f} / 低 {last_bar['low']:.2f} / 收 {last_bar['close']:.2f}"
    )
    return round(atr, 2), last_bar, msg


def company_name(ticker: str) -> str | None:
    """Best-effort long name for display ('NVDA - NVIDIA Corporation')."""
    ticker = (ticker or "").strip().upper()
    if not ticker or yf is None:
        return None
    try:
        info = yf.Ticker(ticker).get_info()
        return info.get("longName") or info.get("shortName")
    except Exception:
        return None

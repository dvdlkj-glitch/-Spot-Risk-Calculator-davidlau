"""
Spot Risk Calculator — pure calculation core (no Streamlit imports).

This module is intentionally dependency-light so it can be unit-tested in
isolation (see test_spot_risk_core.py). Everything UI / IO related lives in
app.py.

Formula note (important):
    The build spec (spot_risk_calculator_spec.md §3) presents a simplified code
    block using a single dollar deviation `dev_usd = support * dev%`. That code
    does NOT reproduce the spec's own §2.2 *measured* values — e.g. it yields a
    take_profit of 220.20 against a measured 220.12 (fails the ±0.05 tolerance).

    The measured values close exactly when the deviation is applied as a
    *percentage of each respective price level*:

        entry       = support          * (1 + dev%)
        cut_loss    = (support - atr)   * (1 - dev%)
        take_profit = resistance        * (1 - dev%)

    This is the version implemented below, and it reproduces every number in
    §2.2 to the cent. The Short side is the mirror image.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from math import floor


# --------------------------------------------------------------------------- #
# Result container
# --------------------------------------------------------------------------- #
@dataclass
class SpotRiskResult:
    # price structure
    entry: float
    cut_loss: float
    take_profit: float
    # per-share economics
    risk_ps: float
    reward_ps: float
    rr: float
    # sizing
    risk_budget: float
    qty: int
    capital_req: float
    total_risk: float
    total_win: float
    risk_acct_pct: float
    win_acct_pct: float
    # echo of deviation buffer (USD on the entry leg, for display)
    dev_usd: float
    # status — "ok" or a human-readable reason the sizing is degraded
    status: str = "ok"

    def as_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------- #
# Core computation
# --------------------------------------------------------------------------- #
def compute_spot_risk(
    capital: float,
    risk_pct: float,
    support: float,
    resistance: float,
    atr: float,
    deviation_pct: float,
    mode: str = "Long",
) -> SpotRiskResult:
    """
    Compute a position-sizing / risk plan.

    Parameters
    ----------
    capital        account size (USD)
    risk_pct       per-trade account risk, in percent (decides quantity)
    support        support price level
    resistance     resistance price level
    atr            Average True Range (volatility buffer for the stop)
    deviation_pct  entry/exit buffer, in percent (applied per price level)
    mode           "Long", "Spot" (== Long) or "Short"

    Returns
    -------
    SpotRiskResult. Never raises on bad market structure; instead returns a
    result with status != "ok" and zeroed sizing so the UI can show a hint
    without crashing.
    """
    dev = deviation_pct / 100.0

    if mode in ("Long", "Spot"):
        entry = support * (1 + dev)
        cut_loss = (support - atr) * (1 - dev)
        take_profit = resistance * (1 - dev)
        risk_ps = entry - cut_loss
        reward_ps = take_profit - entry
    elif mode == "Short":
        entry = resistance * (1 - dev)
        cut_loss = (resistance + atr) * (1 + dev)
        take_profit = support * (1 + dev)
        risk_ps = cut_loss - entry
        reward_ps = entry - take_profit
    else:
        raise ValueError(f"Unknown mode: {mode!r}")

    dev_usd = abs(entry - support) if mode in ("Long", "Spot") else abs(resistance - entry)

    # Guard: degenerate structure (e.g. ATR too large, support>=resistance).
    if risk_ps <= 0:
        return SpotRiskResult(
            entry=entry, cut_loss=cut_loss, take_profit=take_profit,
            risk_ps=risk_ps, reward_ps=reward_ps, rr=0.0,
            risk_budget=capital * risk_pct / 100.0, qty=0,
            capital_req=0.0, total_risk=0.0, total_win=0.0,
            risk_acct_pct=0.0, win_acct_pct=0.0, dev_usd=dev_usd,
            status="風險/股 ≤ 0 — 請檢查 支撐 / 壓力 / ATR（停損已穿越進場）",
        )

    rr = reward_ps / risk_ps
    risk_budget = capital * risk_pct / 100.0
    qty = int(floor(risk_budget / risk_ps)) if risk_ps > 0 else 0
    capital_req = qty * entry
    total_risk = qty * risk_ps
    total_win = qty * reward_ps
    risk_acct_pct = (total_risk / capital * 100.0) if capital else 0.0
    win_acct_pct = (total_win / capital * 100.0) if capital else 0.0

    status = "ok"
    if qty == 0:
        status = "資金不足以買進 1 股（風險預算 < 單股風險）"
    elif reward_ps <= 0:
        status = "報酬/股 ≤ 0 — 停利目標低於進場價"

    return SpotRiskResult(
        entry=entry, cut_loss=cut_loss, take_profit=take_profit,
        risk_ps=risk_ps, reward_ps=reward_ps, rr=rr,
        risk_budget=risk_budget, qty=qty, capital_req=capital_req,
        total_risk=total_risk, total_win=total_win,
        risk_acct_pct=risk_acct_pct, win_acct_pct=win_acct_pct,
        dev_usd=dev_usd, status=status,
    )


# --------------------------------------------------------------------------- #
# ATR(10) — Wilder's smoothing
# --------------------------------------------------------------------------- #
def wilder_atr(highs, lows, closes, period: int = 10) -> float:
    """
    Wilder's ATR over OHLC sequences. `highs/lows/closes` are equal-length
    sequences ordered oldest -> newest. Returns the most recent ATR value.

    Raises ValueError if there isn't enough data (need period+1 bars).
    """
    n = len(closes)
    if n < period + 1:
        raise ValueError(f"need at least {period + 1} bars, got {n}")

    trs = []
    for i in range(1, n):
        hl = highs[i] - lows[i]
        hc = abs(highs[i] - closes[i - 1])
        lc = abs(lows[i] - closes[i - 1])
        trs.append(max(hl, hc, lc))

    # Seed with simple average of first `period` TRs, then Wilder-smooth.
    atr = sum(trs[:period]) / period
    for tr in trs[period:]:
        atr = (atr * (period - 1) + tr) / period
    return atr


# --------------------------------------------------------------------------- #
# TradingView Game Plan generators
# --------------------------------------------------------------------------- #
def make_tv_note(ticker: str, mode: str, r: SpotRiskResult) -> str:
    """One-line plain-text summary suitable for a TradingView note."""
    return (
        f"{ticker} {mode}｜Entry {r.entry:.2f} / Stop {r.cut_loss:.2f} / "
        f"Target {r.take_profit:.2f}｜R:R {r.rr:.2f}｜{r.qty} shares｜"
        f"Risk ${r.total_risk:.2f} ({r.risk_acct_pct:.1f}%)"
    )


def make_pine_script(ticker: str, mode: str, r: SpotRiskResult) -> str:
    """Pine Script v5 snippet that draws entry/stop/target lines on the chart."""
    title = f"Spot Risk Game Plan — {ticker} {mode}"
    return (
        "//@version=5\n"
        f'indicator("{title}", overlay=true)\n'
        f"entry  = input.float({r.entry:.2f},  \"Entry\")\n"
        f"stop   = input.float({r.cut_loss:.2f},  \"Stop\")\n"
        f"target = input.float({r.take_profit:.2f}, \"Target\")\n"
        'hline(entry,  "Entry",  color=color.new(color.blue, 0),  '
        "linewidth=2, linestyle=hline.style_solid)\n"
        'hline(stop,   "Stop",   color=color.new(color.red, 0),   '
        "linewidth=2, linestyle=hline.style_dashed)\n"
        'hline(target, "Target", color=color.new(color.green, 0), '
        "linewidth=2, linestyle=hline.style_dashed)\n"
        "fill(hline(entry), hline(target), color=color.new(color.green, 90))\n"
        "fill(hline(entry), hline(stop),   color=color.new(color.red, 90))\n"
    )

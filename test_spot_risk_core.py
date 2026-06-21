"""
Acceptance tests for the Spot Risk Calculator core.

The golden numbers come from the build spec §2.2 (NVDA worked example, verified
against the author's voice-over). Tolerance ±0.05 per §9.
"""

import math

import pytest

from spot_risk_core import compute_spot_risk, wilder_atr, make_tv_note, make_pine_script

TOL = 0.05

NVDA = dict(
    capital=10000, risk_pct=1.0, support=200, resistance=221,
    atr=7.52, deviation_pct=0.4, mode="Long",
)


def test_nvda_long_golden_values():
    r = compute_spot_risk(**NVDA)
    assert r.status == "ok"
    assert math.isclose(r.entry, 200.80, abs_tol=TOL)
    assert math.isclose(r.cut_loss, 191.71, abs_tol=TOL)
    assert math.isclose(r.take_profit, 220.12, abs_tol=TOL)
    assert math.isclose(r.risk_ps, 9.09, abs_tol=TOL)
    assert math.isclose(r.reward_ps, 19.32, abs_tol=TOL)
    assert math.isclose(r.rr, 2.12, abs_tol=TOL)
    assert r.qty == 11
    assert math.isclose(r.capital_req, 2208.80, abs_tol=TOL)
    assert math.isclose(r.total_risk, 99.99, abs_tol=TOL)
    assert math.isclose(r.total_win, 212.48, abs_tol=TOL)
    assert math.isclose(r.risk_acct_pct, 1.00, abs_tol=0.01)


def test_total_risk_within_one_share_of_budget():
    """§9: total_risk ≈ risk_budget, difference ≤ one share of risk."""
    r = compute_spot_risk(**NVDA)
    assert r.risk_budget - r.total_risk <= r.risk_ps + TOL
    assert r.total_risk <= r.risk_budget + TOL


def test_spot_equals_long():
    long = compute_spot_risk(**{**NVDA, "mode": "Long"})
    spot = compute_spot_risk(**{**NVDA, "mode": "Spot"})
    assert long.as_dict() | {"status": spot.status} == spot.as_dict() | {"status": long.status}
    assert math.isclose(long.entry, spot.entry)
    assert math.isclose(long.cut_loss, spot.cut_loss)


def test_short_is_mirror_and_positive_risk():
    r = compute_spot_risk(**{**NVDA, "mode": "Short"})
    assert r.status == "ok"
    assert r.risk_ps > 0
    assert r.reward_ps > 0
    # Short enters below resistance, stops above it, targets above support.
    assert r.entry < 221
    assert r.cut_loss > r.entry
    assert r.take_profit > 200


def test_degenerate_structure_does_not_raise():
    """ATR so large the stop crosses entry -> status set, no exception."""
    r = compute_spot_risk(capital=10000, risk_pct=1, support=200,
                          resistance=221, atr=500, deviation_pct=0.4, mode="Long")
    assert r.status != "ok"
    assert r.qty == 0


def test_wilder_atr_basic():
    # Constant 1-wide bars -> ATR converges to 1.0
    highs = [101] * 20
    lows = [100] * 20
    closes = [100.5] * 20
    assert math.isclose(wilder_atr(highs, lows, closes, period=10), 1.0, abs_tol=1e-9)


def test_wilder_atr_needs_enough_bars():
    with pytest.raises(ValueError):
        wilder_atr([1, 2], [0, 1], [0.5, 1.5], period=10)


def test_game_plan_text():
    r = compute_spot_risk(**NVDA)
    note = make_tv_note("NVDA", "Long", r)
    assert "NVDA Long" in note
    assert "Entry 200.80" in note
    assert "11 shares" in note

    pine = make_pine_script("NVDA", "Long", r)
    assert "@version=5" in pine
    assert "200.80" in pine and "191.71" in pine and "220.12" in pine

# Spot Risk Calculator — Market-Sentinel edition

A single-page Streamlit tool that turns a **support / resistance / ATR** view
into a complete **position-sizing & risk plan**, plus a copy-paste **TradingView
Game Plan**. Built from `spot_risk_calculator_spec.md` (v2) with an upgraded,
commercial-grade dark UI.

## Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

Opens at http://localhost:8501.

## What it does

| Area | Feature |
|---|---|
| Inputs | Ticker (live name lookup), Long/Short/Spot, Capital, **Risk %** pills, ATR, Support, Resistance, **Deviation %** pills |
| Auto ATR | `⚡ Auto Grab ATR(10)` pulls the latest daily bar via yfinance and computes Wilder ATR(10) |
| Result | Entry / Cut Loss / Take Profit, Risk:Reward gauge, Quantity, Capital Required, Total Risk / Win, % of account — colour-coded |
| Game Plan | `Copy TV Note` (one-liner) and `Copy Pine Script` (v5 overlay with entry/stop/target lines) — both copy via the code-block icon |
| Persistence | Presets + saved calculations. Uses **Supabase** when `SUPABASE_URL`/`SUPABASE_KEY` are set, otherwise a local JSON store. Auto-falls-back if Supabase errors. |
| Export | `⬇ Download Excel` — styled .xlsx of the current plan |

## Formula note (important)

The spec's §3 code block uses a single dollar deviation
(`dev_usd = support × dev%`). That does **not** reproduce the spec's own §2.2
*measured* values (e.g. take_profit 220.20 vs measured 220.12 — fails ±0.05).

The measured numbers close **exactly** when deviation is applied as a
percentage of each price level, which is what this app implements:

```
entry       = support        × (1 + dev%)
cut_loss    = (support − atr) × (1 − dev%)
take_profit = resistance     × (1 − dev%)   # Short is the mirror
```

NVDA worked example (`capital 10000, risk 1%, support 200, resistance 221,
atr 7.52, dev 0.4%, Long`) → entry 200.80, stop 191.71, target 220.12,
R:R 2.12, 11 shares, total risk 99.99 — matches §2.2 to the cent.

## Tests

```bash
pytest test_spot_risk_core.py -q
```

8 tests cover the golden NVDA values, the risk-budget invariant, Long/Short
mirroring, the degenerate-structure guard, Wilder ATR, and the Game Plan output.

## Files

| File | Purpose |
|---|---|
| `app.py` | Streamlit UI (single page) |
| `spot_risk_core.py` | Pure math: `compute_spot_risk`, `wilder_atr`, Game Plan generators |
| `market_data.py` | `auto_grab_atr` via yfinance (graceful fallback) |
| `storage.py` | Supabase REST + local JSON, with auto-fallback |
| `excel_export.py` | Styled .xlsx export |
| `test_spot_risk_core.py` | pytest acceptance suite |

## Supabase

Tables `spot_risk_calculations` and `spot_risk_presets` (schema per spec §7)
live in the Market-Sentinel project (`yeuldzzstlriqpbtmsip`, ap-southeast-2).
Set credentials via `st.secrets` or environment:

```toml
# .streamlit/secrets.toml
SUPABASE_URL = "https://yeuldzzstlriqpbtmsip.supabase.co"
SUPABASE_KEY = "..."
```

> Both tables are created with **RLS disabled** (per spec §7, single-user). With
> the anon key that means anyone holding the key can read/write them — fine for a
> personal tool, but add Row-Level Security + a `user_id` policy before sharing.

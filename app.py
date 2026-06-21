"""
Spot Risk Calculator — Market-Sentinel edition
===============================================

A single-file Streamlit tool that turns a support/resistance/ATR view into a
full position-sizing & risk plan, plus a copy-paste TradingView Game Plan.

Run:  streamlit run app.py

Functional parity with spot_risk_calculator_spec.md (v2), with an upgraded,
commercial-grade dark UI. Pure math + tests live in spot_risk_core.py.
"""

from __future__ import annotations

import json
from datetime import date

import streamlit as st

import storage
from excel_export import build_excel
from market_data import auto_grab_atr, company_name
from spot_risk_core import compute_spot_risk, make_pine_script, make_tv_note

# --------------------------------------------------------------------------- #
# Page config + theme
# --------------------------------------------------------------------------- #
st.set_page_config(
    page_title="Spot Risk Calculator · Market-Sentinel",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed",
)

CSS = """
<style>
:root{
  --bg:#0b1120; --card:#111b30; --card2:#0f1830; --stroke:#1f2d49;
  --txt:#e7ecf5; --muted:#8da2c6; --accent:#3b82f6; --accent2:#6366f1;
  --green:#22c55e; --red:#ef4444; --amber:#f59e0b;
}
.stApp{
  background:
    radial-gradient(1200px 600px at 12% -10%, rgba(59,130,246,.16), transparent 60%),
    radial-gradient(900px 500px at 100% 0%, rgba(99,102,241,.14), transparent 55%),
    linear-gradient(180deg,#070c18 0%,#0b1120 40%,#080d19 100%);
  color:var(--txt);
}
#MainMenu, footer, header{visibility:hidden;}
.block-container{padding-top:1.2rem; max-width:1180px;}

/* hero */
.hero{
  display:flex; align-items:center; justify-content:space-between; gap:1rem;
  padding:22px 26px; border-radius:20px; margin-bottom:18px;
  background:linear-gradient(120deg, rgba(59,130,246,.18), rgba(99,102,241,.10));
  border:1px solid var(--stroke);
  box-shadow:0 10px 40px rgba(2,8,23,.5), inset 0 1px 0 rgba(255,255,255,.04);
}
.hero h1{font-size:1.55rem; margin:0; font-weight:800; letter-spacing:-.02em;
  background:linear-gradient(90deg,#fff,#bcd2ff); -webkit-background-clip:text;
  -webkit-text-fill-color:transparent;}
.hero p{margin:.25rem 0 0; color:var(--muted); font-size:.86rem;}
.badge{display:inline-flex; align-items:center; gap:.4rem; padding:5px 12px;
  border-radius:999px; font-size:.74rem; font-weight:600; color:#cde0ff;
  background:rgba(59,130,246,.16); border:1px solid rgba(59,130,246,.35);}

/* cards */
.card{
  background:linear-gradient(180deg,var(--card),var(--card2));
  border:1px solid var(--stroke); border-radius:18px; padding:18px 20px;
  margin-bottom:16px; box-shadow:0 8px 30px rgba(2,8,23,.35);
}
.card-title{font-size:.78rem; font-weight:700; letter-spacing:.14em;
  text-transform:uppercase; color:var(--muted); margin:0 0 12px;
  display:flex; align-items:center; gap:.5rem;}
.card-title .dot{width:8px;height:8px;border-radius:50%;
  background:linear-gradient(135deg,var(--accent),var(--accent2));
  box-shadow:0 0 12px var(--accent);}

/* result tiles */
.tiles{display:grid; grid-template-columns:repeat(3,1fr); gap:14px;}
.tile{border-radius:16px; padding:16px 18px; border:1px solid var(--stroke);
  background:rgba(255,255,255,.02); position:relative; overflow:hidden;}
.tile::before{content:""; position:absolute; left:0; top:0; bottom:0; width:4px;}
.tile.entry::before{background:var(--accent);}
.tile.stop::before{background:var(--red);}
.tile.target::before{background:var(--green);}
.tile .lab{font-size:.72rem; color:var(--muted); text-transform:uppercase;
  letter-spacing:.1em; font-weight:600;}
.tile .val{font-size:1.9rem; font-weight:800; margin:.2rem 0 .1rem;
  letter-spacing:-.02em;}
.tile.entry .val{color:#dbe9ff;}
.tile.stop .val{color:#ffd1d1;}
.tile.target .val{color:#c7f9d8;}
.tile .sub{font-size:.74rem; color:var(--muted);}

/* metric grid */
.mgrid{display:grid; grid-template-columns:repeat(5,1fr); gap:12px; margin-top:14px;}
.metric{background:rgba(255,255,255,.02); border:1px solid var(--stroke);
  border-radius:14px; padding:13px 14px; text-align:center;}
.metric .lab{font-size:.68rem; color:var(--muted); text-transform:uppercase;
  letter-spacing:.08em;}
.metric .val{font-size:1.25rem; font-weight:800; margin-top:4px;}
.metric .val.green{color:var(--green);} .metric .val.red{color:var(--red);}

/* R:R pill */
.rr{display:flex; align-items:center; gap:14px; margin:6px 0 2px;}
.rr .big{font-size:2.4rem; font-weight:900; letter-spacing:-.03em;}
.rr-pill{padding:6px 14px; border-radius:999px; font-weight:700; font-size:.8rem;}
.rr-good{background:rgba(34,197,94,.16); color:#7ef0a6; border:1px solid rgba(34,197,94,.4);}
.rr-mid{background:rgba(245,158,11,.16); color:#ffd591; border:1px solid rgba(245,158,11,.4);}
.rr-bad{background:rgba(239,68,68,.16); color:#ffb0b0; border:1px solid rgba(239,68,68,.4);}
.rr .meta{color:var(--muted); font-size:.82rem;}

/* gauge bar */
.gauge{height:8px;border-radius:999px;margin-top:10px;
  background:linear-gradient(90deg,var(--red),var(--amber),var(--green));
  position:relative;}
.gauge .pin{position:absolute; top:-4px; width:3px; height:16px; border-radius:2px;
  background:#fff; box-shadow:0 0 8px rgba(255,255,255,.8);}

/* inputs */
.stTextInput input, .stNumberInput input, .stDateInput input{
  background:#0c1526 !important; color:var(--txt) !important;
  border:1px solid var(--stroke) !important; border-radius:10px !important;}
.stButton>button, .stDownloadButton>button{
  border-radius:10px; border:1px solid var(--stroke);
  background:rgba(255,255,255,.03); color:var(--txt); font-weight:600;
  transition:.15s;}
.stButton>button:hover, .stDownloadButton>button:hover{
  border-color:var(--accent); color:#fff; background:rgba(59,130,246,.14);}
div[data-testid="stForm"]{border:none; padding:0;}
.small{color:var(--muted); font-size:.78rem;}
.warnote{background:rgba(245,158,11,.12); border:1px solid rgba(245,158,11,.35);
  border-radius:12px; padding:10px 14px; color:#ffe0ad; font-size:.82rem;}

/* ---- force dark on every Streamlit/BaseWeb widget (overrides inherited theme) ---- */
html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"], .main{
  background:transparent !important; color:var(--txt);
}
[data-testid="stHeader"]{background:transparent !important;}

/* link buttons (← Back To Dashboard) */
[data-testid="stLinkButton"] a, a[data-testid^="stBaseLinkButton"]{
  background:rgba(255,255,255,.03) !important; color:var(--txt) !important;
  border:1px solid var(--stroke) !important; border-radius:10px !important;
  font-weight:600 !important;
}
[data-testid="stLinkButton"] a:hover{
  border-color:var(--accent) !important; color:#fff !important;
  background:rgba(59,130,246,.14) !important;
}

/* primary button -> accent gradient, white text */
button[kind="primary"], button[data-testid="stBaseButton-primary"]{
  background:linear-gradient(135deg,var(--accent),var(--accent2)) !important;
  color:#fff !important; border:none !important; font-weight:700 !important;
}

/* secondary / download / refresh buttons text always visible */
button[kind="secondary"], button[data-testid="stBaseButton-secondary"],
.stDownloadButton button{ color:var(--txt) !important; }
button[kind="secondary"] p, .stButton button p, .stDownloadButton button p{
  color:var(--txt) !important;
}

/* selectbox (closed control) */
[data-baseweb="select"] > div{
  background:#0c1526 !important; border:1px solid var(--stroke) !important;
  color:var(--txt) !important;
}
[data-baseweb="select"] div, [data-baseweb="select"] span,
[data-baseweb="select"] input{ color:var(--txt) !important; }
[data-baseweb="select"] svg{ fill:var(--muted) !important; }

/* selectbox dropdown menu + date picker popover */
[data-baseweb="popover"] div, [data-baseweb="menu"], ul[role="listbox"]{
  background:#0c1526 !important; color:var(--txt) !important;
  border:1px solid var(--stroke) !important;
}
li[role="option"], [role="option"]{ background:#0c1526 !important; color:var(--txt) !important; }
li[role="option"]:hover, [aria-selected="true"]{ background:rgba(59,130,246,.20) !important; }

/* textarea (Note) */
.stTextArea textarea{
  background:#0c1526 !important; color:var(--txt) !important;
  border:1px solid var(--stroke) !important;
}

/* metrics inside Past Calculations */
[data-testid="stMetricValue"]{ color:var(--txt) !important; }
[data-testid="stMetricLabel"], [data-testid="stMetricLabel"] p{ color:var(--muted) !important; }

/* expander (Past Calculations rows) */
[data-testid="stExpander"] details{
  background:rgba(255,255,255,.02) !important; border:1px solid var(--stroke) !important;
  border-radius:12px !important;
}
[data-testid="stExpander"] summary, [data-testid="stExpander"] summary p,
[data-testid="stExpander"] summary svg{ color:var(--txt) !important; fill:var(--txt) !important; }

/* radio (Mode) + slider labels */
[data-testid="stRadio"] label, [data-testid="stRadio"] label p,
[data-testid="stSelectSlider"] label, [data-testid="stSelectSlider"] div{
  color:var(--txt) !important;
}

/* pills */
[data-testid="stPills"] button{ color:var(--txt) !important; }
[data-testid="stPills"] button[aria-checked="true"]{
  background:linear-gradient(135deg,var(--accent),var(--accent2)) !important;
  color:#fff !important; border-color:transparent !important;
}

/* number-input +/- steppers */
.stNumberInput button{ background:#0c1526 !important; color:var(--txt) !important;
  border:1px solid var(--stroke) !important; }

@media (max-width:780px){
  .tiles{grid-template-columns:1fr;} .mgrid{grid-template-columns:repeat(2,1fr);}
  .hero{flex-direction:column; align-items:flex-start;}
}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Session defaults
# --------------------------------------------------------------------------- #
DEFAULTS = dict(
    ticker="NVDA", mode="Long", setup_date=date.today(),
    capital=10000.0, risk_pct=1.0, atr=7.52,
    support=200.0, resistance=221.0, deviation_pct=0.4,
    position_mood="Neutral", note="",
)
for k, v in DEFAULTS.items():
    st.session_state.setdefault(k, v)
st.session_state.setdefault("atr_hint", "")


def _apply_payload(payload: dict):
    for k in DEFAULTS:
        if k in payload:
            val = payload[k]
            if k == "setup_date" and isinstance(val, str):
                try:
                    val = date.fromisoformat(val)
                except Exception:
                    val = date.today()
            st.session_state[k] = val


# --------------------------------------------------------------------------- #
# Hero + top action bar
# --------------------------------------------------------------------------- #
st.markdown(
    f"""
    <div class="hero">
      <div>
        <h1>🎯 Spot Risk Calculator</h1>
        <p>Support / Resistance / ATR → entry · stop · target · size · TradingView game plan</p>
      </div>
      <div style="text-align:right">
        <span class="badge">● Market-Sentinel</span>
        <div class="small" style="margin-top:8px">Storage: {storage.backend_name()}</div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

ab1, ab2, ab3, ab4 = st.columns([1.1, 1.1, 1.2, 3])
with ab1:
    st.link_button("← Back To Dashboard", "https://market-sentinel.streamlit.app",
                   use_container_width=True)
with ab2:
    if st.button("⟳ Refresh Local Tool", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
# (Download button rendered after compute, needs result)


# --------------------------------------------------------------------------- #
# Presets row
# --------------------------------------------------------------------------- #
presets = storage.load_presets()
with st.container():
    st.markdown('<div class="card"><div class="card-title"><span class="dot"></span>Preset</div>',
                unsafe_allow_html=True)
    pc1, pc2, pc3 = st.columns([2.4, 1, 1])
    with pc1:
        choice = st.selectbox(
            "載入已存設定", ["Start a fresh setup"] + sorted(presets.keys()),
            label_visibility="collapsed",
        )
        if choice != "Start a fresh setup" and st.session_state.get("_loaded") != choice:
            _apply_payload(presets[choice])
            st.session_state["_loaded"] = choice
            st.toast(f"已載入 Preset：{choice}")
            st.rerun()
    with pc2:
        new_name = st.text_input("Preset 名稱", placeholder="存成 Preset…",
                                 label_visibility="collapsed")
    with pc3:
        if st.button("💾 Save Preset", use_container_width=True):
            if new_name.strip():
                payload = {k: (st.session_state[k].isoformat()
                               if isinstance(st.session_state[k], date)
                               else st.session_state[k]) for k in DEFAULTS}
                try:
                    storage.save_preset(new_name.strip(), payload)
                    st.toast(f"Preset「{new_name.strip()}」已儲存")
                    st.rerun()
                except Exception as e:
                    st.warning(f"Preset 儲存失敗：{e}")
            else:
                st.toast("請先輸入 Preset 名稱")
    st.markdown("</div>", unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Inputs (two columns of cards)
# --------------------------------------------------------------------------- #
left, right = st.columns(2)

with left:
    # Setup card
    st.markdown('<div class="card"><div class="card-title"><span class="dot"></span>Setup</div>',
                unsafe_allow_html=True)
    st.session_state.ticker = st.text_input("Ticker", st.session_state.ticker).upper().strip()
    cname = None
    if st.session_state.ticker:
        cname = company_name(st.session_state.ticker)
    if cname:
        st.markdown(f'<div class="small">📈 {st.session_state.ticker} — {cname}</div>',
                    unsafe_allow_html=True)
    mc1, mc2 = st.columns(2)
    with mc1:
        st.session_state.mode = st.radio(
            "Mode", ["Long", "Short", "Spot"],
            index=["Long", "Short", "Spot"].index(st.session_state.mode),
            horizontal=True,
        )
    with mc2:
        st.session_state.setup_date = st.date_input("Setup Date", st.session_state.setup_date)
    st.markdown("</div>", unsafe_allow_html=True)

    # Capital / Risk card
    st.markdown('<div class="card"><div class="card-title"><span class="dot"></span>Capital &amp; Risk</div>',
                unsafe_allow_html=True)
    st.session_state.capital = st.number_input(
        "Capital (USD)", min_value=0.0, value=float(st.session_state.capital), step=500.0,
    )
    st.markdown('<div class="small">Risk % of account（決定股數）</div>', unsafe_allow_html=True)
    risk_opts = [0.1, 0.25, 0.5, 0.75, 1.0, 2.0]
    picked = st.pills("Risk %", risk_opts,
                      selection_mode="single",
                      default=st.session_state.risk_pct if st.session_state.risk_pct in risk_opts else None,
                      format_func=lambda x: f"{x:g}%", label_visibility="collapsed")
    if picked is not None:
        st.session_state.risk_pct = float(picked)
    st.session_state.risk_pct = st.number_input(
        "或手動輸入 Risk %", min_value=0.0, max_value=100.0,
        value=float(st.session_state.risk_pct), step=0.1, format="%.2f",
    )
    st.markdown("</div>", unsafe_allow_html=True)

with right:
    # Price structure card
    st.markdown('<div class="card"><div class="card-title"><span class="dot"></span>Price Structure</div>',
                unsafe_allow_html=True)
    ac1, ac2 = st.columns([2, 1])
    with ac1:
        st.session_state.atr = st.number_input(
            "ATR (volatility)", min_value=0.0, value=float(st.session_state.atr),
            step=0.01, format="%.2f",
        )
    with ac2:
        st.markdown('<div style="height:28px"></div>', unsafe_allow_html=True)
        if st.button("⚡ Auto Grab ATR(10)", use_container_width=True):
            atr_val, _bar, msg = auto_grab_atr(st.session_state.ticker)
            st.session_state.atr_hint = msg
            if atr_val is not None:
                st.session_state.atr = float(atr_val)
                st.rerun()
    if st.session_state.atr_hint:
        st.markdown(f'<div class="small">{st.session_state.atr_hint}</div>',
                    unsafe_allow_html=True)

    sc1, sc2 = st.columns(2)
    with sc1:
        st.session_state.support = st.number_input(
            "Support", min_value=0.0, value=float(st.session_state.support),
            step=0.5, format="%.2f")
    with sc2:
        st.session_state.resistance = st.number_input(
            "Resistance", min_value=0.0, value=float(st.session_state.resistance),
            step=0.5, format="%.2f")

    st.markdown('<div class="small">Deviation %（進出場緩衝，與 Risk% 不同）</div>',
                unsafe_allow_html=True)
    dev_opts = [0.1, 0.2, 0.3, 0.4, 0.5, 0.75, 1.0]
    dpick = st.pills("Deviation %", dev_opts, selection_mode="single",
                     default=st.session_state.deviation_pct if st.session_state.deviation_pct in dev_opts else None,
                     format_func=lambda x: f"{x:g}%", label_visibility="collapsed")
    if dpick is not None:
        st.session_state.deviation_pct = float(dpick)
    st.session_state.deviation_pct = st.number_input(
        "或手動輸入 Deviation %", min_value=0.0, max_value=10.0,
        value=float(st.session_state.deviation_pct), step=0.05, format="%.2f")
    st.markdown("</div>", unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Compute
# --------------------------------------------------------------------------- #
res = compute_spot_risk(
    capital=st.session_state.capital, risk_pct=st.session_state.risk_pct,
    support=st.session_state.support, resistance=st.session_state.resistance,
    atr=st.session_state.atr, deviation_pct=st.session_state.deviation_pct,
    mode=st.session_state.mode,
)

# Download Original / current Excel (now that we have a result)
with ab3:
    try:
        xls = build_excel(
            ticker=st.session_state.ticker, mode=st.session_state.mode,
            setup_date=st.session_state.setup_date, capital=st.session_state.capital,
            risk_pct=st.session_state.risk_pct, support=st.session_state.support,
            resistance=st.session_state.resistance,
            deviation_pct=st.session_state.deviation_pct, atr=st.session_state.atr,
            result=res,
        )
        st.download_button(
            "⬇ Download Excel", data=xls,
            file_name=f"spot_risk_{st.session_state.ticker or 'plan'}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    except Exception as e:
        st.button("⬇ Excel (error)", disabled=True, use_container_width=True,
                  help=str(e))


# --------------------------------------------------------------------------- #
# Result card
# --------------------------------------------------------------------------- #
def fmt(x):
    return f"{x:,.2f}"


if res.status != "ok":
    st.markdown(f'<div class="warnote">⚠️ {res.status}</div>', unsafe_allow_html=True)

# R:R styling
if res.rr >= 2:
    rr_cls, rr_lbl = "rr-good", "Strong (≥ 2.0)"
elif res.rr >= 1:
    rr_cls, rr_lbl = "rr-mid", "Marginal (1–2)"
else:
    rr_cls, rr_lbl = "rr-bad", "Weak (< 1.0)"
gauge_pin = max(2, min(98, (res.rr / 3.0) * 100)) if res.rr else 2

st.markdown(
    f"""
    <div class="card">
      <div class="card-title"><span class="dot"></span>Result · {st.session_state.ticker} {st.session_state.mode}</div>
      <div class="tiles">
        <div class="tile entry">
          <div class="lab">Entry</div><div class="val">{fmt(res.entry)}</div>
          <div class="sub">進場價（含 {st.session_state.deviation_pct:g}% 緩衝）</div>
        </div>
        <div class="tile stop">
          <div class="lab">Cut Loss</div><div class="val">{fmt(res.cut_loss)}</div>
          <div class="sub">停損 · risk/share {fmt(res.risk_ps)}</div>
        </div>
        <div class="tile target">
          <div class="lab">Take Profit</div><div class="val">{fmt(res.take_profit)}</div>
          <div class="sub">停利 · reward/share {fmt(res.reward_ps)}</div>
        </div>
      </div>

      <div class="rr">
        <div class="big">{res.rr:.2f}</div>
        <span class="rr-pill {rr_cls}">R : R · {rr_lbl}</span>
        <span class="meta">reward {fmt(res.reward_ps)} vs risk {fmt(res.risk_ps)}</span>
      </div>
      <div class="gauge"><div class="pin" style="left:{gauge_pin:.0f}%"></div></div>

      <div class="mgrid">
        <div class="metric"><div class="lab">Quantity</div><div class="val">{res.qty:,}</div></div>
        <div class="metric"><div class="lab">Capital Req.</div><div class="val">{fmt(res.capital_req)}</div></div>
        <div class="metric"><div class="lab">Total Risk</div><div class="val red">{fmt(res.total_risk)}</div></div>
        <div class="metric"><div class="lab">Total Win</div><div class="val green">{fmt(res.total_win)}</div></div>
        <div class="metric"><div class="lab">% of Account</div>
          <div class="val"><span class="red">{res.risk_acct_pct:.2f}%</span> / <span class="green">{res.win_acct_pct:.2f}%</span></div></div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------------------------------- #
# Game Plan card
# --------------------------------------------------------------------------- #
st.markdown('<div class="card"><div class="card-title"><span class="dot"></span>TradingView Game Plan</div>',
            unsafe_allow_html=True)
note = make_tv_note(st.session_state.ticker, st.session_state.mode, res)
pine = make_pine_script(st.session_state.ticker, st.session_state.mode, res)
gp1, gp2 = st.columns(2)
with gp1:
    st.markdown('<div class="small">Copy TV Note（用右上角圖示複製）</div>', unsafe_allow_html=True)
    st.code(note, language="text")
with gp2:
    st.markdown('<div class="small">Copy Pine Script（用右上角圖示複製）</div>', unsafe_allow_html=True)
    st.code(pine, language="javascript")
st.markdown("</div>", unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Mood + Note + Save / Clear
# --------------------------------------------------------------------------- #
st.markdown('<div class="card"><div class="card-title"><span class="dot"></span>Mood &amp; Note</div>',
            unsafe_allow_html=True)
moods = ["Confident", "Neutral", "Cautious", "FOMO", "Patient"]
st.session_state.position_mood = st.select_slider(
    "Position mood", moods,
    value=st.session_state.position_mood if st.session_state.position_mood in moods else "Neutral")
st.session_state.note = st.text_area("備註", st.session_state.note,
                                     placeholder="觀察、催化劑、要等的訊號…", height=80)

bcol1, bcol2, _ = st.columns([1, 1, 3])
with bcol1:
    if st.button("💾 Save This Calculation", use_container_width=True, type="primary"):
        record = {
            "ticker": st.session_state.ticker, "mode": st.session_state.mode,
            "setup_date": st.session_state.setup_date.isoformat(),
            "capital": st.session_state.capital, "risk_pct": st.session_state.risk_pct,
            "atr": st.session_state.atr, "support": st.session_state.support,
            "resistance": st.session_state.resistance,
            "deviation_pct": st.session_state.deviation_pct,
            **{k: getattr(res, k) for k in (
                "dev_usd", "entry", "cut_loss", "take_profit", "risk_ps",
                "reward_ps", "rr", "qty", "capital_req", "total_risk",
                "total_win", "risk_acct_pct", "win_acct_pct")},
            "position_mood": st.session_state.position_mood,
            "note": st.session_state.note,
        }
        try:
            storage.save_calculation(record)
            st.toast("已存入 Past Calculations ✅")
            st.rerun()
        except Exception as e:
            st.warning(f"儲存失敗（不影響計算）：{e}")
with bcol2:
    if st.button("🧹 Clear Form", use_container_width=True):
        for k, v in DEFAULTS.items():
            st.session_state[k] = v
        st.session_state["_loaded"] = None
        st.session_state.atr_hint = ""
        st.rerun()
st.markdown("</div>", unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Past Calculations
# --------------------------------------------------------------------------- #
st.markdown('<div class="card"><div class="card-title"><span class="dot"></span>Past Calculations</div>',
            unsafe_allow_html=True)
rows = []
try:
    rows = storage.load_calculations(limit=30)
except Exception as e:
    st.warning(f"讀取歷史失敗：{e}")

if not rows:
    st.markdown('<div class="small">尚無紀錄。算好一筆後按 “Save This Calculation”。</div>',
                unsafe_allow_html=True)
else:
    for row in rows:
        created = str(row.get("created_at", ""))[:16].replace("T", " ")
        label = (f"{row.get('ticker','?')} · {row.get('mode','')} · "
                 f"R:R {float(row.get('rr',0)):.2f} · {row.get('qty','?')} sh · {created}")
        with st.expander(label):
            ec1, ec2, ec3, ec4 = st.columns(4)
            ec1.metric("Entry", f"{float(row.get('entry',0)):.2f}")
            ec2.metric("Stop", f"{float(row.get('cut_loss',0)):.2f}")
            ec3.metric("Target", f"{float(row.get('take_profit',0)):.2f}")
            ec4.metric("Total Risk", f"{float(row.get('total_risk',0)):.2f}")
            if row.get("note"):
                st.markdown(f'<div class="small">📝 {row["note"]}</div>', unsafe_allow_html=True)
            lc1, lc2 = st.columns([1, 1])
            with lc1:
                if st.button("↩ Load 回填", key=f"load_{row.get('id')}", use_container_width=True):
                    _apply_payload(row)
                    st.session_state["_loaded"] = None
                    st.toast("已回填此筆設定")
                    st.rerun()
            with lc2:
                if st.button("🗑 Delete", key=f"del_{row.get('id')}", use_container_width=True):
                    try:
                        storage.delete_calculation(row.get("id"))
                        st.rerun()
                    except Exception as e:
                        st.warning(f"刪除失敗：{e}")
st.markdown("</div>", unsafe_allow_html=True)

st.markdown(
    '<div class="small" style="text-align:center;margin-top:8px">'
    'Position-sizing math only · not financial advice · '
    'verified against spec §2.2 (NVDA worked example).</div>',
    unsafe_allow_html=True,
)

"""
Persistence for the Spot Risk Calculator.

Two backends:

  * Supabase (REST)  — used when both SUPABASE_URL and SUPABASE_KEY are present
                       in st.secrets or the environment. Tables per spec §7.
  * Local JSON       — zero-config fallback, stored next to this file.

Design rule (spec §8): a backend never crashes the app. Every Supabase call is
wrapped; on ANY failure (missing table, network, auth) the call transparently
falls back to the local JSON store and the session is flagged degraded so the
UI can show the real backend in use.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

_DATA_DIR = Path(__file__).parent / "_data"
_CALC_FILE = _DATA_DIR / "calculations.json"
_PRESET_FILE = _DATA_DIR / "presets.json"

# Set True the first time a Supabase call fails, so we stop pretending and the
# header reports the backend honestly for the rest of the session.
_DEGRADED = False
_LAST_ERROR = ""


# --------------------------------------------------------------------------- #
# Backend selection
# --------------------------------------------------------------------------- #
def _secret(key: str) -> str | None:
    try:
        import streamlit as st

        if key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        pass
    return os.environ.get(key)


def _supabase_cfg() -> tuple[str, str] | None:
    if _DEGRADED:
        return None
    url, key = _secret("SUPABASE_URL"), _secret("SUPABASE_KEY")
    if url and key:
        if not url.startswith("http"):
            url = "https://" + url
        return url.rstrip("/"), key
    return None


def backend_name() -> str:
    return "Supabase" if _supabase_cfg() else "Local"


def last_error() -> str:
    return _LAST_ERROR


def _degrade(err: Exception) -> None:
    global _DEGRADED, _LAST_ERROR
    _DEGRADED = True
    _LAST_ERROR = f"{type(err).__name__}: {err}"


# --------------------------------------------------------------------------- #
# Local JSON helpers
# --------------------------------------------------------------------------- #
def _read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def _write_json(path: Path, data: Any) -> None:
    _DATA_DIR.mkdir(exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str),
                    encoding="utf-8")


# --------------------------------------------------------------------------- #
# Supabase REST helpers
# --------------------------------------------------------------------------- #
def _sb_headers(key: str, prefer: str = "return=representation") -> dict:
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": prefer,
    }


# --------------------------------------------------------------------------- #
# Calculations
# --------------------------------------------------------------------------- #
def save_calculation(record: dict) -> dict:
    record = dict(record)
    record.setdefault("id", str(uuid.uuid4()))
    record.setdefault("created_at", datetime.now(timezone.utc).isoformat())

    cfg = _supabase_cfg()
    if cfg:
        try:
            url, key = cfg
            r = requests.post(f"{url}/rest/v1/spot_risk_calculations",
                              headers=_sb_headers(key),
                              data=json.dumps(record, default=str), timeout=10)
            r.raise_for_status()
            out = r.json()
            return out[0] if isinstance(out, list) and out else record
        except Exception as e:
            _degrade(e)

    rows = _read_json(_CALC_FILE, [])
    rows.insert(0, record)
    _write_json(_CALC_FILE, rows)
    return record


def load_calculations(limit: int = 50) -> list[dict]:
    cfg = _supabase_cfg()
    if cfg:
        try:
            url, key = cfg
            r = requests.get(
                f"{url}/rest/v1/spot_risk_calculations"
                f"?select=*&order=created_at.desc&limit={limit}",
                headers=_sb_headers(key), timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            _degrade(e)

    return _read_json(_CALC_FILE, [])[:limit]


def delete_calculation(calc_id: str) -> None:
    cfg = _supabase_cfg()
    if cfg:
        try:
            url, key = cfg
            r = requests.delete(
                f"{url}/rest/v1/spot_risk_calculations?id=eq.{calc_id}",
                headers=_sb_headers(key), timeout=10)
            r.raise_for_status()
            return
        except Exception as e:
            _degrade(e)

    rows = [r for r in _read_json(_CALC_FILE, []) if r.get("id") != calc_id]
    _write_json(_CALC_FILE, rows)


# --------------------------------------------------------------------------- #
# Presets
# --------------------------------------------------------------------------- #
def save_preset(name: str, payload: dict) -> None:
    cfg = _supabase_cfg()
    if cfg:
        try:
            url, key = cfg
            r = requests.post(
                f"{url}/rest/v1/spot_risk_presets?on_conflict=name",
                headers=_sb_headers(key, "resolution=merge-duplicates,return=representation"),
                data=json.dumps({"name": name, "payload": payload}, default=str),
                timeout=10)
            r.raise_for_status()
            return
        except Exception as e:
            _degrade(e)

    presets = _read_json(_PRESET_FILE, {})
    presets[name] = payload
    _write_json(_PRESET_FILE, presets)


def load_presets() -> dict[str, dict]:
    cfg = _supabase_cfg()
    if cfg:
        try:
            url, key = cfg
            r = requests.get(
                f"{url}/rest/v1/spot_risk_presets?select=name,payload&order=name.asc",
                headers=_sb_headers(key), timeout=10)
            r.raise_for_status()
            return {row["name"]: row["payload"] for row in r.json()}
        except Exception as e:
            _degrade(e)

    return _read_json(_PRESET_FILE, {})


def delete_preset(name: str) -> None:
    cfg = _supabase_cfg()
    if cfg:
        try:
            url, key = cfg
            r = requests.delete(f"{url}/rest/v1/spot_risk_presets?name=eq.{name}",
                                headers=_sb_headers(key), timeout=10)
            r.raise_for_status()
            return
        except Exception as e:
            _degrade(e)

    presets = _read_json(_PRESET_FILE, {})
    presets.pop(name, None)
    _write_json(_PRESET_FILE, presets)

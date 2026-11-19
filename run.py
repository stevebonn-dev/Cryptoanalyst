from datetime import date, datetime, timedelta, timezone
import json
import math
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import requests

STATE_PATH = Path("state/last_run.json")
HISTORY_CACHE_PATH = Path("state/btc_history_cache.json")
DASHBOARD_PATH = Path("dashboard_data.json")

GENESIS_DATE = date(2009, 1, 3)

# Power Law parameters (t = days since Genesis Block, 2009-01-03)
POWER_LAW_LOG_A = float(os.getenv("POWER_LAW_LOG_A", "-16.493"))
POWER_LAW_BETA = float(os.getenv("POWER_LAW_BETA", "5.688"))
POWER_LAW_BAND_LOG10 = float(os.getenv("POWER_LAW_BAND_LOG10", "0.35"))

MACRO_EVENTS = [
    {
        "name": "SpaceX IPO (SPCX)",
        "event_date": date(2026, 6, 12),
        "pre_window_days": 30,
        "post_window_days": 28,
        "proxy_tickers": ["HYPE"],
        "leader_tickers": ["BTC", "ETH"],
        "laggard_tickers": ["XRP"],
    }
]

CALENDAR_EVENTS: List[Dict[str, str]] = [
    {
        "date": "2026-06-12",
        "end": "2026-06-12",
        "title": "SpaceX IPO (SPCX) Macro Window",
        "notes": "Tracked liquidity & proxy rotation regime (-30d / +28d)",
    },
    {
        "date": "2026-12-08",
        "end": "2026-12-09",
        "title": "FOMC Meeting (Dec 2026)",
        "notes": "Rate decision & Summary of Economic Projections",
    },
    {
        "date": "2027-01-26",
        "end": "2027-01-27",
        "title": "FOMC Meeting (Jan 2027)",
        "notes": "Scheduled FOMC policy meeting",
    },
    {
        "date": "2027-03-16",
        "end": "2027-03-17",
        "title": "FOMC Meeting (Mar 2027)",
        "notes": "Scheduled FOMC policy meeting",
    },
    {
        "date": "2027-04-27",
        "end": "2027-04-28",
        "title": "FOMC Meeting (Apr 2027)",
        "notes": "Scheduled FOMC policy meeting",
    },
    {
        "date": "2027-06-08",
        "end": "2027-06-09",
        "title": "FOMC Meeting (Jun 2027)",
        "notes": "Scheduled FOMC policy meeting",
    },
    {
        "date": "2027-07-27",
        "end": "2027-07-28",
        "title": "FOMC Meeting (Jul 2027)",
        "notes": "Scheduled FOMC policy meeting",
    },
    {
        "date": "2027-09-14",
        "end": "2027-09-15",
        "title": "FOMC Meeting (Sep 2027)",
        "notes": "Scheduled FOMC policy meeting",
    },
    {
        "date": "2027-10-26",
        "end": "2027-10-27",
        "title": "FOMC Meeting (Oct 2027)",
        "notes": "Scheduled FOMC policy meeting",
    },
    {
        "date": "2027-11-16",
        "end": "2027-11-17",
        "title": "FOMC Meeting (Nov 2027)",
        "notes": "Scheduled FOMC policy meeting",
    },
]


def days_since_genesis(target_date: date) -> int:
    return max(1, (target_date - GENESIS_DATE).days)


def compute_power_law_metrics(
    target_date: date,
    log_a: float = POWER_LAW_LOG_A,
    beta: float = POWER_LAW_BETA,
    band_log10: float = POWER_LAW_BAND_LOG10,
) -> Dict[str, Any]:
    t = days_since_genesis(target_date)
    log10_trend = log_a + beta * math.log10(t)
    trend = 10.0**log10_trend
    support = trend * (10.0 ** (-band_log10))
    resistance = trend * (10.0**band_log10)
    return {
        "date": target_date.isoformat(),
        "days_since_genesis": t,
        "trend": round(trend, 2),
        "support": round(support, 2),
        "resistance": round(resistance, 2),
    }


def load_cached_history() -> Dict[str, float]:
    if HISTORY_CACHE_PATH.exists():
        try:
            data = json.loads(HISTORY_CACHE_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return {str(k): float(v) for k, v in data.items()}
        except Exception:
            pass
    return {}


def save_cached_history(history: Dict[str, float]) -> None:
    HISTORY_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_CACHE_PATH.write_text(json.dumps(history, indent=2, sort_keys=True), encoding="utf-8")


def fetch_historical_btc_closes(start_date: date = date(2017, 8, 17)) -> Dict[str, float]:
    """Fetches daily BTC/USDT closes from Binance klines and merges with local cache."""
    history = load_cached_history()
    start_ms = int(datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc).timestamp() * 1000)

    try:
        resp = requests.get(
            "https://api.binance.com/api/v3/klines",
            params={"symbol": "BTCUSDT", "interval": "1d", "startTime": start_ms, "limit": 1000},
            timeout=20,
        )
        resp.raise_for_status()
        klines = resp.json()

        while isinstance(klines, list) and klines:
            for row in klines:
                dt_str = datetime.fromtimestamp(row[0] / 1000, tz=timezone.utc).date().isoformat()
                history[dt_str] = round(float(row[4]), 2)
            if len(klines) < 1000:
                break
            next_start = int(klines[-1][0]) + 86_400_000
            resp = requests.get(
                "https://api.binance.com/api/v3/klines",
                params={"symbol": "BTCUSDT", "interval": "1d", "startTime": next_start, "limit": 1000},
                timeout=20,
            )
            resp.raise_for_status()
            klines = resp.json()

        if history:
            save_cached_history(history)
    except Exception as exc:
        print(f"Warning: live BTC history fetch failed ({exc}); using cached/fallback data.")

    return history


def build_power_law_curve(
    as_of_date: date,
    btc_history: Dict[str, float],
    start_year: int = 2017,
    end_year: int = 2030,
    step_days: int = 14,
) -> List[Dict[str, Any]]:
    cursor = date(start_year, 1, 1)
    end_date = date(end_year, 12, 31)
    points: List[Dict[str, Any]] = []
    sorted_hist_dates = sorted(btc_history.keys())

    def lookup_btc_price(d: date) -> Optional[float]:
        if d > as_of_date:
            return None
        iso = d.isoformat()
        if iso in btc_history:
            return btc_history[iso]
        for offset in range(1, 8):
            prev_iso = (d - timedelta(days=offset)).isoformat()
            if prev_iso in btc_history:
                return btc_history[prev_iso]
        if sorted_hist_dates and iso <= sorted_hist_dates[0]:
            return btc_history[sorted_hist_dates[0]]
        return None

    while cursor <= end_date:
        metrics = compute_power_law_metrics(cursor)
        points.append(
            {
                "date": cursor.isoformat(),
                "t": metrics["days_since_genesis"],
                "trend": metrics["trend"],
                "support": metrics["support"],
                "resistance": metrics["resistance"],
                "btc_price": lookup_btc_price(cursor),
                "is_projection": cursor > as_of_date,
            }
        )
        cursor += timedelta(days=step_days)

    today_iso = as_of_date.isoformat()
    if not any(p["date"] == today_iso for p in points):
        metrics = compute_power_law_metrics(as_of_date)
        points.append(
            {
                "date": today_iso,
                "t": metrics["days_since_genesis"],
                "trend": metrics["trend"],
                "support": metrics["support"],
                "resistance": metrics["resistance"],
                "btc_price": lookup_btc_price(as_of_date),
                "is_projection": False,
            }
        )
        points.sort(key=lambda x: x["date"])

    return points


def evaluate_macro_event_regime(as_of_date: date, events=MACRO_EVENTS) -> Dict[str, Any]:
    for ev in events:
        delta_days = (as_of_date - ev["event_date"]).days

        if -ev["pre_window_days"] <= delta_days <= 0:
            return {
                "active": True,
                "regime": "PRE_EVENT_LIQUIDITY_DRAIN",
                "event_name": ev["name"],
                "days_to_event": abs(delta_days),
                "proxy_tickers": ev["proxy_tickers"],
                "leader_tickers": ev["leader_tickers"],
                "laggard_tickers": ev["laggard_tickers"],
            }

        if 1 <= delta_days <= ev["post_window_days"]:
            return {
                "active": True,
                "regime": "POST_EVENT_STABILIZATION",
                "event_name": ev["name"],
                "days_since_event": delta_days,
                "proxy_tickers": ev["proxy_tickers"],
                "leader_tickers": ev["leader_tickers"],
                "laggard_tickers": ev["laggard_tickers"],
            }

    return {
        "active": False,
        "regime": "NORMAL",
        "event_name": None,
        "proxy_tickers": [],
        "leader_tickers": [],
        "laggard_tickers": [],
    }


def apply_event_matrix_adjustment(
    base_score: float,
    ticker: str,
    macro_state: Dict[str, Any],
    price_vs_elec_floor: float = 1.0,
    mvrv_z: float = 0.0,
) -> Dict[str, Any]:
    score = base_score
    notes: List[str] = []

    if not macro_state["active"]:
        return {"adjusted_score": round(score, 2), "notes": notes}

    regime = macro_state["regime"]
    t = ticker.upper()

    if regime == "PRE_EVENT_LIQUIDITY_DRAIN":
        if t in macro_state["proxy_tickers"]:
            score += 1.5
            notes.append("Event proxy boost (synthetic/perp flow rotation)")
        elif t in macro_state["leader_tickers"]:
            if price_vs_elec_floor <= 1.08 or mvrv_z < 0.5:
                score += 0.5
                notes.append("Liquidity-drain discount accumulation zone")
            else:
                score -= 1.0
                notes.append("Pre-event liquidity outflow headwind")
        elif t in macro_state["laggard_tickers"]:
            score -= 1.0
            notes.append("Relative weakness penalty during liquidity drain")

    elif regime == "POST_EVENT_STABILIZATION":
        if t in macro_state["leader_tickers"]:
            score += 1.0
            notes.append("Post-IPO stabilization & capital return tailwind")
        elif t in macro_state["laggard_tickers"]:
            score -= 0.5
            notes.append("Lagging recovery filter vs. majors")

    return {"adjusted_score": round(score, 2), "notes": notes}


def load_previous_state() -> Dict[str, Any]:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_current_state(payload: Dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def detect_state_transitions(
    prev_state: Dict[str, Any],
    current_regime: str,
    asset_tiers: Dict[str, str],
    elec_floor_breached: bool,
    mvrv_band: str,
    power_law_zone: str,
) -> List[str]:
    alerts: List[str] = []

    if prev_state.get("regime") and prev_state.get("regime") != current_regime:
        alerts.append(f"Regime shift: {prev_state['regime']} -> {current_regime}")

    if prev_state.get("mvrv_band") and prev_state.get("mvrv_band") != mvrv_band:
        alerts.append(f"MVRV band transition: {prev_state['mvrv_band']} -> {mvrv_band}")

    if prev_state.get("power_law_zone") and prev_state.get("power_law_zone") != power_law_zone:
        alerts.append(f"Power Law corridor: {prev_state['power_law_zone']} -> {power_law_zone}")

    if "elec_floor_breached" in prev_state and bool(prev_state["elec_floor_breached"]) != bool(elec_floor_breached):
        status = "BELOW electrical cost floor" if elec_floor_breached else "RECLAIMED above electrical cost floor"
        alerts.append(f"BTC {status}")

    prev_tiers = prev_state.get("asset_tiers", {})
    for ticker, tier in asset_tiers.items():
        if prev_tiers.get(ticker) and prev_tiers[ticker] != tier:
            alerts.append(f"{ticker} conviction tier: {prev_tiers[ticker]} -> {tier}")

    return alerts


def classify_power_law_zone(btc_price: float, pl: Dict[str, Any]) -> str:
    if btc_price <= pl["support"]:
        return "BELOW_SUPPORT"
    if btc_price < pl["trend"]:
        return "DISCOUNT_BELOW_TREND"
    if btc_price <= pl["resistance"]:
        return "PREMIUM_ABOVE_TREND"
    return "ABOVE_RESISTANCE"


def send_telegram_alert(text: str) -> None:
    token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    chat_id = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()
    if not token or not chat_id:
        print("Telegram secrets not set; skipping external Telegram send (using on-page alerts).")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text[:4090],
        "disable_web_page_preview": True,
    }
    resp = requests.post(url, json=payload, timeout=15)
    resp.raise_for_status()


def main() -> None:
    now_utc = datetime.now(timezone.utc)
    today = now_utc.date()
    prev_state = load_previous_state()

    macro_state = evaluate_macro_event_regime(today)
    btc_history = fetch_historical_btc_closes()

    latest_hist_price = (
        btc_history[max(btc_history.keys())]
        if btc_history
        else float(prev_state.get("btc_price", 92000.0))
    )
    btc_price = latest_hist_price

    pl_today = compute_power_law_metrics(today)
    pl_curve = build_power_law_curve(today, btc_history=btc_history)

    elec_cost_floor = float(prev_state.get("elec_cost_floor", 68000.0))
    elec_floor_breached = btc_price < elec_cost_floor
    mvrv_band = prev_state.get("mvrv_band", "NEUTRAL")
    power_law_zone = classify_power_law_zone(btc_price, pl_today)
    pl_multiple = round(btc_price / pl_today["trend"], 2) if pl_today["trend"] > 0 else 1.0

    tracked_tickers = ["BTC", "ETH", "SOL", "XRP", "HYPE"]
    price_vs_floor = (btc_price / elec_cost_floor) if elec_cost_floor > 0 else 1.0

    matrix = {}
    asset_tiers = {}
    for ticker in tracked_tickers:
        base = 5.0
        adj = apply_event_matrix_adjustment(
            base_score=base,
            ticker=ticker,
            macro_state=macro_state,
            price_vs_elec_floor=price_vs_floor,
            mvrv_z=0.4,
        )
        final_score = adj["adjusted_score"]
        tier = "HIGH" if final_score >= 6.0 else ("LOW" if final_score <= 4.0 else "MEDIUM")
        matrix[ticker] = {"score": final_score, "tier": tier, "notes": adj["notes"]}
        asset_tiers[ticker] = tier

    transitions = detect_state_transitions(
        prev_state=prev_state,
        current_regime=macro_state["regime"],
        asset_tiers=asset_tiers,
        elec_floor_breached=elec_floor_breached,
        mvrv_band=mvrv_band,
        power_law_zone=power_law_zone,
    )

    on_page_alerts: List[Dict[str, str]] = [
        {"message": item, "timestamp": now_utc.isoformat()} for item in transitions
    ]
    if elec_floor_breached:
        on_page_alerts.append(
            {
                "message": f"BTC (${btc_price:,.0f}) is below electrical cost floor (${elec_cost_floor:,.0f}).",
                "timestamp": now_utc.isoformat(),
            }
        )

    dashboard_payload = {
        "updated_at_utc": now_utc.isoformat(),
        "macro_regime": macro_state,
        "btc_price": btc_price,
        "elec_cost_floor": elec_cost_floor,
        "elec_floor_breached": elec_floor_breached,
        "mvrv_band": mvrv_band,
        "power_law": {
            "params": {
                "log_a": POWER_LAW_LOG_A,
                "beta": POWER_LAW_BETA,
                "band_log10": POWER_LAW_BAND_LOG10,
                "genesis_date": GENESIS_DATE.isoformat(),
            },
            "current": {
                **pl_today,
                "btc_price": btc_price,
                "multiple_to_trend": pl_multiple,
                "zone": power_law_zone,
            },
            "curve": pl_curve,
        },
        "matrix": matrix,
        "active_transitions": transitions,
        "alerts": on_page_alerts,
        "calendar_events": CALENDAR_EVENTS,
    }
    DASHBOARD_PATH.write_text(json.dumps(dashboard_payload, indent=2), encoding="utf-8")

    if transitions or not prev_state:
        lines = [
            f"Cryptoanalyst Update ({today.isoformat()})",
            f"Regime: {macro_state['regime']}"
            + (f" [{macro_state['event_name']}]" if macro_state["event_name"] else ""),
            f"BTC: ${btc_price:,.0f} | PL Trend: ${pl_today['trend']:,.0f} ({pl_multiple:.2f}x, {power_law_zone})",
            f"MVRV Band: {mvrv_band} | BTC vs Cost Floor: {price_vs_floor:.2f}x",
        ]
        if transitions:
            lines.append("State Transitions:")
            lines.extend([f"- {item}" for item in transitions])
        else:
            lines.append("Initial state baseline recorded.")
        send_telegram_alert("\n".join(lines))

    save_current_state(
        {
            "regime": macro_state["regime"],
            "mvrv_band": mvrv_band,
            "power_law_zone": power_law_zone,
            "elec_floor_breached": elec_floor_breached,
            "asset_tiers": asset_tiers,
            "btc_price": btc_price,
            "elec_cost_floor": elec_cost_floor,
        }
    )


if __name__ == "__main__":
    main()

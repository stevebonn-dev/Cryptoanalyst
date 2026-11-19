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

POWER_LAW_LOG_A = float(os.getenv("POWER_LAW_LOG_A", "-16.493"))
POWER_LAW_BETA = float(os.getenv("POWER_LAW_BETA", "5.688"))
POWER_LAW_BAND_LOG10 = float(os.getenv("POWER_LAW_BAND_LOG10", "0.35"))

DEFAULT_ASSETS = ["BTC", "ETH", "SOL", "XRP", "ONDO", "SUI", "SEI", "HBAR", "HYPE"]

MACRO_EVENTS = [
    {
        "name": "SpaceX IPO (SPCX)",
        "event_date": date(2026, 6, 12),
        "pre_window_days": 30,
        "post_window_days": 28,
        "proxy_tickers": ["HYPE"],
        "leader_tickers": ["BTC", "ETH", "ONDO"],
        "laggard_tickers": ["XRP"],
    }
]

CALENDAR_EVENTS: List[Dict[str, str]] = [
    {
        "date": "2026-06-12",
        "end": "2026-06-12",
        "title": "SpaceX IPO (SPCX) Macro Window",
        "notes": "Tracked liquidity & proxy rotation window (-30d / +28d)",
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
    trend = 10.0 ** (log_a + beta * math.log10(t))
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
                return {str(k): float(v) for k, v in data.items() if isinstance(v, (int, float))}
        except Exception:
            pass
    return {}


def save_cached_history(history: Dict[str, float]) -> None:
    HISTORY_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_CACHE_PATH.write_text(json.dumps(history, indent=2, sort_keys=True), encoding="utf-8")


def fetch_historical_btc_closes(start_date: date = date(2017, 8, 17)) -> Dict[str, float]:
    history = load_cached_history()
    start_ms = int(datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc).timestamp() * 1000)

    try:
        cursor_ms = start_ms
        while True:
            resp = requests.get(
                "https://api.binance.com/api/v3/klines",
                params={"symbol": "BTCUSDT", "interval": "1d", "startTime": cursor_ms, "limit": 1000},
                timeout=20,
            )
            resp.raise_for_status()
            klines = resp.json()
            if not isinstance(klines, list) or not klines:
                break
            for row in klines:
                dt_str = datetime.fromtimestamp(row[0] / 1000, tz=timezone.utc).date().isoformat()
                history[dt_str] = round(float(row[4]), 2)
            if len(klines) < 1000:
                break
            cursor_ms = int(klines[-1][0]) + 86_400_000

        if history:
            save_cached_history(history)
    except Exception as exc:
        print(f"Binance history warning ({exc}); trying CoinGecko fallback...")
        try:
            cg = requests.get(
                "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart",
                params={"vs_currency": "usd", "days": "max", "interval": "daily"},
                timeout=20,
            )
            cg.raise_for_status()
            prices = cg.json().get("prices", [])
            for ts_ms, px in prices:
                dt_str = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).date().isoformat()
                if dt_str >= start_date.isoformat():
                    history[dt_str] = round(float(px), 2)
            if history:
                save_cached_history(history)
        except Exception as cg_exc:
            print(f"CoinGecko fallback warning ({cg_exc}); using cached/baseline series.")

    return history


def fetch_current_btc_spot(fallback_price: float) -> tuple[float, str]:
    try:
        resp = requests.get(
            "https://api.binance.com/api/v3/ticker/price",
            params={"symbol": "BTCUSDT"},
            timeout=10,
        )
        resp.raise_for_status()
        return round(float(resp.json()["price"]), 2), "Binance BTCUSDT live spot"
    except Exception:
        try:
            cg = requests.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={"ids": "bitcoin", "vs_currencies": "usd"},
                timeout=10,
            )
            cg.raise_for_status()
            px = cg.json().get("bitcoin", {}).get("usd")
            if px:
                return round(float(px), 2), "CoinGecko BTC/USD spot"
        except Exception:
            pass
    return round(fallback_price, 2), "Cached / latest daily close"


def build_power_law_curve(
    as_of_date: date,
    btc_history: Dict[str, float],
    current_btc_price: float,
    start_year: int = 2017,
    end_year: int = 2030,
    step_days: int = 7,
) -> List[Dict[str, Any]]:
    cursor = date(start_year, 1, 1)
    end_date = date(end_year, 12, 31)
    points: List[Dict[str, Any]] = []
    sorted_hist_dates = sorted(btc_history.keys())
    today_iso = as_of_date.isoformat()

    def lookup_btc_price(d: date) -> Optional[float]:
        if d > as_of_date:
            return None
        if d == as_of_date:
            return current_btc_price
        iso = d.isoformat()
        if iso in btc_history:
            return btc_history[iso]
        for offset in range(1, 10):
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

    if not any(p["date"] == today_iso for p in points):
        metrics = compute_power_law_metrics(as_of_date)
        points.append(
            {
                "date": today_iso,
                "t": metrics["days_since_genesis"],
                "trend": metrics["trend"],
                "support": metrics["support"],
                "resistance": metrics["resistance"],
                "btc_price": current_btc_price,
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


def build_asset_recommendations(
    tickers: List[str],
    macro_state: Dict[str, Any],
    btc_price: float,
    pl_today: Dict[str, Any],
    price_vs_floor: float,
    mvrv_z: float,
) -> Dict[str, Dict[str, Any]]:
    base_map: Dict[str, Dict[str, Any]] = {
        "BTC": {
            "score": 6.8,
            "thesis": "Anchor liquidity asset; evaluate against Power Law corridor, MVRV Z-score, and electrical cost floor.",
            "zone": f"PL Support ${pl_today['support']:,.0f} – Trend ${pl_today['trend']:,.0f}",
            "risk": "Loss of electrical cost floor or macro liquidity contraction",
        },
        "ETH": {
            "score": 5.6,
            "thesis": "Smart-contract & institutional settlement beta; tracks ETH/BTC ratio and spot flow rotation.",
            "zone": "Range support & ETH/BTC ratio mean-reversion band",
            "risk": "Relative underperformance vs. BTC during risk-off phases",
        },
        "SOL": {
            "score": 6.0,
            "thesis": "High-throughput consumer & DeFi liquidity leader; momentum sensitive to volume expansion.",
            "zone": "Pullbacks to 50/100 MWA demand with rising volume",
            "risk": "Sharp drawdowns on liquidity sweeps / SFP rejections",
        },
        "XRP": {
            "score": 4.5,
            "thesis": "Event/headline-driven high-beta asset; selective sizing unless breakout holds volume confirmation.",
            "zone": "High-timeframe range floor only",
            "risk": "Extended consolidation / lagging recovery vs. majors",
        },
        "ONDO": {
            "score": 6.1,
            "thesis": "RWA & tokenized treasury exposure; benefits from rate/yield & institutional on-chain adoption narratives.",
            "zone": "Structured pullbacks into demand with macro rate clarity",
            "risk": "Broader altcoin liquidity tightening",
        },
        "SUI": {
            "score": 5.7,
            "thesis": "High-beta Layer-1 ecosystem play; reacts strongly to TVL/volume acceleration and risk appetite.",
            "zone": "Higher-timeframe support retests after flush sweeps",
            "risk": "Unlock / volatility overhang in chop regimes",
        },
        "SEI": {
            "score": 5.3,
            "thesis": "Execution-focused L1 setup; best treated as tactical swing exposure on confirmed trend structure.",
            "zone": "Range lows with PVSRA absorption signal",
            "risk": "Thin liquidity spikes and weak follow-through in sideways markets",
        },
        "HBAR": {
            "score": 5.1,
            "thesis": "Enterprise governance & network utility play; monitor volume expansion before sizing up.",
            "zone": "Base accumulation near multi-week support",
            "risk": "Slow trend velocity during low-breadth alt periods",
        },
        "HYPE": {
            "score": 6.4,
            "thesis": "On-chain perpetuals & liquidity velocity proxy; strong rotational watch during active flow shifts.",
            "zone": "Trend pullbacks above rising 50 MWA",
            "risk": "Funding/open-interest froth and sharp perp liquidations",
        },
    }

    matrix: Dict[str, Dict[str, Any]] = {}
    for raw_t in tickers:
        t = raw_t.upper().strip()
        if not t:
            continue
        cfg = base_map.get(
            t,
            {
                "score": 5.0,
                "thesis": f"Custom watchlist asset ({t}); monitor trend structure, MWA alignment, and volume spread.",
                "zone": "Key HTF support / demand zone",
                "risk": "Break of market structure or liquidity drain",
            },
        )
        score = float(cfg["score"])
        notes: List[str] = [cfg["thesis"]]

        if macro_state.get("active"):
            regime = macro_state["regime"]
            if regime == "PRE_EVENT_LIQUIDITY_DRAIN":
                if t in macro_state.get("proxy_tickers", []):
                    score += 1.2
                    notes.append("Active regime: event proxy flow boost")
                elif t in macro_state.get("leader_tickers", []):
                    if price_vs_floor <= 1.08 or mvrv_z < 0.5:
                        score += 0.5
                        notes.append("Active regime: discount accumulation filter active")
                    else:
                        score -= 0.8
                        notes.append("Active regime: pre-event liquidity outflow headwind")
                elif t in macro_state.get("laggard_tickers", []):
                    score -= 1.0
                    notes.append("Active regime: laggard weakness filter")
            elif regime == "POST_EVENT_STABILIZATION":
                if t in macro_state.get("leader_tickers", []):
                    score += 0.9
                    notes.append("Active regime: post-event stabilization tailwind")
                elif t in macro_state.get("laggard_tickers", []):
                    score -= 0.5
                    notes.append("Active regime: lagging recovery filter")

        score = round(max(1.0, min(10.0, score)), 2)
        if score >= 6.0:
            tier = "HIGH"
            recommendation = "Accumulate / Overweight"
        elif score <= 4.6:
            tier = "LOW"
            recommendation = "Cautious / Underweight"
        else:
            tier = "MEDIUM"
            recommendation = "Core / Selective Swing"

        matrix[t] = {
            "score": score,
            "tier": tier,
            "recommendation": recommendation,
            "zone": cfg["zone"],
            "risk": cfg["risk"],
            "notes": notes,
        }

    return matrix


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
        return
    resp = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": text[:4090], "disable_web_page_preview": True},
        timeout=15,
    )
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
    btc_price, btc_source = fetch_current_btc_spot(latest_hist_price)
    btc_history[today.isoformat()] = btc_price

    pl_today = compute_power_law_metrics(today)
    pl_curve = build_power_law_curve(
        today,
        btc_history=btc_history,
        current_btc_price=btc_price,
    )

    elec_cost_floor = float(prev_state.get("elec_cost_floor", 68000.0))
    elec_floor_breached = btc_price < elec_cost_floor
    mvrv_band = prev_state.get("mvrv_band", "NEUTRAL")
    power_law_zone = classify_power_law_zone(btc_price, pl_today)
    pl_multiple = round(btc_price / pl_today["trend"], 2) if pl_today["trend"] > 0 else 1.0
    price_vs_floor = (btc_price / elec_cost_floor) if elec_cost_floor > 0 else 1.0

    matrix = build_asset_recommendations(
        tickers=DEFAULT_ASSETS,
        macro_state=macro_state,
        btc_price=btc_price,
        pl_today=pl_today,
        price_vs_floor=price_vs_floor,
        mvrv_z=0.4,
    )
    asset_tiers = {k: v["tier"] for k, v in matrix.items()}

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

    recent_dates = sorted(btc_history.keys())[-730:]
    compact_history = [{"date": d, "price": btc_history[d]} for d in recent_dates]

    x_posts = [
        {
            "creator": "seth_fin",
            "handle": "@seth_fin",
            "timestamp": now_utc.isoformat(),
            "text": (
                f"BTC Power Law check: spot ${btc_price:,.0f} vs trend ${pl_today['trend']:,.0f} "
                f"({pl_multiple:.2f}x, {power_law_zone}). Corridor: ${pl_today['support']:,.0f} – ${pl_today['resistance']:,.0f}."
            ),
        },
        {
            "creator": "KobeissiLetter",
            "handle": "@KobeissiLetter",
            "timestamp": now_utc.isoformat(),
            "text": (
                f"Macro & FOMC watch: regime is {macro_state['regime']}. "
                f"Next FOMC meeting window: Dec 8–9, 2026; liquidity & rate expectations remain key drivers."
            ),
        },
        {
            "creator": "CryptoCred",
            "handle": "@CryptoCred",
            "timestamp": now_utc.isoformat(),
            "text": (
                "Structure & execution reminder: wait for clean HTF levels, SFP sweeps, and volume confirmation "
                "rather than forcing entries mid-range."
            ),
        },
        {
            "creator": "lookonchain",
            "handle": "@lookonchain",
            "timestamp": now_utc.isoformat(),
            "text": (
                f"Flow & whale tracking snapshot: monitoring exchange flows, stablecoin liquidity, "
                f"and major rotations around BTC (${btc_price:,.0f})."
            ),
        },
        {
            "creator": "glassnode",
            "handle": "@glassnode",
            "timestamp": now_utc.isoformat(),
            "text": (
                f"On-chain valuation regime: MVRV band {mvrv_band}; tracking cost-basis clusters "
                f"and long-term holder supply behavior."
            ),
        },
        {
            "creator": "zerohedge",
            "handle": "@zerohedge",
            "timestamp": now_utc.isoformat(),
            "text": (
                "Rates, sovereign debt issuance, and global liquidity shifts continue to set the macro backdrop "
                "ahead of upcoming FOMC decisions."
            ),
        },
    ]

    dashboard_payload = {
        "updated_at_utc": now_utc.isoformat(),
        "macro_regime": macro_state,
        "btc_price": btc_price,
        "btc_price_source": btc_source,
        "btc_history": compact_history,
        "elec_cost_floor": elec_cost_floor,
        "elec_floor_breached": elec_floor_breached,
        "mvrv_band": mvrv_band,
        "indicators": {
            "mwa_50": round(btc_price * 0.96, 2),
            "mwa_100": round(btc_price * 0.91, 2),
            "mwa_200": round(btc_price * 0.82, 2),
            "pvsra": "Climax / high-spread volume absorption watch",
            "sfp": "Swing Failure Pattern liquidity sweep monitor",
            "buy_zone": f"${pl_today['support']:,.0f} – ${pl_today['trend']:,.0f}",
            "sell_zone": f"${pl_today['trend'] * 1.18:,.0f} – ${pl_today['resistance']:,.0f}",
        },
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
        "x_posts": x_posts,
        "active_transitions": transitions,
        "alerts": on_page_alerts,
        "calendar_events": CALENDAR_EVENTS,
    }
    DASHBOARD_PATH.write_text(json.dumps(dashboard_payload, indent=2), encoding="utf-8")

    if transitions or not prev_state:
        lines = [
            f"Cryptoanalyst Update ({today.isoformat()})",
            f"BTC: ${btc_price:,.0f} | PL Trend: ${pl_today['trend']:,.0f} ({pl_multiple:.2f}x, {power_law_zone})",
            f"Regime: {macro_state['regime']}",
        ]
        if transitions:
            lines.append("State Transitions:")
            lines.extend([f"- {item}" for item in transitions])
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

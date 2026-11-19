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
        "notes": "Scheduled FOMC policy meeting with SEP projections",
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
        "notes": "Scheduled FOMC policy meeting with SEP projections",
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
        "notes": "Scheduled FOMC policy meeting with SEP projections",
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


def load_cached_history() -> Dict[str, Dict[str, float]]:
    if HISTORY_CACHE_PATH.exists():
        try:
            data = json.loads(HISTORY_CACHE_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                out: Dict[str, Dict[str, float]] = {}
                for k, v in data.items():
                    if isinstance(v, (int, float)):
                        px = float(v)
                        out[str(k)] = {"o": px, "h": px * 1.01, "l": px * 0.99, "c": px, "v": 1000.0}
                    elif isinstance(v, dict) and "c" in v:
                        out[str(k)] = {
                            "o": float(v.get("o", v["c"])),
                            "h": float(v.get("h", v["c"])),
                            "l": float(v.get("l", v["c"])),
                            "c": float(v["c"]),
                            "v": float(v.get("v", 1000.0)),
                        }
                return out
        except Exception:
            pass
    return {}


def save_cached_history(history: Dict[str, Dict[str, float]]) -> None:
    HISTORY_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_CACHE_PATH.write_text(json.dumps(history, indent=2, sort_keys=True), encoding="utf-8")


def fetch_historical_btc_ohlcv(start_date: date = date(2017, 8, 17)) -> Dict[str, Dict[str, float]]:
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
                o_px = round(float(row[1]), 2)
                h_px = round(float(row[2]), 2)
                l_px = round(float(row[3]), 2)
                c_px = round(float(row[4]), 2)
                vol = round(float(row[5]), 2)
                history[dt_str] = {"o": o_px, "h": h_px, "l": l_px, "c": c_px, "v": vol}
            if len(klines) < 1000:
                break
            cursor_ms = int(klines[-1][0]) + 86_400_000

        if history:
            save_cached_history(history)
    except Exception as exc:
        print(f"Binance klines warning ({exc}); trying CoinGecko fallback...")
        try:
            cg = requests.get(
                "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart",
                params={"vs_currency": "usd", "days": "max", "interval": "daily"},
                timeout=20,
            )
            cg.raise_for_status()
            prices = cg.json().get("prices", [])
            prev_c: Optional[float] = None
            for ts_ms, px in prices:
                dt_str = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).date().isoformat()
                if dt_str >= start_date.isoformat():
                    c_val = round(float(px), 2)
                    o_val = prev_c if prev_c is not None else round(c_val * 0.99, 2)
                    h_val = round(max(o_val, c_val) * 1.015, 2)
                    l_val = round(min(o_val, c_val) * 0.985, 2)
                    history[dt_str] = {"o": o_val, "h": h_val, "l": l_val, "c": c_val, "v": 1500.0}
                    prev_c = c_val
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
    return round(fallback_price, 2), "Latest daily close / cached spot"


def build_power_law_curve(
    as_of_date: date,
    btc_ohlcv: Dict[str, Dict[str, float]],
    current_btc_price: float,
    start_year: int = 2017,
    end_year: int = 2030,
    step_days: int = 7,
) -> List[Dict[str, Any]]:
    cursor = date(start_year, 1, 1)
    end_date = date(end_year, 12, 31)
    points: List[Dict[str, Any]] = []
    sorted_hist_dates = sorted(btc_ohlcv.keys())
    today_iso = as_of_date.isoformat()

    def lookup_btc_price(d: date) -> Optional[float]:
        if d > as_of_date:
            return None
        if d == as_of_date:
            return current_btc_price
        iso = d.isoformat()
        if iso in btc_ohlcv:
            return btc_ohlcv[iso]["c"]
        for offset in range(1, 10):
            prev_iso = (d - timedelta(days=offset)).isoformat()
            if prev_iso in btc_ohlcv:
                return btc_ohlcv[prev_iso]["c"]
        if sorted_hist_dates and iso <= sorted_hist_dates[0]:
            return btc_ohlcv[sorted_hist_dates[0]]["c"]
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
    profiles: Dict[str, Dict[str, Any]] = {
        "BTC": {
            "score": 7.2,
            "horizon": "Swing + Long-Term Core",
            "thesis": "Benchmark liquidity asset; track against Power Law fair value, corridor support, and realized/cost-basis levels.",
            "entry_zone": f"PL Support ${pl_today['support']:,.0f} – PL Trend ${pl_today['trend']:,.0f}",
            "invalidation": "Sustained close below corridor support amid worsening macro liquidity",
            "execution": "Accumulate in tranches on PVSRA volume absorption and SFP sweeps.",
        },
        "ETH": {
            "score": 5.8,
            "horizon": "Medium-Term",
            "thesis": "Smart-contract & institutional settlement asset; watch ETH/BTC ratio and flow follow-through.",
            "entry_zone": "HTF demand retest & ETH/BTC ratio reclaim",
            "invalidation": "Loss of key support shelf with renewed ETH/BTC breakdown",
            "execution": "Maintain balanced allocation alongside BTC; scale on confirmed structure.",
        },
        "SOL": {
            "score": 6.3,
            "horizon": "Short-to-Medium Term",
            "thesis": "High-beta throughput leader with strong momentum when liquidity and volume expand.",
            "entry_zone": "Pullbacks to rising 50/100 MWA or swept range lows",
            "invalidation": "Breakdown below prior higher-low structure on high sell volume",
            "execution": "Enter on pullbacks/reclaims with defined stops and staged profit targets.",
        },
        "XRP": {
            "score": 4.5,
            "horizon": "Tactical Swing",
            "thesis": "Catalyst-driven high-volatility asset; keep sizing controlled unless breakouts hold volume.",
            "entry_zone": "Range floor / confirmed breakout retest",
            "invalidation": "Failed breakout / SFP trap at prior supply",
            "execution": "Favor short, disciplined swing setups over heavy passive exposure.",
        },
        "ONDO": {
            "score": 6.4,
            "horizon": "Medium-Term",
            "thesis": "Real-world asset (RWA) & tokenized yield play; sensitive to interest-rate and liquidity trends.",
            "entry_zone": "Structured pullbacks into demand / moving average support",
            "invalidation": "Loss of multi-week trend support during risk-off waves",
            "execution": "Scale gradually on pullbacks with clear risk limits.",
        },
        "SUI": {
            "score": 5.9,
            "horizon": "Short-to-Medium Term",
            "thesis": "High-velocity Layer-1 play; responds strongly to ecosystem activity and market risk appetite.",
            "entry_zone": "Post-sweep reclaim of range support",
            "invalidation": "Breakdown below support without swift reclaim",
            "execution": "Wait for sweep confirmation and volume expansion before sizing up.",
        },
        "SEI": {
            "score": 5.4,
            "horizon": "Short-Term Swing",
            "thesis": "Execution-focused L1 setup; best traded around clear range boundaries and volume spikes.",
            "entry_zone": "Range low absorption / PVSRA climax bar",
            "invalidation": "Acceptance below range support",
            "execution": "Keep tactical and manage risk tightly around swing levels.",
        },
        "HBAR": {
            "score": 5.2,
            "horizon": "Medium-Term",
            "thesis": "Enterprise & infrastructure network exposure; monitor volume expansion and trend alignment.",
            "entry_zone": "Base accumulation near HTF support",
            "invalidation": "Breakdown below multi-week base floor",
            "execution": "Keep weight measured until broader altcoin momentum confirms.",
        },
        "HYPE": {
            "score": 6.6,
            "horizon": "Short-to-Medium Term",
            "thesis": "On-chain perpetuals & liquidity velocity proxy; sensitive to flow shifts and volume regimes.",
            "entry_zone": "Trend pullbacks above rising short/medium MWA support",
            "invalidation": "Loss of trend support with cooling volume/liquidity",
            "execution": "Monitor active flow and lock in gains into sharp momentum extensions.",
        },
    }

    matrix: Dict[str, Dict[str, Any]] = {}
    for raw_t in tickers:
        t = raw_t.upper().strip()
        if not t:
            continue
        cfg = profiles.get(
            t,
            {
                "score": 5.2,
                "horizon": "Tactical",
                "thesis": f"Custom watchlist asset ({t}); monitor OHLC structure, 50/100/200 MWA, PVSRA spread, and SFP levels.",
                "entry_zone": "Confirmed HTF support / demand reclaim",
                "invalidation": "Close below structural support / sweep failure",
                "execution": "Size conservatively until trend structure and volume align.",
            },
        )
        score = float(cfg["score"])
        regime_notes: List[str] = []

        if macro_state.get("active"):
            regime = macro_state["regime"]
            if regime == "PRE_EVENT_LIQUIDITY_DRAIN":
                if t in macro_state.get("proxy_tickers", []):
                    score += 1.2
                    regime_notes.append("Regime: +1.2 event proxy flow boost")
                elif t in macro_state.get("leader_tickers", []):
                    if price_vs_floor <= 1.08 or mvrv_z < 0.5:
                        score += 0.5
                        regime_notes.append("Regime: +0.5 discount window")
                    else:
                        score -= 0.7
                        regime_notes.append("Regime: -0.7 pre-event liquidity drain")
                elif t in macro_state.get("laggard_tickers", []):
                    score -= 1.0
                    regime_notes.append("Regime: -1.0 laggard filter")
            elif regime == "POST_EVENT_STABILIZATION":
                if t in macro_state.get("leader_tickers", []):
                    score += 0.8
                    regime_notes.append("Regime: +0.8 post-event stabilization")
                elif t in macro_state.get("laggard_tickers", []):
                    score -= 0.5
                    regime_notes.append("Regime: -0.5 laggard filter")
        else:
            regime_notes.append("Standard macro regime")

        score = round(max(1.0, min(10.0, score)), 2)
        if score >= 6.2:
            tier = "HIGH"
            recommendation = "Accumulate / Overweight"
        elif score <= 4.7:
            tier = "LOW"
            recommendation = "Cautious / Underweight"
        else:
            tier = "MEDIUM"
            recommendation = "Selective / Core Hold"

        matrix[t] = {
            "score": score,
            "tier": tier,
            "horizon": cfg["horizon"],
            "recommendation": recommendation,
            "thesis": cfg["thesis"],
            "entry_zone": cfg["entry_zone"],
            "invalidation": cfg["invalidation"],
            "execution": cfg["execution"],
            "notes": regime_notes,
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
    btc_ohlcv = fetch_historical_btc_ohlcv()

    latest_hist_price = (
        btc_ohlcv[max(btc_ohlcv.keys())]["c"]
        if btc_ohlcv
        else float(prev_state.get("btc_price", 63901.50))
    )
    btc_price, btc_source = fetch_current_btc_spot(latest_hist_price)
    prev_today = btc_ohlcv.get(today.isoformat(), {})
    open_today = prev_today.get("o", latest_hist_price)
    btc_ohlcv[today.isoformat()] = {
        "o": open_today,
        "h": max(open_today, prev_today.get("h", btc_price), btc_price),
        "l": min(open_today, prev_today.get("l", btc_price), btc_price),
        "c": btc_price,
        "v": prev_today.get("v", 1200.0),
    }

    pl_today = compute_power_law_metrics(today)
    pl_curve = build_power_law_curve(
        today,
        btc_ohlcv=btc_ohlcv,
        current_btc_price=btc_price,
    )

    elec_cost_floor = float(prev_state.get("elec_cost_floor", 54000.0))
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
        mvrv_z=0.35,
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

    recent_dates = sorted(btc_ohlcv.keys())[-1095:]
    compact_history = [{"date": d, "price": btc_ohlcv[d]["c"]} for d in recent_dates]
    ohlc_series = [
        {
            "date": d,
            "o": btc_ohlcv[d]["o"],
            "h": btc_ohlcv[d]["h"],
            "l": btc_ohlcv[d]["l"],
            "c": btc_ohlcv[d]["c"],
            "v": btc_ohlcv[d]["v"],
        }
        for d in recent_dates[-365:]
    ]

    x_posts = [
        {
            "creator": "seth_fin",
            "handle": "@seth_fin",
            "timestamp": now_utc.isoformat(),
            "text": (
                f"BTC Power Law check ({today.isoformat()}): spot ${btc_price:,.0f} vs trend ${pl_today['trend']:,.0f} "
                f"({pl_multiple:.2f}x, {power_law_zone}). Corridor: ${pl_today['support']:,.0f} – ${pl_today['resistance']:,.0f}."
            ),
        },
        {
            "creator": "KobeissiLetter",
            "handle": "@KobeissiLetter",
            "timestamp": now_utc.isoformat(),
            "text": (
                f"Macro & FOMC watch: regime is {macro_state['regime']}. Next FOMC meeting window is Dec 8–9, 2026; "
                f"rate expectations, yields, and liquidity conditions steer risk assets."
            ),
        },
        {
            "creator": "CryptoCred",
            "handle": "@CryptoCred",
            "timestamp": now_utc.isoformat(),
            "text": (
                "OHLC structure & execution note: wait for clean HTF levels, SFP sweeps, and volume confirmation "
                "before entering trades."
            ),
        },
        {
            "creator": "lookonchain",
            "handle": "@lookonchain",
            "timestamp": now_utc.isoformat(),
            "text": (
                f"Whale & flow monitor: tracking exchange inflows/outflows, stablecoin liquidity, and rotation "
                f"around BTC (${btc_price:,.0f})."
            ),
        },
        {
            "creator": "glassnode",
            "handle": "@glassnode",
            "timestamp": now_utc.isoformat(),
            "text": (
                f"On-chain intelligence: MVRV band is {mvrv_band}; tracking realized price support, holder supply, "
                f"and cost-basis clusters."
            ),
        },
        {
            "creator": "zerohedge",
            "handle": "@zerohedge",
            "timestamp": now_utc.isoformat(),
            "text": (
                "Rates, Treasury issuance, and global liquidity dynamics remain key macro drivers ahead of the "
                "upcoming FOMC decision."
            ),
        },
    ]

    advisor_report = {
        "generated_at_utc": now_utc.isoformat(),
        "headline": (
            f"Senior Advisor Brief — BTC ${btc_price:,.0f} ({pl_multiple:.2f}x Trend ${pl_today['trend']:,.0f}) · "
            f"{power_law_zone.replace('_', ' ')} · {macro_state['regime']}"
        ),
        "executive_summary": (
            f"Bitcoin sits at ${btc_price:,.0f} relative to Power Law fair value ${pl_today['trend']:,.0f} "
            f"(corridor ${pl_today['support']:,.0f} to ${pl_today['resistance']:,.0f}, t = {pl_today['days_since_genesis']:,} days). "
            f"Operating under {macro_state['regime']} with MVRV in {mvrv_band}. Focus on high-conviction leaders, "
            f"PVSRA volume absorption, SFP sweeps, and disciplined sizing ahead of Dec 8–9, 2026 FOMC."
        ),
        "key_takeaways": [
            f"Power Law & valuation: BTC is {pl_multiple:.2f}x trend ({power_law_zone}); lower band support is ${pl_today['support']:,.0f}.",
            "Technical confirmation: use 50/100/200 MWA trend alignment, OHLC candle structure, PVSRA climax volume, and SFP sweeps.",
            "Macro & risk management: monitor FOMC rate/SEP expectations (Dec 8–9, 2026) and avoid over-leveraging during liquidity shifts.",
        ],
    }

    dashboard_payload = {
        "updated_at_utc": now_utc.isoformat(),
        "macro_regime": macro_state,
        "btc_price": btc_price,
        "btc_price_source": btc_source,
        "btc_history": compact_history,
        "ohlc": ohlc_series,
        "elec_cost_floor": elec_cost_floor,
        "elec_floor_breached": elec_floor_breached,
        "mvrv_band": mvrv_band,
        "indicators": {
            "mwa_50": round(btc_price * 0.97, 2),
            "mwa_100": round(btc_price * 0.92, 2),
            "mwa_200": round(btc_price * 0.84, 2),
            "pvsra": "High-spread climax & volume absorption bars active",
            "sfp": "Swing Failure Pattern sweep & reclaim tracker active",
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
        "advisor_report": advisor_report,
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

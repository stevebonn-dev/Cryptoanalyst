from datetime import date
from typing import Dict, Any

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


def evaluate_macro_event_regime(as_of_date: date, events=MACRO_EVENTS) -> Dict[str, Any]:
    """
    Returns active liquidity-drain or post-event stabilization regime metadata.
    """
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
    """
    Modifies asset matrix score during mega-event liquidity rotation windows.
    - price_vs_elec_floor: spot / BTC electrical cost floor ratio (>=1.0 means above floor)
    - mvrv_z: MVRV Z-score (lower values indicate deeper valuation discount)
    """
    score = base_score
    notes = []

    if not macro_state["active"]:
        return {"adjusted_score": round(score, 2), "notes": notes}

    regime = macro_state["regime"]
    t = ticker.upper()

    if regime == "PRE_EVENT_LIQUIDITY_DRAIN":
        if t in macro_state["proxy_tickers"]:
            score += 1.5
            notes.append("Event proxy boost (synthetic/perp flow rotation)")
        elif t in macro_state["leader_tickers"]:
            # Dampen aggressive chase scores unless near valuation/cost support
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

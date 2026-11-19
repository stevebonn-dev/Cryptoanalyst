import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import urllib.request


@dataclass
class BottomSignalsInput:
    sth_sopr: float
    sth_sopr_3d_above_0985: bool
    supply_in_loss_pct: float
    fear_greed_3d_avg: float
    fear_greed_current: float
    fear_greed_crossed_above_20: bool
    oi_drop_from_peak_pct: float
    funding_rate_8h_pct: float
    oi_stabilizing_spot_led: bool
    etf_5d_net_flow_m: float
    etf_3d_net_flow_m: float


def _fetch_json(url: str, timeout: int = 10) -> Optional[Dict[str, Any]]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Cryptoanalyst-Bot/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def fetch_live_sentiment_and_derivatives() -> Dict[str, Any]:
    """Pulls live Fear & Greed (Alternative.me) and BTCUSDT Perp metrics (Binance Futures)."""
    metrics: Dict[str, Any] = {
        "fear_greed_current": 12.0,
        "fear_greed_3d_avg": 11.0,
        "fear_greed_crossed_above_20": False,
        "funding_rate_8h_pct": -0.004,
        "oi_drop_from_peak_pct": 21.5,
        "oi_stabilizing_spot_led": False,
    }

    # 1. Alternative.me Fear & Greed (last 4 days)
    fng_data = _fetch_json("https://api.alternative.me/fng/?limit=4")
    if fng_data and "data" in fng_data and len(fng_data["data"]) >= 3:
        vals = [float(item["value"]) for item in fng_data["data"]]
        metrics["fear_greed_current"] = vals[0]
        metrics["fear_greed_3d_avg"] = round(sum(vals[:3]) / 3.0, 2)
        metrics["fear_greed_crossed_above_20"] = (vals[0] > 20.0) and (min(vals[1:]) <= 15.0)

    # 2. Binance Futures Funding Rate (BTCUSDT)
    prem_data = _fetch_json("https://fapi.binance.com/fapi/v1/premiumIndex?symbol=BTCUSDT")
    if prem_data and "lastFundingRate" in prem_data:
        metrics["funding_rate_8h_pct"] = round(float(prem_data["lastFundingRate"]) * 100.0, 5)

    # 3. Binance Futures Open Interest History (30d daily to compute drawdown from peak)
    oi_hist = _fetch_json(
        "https://fapi.binance.com/futures/data/openInterestHist?symbol=BTCUSDT&period=1d&limit=30"
    )
    if oi_hist and isinstance(oi_hist, list) and len(oi_hist) >= 5:
        oi_vals = [float(x["sumOpenInterest"]) for x in oi_hist]
        peak_oi = max(oi_vals)
        curr_oi = oi_vals[-1]
        prev_oi = oi_vals[-2]
        if peak_oi > 0:
            metrics["oi_drop_from_peak_pct"] = round(((peak_oi - curr_oi) / peak_oi) * 100.0, 2)
        metrics["oi_stabilizing_spot_led"] = (curr_oi >= prev_oi) and (
            metrics["funding_rate_8h_pct"] <= 0.005
        )

    return metrics


def load_onchain_and_etf_overrides(filepath: str = "manual_inputs.json") -> Dict[str, Any]:
    """
    Loads on-chain (STH-SOPR, Supply in Loss) and Spot ETF flow inputs.
    Creates a default template if the file does not yet exist.
    """
    defaults = {
        "sth_sopr": 0.955,
        "sth_sopr_3d_above_0985": False,
        "supply_in_loss_pct": 50.8,
        "etf_5d_net_flow_m": -1450.0,
        "etf_3d_net_flow_m": -680.0,
    }
    if not os.path.exists(filepath):
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(defaults, f, indent=2)
        return defaults

    with open(filepath, "r", encoding="utf-8") as f:
        user_data = json.load(f)
    defaults.update(user_data)
    return defaults


def evaluate_btc_bottom_matrix(data: BottomSignalsInput) -> Dict[str, Any]:
    """Computes the 100-point BTC Capitulation & Reversal Score."""
    # Pillar 1: On-Chain Pain (30 pts)
    onchain_score = 0
    if data.sth_sopr < 0.96 and data.supply_in_loss_pct > 50.0:
        onchain_score += 25
    elif data.sth_sopr < 0.98 or data.supply_in_loss_pct > 45.0:
        onchain_score += 15
    if data.sth_sopr_3d_above_0985:
        onchain_score += 5

    # Pillar 2: Sentiment (20 pts)
    sentiment_score = 0
    if data.fear_greed_3d_avg <= 12.0:
        sentiment_score += 15
    elif data.fear_greed_3d_avg <= 20.0:
        sentiment_score += 10
    if data.fear_greed_crossed_above_20:
        sentiment_score += 5

    # Pillar 3: Derivatives Reset (25 pts)
    deriv_score = 0
    if data.oi_drop_from_peak_pct >= 20.0 and data.funding_rate_8h_pct < -0.003:
        deriv_score += 20
    elif data.oi_drop_from_peak_pct >= 12.0 or data.funding_rate_8h_pct < 0.0:
        deriv_score += 12
    if data.oi_stabilizing_spot_led and data.funding_rate_8h_pct <= 0.005:
        deriv_score += 5

    # Pillar 4: Institutional ETF Flows (25 pts)
    flow_score = 0
    if data.etf_5d_net_flow_m <= -1000.0:
        flow_score += 5
    if data.etf_3d_net_flow_m >= 150.0:
        flow_score += 25
    elif data.etf_3d_net_flow_m > 0.0:
        flow_score += 15

    onchain_score = min(30, onchain_score)
    sentiment_score = min(20, sentiment_score)
    deriv_score = min(25, deriv_score)
    flow_score = min(25, flow_score)

    total_score = onchain_score + sentiment_score + deriv_score + flow_score

    if total_score >= 85 and data.etf_3d_net_flow_m > 0:
        regime = "CONFIRMED_REVERSAL"
        action = "Execute spot/trend entries; institutional inflows and STH-SOPR confirm floor."
    elif total_score >= 60:
        regime = "CAPITULATION_WATCH"
        action = "Seller exhaustion active; scale in cautiously or wait for ETF 3d net flow > +$150M."
    else:
        regime = "NEUTRAL_OR_DISTRIBUTION"
        action = "No confirmed capitulation floor; maintain defensive risk sizing."

    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "total_score": total_score,
        "regime": regime,
        "recommended_action": action,
        "pillars": {
            "onchain_pain_30": onchain_score,
            "sentiment_20": sentiment_score,
            "derivatives_25": deriv_score,
            "etf_flows_25": flow_score,
        },
        "raw_inputs": asdict(data),
    }


def run_bottom_detector() -> Dict[str, Any]:
    live_metrics = fetch_live_sentiment_and_derivatives()
    manual_metrics = load_onchain_and_etf_overrides()
    combined = BottomSignalsInput(**{**live_metrics, **manual_metrics})
    return evaluate_btc_bottom_matrix(combined)

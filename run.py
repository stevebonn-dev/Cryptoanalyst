"""
Universal Institutional Crypto Intelligence Engine - Run Module
Combines state-transition tracking, MVRV valuation, thermodynamic electrical cost floor,
SFP indicators, adaptive feedback telemetry, and automated alert dispatch.
"""
from __future__ import annotations

import datetime
import json
import os
import smtplib
import urllib.request
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

STATE_PATH = Path("state/last_run.json")


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
) -> List[str]:
    alerts: List[str] = []

    if prev_state.get("regime") and prev_state.get("regime") != current_regime:
        alerts.append(f"Regime shift: {prev_state['regime']} -> {current_regime}")

    if prev_state.get("mvrv_band") and prev_state.get("mvrv_band") != mvrv_band:
        alerts.append(f"MVRV band transition: {prev_state['mvrv_band']} -> {mvrv_band}")

    if bool(prev_state.get("elec_floor_breached")) != bool(elec_floor_breached):
        status = (
            "BELOW electrical cost floor"
            if elec_floor_breached
            else "RECLAIMED above electrical cost floor"
        )
        alerts.append(f"BTC {status}")

    prev_tiers = prev_state.get("asset_tiers", {})
    for ticker, tier in asset_tiers.items():
        if prev_tiers.get(ticker) and prev_tiers.get(ticker) != tier:
            alerts.append(f"{ticker} conviction tier: {prev_tiers[ticker]} -> {tier}")

    return alerts


class UniversalCryptoEngine:
    def __init__(self) -> None:
        self.watchlist: Dict[str, Dict[str, Any]] = {
            "BTC": {
                "class": "Macro Anchor",
                "alpha": 0.08,
                "mvrv": 1.15,
                "spot_price": 63635.16,
                "electrical_cost_floor": 54500.0,
                "sth_basis": 76150.0,
            },
            "ETH": {"class": "Macro Anchor", "alpha": 0.08, "mvrv": 1.65, "spot_price": 1761.48},
            "SOL": {"class": "High-Beta Altcoin", "alpha": 0.12, "mvrv": 2.10, "spot_price": 74.12},
            "XRP": {"class": "High-Beta Altcoin", "alpha": 0.12, "mvrv": 1.85, "spot_price": 0.9708},
            "ONDO": {"class": "High-Beta Altcoin", "alpha": 0.12, "mvrv": 1.40, "spot_price": 0.584},
            "SUI": {"class": "High-Beta Altcoin", "alpha": 0.12, "mvrv": 1.50, "spot_price": 0.968},
            "SEI": {"class": "High-Beta Altcoin", "alpha": 0.12, "mvrv": 1.30, "spot_price": 0.0485},
            "HBAR": {"class": "High-Beta Altcoin", "alpha": 0.12, "mvrv": 1.55, "spot_price": 0.1175},
            "HYPE": {"class": "High-Beta Altcoin", "alpha": 0.12, "mvrv": 1.70, "spot_price": 24.50},
        }
        self.feedback_history: List[Dict[str, Any]] = []

    def classify_mvrv_band(self, mvrv_value: float) -> str:
        if mvrv_value < 1.2:
            return "UNDERVALUED_BOTTOM"
        if mvrv_value <= 2.4:
            return "FAIR_VALUE_ACCUMULATION"
        return "OVERVALUED_EUPHORIA"

    def evaluate_mvrv_valuation(self, mvrv_value: float) -> str:
        if mvrv_value < 1.2:
            return "Significantly Undervalued (Historical Market Bottom / Strong Buy)"
        if mvrv_value <= 2.4:
            return "Fairly Valued (Structural Accumulation / Neutral)"
        return "Overvalued (Euphoria / Distribution Zone)"

    def evaluate_sfp_signal(
        self, price_series: List[float], volume_series: List[float], sweep_level: float
    ) -> bool:
        if len(price_series) < 2 or len(volume_series) < 2:
            return False
        sweep = price_series[-2] < sweep_level and price_series[-1] > sweep_level
        volume_spike = volume_series[-1] > float(np.mean(volume_series)) * 1.4
        return bool(sweep and volume_spike)

    def compute_conviction_tier(self, ticker: str, asset: Dict[str, Any]) -> str:
        mvrv = float(asset.get("mvrv", 1.5))
        price = float(asset.get("spot_price", 0.0))
        if ticker == "BTC" and "electrical_cost_floor" in asset:
            floor = float(asset["electrical_cost_floor"])
            if price <= floor:
                return "CAPITULATION_WATCH"
            if mvrv < 1.2:
                return "HIGH_CONVICTION_ACCUMULATE"
        if mvrv < 1.2:
            return "HIGH_CONVICTION_ACCUMULATE"
        if mvrv > 2.4:
            return "TRIM_DISTRIBUTION"
        return "CORE_HOLD"

    def check_institutional_alerts(self, ticker: str, spot_price: float) -> List[Dict[str, str]]:
        symbol = ticker.upper()
        if symbol not in self.watchlist:
            return []
        asset = self.watchlist[symbol]
        alerts: List[Dict[str, str]] = []

        mvrv = float(asset.get("mvrv", 1.5))
        if mvrv < 1.2:
            alerts.append(
                {
                    "level": "CRITICAL_OPPORTUNITY",
                    "indicator": "MVRV Ratio",
                    "message": f"[{symbol}] MVRV is {mvrv} (< 1.2): Historical Market Bottom / Strong Buy Signal",
                }
            )

        if symbol == "BTC" and "electrical_cost_floor" in asset:
            energy_floor = float(asset["electrical_cost_floor"])
            sth_basis = float(asset.get("sth_basis", 76150.0))
            if spot_price <= energy_floor:
                alerts.append(
                    {
                        "level": "EMERGENCY_CAPITULATION",
                        "indicator": "Electrical Cost Floor",
                        "message": f"BTC Spot (${spot_price:,.2f}) at/below Electrical Cost Floor (${energy_floor:,.2f})",
                    }
                )
            elif spot_price <= sth_basis:
                alerts.append(
                    {
                        "level": "WARNING_SUPPORT",
                        "indicator": "STH Cost Basis",
                        "message": f"BTC Spot (${spot_price:,.2f}) testing STH Cost Basis (${sth_basis:,.2f})",
                    }
                )
            else:
                margin = ((spot_price - energy_floor) / energy_floor) * 100.0
                alerts.append(
                    {
                        "level": "INFO_STABLE",
                        "indicator": "Thermodynamic Margin",
                        "message": f"BTC Spot maintaining +{margin:.1f}% margin above ${energy_floor:,.0f} electrical floor",
                    }
                )

        return alerts

    def run_feedback_loop(
        self, ticker: str, predicted_target: float, realized_price: float, timeframe: str = "24h"
    ) -> Dict[str, Any]:
        symbol = ticker.upper()
        if symbol not in self.watchlist:
            self.watchlist[symbol] = {"class": "High-Beta Altcoin", "alpha": 0.12, "mvrv": 1.4}

        asset = self.watchlist[symbol]
        asset["spot_price"] = realized_price
        alpha = float(asset.get("alpha", 0.12))
        error = abs(realized_price - predicted_target) / max(predicted_target, 1e-9)
        accuracy = max(0.0, 100.0 * (1.0 - error))
        adjustment = alpha * error
        alerts = self.check_institutional_alerts(symbol, realized_price)

        entry = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "ticker": symbol,
            "timeframe": timeframe,
            "mvrv_ratio": asset.get("mvrv", 1.4),
            "valuation_status": self.evaluate_mvrv_valuation(float(asset.get("mvrv", 1.4))),
            "error_pct": round(error * 100.0, 2),
            "accuracy_score": round(accuracy, 2),
            "dynamic_adjustment": round(adjustment, 4),
            "alerts_triggered": alerts,
        }
        self.feedback_history.append(entry)
        return entry


def dispatch_notifications(summary_text: str, payload: Dict[str, Any]) -> None:
    webhook_url = os.getenv("ALERT_WEBHOOK_URL", "").strip()
    if webhook_url:
        try:
            req = urllib.request.Request(
                webhook_url,
                data=json.dumps({"text": summary_text, "state": payload}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10):
                pass
        except Exception as exc:
            print(f"[WARN] Webhook dispatch skipped/failed: {exc}")

    smtp_host = os.getenv("SMTP_HOST", "").strip()
    smtp_user = os.getenv("SMTP_USER", "").strip()
    smtp_pass = os.getenv("SMTP_PASS", "").strip()
    email_to = os.getenv("ALERT_EMAIL_TO", "").strip()
    smtp_port = int(os.getenv("SMTP_PORT", "587") or "587")

    if smtp_host and smtp_user and smtp_pass and email_to:
        try:
            msg = EmailMessage()
            msg["Subject"] = "CryptoAnalyst Intelligence & State Alert"
            msg["From"] = smtp_user
            msg["To"] = email_to
            msg.set_content(summary_text)
            with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)
        except Exception as exc:
            print(f"[WARN] SMTP email dispatch skipped/failed: {exc}")


def main() -> None:
    engine = UniversalCryptoEngine()
    prev_state = load_previous_state()

    btc_asset = engine.watchlist["BTC"]
    btc_spot = float(btc_asset["spot_price"])
    elec_floor = float(btc_asset["electrical_cost_floor"])
    elec_floor_breached = btc_spot <= elec_floor
    mvrv_band = engine.classify_mvrv_band(float(btc_asset["mvrv"]))

    asset_tiers = {
        ticker: engine.compute_conviction_tier(ticker, cfg)
        for ticker, cfg in engine.watchlist.items()
    }
    current_regime = (
        "THERMODYNAMIC_STRESS"
        if elec_floor_breached
        else ("ACCUMULATION_DISCOUNT" if mvrv_band == "UNDERVALUED_BOTTOM" else "STRUCTURAL_EXPANSION")
    )

    transitions = detect_state_transitions(
        prev_state=prev_state,
        current_regime=current_regime,
        asset_tiers=asset_tiers,
        elec_floor_breached=elec_floor_breached,
        mvrv_band=mvrv_band,
    )

    feedback_entry = engine.run_feedback_loop("BTC", predicted_target=64000.0, realized_price=btc_spot, timeframe="24h")
    all_alerts = transitions + [a["message"] for a in feedback_entry["alerts_triggered"]]

    state_payload: Dict[str, Any] = {
        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "regime": current_regime,
        "mvrv_band": mvrv_band,
        "elec_floor_breached": elec_floor_breached,
        "btc_spot": btc_spot,
        "electrical_cost_floor": elec_floor,
        "asset_tiers": asset_tiers,
        "transitions": transitions,
        "alerts": all_alerts,
        "latest_feedback": feedback_entry,
    }
    save_current_state(state_payload)

    summary = (
        f"Regime: {current_regime} | MVRV Band: {mvrv_band} | BTC: ${btc_spot:,.2f}\n"
        + ("\n".join(f"- {item}" for item in all_alerts) if all_alerts else "- No new state transitions or alerts.")
    )
    dispatch_notifications(summary, state_payload)
    print(json.dumps(state_payload, indent=2))


if __name__ == "__main__":
    main()

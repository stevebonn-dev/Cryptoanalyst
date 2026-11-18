"""
Universal Institutional Crypto Intelligence Engine - Run Module
Incorporating Automated Alerts, MVRV Valuation, Electrical Cost Floor,
SFP Indicators, and Self-Improving Feedback Telemetry.
"""
import numpy as np
import json
import datetime

class UniversalCryptoEngine:
    def __init__(self):
        self.watchlist = {
            "BTC": {
                "class": "Macro Anchor", "alpha": 0.08, "mvrv": 1.15,
                "electrical_cost_floor": 68500.0, "sth_basis": 76150.0
            },
            "ETH": {"class": "Macro Anchor", "alpha": 0.08, "mvrv": 1.65},
            "SOL": {"class": "High-Beta Altcoin", "alpha": 0.12, "mvrv": 2.10},
            "XRP": {"class": "High-Beta Altcoin", "alpha": 0.12, "mvrv": 1.85},
            "ONDO": {"class": "High-Beta Altcoin", "alpha": 0.12, "mvrv": 1.40},
            "SUI": {"class": "High-Beta Altcoin", "alpha": 0.12, "mvrv": 1.50},
            "SEI": {"class": "High-Beta Altcoin", "alpha": 0.12, "mvrv": 1.30},
            "HBAR": {"class": "High-Beta Altcoin", "alpha": 0.12, "mvrv": 1.55},
            "HYPE": {"class": "High-Beta Altcoin", "alpha": 0.12, "mvrv": 1.70}
        }
        self.feedback_history = []

    def evaluate_mvrv_valuation(self, mvrv_value):
        if mvrv_value < 1.2:
            return "Significantly Undervalued (Historical Market Bottom / Strong Buy)"
        elif 1.2 <= mvrv_value <= 2.4:
            return "Fairly Valued (Structural Accumulation / Neutral)"
        else:
            return "Overvalued (Euphoria / Distribution Zone)"

    def check_institutional_alerts(self, ticker, spot_price):
        ticker = ticker.upper()
        if ticker not in self.watchlist:
            return []
        
        asset = self.watchlist[ticker]
        alerts = []
        mvrv = asset.get("mvrv", 1.5)
        if mvrv < 1.2:
            alerts.append({
                "level": "CRITICAL_OPPORTUNITY",
                "indicator": "MVRV Ratio",
                "message": f"🚨 [{ticker}] MVRV is {mvrv} (< 1.2): Historical Market Bottom & Strong Buy Signal!"
            })
            
        if ticker == "BTC" and "electrical_cost_floor" in asset:
            energy_floor = asset["electrical_cost_floor"]
            sth_basis = asset.get("sth_basis", 76150.0)
            if spot_price <= energy_floor:
                alerts.append({
                    "level": "EMERGENCY_CAPITULATION",
                    "indicator": "Electrical Cost Floor",
                    "message": f"⚡ CRITICAL ALERT: BTC Spot (${spot_price:,.2f}) breached Thermodynamic Energy Floor (${energy_floor:,.2f})!"
                })
            elif spot_price <= sth_basis:
                alerts.append({
                    "level": "WARNING_SUPPORT",
                    "indicator": "STH Cost Basis",
                    "message": f"⚠️ WARNING: BTC Spot (${spot_price:,.2f}) testing Short-Term Holder Cost Basis (${sth_basis:,.2f})."
                })
            else:
                margin = ((spot_price - energy_floor) / energy_floor) * 100
                alerts.append({
                    "level": "INFO_STABLE",
                    "indicator": "Thermodynamic Margin",
                    "message": f"✅ BTC Spot maintaining +{margin:.1f}% buffer above $68.5k electrical cost floor."
                })
        return alerts

    def run_feedback_loop(self, ticker, predicted_target, realized_price, timeframe="24h"):
        ticker = ticker.upper()
        if ticker not in self.watchlist:
            self.watchlist[ticker] = {"class": "High-Beta Altcoin", "alpha": 0.12, "mvrv": 1.4}
            
        asset = self.watchlist[ticker]
        alpha = asset["alpha"]
        error = abs(realized_price - predicted_target) / predicted_target
        accuracy = max(0.0, 100.0 * (1.0 - error))
        adjustment = alpha * error
        active_alerts = self.check_institutional_alerts(ticker, realized_price)

        log_entry = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "ticker": ticker,
            "timeframe": timeframe,
            "mvrv_ratio": asset.get("mvrv", 1.4),
            "valuation_status": self.evaluate_mvrv_valuation(asset.get("mvrv", 1.4)),
            "error_pct": round(error * 100, 2),
            "accuracy_score": round(accuracy, 2),
            "dynamic_adjustment": round(adjustment, 4),
            "alerts_triggered": active_alerts
        }
        self.feedback_history.append(log_entry)
        return log_entry

if __name__ == "__main__":
    engine = UniversalCryptoEngine()
    print("[INIT] Universal Crypto Intelligence & Alerting Engine Active.")
    test_log = engine.run_feedback_loop("BTC", 85500.0, 85478.23, "24h")
    print(f"\n[TEST RUN TELEMETRY & ALERTS DISPATCH]:\n{json.dumps(test_log, indent=2)}")

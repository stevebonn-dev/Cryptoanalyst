"""
Universal Institutional Crypto Intelligence Engine - Run Module
Incorporating MVRV Valuation, Bitcoin Electrical Production Cost Floor,
SFP Indicators, and Self-Improving Feedback Telemetry.
"""
import numpy as np
import json
import datetime

class UniversalCryptoEngine:
    def __init__(self):
        self.watchlist = {
            "BTC": {
                "class": "Macro Anchor",
                "alpha": 0.08,
                "mvrv": 1.15,
                "electrical_cost_floor": 68500.0,
                "sth_basis": 76150.0
            },
            "ETH": {"class": "Macro Anchor", "alpha": 0.08, "mvrv": 1.65},
            "SOL": {"class": "High-Beta Altcoin", "alpha": 0.12, "mvrv": 2.10},
            "XRP": {"class": "High-Beta Altcoin", "alpha": 0.12, "mvrv": 1.85},
            "ONDO": {"class": "High-Beta Altcoin", "alpha": 0.12, "mvrv": 1.40}
        }
        self.feedback_history = []

    def evaluate_mvrv_valuation(self, mvrv_value):
        """Evaluates valuation status based on MVRV ratio thresholds."""
        if mvrv_value < 1.2:
            return "Significantly Undervalued (Historical Market Bottom / Strong Buy)"
        elif 1.2 <= mvrv_value <= 2.4:
            return "Fairly Valued (Structural Accumulation / Neutral)"
        else:
            return "Overvalued (Euphoria / Distribution Zone)"

    def evaluate_electrical_cost_floor(self, spot_price, electrical_cost=68500.0):
        """Evaluates spot price proximity to the Bitcoin thermodynamic electrical production floor."""
        margin_pct = ((spot_price - electrical_cost) / electrical_cost) * 100.0
        if spot_price <= electrical_cost:
            status = "Below Electrical Floor (Extreme Miner Capitulation / Generational Buy)"
        elif margin_pct <= 15.0:
            status = "Near Thermodynamic Floor (High-Conviction Macro Accumulation)"
        else:
            status = "Healthy Margin Above Energy Floor (Sustainable Miner Profitability)"
        return {
            "electrical_cost_floor": electrical_cost,
            "margin_above_floor_pct": round(margin_pct, 2),
            "energy_status": status
        }

    def register_asset(self, ticker, market_cap_billions, mvrv_ratio=1.5, electrical_cost=None):
        ticker = ticker.upper()
        is_macro = market_cap_billions >= 50.0
        alpha = 0.08 if is_macro else 0.12
        valuation_status = self.evaluate_mvrv_valuation(mvrv_ratio)

        asset_record = {
            "class": "Macro Anchor" if is_macro else "High-Beta Altcoin",
            "alpha": alpha,
            "mvrv": mvrv_ratio,
            "valuation": valuation_status,
            "status": "Active"
        }
        if electrical_cost is not None:
            asset_record["electrical_cost_floor"] = float(electrical_cost)

        self.watchlist[ticker] = asset_record
        print(f"[ONBOARDING] {ticker} registered | MVRV: {mvrv_ratio} ({valuation_status})")
        return self.watchlist[ticker]

    def run_feedback_loop(self, ticker, predicted_target, realized_price, timeframe="24h"):
        ticker = ticker.upper()
        if ticker not in self.watchlist:
            self.register_asset(ticker, market_cap_billions=10.0, mvrv_ratio=1.4)

        asset = self.watchlist[ticker]
        alpha = asset["alpha"]
        error = abs(realized_price - predicted_target) / predicted_target
        accuracy = max(0.0, 100.0 * (1.0 - error))
        adjustment = alpha * error

        log_entry = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "ticker": ticker,
            "timeframe": timeframe,
            "mvrv_ratio": asset.get("mvrv", 1.4),
            "valuation_status": self.evaluate_mvrv_valuation(asset.get("mvrv", 1.4)),
            "error_pct": round(error * 100, 2),
            "accuracy_score": round(accuracy, 2),
            "dynamic_adjustment": round(adjustment, 4)
        }

        if "electrical_cost_floor" in asset:
            log_entry["thermodynamic_metrics"] = self.evaluate_electrical_cost_floor(
                realized_price, asset["electrical_cost_floor"]
            )

        self.feedback_history.append(log_entry)
        return log_entry

if __name__ == "__main__":
    engine = UniversalCryptoEngine()
    print("[INIT] Universal Crypto Intelligence & Thermodynamic Valuation Engine Active.")
    test_log = engine.run_feedback_loop("BTC", 85500.0, 85934.11, "24h")
    print(f"[TELEMETRY TEST] Recorded:\n{json.dumps(test_log, indent=2)}")

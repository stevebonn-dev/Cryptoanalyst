"""
Institutional Crypto Intelligence Engine - Run Module
Handles automated dispatch, SFP detection, self-improving feedback loop,
and persistent state files for the frontend dashboard.
"""
import json
import os
from datetime import datetime, timezone
import numpy as np


DEFAULT_ASSETS = ["BTC", "ETH", "SOL", "XRP", "ONDO", "SUI", "SEI", "HBAR", "HYPE"]
MACRO_ASSETS = {"BTC", "ETH"}


class CryptoEngine:
    def __init__(
        self,
        alpha_macro: float = 0.08,
        alpha_high_beta: float = 0.12,
        state_path: str = "state/last_run.json",
        recommendations_path: str = "state/recommendations_log.json",
        reliability_path: str = "state/feed_reliability.json",
    ):
        self.alpha_macro = alpha_macro
        self.alpha_high_beta = alpha_high_beta
        self.state_path = state_path
        self.recommendations_path = recommendations_path
        self.reliability_path = reliability_path
        self.history = []
        self.recommendations = []
        self._load_existing_state()

    def _load_existing_state(self):
        """Loads existing run history and recommendations so deployments do not wipe state."""
        if os.path.exists(self.state_path):
            try:
                with open(self.state_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and isinstance(data.get("history"), list):
                    self.history = data["history"]
            except (OSError, json.JSONDecodeError):
                pass

        if os.path.exists(self.recommendations_path):
            try:
                with open(self.recommendations_path, "r", encoding="utf-8") as f:
                    recs = json.load(f)
                if isinstance(recs, list):
                    self.recommendations = recs
            except (OSError, json.JSONDecodeError):
                pass

    def calculate_sfp_signal(self, price_series, volume_series, vh_level: float) -> bool:
        """Detects Swing Failure Pattern (SFP) / Failed Auction setups."""
        if len(price_series) < 2 or len(volume_series) < 1:
            return False
        sweep = price_series[-2] < vh_level and price_series[-1] > vh_level
        volume_spike = volume_series[-1] > np.mean(volume_series) * 1.5
        return bool(sweep and volume_spike)

    def run_feedback_loop(
        self, asset: str, predicted_target: float, realized_price: float, timeframe: str = "24h"
    ) -> dict:
        """Closed-loop error correction tracking predictive variance."""
        if predicted_target == 0:
            raise ValueError("predicted_target must be non-zero")
        error = abs(realized_price - predicted_target) / predicted_target
        alpha = self.alpha_macro if asset in MACRO_ASSETS else self.alpha_high_beta

        accuracy_score = max(0.0, 100.0 * (1.0 - error))
        adjustment = alpha * error

        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "asset": asset,
            "timeframe": timeframe,
            "error_pct": round(error * 100, 2),
            "accuracy_pct": round(accuracy_score, 2),
            "adjustment_applied": round(adjustment, 4),
        }
        self.history.append(log_entry)
        return log_entry

    def record_recommendation(
        self,
        asset: str,
        action: str,
        entry_price: float,
        target_price: float | None = None,
        bias: str = "NEUTRAL",
        notes: str = "",
    ) -> dict:
        """Appends a recommendation record while preserving backward-compatible keys."""
        entry = {
            "id": f"rec_{len(self.recommendations) + 1}_{int(datetime.now(timezone.utc).timestamp())}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "asset": asset,
            "ticker": asset,
            "action": action,
            "bias": bias,
            "entryPrice": entry_price,
            "targetPrice": target_price,
            "notes": notes,
        }
        self.recommendations.append(entry)
        return entry

    def write_feed_reliability_benchmark(self, feed_scores: dict | None = None):
        """Writes ./state/feed_reliability.json for frontend reliability syncing."""
        os.makedirs(os.path.dirname(self.reliability_path) or ".", exist_ok=True)
        payload = {
            "sourceName": "ThirdPartySignalIndex",
            "updatedAt": datetime.now(timezone.utc).isoformat(),
            "defaultPrior": {
                "score": 55,
                "source": "DefaultBaseline",
            },
            "feeds": feed_scores
            if feed_scores is not None
            else {
                "@seliseli_46": {
                    "score": 72,
                    "source": "ThirdPartySignalIndex",
                    "verifiedCalls": 10,
                }
            },
        }
        with open(self.reliability_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    def save_state(self):
        """Persists latest execution telemetry and recommendations to disk."""
        os.makedirs(os.path.dirname(self.state_path) or ".", exist_ok=True)
        os.makedirs(os.path.dirname(self.recommendations_path) or ".", exist_ok=True)

        run_payload = {
            "lastRunAt": datetime.now(timezone.utc).isoformat(),
            "assets": DEFAULT_ASSETS,
            "history": self.history,
        }
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump(run_payload, f, indent=2)

        with open(self.recommendations_path, "w", encoding="utf-8") as f:
            json.dump(self.recommendations, f, indent=2)


if __name__ == "__main__":
    engine = CryptoEngine()
    engine.write_feed_reliability_benchmark()
    engine.save_state()
    print("Institutional Crypto Intelligence Engine Initialized & State Saved.")

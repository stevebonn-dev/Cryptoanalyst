import json
import os
from datetime import datetime, timezone
import numpy as np


DEFAULT_ASSETS = ["BTC", "ETH", "SOL", "XRP", "ONDO", "SUI", "SEI", "HBAR", "HYPE"]
MACRO_ASSETS = {"BTC", "ETH"}

DEFAULT_ZONE_WEIGHTS = {
    "z_score": 0.24,
    "trend_ma": 0.22,
    "pvsra_vd": 0.20,
    "sfp_liq": 0.18,
    "cycle_model": 0.16,
}

ZONES = ("Bottoming", "Buy Zone", "Hold", "Break Out", "Sell Zone")


def classify_action_zone(
    score: float,
    momentum: float,
    z_score: float = 0.0,
    pvsra_climax: bool = False,
    sfp_bullish: bool = False,
) -> str:
    """Maps a composite score (-100..+100) and momentum (-100..+100) into one of 5 zones."""
    if score <= -65.0 and (z_score <= -2.5 or pvsra_climax or sfp_bullish):
        return "Bottoming"
    if score <= -25.0:
        return "Buy Zone"
    if score >= 70.0:
        return "Sell Zone"
    if score >= 30.0 and momentum >= 25.0:
        return "Break Out"
    return "Hold"


class CryptoEngine:
    def __init__(
        self,
        alpha_macro: float = 0.08,
        alpha_high_beta: float = 0.12,
        state_path: str = "state/last_run.json",
        recommendations_path: str = "state/recommendations_log.json",
        reliability_path: str = "state/feed_reliability.json",
        matrix_path: str = "state/action_matrix.json",
    ):
        self.alpha_macro = alpha_macro
        self.alpha_high_beta = alpha_high_beta
        self.state_path = state_path
        self.recommendations_path = recommendations_path
        self.reliability_path = reliability_path
        self.matrix_path = matrix_path
        self.history = []
        self.recommendations = []
        self.zone_weights = dict(DEFAULT_ZONE_WEIGHTS)
        self.indicator_accuracy = {k: 0.55 for k in DEFAULT_ZONE_WEIGHTS}
        self.latest_matrix = []
        self._load_existing_state()

    def _normalize_weights(self, weights: dict) -> dict:
        """Clamps weights to [0.05, 0.45] and normalizes so they sum to 1.0."""
        cleaned = {}
        for k in DEFAULT_ZONE_WEIGHTS:
            val = float(weights.get(k, DEFAULT_ZONE_WEIGHTS[k]))
            cleaned[k] = float(np.clip(val, 0.05, 0.45))
        total = sum(cleaned.values())
        if total <= 0:
            return dict(DEFAULT_ZONE_WEIGHTS)
        return {k: round(v / total, 6) for k, v in cleaned.items()}

    def _load_existing_state(self):
        """Loads existing run history, optimized weights, and recommendations."""
        if os.path.exists(self.state_path):
            try:
                with open(self.state_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    if isinstance(data.get("history"), list):
                        self.history = data["history"]
                    if isinstance(data.get("zoneWeights"), dict):
                        self.zone_weights = self._normalize_weights(data["zoneWeights"])
                    if isinstance(data.get("indicatorAccuracy"), dict):
                        for k in DEFAULT_ZONE_WEIGHTS:
                            if k in data["indicatorAccuracy"]:
                                self.indicator_accuracy[k] = float(
                                    np.clip(data["indicatorAccuracy"][k], 0.0, 1.0)
                                )
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

    def optimize_zone_weights(
        self,
        asset: str,
        realized_return_pct: float,
        indicator_signals: dict | None = None,
    ) -> dict:
        """
        Continuously updates indicator weights based on directional alignment with
        realized forward returns. Positive indicator signals paired with positive
        returns (or negative signals paired with negative returns) reinforce that
        indicator's weight and rolling accuracy score.
        """
        alpha = self.alpha_macro if asset in MACRO_ASSETS else self.alpha_high_beta
        if not indicator_signals:
            return self.zone_weights

        direction = 1.0 if realized_return_pct > 0.25 else (-1.0 if realized_return_pct < -0.25 else 0.0)
        if direction == 0.0:
            return self.zone_weights

        updated = dict(self.zone_weights)
        for key in DEFAULT_ZONE_WEIGHTS:
            sig = float(np.clip(indicator_signals.get(key, 0.0), -1.0, 1.0))
            aligned = (sig * direction) > 0
            prev_acc = self.indicator_accuracy.get(key, 0.55)
            new_acc = prev_acc + alpha * ((1.0 if aligned else 0.0) - prev_acc)
            self.indicator_accuracy[key] = round(float(np.clip(new_acc, 0.05, 0.99)), 4)

            delta = alpha * (1.0 if aligned else -0.65) * abs(sig if sig != 0 else 0.5)
            updated[key] = updated.get(key, DEFAULT_ZONE_WEIGHTS[key]) * (1.0 + delta)

        self.zone_weights = self._normalize_weights(updated)
        return self.zone_weights

    def score_asset_zone(self, asset: str, metrics: dict) -> dict:
        """
        Computes a weighted composite score (-100..+100), momentum score (-100..+100),
        and 5-zone classification for a single asset from indicator metrics.

        Expected optional keys in `metrics`:
          price, z_score, vd_score, ma50_dist_pct, ma200_dist_pct,
          pvsra_climax (bool), pvsra_rising (bool), sfp_bullish (bool), sfp_bearish (bool),
          liq_skew (-1..+1), pl_dev_pct, mvrv, range_pos (-1..+1)
        """
        price = float(metrics.get("price", 0.0))
        z_score = float(metrics.get("z_score", 0.0))
        vd_score = float(metrics.get("vd_score", 0.0))
        ma50_dist = float(metrics.get("ma50_dist_pct", 0.0))
        ma200_dist = float(metrics.get("ma200_dist_pct", 0.0))
        pvsra_climax = bool(metrics.get("pvsra_climax", False))
        pvsra_rising = bool(metrics.get("pvsra_rising", False))
        sfp_bullish = bool(metrics.get("sfp_bullish", False))
        sfp_bearish = bool(metrics.get("sfp_bearish", False))
        liq_skew = float(metrics.get("liq_skew", 0.0))
        pl_dev_pct = float(metrics.get("pl_dev_pct", 0.0))
        mvrv = float(metrics.get("mvrv", 1.0))
        range_pos = float(metrics.get("range_pos", 0.0))

        # 1. Z-Score component (-1..+1; deep negative = buy/bottoming, high positive = sell/trim)
        if z_score <= -4.27:
            z_comp = -1.0
        elif z_score <= -1.58:
            z_comp = float(np.interp(z_score, [-4.27, -1.58], [-1.0, -0.55]))
        elif z_score >= 1.58:
            z_comp = float(np.interp(z_score, [1.58, 4.0], [0.55, 1.0]))
        else:
            z_comp = float(np.clip(z_score / 1.58 * 0.55, -0.55, 0.55))

        # 2. Trend / MA component (-1..+1)
        ma_comp = float(np.clip((0.6 * (ma200_dist / 25.0)) + (0.4 * (ma50_dist / 12.0)), -1.0, 1.0))

        # 3. PVSRA + VD volume/delta component (-1..+1)
        vd_norm = float(np.clip(vd_score / 1.2, -1.0, 1.0))
        pvsra_adj = 0.0
        if pvsra_climax:
            pvsra_adj = -0.35 if vd_norm < 0 else 0.35
        elif pvsra_rising:
            pvsra_adj = 0.15 * np.sign(vd_norm)
        pvsra_vd_comp = float(np.clip(0.75 * vd_norm + pvsra_adj, -1.0, 1.0))

        # 4. SFP & Liquidation Skew component (-1..+1)
        sfp_adj = (-0.45 if sfp_bullish else 0.0) + (0.45 if sfp_bearish else 0.0)
        sfp_liq_comp = float(np.clip(0.6 * np.clip(liq_skew, -1.0, 1.0) + sfp_adj, -1.0, 1.0))

        # 5. Cycle / Valuation / Range component (-1..+1)
        if asset == "BTC":
            pl_comp = float(np.clip(pl_dev_pct / 60.0, -1.0, 1.0))
            mvrv_comp = float(np.clip((mvrv - 1.0) / 0.6, -1.0, 1.0))
            cycle_comp = float(np.clip(0.6 * pl_comp + 0.4 * mvrv_comp, -1.0, 1.0))
        else:
            cycle_comp = float(np.clip(range_pos, -1.0, 1.0))

        components = {
            "z_score": round(z_comp, 4),
            "trend_ma": round(ma_comp, 4),
            "pvsra_vd": round(pvsra_vd_comp, 4),
            "sfp_liq": round(sfp_liq_comp, 4),
            "cycle_model": round(cycle_comp, 4),
        }

        w = self.zone_weights
        weighted_norm = sum(w[k] * components[k] for k in DEFAULT_ZONE_WEIGHTS)
        composite_score = round(float(np.clip(weighted_norm * 100.0, -100.0, 100.0)), 2)

        momentum_raw = (
            (45.0 * vd_norm)
            + (35.0 * np.clip(ma50_dist / 10.0, -1.0, 1.0))
            + (20.0 if pvsra_climax or pvsra_rising else 0.0)
        )
        momentum = round(float(np.clip(momentum_raw, -100.0, 100.0)), 2)

        zone = classify_action_zone(
            score=composite_score,
            momentum=momentum,
            z_score=z_score,
            pvsra_climax=pvsra_climax,
            sfp_bullish=sfp_bullish,
        )

        # Rank top drivers by absolute weighted contribution
        ranked = sorted(
            DEFAULT_ZONE_WEIGHTS.keys(),
            key=lambda k: abs(w[k] * components[k]),
            reverse=True,
        )
        top_drivers = [
            f"{k} ({components[k]:+.2f}, w={w[k]:.2f})" for k in ranked[:3]
        ]

        return {
            "asset": asset,
            "price": price,
            "compositeScore": composite_score,
            "momentum": momentum,
            "zone": zone,
            "zScore": round(z_score, 2),
            "components": components,
            "topDrivers": top_drivers,
        }

    def build_action_matrix(self, asset_metrics: dict[str, dict]) -> list[dict]:
        """Computes and stores the 5-zone action matrix across all supplied assets."""
        assets = list(asset_metrics.keys()) if asset_metrics else DEFAULT_ASSETS
        matrix = []
        for sym in assets:
            m = asset_metrics.get(sym, {}) if isinstance(asset_metrics, dict) else {}
            matrix.append(self.score_asset_zone(sym, m))
        self.latest_matrix = matrix
        return matrix

    def run_feedback_loop(
        self,
        asset: str,
        predicted_target: float,
        realized_price: float,
        timeframe: str = "24h",
        indicator_signals: dict | None = None,
    ) -> dict:
        """Closed-loop error correction tracking predictive variance & optimizing weights."""
        if predicted_target == 0:
            raise ValueError("predicted_target must be non-zero")
        error = abs(realized_price - predicted_target) / predicted_target
        realized_return_pct = ((realized_price - predicted_target) / predicted_target) * 100.0
        alpha = self.alpha_macro if asset in MACRO_ASSETS else self.alpha_high_beta

        accuracy_score = max(0.0, 100.0 * (1.0 - error))
        adjustment = alpha * error

        self.optimize_zone_weights(
            asset=asset,
            realized_return_pct=realized_return_pct,
            indicator_signals=indicator_signals,
        )

        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "asset": asset,
            "timeframe": timeframe,
            "error_pct": round(error * 100, 2),
            "accuracy_pct": round(accuracy_score, 2),
            "adjustment_applied": round(adjustment, 4),
            "zone_weights": dict(self.zone_weights),
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

    def write_action_matrix_state(self):
        """Writes ./state/action_matrix.json for frontend action-zone matrix rendering."""
        os.makedirs(os.path.dirname(self.matrix_path) or ".", exist_ok=True)
        grouped = {z: [row["asset"] for row in self.latest_matrix if row["zone"] == z] for z in ZONES}
        payload = {
            "updatedAt": datetime.now(timezone.utc).isoformat(),
            "zones": list(ZONES),
            "zoneWeights": self.zone_weights,
            "indicatorAccuracy": self.indicator_accuracy,
            "zoneCounts": {z: len(grouped[z]) for z in ZONES},
            "groupedAssets": grouped,
            "assets": self.latest_matrix,
        }
        with open(self.matrix_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    def save_state(self):
        """Persists latest execution telemetry, zone weights, and recommendations to disk."""
        os.makedirs(os.path.dirname(self.state_path) or ".", exist_ok=True)
        os.makedirs(os.path.dirname(self.recommendations_path) or ".", exist_ok=True)

        if not self.latest_matrix:
            self.build_action_matrix({sym: {} for sym in DEFAULT_ASSETS})

        run_payload = {
            "lastRunAt": datetime.now(timezone.utc).isoformat(),
            "assets": DEFAULT_ASSETS,
            "zoneWeights": self.zone_weights,
            "indicatorAccuracy": self.indicator_accuracy,
            "history": self.history,
        }
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump(run_payload, f, indent=2)

        with open(self.recommendations_path, "w", encoding="utf-8") as f:
            json.dump(self.recommendations, f, indent=2)

        self.write_action_matrix_state()


if __name__ == "__main__":
    engine = CryptoEngine()
    engine.write_feed_reliability_benchmark()
    engine.save_state()
    print("Institutional Crypto Intelligence Engine Initialized & State Saved.")

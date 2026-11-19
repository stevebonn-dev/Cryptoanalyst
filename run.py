import json
import os
from datetime import datetime, timezone
from typing import Dict, List, Any
import urllib.request
import numpy as np
import pandas as pd

from bottom_matrix import run_bottom_detector

WATCHLIST = ["BTC", "ETH", "SOL", "XRP", "ONDO", "SUI", "SEI", "HBAR", "HYPE"]
OUTPUT_FILE = "data.json"
TELEMETRY_LOG = "feedback_telemetry.json"


def fetch_binance_klines(symbol: str, limit: int = 210) -> pd.DataFrame:
    """Fetches daily OHLCV candles from Binance Spot API for MWA calculation."""
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}USDT&interval=1d&limit={limit}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Cryptoanalyst-Bot/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
        df = pd.DataFrame(
            raw,
            columns=[
                "open_time", "open", "high", "low", "close", "volume",
                "close_time", "qav", "num_trades", "taker_base", "taker_quote", "ignore"
            ],
        )
        df["close"] = df["close"].astype(float)
        df["volume"] = df["volume"].astype(float)
        return df
    except Exception:
        return pd.DataFrame()


def compute_asset_matrix(ticker: str, bottom_regime: str) -> Dict[str, Any]:
    df = fetch_binance_klines(ticker, limit=210)
    if df.empty or len(df) < 50:
        return {
            "ticker": ticker,
            "status": "NO_SPOT_PAIR_ON_BINANCE",
            "price": None,
            "mwa_50": None,
            "mwa_100": None,
            "mwa_200": None,
            "signal": "HOLD",
        }

    price = float(df["close"].iloc[-1])
    mwa_50 = float(df["close"].rolling(50).mean().iloc[-1])
    mwa_100 = float(df["close"].rolling(100).mean().iloc[-1]) if len(df) >= 100 else mwa_50
    mwa_200 = float(df["close"].rolling(200).mean().iloc[-1]) if len(df) >= 200 else mwa_100

    # Combine trend structure with macro BTC bottom regime
    if price > mwa_200 and price > mwa_50:
        signal = "BULLISH_TREND"
    elif bottom_regime == "CONFIRMED_REVERSAL" and price < mwa_50:
        signal = "ACCUMULATE_REVERSAL"
    elif bottom_regime == "CAPITULATION_WATCH":
        signal = "STAGED_BID_WATCH"
    else:
        signal = "DEFENSIVE"

    return {
        "ticker": ticker,
        "status": "ACTIVE",
        "price": round(price, 4),
        "mwa_50": round(mwa_50, 4),
        "mwa_100": round(mwa_100, 4),
        "mwa_200": round(mwa_200, 4),
        "dist_200mwa_pct": round(((price - mwa_200) / mwa_200) * 100.0, 2),
        "signal": signal,
    }


def update_feedback_loop(current_assets: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Maintains rolling 7-day predictive error tracking and dynamic weight calibration."""
    history: List[Dict[str, Any]] = []
    if os.path.exists(TELEMETRY_LOG):
        try:
            with open(TELEMETRY_LOG, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            history = []

    btc_entry = next((a for a in current_assets if a["ticker"] == "BTC"), None)
    btc_price = btc_entry["price"] if btc_entry else None

    # Calculate 7-day realized variance if historical snapshot exists
    error_pct = 0.0
    learning_rate = 0.05
    if len(history) >= 7 and btc_price:
        prior_btc = history[-7].get("btc_price")
        prior_signal = history[-7].get("btc_signal")
        if prior_btc:
            realized_return = ((btc_price - prior_btc) / prior_btc) * 100.0
            expected_return = 4.0 if prior_signal in ("BULLISH_TREND", "ACCUMULATE_REVERSAL") else -2.0
            error_pct = round(abs(realized_return - expected_return), 2)
            # Adaptive weight adjustment bounded between 0.01 and 0.15
            learning_rate = round(float(np.clip(0.05 * (1 + error_pct / 20.0), 0.01, 0.15)), 4)

    snapshot = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "btc_price": btc_price,
        "btc_signal": btc_entry["signal"] if btc_entry else "UNKNOWN",
        "rolling_7d_error_pct": error_pct,
        "dynamic_learning_rate": learning_rate,
    }
    history.append(snapshot)
    history = history[-90:]  # Keep 90 runs

    with open(TELEMETRY_LOG, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)

    return snapshot


def main() -> None:
    bottom_report = run_bottom_detector()
    regime = bottom_report["regime"]

    asset_matrix = [compute_asset_matrix(ticker, regime) for ticker in WATCHLIST]
    telemetry = update_feedback_loop(asset_matrix)

    dashboard_payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "btc_bottom_matrix": bottom_report,
        "assets": asset_matrix,
        "feedback_telemetry": telemetry,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(dashboard_payload, f, indent=2)

    print(
        f"[{dashboard_payload['generated_at_utc']}] Completed run | "
        f"BTC Bottom Score: {bottom_report['total_score']}/100 ({regime})"
    )


if __name__ == "__main__":
    main()

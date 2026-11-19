import json
from pathlib import Path
from typing import Dict, Any, List

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
        status = "BELOW electrical cost floor" if elec_floor_breached else "RECLAIMED above electrical cost floor"
        alerts.append(f"BTC {status}")

    prev_tiers = prev_state.get("asset_tiers", {})
    for ticker, tier in asset_tiers.items():
        if prev_tiers.get(ticker) and prev_tiers.get(ticker) != tier:
            alerts.append(f"{ticker} conviction tier: {prev_tiers[ticker]} -> {tier}")

    return alerts

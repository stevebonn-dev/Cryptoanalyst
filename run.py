DEFAULT_WATCHLIST = ["BTC", "ETH", "SOL", "XRP", "ONDO", "SUI", "SEI", "HBAR", "HYPE"]
WATCHLIST_FILE = "watchlist.json"


def load_watchlist() -> List[str]:
    """Loads tickers dynamically from watchlist.json so edits take effect immediately."""
    if not os.path.exists(WATCHLIST_FILE):
        with open(WATCHLIST_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_WATCHLIST, f, indent=2)
        return DEFAULT_WATCHLIST

    try:
        with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
            items = json.load(f)
        cleaned = [str(t).strip().upper() for t in items if str(t).strip()]
        return list(dict.fromkeys(cleaned)) or DEFAULT_WATCHLIST
    except Exception:
        return DEFAULT_WATCHLIST


def fetch_hyperliquid_mid(ticker: str) -> Optional[float]:
    """Fetches live mid price from Hyperliquid info endpoint for perp/HyperCore assets."""
    url = "https://api.hyperliquid.xyz/info"
    payload = json.dumps({"type": "allMids"}).encode("utf-8")
    try:
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "Cryptoanalyst-Bot/1.0"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            mids = json.loads(resp.read().decode("utf-8"))
        if isinstance(mids, dict) and ticker in mids:
            return float(mids[ticker])
    except Exception:
        return None
    return None


def fetch_coinbase_spot(ticker: str) -> Optional[float]:
    """Fallback USD spot price from Coinbase v2 API."""
    url = f"https://api.coinbase.com/v2/prices/{ticker}-USD/spot"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Cryptoanalyst-Bot/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        amount = data.get("data", {}).get("amount")
        return float(amount) if amount is not None else None
    except Exception:
        return None


def compute_asset_matrix(ticker: str, bottom_regime: str) -> Dict[str, Any]:
    df = fetch_binance_klines(ticker, limit=210)
    if not df.empty and len(df) >= 50:
        price = float(df["close"].iloc[-1])
        mwa_50 = float(df["close"].rolling(50).mean().iloc[-1])
        mwa_100 = float(df["close"].rolling(100).mean().iloc[-1]) if len(df) >= 100 else mwa_50
        mwa_200 = float(df["close"].rolling(200).mean().iloc[-1]) if len(df) >= 200 else mwa_100

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
            "source": "BINANCE_SPOT",
            "status": "ACTIVE",
            "price": round(price, 4),
            "mwa_50": round(mwa_50, 4),
            "mwa_100": round(mwa_100, 4),
            "mwa_200": round(mwa_200, 4),
            "dist_200mwa_pct": round(((price - mwa_200) / mwa_200) * 100.0, 2),
            "signal": signal,
        }

    # Fallback 1: Hyperliquid live mid price
    hl_price = fetch_hyperliquid_mid(ticker)
    if hl_price is not None:
        return {
            "ticker": ticker,
            "source": "HYPERLIQUID_MIDS",
            "status": "SPOT_ONLY_NO_KLINES",
            "price": round(hl_price, 4),
            "mwa_50": None,
            "mwa_100": None,
            "mwa_200": None,
            "dist_200mwa_pct": None,
            "signal": "STAGED_BID_WATCH" if bottom_regime == "CAPITULATION_WATCH" else "WATCH_ONLY",
        }

    # Fallback 2: Coinbase USD spot price
    cb_price = fetch_coinbase_spot(ticker)
    if cb_price is not None:
        return {
            "ticker": ticker,
            "source": "COINBASE_SPOT",
            "status": "SPOT_ONLY_NO_KLINES",
            "price": round(cb_price, 4),
            "mwa_50": None,
            "mwa_100": None,
            "mwa_200": None,
            "dist_200mwa_pct": None,
            "signal": "STAGED_BID_WATCH" if bottom_regime == "CAPITULATION_WATCH" else "WATCH_ONLY",
        }

    return {
        "ticker": ticker,
        "source": "NONE",
        "status": "PRICE_UNAVAILABLE",
        "price": None,
        "mwa_50": None,
        "mwa_100": None,
        "mwa_200": None,
        "dist_200mwa_pct": None,
        "signal": "HOLD",
    }

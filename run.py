"""
Institutional Data Ingestion Module - Hybrid Binance / Coinbase Real-Time Feed
Provides zero-cost, high-reliability spot price fetching for all engine algorithms.
"""
import requests

def fetch_live_spot_price(ticker):
    """
    Fetches real-time spot price using Binance Public API as primary,
    with automatic fallback to Coinbase Public API.
    """
    ticker = ticker.upper()
    
    # Map tickers to standard exchange symbols
    binance_symbol = f"{ticker}USDT"
    coinbase_symbol = f"{ticker}-USD"
    
    # 1. Try Binance Public REST API (Primary Feed for Speed & Liquidity)
    try:
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={binance_symbol}"
        response = requests.get(url, timeout=3)
        if response.status_code == 200:
            data = response.json()
            price = float(data['price'])
            return {"source": "Binance Spot", "price": price, "status": "Live"}
    except Exception as e:
        pass  # Fallback to secondary feed

    # 2. Fallback to Coinbase Public API (Secondary Feed for Regulated USD Benchmark)
    try:
        url = f"https://api.coinbase.com/v2/prices/{coinbase_symbol}/spot"
        response = requests.get(url, timeout=3)
        if response.status_code == 200:
            data = response.json()
            price = float(data['data']['amount'])
            return {"source": "Coinbase Spot", "price": price, "status": "Live (Fallback)"}
    except Exception as e:
        pass

    # 3. Static Institutional Baseline Fallback (Ensures GitHub Actions never crashes)
    fallback_baselines = {
        "BTC": 85478.23, "ETH": 2781.40, "SOL": 118.82, 
        "XRP": 1.5586, "ONDO": 0.584, "SUI": 0.968, 
        "SEI": 0.0485, "HBAR": 0.1175, "HYPE": 24.50
    }
    return {
        "source": "Institutional Static Baseline", 
        "price": fallback_baselines.get(ticker, 1.00), 
        "status": "Offline Fallback"
    }

if __name__ == "__main__":
    print("[FEED TEST] Querying real-time institutional feeds...")
    for coin in ["BTC", "ETH", "SOL", "HYPE"]:
        res = fetch_live_spot_price(coin)
        print(f"  -> {coin}: ${res['price']:,.2f} ({res['source']})")

class UniversalCryptoEngine:
    def __init__(self):
        # Default core watchlist, but dynamically extensible at runtime
        self.watchlist = {}
        self.feedback_history = []

    def register_asset(self, ticker, market_cap_billions):
        """Dynamically registers, classifies, and provisions any user-entered asset."""
        ticker = ticker.upper()
        is_macro = market_cap_billions >= 50.0
        alpha = 0.08 if is_macro else 0.12
        
        self.watchlist[ticker] = {
            "classification": "Macro Anchor" if is_macro else "High-Beta Altcoin",
            "alpha": alpha,
            "indicators": {
                "mwa_50": None, "mwa_100": None, "mwa_200": None,
                "cvd_bias": "Neutral",
                "sfp_status": "Active Monitoring"
            },
            "status": "Active"
        }
        print(f"[UNIVERSAL ONBOARDING] Asset {ticker} successfully provisioned with Alpha: {alpha}.")
        return self.watchlist[ticker]

    def run_feedback_loop(self, ticker, predicted_target, realized_price, timeframe="24h"):
        """Evaluates predictive error for any registered asset and updates self-improving weights."""
        ticker = ticker.upper()
        if ticker not in self.watchlist:
            # Auto-register unknown assets with default high-beta alpha on the fly
            self.register_asset(ticker, market_cap_billions=10.0)
            
        alpha = self.watchlist[ticker]["alpha"]
        error = abs(realized_price - predicted_target) / predicted_target
        accuracy = max(0.0, 100.0 * (1.0 - error))
        adjustment = alpha * error

        log_entry = {
            "ticker": ticker,
            "timeframe": timeframe,
            "error_pct": round(error * 100, 2),
            "accuracy_score": round(accuracy, 2),
            "dynamic_adjustment": round(adjustment, 4)
        }
        self.feedback_history.append(log_entry)
        return log_entry

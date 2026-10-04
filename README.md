# Crypto Intelligence Dashboard (PWA + server loop)

## Files (repo root)
index.html, manifest.json, sw.js, icon.svg, config.json, README.md
server/run.js
.github/workflows/loop.yml

## Turn on the server loop
1. Repo > Settings > Actions > General > Workflow permissions: choose "Read and write permissions".
2. (Optional, phone alerts) Install the free ntfy app, subscribe to a hard-to-guess topic name, then add it under
   Settings > Secrets and variables > Actions > New repository secret: NTFY_TOPIC = that topic name.
3. (Optional) Secret GLASSNODE_KEY = your Glassnode API key, for exchange netflow.
4. Actions tab > "G loop" > Run workflow once. It then runs hourly and commits data/state.json and data/latest.json.
5. Open the page: the "Server loop" card appears and the page uses the server's scoring history and tuned thresholds.

## Notes
- Assets the server tracks are listed in config.json ("assets": null = default list; or e.g. [["BTC","Bitcoin",0.08],["AVAX","AVAX",0.12]]).
  Assets added in the browser are not synced to the server.
- Binance blocks some US datacenter IPs. Spot data falls back to data-api.binance.vision; futures data (funding, OI,
  long/short, taker flow) may be unavailable from GitHub's runners, in which case those inputs stay empty on server runs.
- GitHub may pause scheduled workflows after about 60 days without repository activity; re-enable them in the Actions tab if needed.
- Each run makes a commit, so history grows. Change the cron in loop.yml (for example '7 */4 * * *') to commit less often.
- Not financial advice. Backtests and scores do not guarantee future results.

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

## Keeping the server's asset list and positions in step with the page
In the page, Settings > "Sync to server (GitHub)": enter owner/repo, branch and a fine-grained token
(Contents: read/write on this repo only; add Actions: read/write if you want it to start the loop right away).
After that, adding or removing an asset (and, if you tick the box, saving an entry price) updates config.json in the repo,
and the next server run analyses exactly those assets. Entry prices in config.json are public if the repo is public.

## Free on-chain data (instead of Glassnode)
The dashboard now reads these free, key-free sources: Coin Metrics Community API (BTC and ETH: MVRV, active addresses, transactions),
DefiLlama (value locked and stablecoins per network for ETH, SOL, XRP, SUI, SEI, HBAR), alternative.me (Fear and Greed), CoinGecko (dominance),
Deribit (Bitcoin implied volatility), Binance (ETH/BTC, premium). Exchange netflow is not free anywhere; the Glassnode key option stays available.
Coin Metrics Community data is licensed for non-commercial use and rate limited; if a source cannot be reached, its rows show n/a.

## Event calendar
Settings > Event calendar: one event per line as YYYY-MM-DD|name. It is pre-filled with FOMC decision days (2027 dates are tentative).
Within 48 hours of an event the sample portfolio reduces exposure by 20% and the reports add a warning.

## Derivatives history
The server loop saves an hourly snapshot to data/hist/ (kept for 150 days). GitHub's US runners cannot reach Binance futures, so those
fields are empty there. Optional fix: deploy worker/logger.js as a Cloudflare Worker with a cron trigger of "0 * * * *" and these variables:
REPO (owner/repo), GITHUB_TOKEN (fine-grained, Contents read/write on this repo, set as a secret), optional BRANCH and SYMBOLS.
The page merges data/hist/derivs/ with data/hist/ automatically. Model health then shows how each logged signal related to the next 24 hours.

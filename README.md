# Stock Discovery Agent

Personal research pipeline for US S&P 500 names: fetch Yahoo Finance data, rank undervalued / overvalued / large movers, filter company news, and write GPT verdicts into a dated run folder.

GitHub: [rishab2223/StockDiscoveryAgent](https://github.com/rishab2223/StockDiscoveryAgent)

This is **not** investment advice. Valuation is a local model, not a vendor "fair value". Quotes from Yahoo are delayed.

## Pipeline

1. **Fetch** — all S&P 500 constituents (or `--limit` / `--tickers`). One batched price download (6 months daily) plus per-ticker fundamentals: P/E, P/S, margins, FCF, annual net income / EBIT / revenue / FCF. Sectors come from the index list (GICS); Yahoo's own labels are mapped onto GICS so sector medians are computed on one taxonomy.
2. **Screen** — deterministic scores, no LLM. Default **20** names in each of four lists (up to 80 slots; overlap means fewer unique tickers):
   - undervalued (net-income growth, cheap vs sector P/E and P/S, simple 5-year DCF yield, margin stability; value traps excluded)
   - overvalued (same factors inverted, plus a stretched 1-month move)
   - largest absolute 1-week move
   - largest absolute 1-month move
3. **News** — Yahoo headlines for the shortlist only, fetched in parallel. A story counts only if Yahoo's `relatedTickers` names the company (or, failing that, the symbol or a distinctive word of the name appears). Opinion publishers and analyst-rating headlines are dropped by rule; leftovers are dropped unless `SMA_LLM_NEWS_CLASSIFIER=1`.
4. **Verdict** — OpenAI writes a free-form conclusion per unique ticker from the screen metrics plus the cleaned news.

`python -m sda run` wires the four steps with LangGraph. Fetch and screen never call an LLM.

## Setup

Python 3.12+ (tested on 3.14).

```text
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Put `OPENAI_API_KEY` in `.env` (gitignored). Do not put the key in `.env.example`.

```text
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
SMA_LLM_NEWS_CLASSIFIER=0
```

`SMA_LLM_NEWS_CLASSIFIER=1` sends only **maybe** headlines to GPT for keep/drop. Verdicts always need the API key. Optional `SDA_OUTPUT_DIR` / `SDA_CACHE_DIR` move the run folders and caches elsewhere.

## Commands

```text
python -m sda fetch                  # S&P 500 -> output/<stamp>/market.json
python -m sda fetch --limit 25       # plumbing test only; sector medians will be weak
python -m sda fetch --tickers AAPL,MSFT
python -m sda fetch --refresh        # ignore cached universe + fundamentals
python -m sda screen --n 20          # latest run's market.json -> screen.json/.md/.csv
python -m sda screen --market output/2026-10-17_110832Z/market.json
python -m sda news                   # latest run's screen.json -> news_clean.json
python -m sda verdict                # latest run's news + screen -> verdicts.json/.md

python -m sda run --n 20             # full graph: fetch -> screen -> news -> verdict
python -m sda run --n 5 --limit 25   # small test
python -m sda run --skip-fetch       # reuse the newest earlier market.json (or --market PATH)
```

`--n` is names **per list**, not unique tickers. `--n 20` is four lists of 20 (the "80 stock" shortlist, with overlap). Each step works on the newest run folder unless you point it at a file; a file from outside `output/` gets a fresh run folder.

## Output

Each run writes to `output/<UTC-timestamp>/` so runs do not overwrite each other:

| File | Contents |
|---|---|
| `market.json` | Full fetched universe, plus `errors` (tickers Yahoo throttled or dropped) and `fundamentals_cached` |
| `screen.json` / `.md` / `.csv` | Four shortlists |
| `news_clean.json` | Kept headlines per ticker with bucket membership and raw/dropped counts |
| `verdicts.json` / `.md` | GPT conclusions (watchlist) |

`output/` and `data/cache/` are gitignored.

## Caching and speed

Yahoo throttles per-ticker `.info` calls at full-index scale and answers with an empty dict rather than an error. The fetch step retries those (`INFO_RETRIES`), records the tickers it still could not complete under `errors`, and keeps a partial record (price only) so they can still appear in the mover lists.

Per-ticker fundamentals are cached in `data/cache/fundamentals/` for 24 hours and the S&P 500 list in `data/cache/universe/` for 7 days (`sda/config.py`). Measured on 60 names: cold fetch 14 s, warm fetch 4 s (prices are always re-downloaded). Screen is instant; news for ~16 tickers takes ~4 s with 8 threads; verdicts run 8 LLM calls at a time. A full-index run is dominated by the first fetch of the day (roughly 1–2 minutes) and the ~70 verdict calls.

## Layout

```text
sda/
  config.py        thresholds, cache TTLs, env-driven paths
  sectors.py       Yahoo -> GICS sector mapping
  run_dir.py       output/<stamp>/ resolution
  fetch/           S&P 500 list (universe.py), yfinance client, on-disk cache
  screen/          metrics (growth, DCF, margins), composite scorer, writers
  news/            Yahoo news fetch, rule filter, optional GPT classifier
  verdict/         LangChain + OpenAI verdict chain
  graph/           LangGraph wiring for `run`
  cli.py           python -m sda ...
tests/             unit tests for every step (no network, no LLM)
```

```text
python -m pytest tests -q
```

## Limits

- Yahoo / `yfinance` is unofficial and can throttle or break; `Ticker.news` already stopped returning items in yfinance 1.x, so news comes from `yf.Search`.
- Fundamentals from Yahoo are a current snapshot, not point-in-time; do not backtest with them.
- Simple DCF is harsh on capex-heavy names and is skipped for Financials.
- Cheap P/E is not a buy; the trap flag and news verdict exist because of that.
- Full-index fetch plus ~70 GPT verdicts takes a few minutes and uses API quota.

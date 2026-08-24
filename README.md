# Stock Market Analysis Agent

Personal research pipeline for US S&P 500 names: fetch Yahoo Finance data, rank undervalued / overvalued / large movers, filter company news, and write GPT verdicts into a dated run folder.

This is **not** investment advice. Valuation is a local model, not a vendor “fair value.” Quotes from Yahoo are delayed.

## Pipeline

1. **Fetch** — all S&P 500 constituents (unless `--limit` / `--tickers`). Prices, 1-week and 1-month change, P/E, P/S, profits, FCF, sector.
2. **Screen** — deterministic scores. Default **20** names in each of four lists (up to 80 slots; overlap means fewer unique tickers):
   - undervalued (growth, cheap vs sector P/E and P/S, simple DCF; value traps excluded)
   - overvalued (same factors inverted)
   - largest absolute 1-week move
   - largest absolute 1-month move
3. **News** — Yahoo headlines for the shortlist only. Regex drops analyst recs and opinion; leftovers are dropped unless `SMA_LLM_NEWS_CLASSIFIER=1`.
4. **Verdict** — OpenAI writes a free-form conclusion per unique ticker from screen metrics + cleaned news.

LangGraph runs those four steps in order (`python -m sma run`). Fetch and screen do not use an LLM.

## Setup

Python 3.12+ recommended.

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

`SMA_LLM_NEWS_CLASSIFIER=1` sends only **maybe** headlines to GPT for keep/drop. Verdicts always need the API key.

## Commands

```text
python -m sma fetch                 # S&P 500 → new run folder / market.json
python -m sma fetch --limit 25      # plumbing test only; sector medians will be weak
python -m sma screen --n 20
python -m sma news
python -m sma verdict

python -m sma run --n 20            # full graph: fetch → screen → news → verdict
python -m sma run --n 5 --limit 25  # small test
```

`--n` is names **per list**, not unique tickers. `--n 20` is four lists of 20 (the “80 stock” shortlist, with overlap).

## Output

Each run writes to `output/<UTC-timestamp>/` so runs do not overwrite each other:

| File | Contents |
|---|---|
| `market.json` | Full fetched universe |
| `screen.json` / `.md` / `.csv` | Four shortlists |
| `news_clean.json` | Kept headlines |
| `verdicts.json` / `.md` | GPT conclusions (watchlist) |

`output/` is gitignored.

## Layout

```text
sma/
  fetch/     yfinance + S&P 500 universe
  screen/    metrics, composite scores, writers
  news/      Yahoo news, keyword filter, optional classifier
  verdict/   LangChain + OpenAI verdict chain
  graph/     LangGraph wiring
  cli.py     python -m sma ...
tests/       scoring and news-filter unit tests
```

```text
python -m pytest tests -q
```

## Limits

- Yahoo / `yfinance` is unofficial and can throttle or break.
- Simple DCF is harsh on capex-heavy names and is skipped for many financials.
- Cheap P/E is not a buy; the trap flag and news verdict exist because of that.
- Full-index fetch plus ~70 GPT verdicts takes a few minutes and uses API quota.

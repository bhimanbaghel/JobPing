# feature/scrapers

Notes for the scraping layer (Task 3). Lives alongside [feature-jobs_schema.md](feature-jobs_schema.md); together they define the write path that will eventually populate the `jobs` table for the recommender.

## Goal

Implement the **scraper contract** and **per-company implementations** that the (future) scheduler will drive. Six scrapers hitting six real company career APIs, all returning a common `ScrapedJob` shape.

## What was built

New package [backend/scrapers/](backend/scrapers/):

```
scrapers/
  __init__.py       # SCRAPER_REGISTRY
  base.py           # BaseScraper (ABC) + ScrapedJob dataclass
  greenhouse.py     # shared GreenhouseScraper(BaseScraper)
  lever.py          # shared LeverScraper(BaseScraper)
  airbnb.py         # AirbnbScraper(GreenhouseScraper)      ~5 lines
  stripe.py         # StripeScraper(GreenhouseScraper)      ~5 lines
  coinbase.py       # CoinbaseScraper(GreenhouseScraper)    ~5 lines
  spotify.py        # SpotifyScraper(LeverScraper)          ~5 lines
  palantir.py       # PalantirScraper(LeverScraper)         ~5 lines
  plaid.py          # PlaidScraper(LeverScraper)            ~5 lines
```

New test: [backend/test_scrapers.py](backend/test_scrapers.py) — 11 tests, all mocked, zero network.
Modified: [backend/requirements.txt](backend/requirements.txt) — added `requests>=2.31.0`.

## Design decisions (and why)

### 1. ATS-backed companies only (Greenhouse + Lever), not Google/Meta

The original spec sketched `google.py` / `meta.py` / `microsoft.py`. Those companies run custom SPA-heavy careers sites with no stable public API — any scraper against them would be fragile on day one and rot fast. Instead:

- **Greenhouse** companies expose `GET https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true` — one HTTP call returns every posting. Used by: Airbnb, Stripe, Coinbase (and many more).
- **Lever** companies expose `GET https://api.lever.co/v0/postings/{company}?mode=json` — flat array of postings. Used by: Spotify, Palantir, Plaid.

Both are public, documented, pagination-free, and return JSON. The student can verify any board token with a single `curl`.

### 2. Shared intermediate base classes (not one self-contained file per company)

The spec example had each company file duplicate the HTTP + parsing logic. With 6 companies split evenly across 2 ATS platforms, that would be ~60 lines of copy-paste with minor variations. Instead:

- [base.py](backend/scrapers/base.py) defines the contract (`BaseScraper`, `ScrapedJob`) — **matches the spec verbatim**.
- [greenhouse.py](backend/scrapers/greenhouse.py) and [lever.py](backend/scrapers/lever.py) are intermediate bases: they inherit `BaseScraper`, implement `scrape()` against their respective ATS, and expose a single subclass-configurable attribute (`board_token` or `lever_company`).
- Each per-company file is ~5 lines: subclass the ATS base, set `company_slug` and the ATS slug. Example from [airbnb.py](backend/scrapers/airbnb.py):

  ```python
  from .greenhouse import GreenhouseScraper

  class AirbnbScraper(GreenhouseScraper):
      company_slug = "airbnb"
      board_token = "airbnb"
  ```

Adding a new Greenhouse-backed company is now ~5 lines + one registry import. The BaseScraper interface stays exactly as the spec defined it, so the scheduler never needs to know whether a scraper is ATS-based or hand-rolled.

### 3. Scrapers return `List[ScrapedJob]`, they do not write to the DB

Persistence is deferred to the (future) scheduler task. Reasons:

- **Keeps this PR small and testable** — no DB fixture, no mocking of `db.session`, unit tests have no Flask app context.
- **Avoids unresolved schema questions.** The `ScrapedJob` shape in the spec doesn't match the `Job` table ([backend/app/models.py:28-50](backend/app/models.py#L28-L50)):
  - `ScrapedJob.external_id` has no matching column on `Job` — a dedup/upsert strategy needs a new column + migration.
  - `ScrapedJob.location` is one string, but `Job` has `city` / `state` / `country` — parsing strategy needs to be decided.
  These belong in the scheduler task, not here.

### 4. Sibling package to `app/`, not nested inside it

Scrapers are background workers with a different lifecycle from HTTP request handling. Nesting under [backend/app/](backend/app/) would conflate the two — the `create_app()` factory in [backend/app/__init__.py](backend/app/__init__.py) registers blueprints (HTTP), not worker processes. Putting scrapers at `backend/scrapers/` (sibling) keeps the separation clean and matches what the original spec's directory diagram showed.

### 5. Company choices were verified live, not guessed

The plan originally named `netflix` and `figma` as the Lever companies. Smoke-testing against the real API showed:
- `netflix` returns an empty list (they're technically still on Lever but don't expose postings via the public endpoint).
- `figma` 404s (they moved off Lever since the training-data cutoff).

Both were swapped for probed-working alternatives: **spotify** (174 jobs) and **palantir** (236 jobs). This is worth flagging because ATS slugs *do* drift over time — if a future smoke run shows any scraper failing, the fix is a one-line change to that company's file.

### 6. No BeautifulSoup dependency

The spec showed an HTML-scraping example using BeautifulSoup. Since we went pure-JSON-API, the only DOM-ish thing we deal with is Greenhouse's HTML-encoded `content` field, which only needs `html.unescape()` (stdlib). Only `requests` was added to [requirements.txt](backend/requirements.txt).

## Verification (what was actually run)

### Unit tests — all mocked, no network

```bash
cd backend
.venv/bin/pytest test_scrapers.py -v
```
11 tests pass in <1s. Covers: `ScrapedJob` dataclass, `BaseScraper` abstract enforcement, Greenhouse parsing (including HTML-entity unescaping and `updated_at` → `date`), Lever parsing (unix-ms → `date`), and the registry.

### Live smoke test against all 6 real sites

```bash
.venv/bin/python -c "
from scrapers import SCRAPER_REGISTRY
for s in SCRAPER_REGISTRY:
    jobs = s.scrape()
    print(f'{s.company_slug}: {len(jobs)} jobs; sample: {jobs[0].title if jobs else \"(empty)\"}')
"
```

Result at time of writing:

| Slug     | Platform   | Jobs | Sample title                         |
|----------|------------|------|--------------------------------------|
| airbnb   | Greenhouse | 237  | Account Executive (12 Month FTC)     |
| stripe   | Greenhouse | 499  | Account Executive, AI Sales          |
| coinbase | Greenhouse | 114  | Accountant                           |
| spotify  | Lever      | 174  | Account Executive - Backstage        |
| palantir | Lever      | 236  | Account Executive                    |
| plaid    | Lever      | 92   | Account Executive - Fintech Named    |

**Total: 1,352 real job listings fetched across 6 companies.**

## Deferred to the scheduler task (next)

- `ScrapedJob → Job` field mapping — specifically `external_id` (needs a new column + migration) and `location` → `city` / `state` / `country` parsing.
- Upsert / dedup strategy (likely unique index on `(company, external_id)`).
- Cadence / scheduling — APScheduler? Render cron? Separate worker process? Unresolved.
- Error handling for *partial* registry failures (one scraper breaking shouldn't abort the batch).

## Future: user-suggested companies (design note, not built)

The product direction is that users will eventually be able to suggest companies for JobPing to scrape. That changes the scraper architecture materially and is why we are **not** speculatively adding a BeautifulSoup-based HTML scraper to the current registry pattern — the way HTML scraping should be wired differs depending on whether the target is compile-time known (current) or runtime-supplied (future).

### Why the current registry doesn't fit

`SCRAPER_REGISTRY = [AirbnbScraper(), StripeScraper(), ...]` is a compile-time list of hand-written classes. User-suggested companies are runtime data — scrapers need to become **instances built from config**, not class definitions.

- **ATS case** — config is `{platform: "greenhouse", board_token: "<token>"}`. This is a small refactor of what we already have: move `board_token` / `lever_company` from class attributes to constructor arguments, keep the ATS base classes. When a user suggests a Greenhouse-backed company, no code change is needed — an `ATSScraper` instance is constructed from their suggestion's row in the DB.
- **Server-rendered HTML case** — config is `{url: "...", selectors: {card, title, location, url, external_id}}`. A single `HtmlScraper(BaseScraper)` class (~50 lines: `requests` + `BeautifulSoup.select()`) reads its selectors from config. There's no generic "HtmlScraper base" the way `GreenhouseScraper` is generic over Greenhouse companies — HTML structure differs per site, so the per-company distinction lives in the *selector config*, not subclasses.

### The hard part is onboarding, not scraping

When a user submits a suggestion (company name + careers URL), something has to classify the target:

1. **Is it ATS-backed?** Fetch the URL and look for Greenhouse/Lever/Ashby/Workday markers (iframe embeds, redirects to `boards.greenhouse.io`, script tags). → auto-configure, no user input needed.
2. **Is it server-rendered HTML?** A bare `requests.get()` returns real job content in the HTML. → needs selectors. Two sub-options:
   - Ask the user to supply CSS selectors as part of their suggestion (puts the burden on them).
   - LLM-extract selectors from one sample page (better UX, new dependency + cost).
3. **Is it a SPA?** `requests.get()` returns an empty app shell; jobs are rendered by JavaScript. → BeautifulSoup cannot help. Either reject the suggestion ("this site isn't supported") or queue it for a Playwright-backed path (significantly larger engineering lift: headless browser, slower scrapes, different deployment constraints).

### Storage implications

A new table is required, roughly:

```
suggested_companies
  id
  suggested_by_user_id  → users.id
  company_name
  careers_url
  platform              enum('greenhouse', 'lever', 'html', 'spa', 'unsupported')
  config_json           board_token / lever_slug / selectors, depending on platform
  status                enum('pending', 'approved', 'rejected', 'broken')
  created_at
```

The scheduler would then iterate the built-in `SCRAPER_REGISTRY` **plus** approved rows from `suggested_companies`, constructing the appropriate scraper instance per row.

### Recommended approach

Don't retrofit HTML scraping into the current registry. When the user-suggestions feature is prioritized, design the full pipeline (**detect → store → construct → run**) as one coherent piece, which includes:

- Refactoring the existing ATS scrapers to accept their slug as a constructor argument (so one class serves many companies).
- Adding the `HtmlScraper` class alongside.
- Building the detector and the `suggested_companies` table.
- Deciding on the selector-input UX (manual vs LLM-assisted).

The current six pre-written scrapers become the "built-in seed list" — they still work, they just coexist with runtime-configured instances from the suggestions table.

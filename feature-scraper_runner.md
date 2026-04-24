# feature/scraper-runner

Notes for the Scraper Runner + Database Writer (Task 4). Builds on [feature-scrapers.md](feature-scrapers.md) (the `BaseScraper` contract + 6 ATS scrapers) and [feature-jobs_schema.md](feature-jobs_schema.md) (the `jobs` table). This is the orchestrator — the piece that actually turns scraped results into rows in Postgres.

## Goal

Implement the **"Job Data Aggregation"** subsystem from the deployment diagram: a single entry point that iterates every registered scraper, upserts results into the `jobs` table using the `(company, external_id)` unique constraint, and tracks staleness so jobs that disappear from an ATS can be hidden from users without deleting history.

## What was built

New files:

```
backend/scrapers/runner.py                  # parse_location + run_single_scraper + run_all_scrapers
backend/test_runner.py                      # 12 tests: 7 unit for parse_location, 5 integration
backend/migrations/versions/
  7c4d8a2f9e1b_add_is_active_last_seen_at_to_jobs.py
```

Modified files:

```
backend/app/models.py                       # Job: + is_active, + last_seen_at
backend/app/__init__.py                     # + @app.cli.command("run-scrapers")
```

Invocation:

```bash
cd backend
.venv/bin/flask run-scrapers    # runs all 6 scrapers, writes to DATABASE_URL
```

The CLI command is a thin wrapper over `scrapers.runner.run_all_scrapers()`, which is itself the unit we test directly — no test goes through the CLI layer.

## Design decisions (and why)

### 1. Adapted the spec's reference code to the actual schema

The reference code for Task 4 assumed a layout we never built: a `models/` Python package with separate `Job` and `Company` modules, an `extensions.py` holding `db`, and `is_active` / `date_scraped` columns already present on `Job`. None of that exists — models live in [backend/app/models.py](backend/app/models.py), `db` is declared there, there's no `Company` table, and `Job` didn't have staleness columns. The runner was written against the real schema instead of forcing the codebase to match the spec:

| Spec reference | Actual |
| -------------- | ------ |
| `from models.job import Job` | `from app.models import Job` |
| `from extensions import db` | `from app.models import db` |
| `Company.query.filter_by(slug=...)` | `Job.company` is a string slug — no Company table |
| `existing.title`, `existing.url`, `existing.date_posted` | `existing.role`, `existing.link`, `existing.posted_at` |
| `ScrapedJob.location` → `Job.location` | `ScrapedJob.location` → `Job.city` / `state` / `country` (parsed) |
| `existing.date_scraped` | `existing.last_seen_at` (new column) |

The naming drift is purely historical — `Job.role`/`link`/`posted_at` predate the scrapers (see [feature-jobs_schema.md](feature-jobs_schema.md)) and renaming would cascade into the HTTP blueprint layer for no real benefit.

### 2. Added `is_active` + `last_seen_at` via migration (rather than skip staleness or hard-delete)

Three options were on the table:

- **Skip staleness** — only insert and update. Stale jobs would linger forever; closed roles would still surface to users. Rejected: silently showing closed jobs is the worst user-facing outcome.
- **Hard-delete stale rows** — simpler (no migration), but you lose the ability to distinguish "never existed" from "was taken down," which matters for the recommender's future telemetry and for debugging flaky scrapers (a temporary upstream hiccup would permanently destroy history).
- **Soft-delete via `is_active` flag + `last_seen_at` timestamp** — chosen. One migration, cheap on writes (bulk `UPDATE ... WHERE external_id NOT IN (...)`), reversible, and preserves history.

New migration: [7c4d8a2f9e1b_add_is_active_last_seen_at_to_jobs.py](backend/migrations/versions/7c4d8a2f9e1b_add_is_active_last_seen_at_to_jobs.py).

- `is_active BOOLEAN NOT NULL DEFAULT TRUE` — default applied via `server_default=sa.true()` so the backfill on existing rows is handled by the DB, not by the migration script.
- `last_seen_at DATETIME(timezone=True) NULLABLE` — null for rows predating the runner, populated on first scrape.

Both `batch_alter_table` wrapped so SQLite dev DBs can apply the column adds. `down_revision = '5b2e8f91c4d7'` (the external_id migration). Downgrade drops both columns in reverse order.

### 3. Kept `Job.company` as a string slug — no `Company` table

An alternative was to introduce a full `companies` table with id/slug/name and a FK from `Job.company_id`. Rejected for this PR:

- The `jobs.company` column is already present, indexed, and part of the unique constraint `(company, external_id)` — introducing a FK would require a data backfill migration plus refactoring every existing query in [backend/app/blueprints/jobs/](backend/app/blueprints/jobs/).
- With 6 scrapers of known slug, normalization buys nothing today. If a `Company` model is justified later (e.g., for user-suggested companies — see the deferred section in [feature-scrapers.md](feature-scrapers.md)), that's a cleaner standalone migration than piggybacking on the runner.
- `scraper.company_slug` → `Job.company` is a direct string assignment, which keeps the runner short.

### 4. Runner as a pure function; CLI command as a thin wrapper

Three options:

- **Standalone script** (`python scrapers/runner.py`) — matches the reference literally but creates a second entry point that mints its own `app_context`. Duplication with the Flask CLI.
- **Flask CLI only** — clean, but the runner logic becomes tied to the CLI invocation, awkward for pytest.
- **Both** (chosen) — `run_all_scrapers()` and `run_single_scraper()` are pure functions in [backend/scrapers/runner.py](backend/scrapers/runner.py) that assume an active app context. The Flask CLI command in [backend/app/__init__.py:42-52](backend/app/__init__.py#L42-L52) is a ~10-line wrapper that calls them. Tests push their own app context from the `create_app("testing")` fixture — the CLI layer is not on the test path at all.

This matches how Flask-SQLAlchemy and Flask-Migrate work (context-dependent functions, not context-creating), and keeps the testable surface pure.

### 5. Batch-fetch existing rows, don't query per scraped job

The reference code does one `Job.query.filter_by(company_id=..., external_id=sj.external_id).first()` per scraped job — that's 1,352 roundtrips per full run. Instead the runner does one query per scraper:

```python
existing_by_eid = {
    j.external_id: j
    for j in Job.query.filter_by(company=slug).all()
}
```

All lookups are then dict hits. Worst case (Stripe, 499 jobs) goes from 499 round-trips to 1. The memory cost is negligible — even at 10× current volume we're holding a few thousand small ORM objects for the duration of one scraper.

### 6. Empty-scrape guard — don't mass-deactivate when a scraper returns zero jobs

A naive implementation of the staleness sweep would deactivate **every** job for a company whenever that company's scraper returns an empty list. But `scrape()` returning `[]` is almost always an upstream problem (Greenhouse 500, Lever rate-limit, our API key getting blocked) — not a genuine "this company posted zero jobs today" event.

The runner explicitly guards this in [scrapers/runner.py](backend/scrapers/runner.py):

```python
if seen_external_ids:
    deactivated = Job.query.filter(...).update(...)
else:
    logger.warning("%s: scrape() returned 0 jobs — skipping staleness sweep ...")
```

Consequence: a temporarily broken scraper causes a visible warning and zero data damage. A scraper that legitimately starts returning zero jobs (rare) would need to be caught another way — but that's the right tradeoff, and the `test_empty_scrape_skips_staleness` test pins the behavior.

### 7. Per-scraper commit boundaries + rollback on failure

Each scraper gets its own `db.session.commit()` inside [run_single_scraper](backend/scrapers/runner.py). The outer [run_all_scrapers](backend/scrapers/runner.py) wraps each call in `try/except Exception`, calls `db.session.rollback()` on failure, logs with `exc_info=True`, and continues to the next scraper.

Consequences:

- **Partial success is a valid outcome.** If Coinbase's API is down but the other five work, the other five still commit. Users see stale Coinbase data until the next run instead of losing everything.
- **A bug in one scraper can't corrupt another's write.** Rollback clears the session before the next scraper opens its own transaction.
- **The return value of `run_all_scrapers()` is a per-scraper list of result dicts** — successful ones carry stats (`fetched` / `inserted` / `updated` / `deactivated`), failed ones carry `{"slug": ..., "error": ...}`. This is what a future scheduler would log/monitor.

### 8. `parse_location` — permissive comma-split, not a real gazetteer

`ScrapedJob.location` is a single freeform string; `Job` has separate `city` / `state` / `country` columns. The runner splits on commas with a simple rule:

- 1 part → `(city, None, None)` — covers `"Remote"`, `"London"`
- 2 parts → `(city, state, None)` — covers `"San Francisco, CA"`
- 3+ parts → `(city, state, "<everything else joined>")` — covers `"New York, NY, USA"` and also `"Berlin, Berlin, Germany, EU"` without silently dropping data

No attempt is made to validate that e.g. `"CA"` is a real state code or that `"USA"` is a country. That's deliberate — ATS location strings are fundamentally unreliable (see Lever postings with `"Remote - EMEA"` or Greenhouse ones with just `"Multiple locations"`), and pretending the runner can clean them would create false confidence for the recommender. The recommender can do its own normalization later with proper libraries (e.g., `geonamescache`) if needed.

### 9. Logging: module logger, no global `basicConfig`

[scrapers/runner.py](backend/scrapers/runner.py) declares `logger = logging.getLogger(__name__)` and logs INFO on per-scraper success, WARNING on empty scrapes, ERROR with traceback on exceptions. It does **not** call `logging.basicConfig()` — that would stomp on whatever handler structure the caller has set up (gunicorn, Render's log shipper, pytest's `caplog`).

The only place `basicConfig` is called is inside the CLI command itself, guarded by `if not logging.getLogger().handlers:`, so `flask run-scrapers` produces readable output from a bare terminal but doesn't fight an already-configured environment.

## Verification (what was actually run)

### Unit + integration tests

```bash
cd backend && .venv/bin/pytest test_runner.py test_scrapers.py -v
```

24 tests pass:

- 7 unit tests for `parse_location` (empty / whitespace / 1 / 2 / 3 / 4-part / whitespace-stripping)
- 5 integration tests covering the runner's full behavior against an in-memory SQLite:
  - `test_inserts_new_jobs` — field mapping + `is_active=True`, `last_seen_at` set
  - `test_updates_existing_job` — same `external_id` → row updated in place, not duplicated
  - `test_deactivates_unseen_jobs` — job missing from new scrape → `is_active=False`, `last_seen_at` bumped
  - `test_empty_scrape_skips_staleness` — empty scrape → zero deactivations, warning logged
  - `test_scoped_to_company` — running airbnb's scraper does **not** touch stripe's rows
  - `test_failure_isolated_between_scrapers` — one scraper raising doesn't block the other's commit
- 12 pre-existing scraper tests from [feature-scrapers.md](feature-scrapers.md) still pass.

### Migration applied against local `app.db`

```bash
.venv/bin/flask db current   # was: 1845a468133d
.venv/bin/flask db upgrade   # ran 1845... → 5b2e... → 7c4d8a2f9e1b
.venv/bin/flask db current   # now: 7c4d8a2f9e1b (head)
```

`PRAGMA table_info(jobs)` confirms the new columns:

```
(12, 'is_active',    'BOOLEAN',  1, '1',  0)
(13, 'last_seen_at', 'DATETIME', 0, None, 0)
```

### End-to-end live run (not run yet — hits 6 real ATS APIs)

```bash
cd backend && .venv/bin/flask run-scrapers
```

Expected output per [feature-scrapers.md](feature-scrapers.md)'s smoke numbers: ~1,352 inserts on first run; on re-run, ~0 inserts and ~0 deactivations (idempotent).

## Consequences / things a reader should know

1. **Migration is destructive-in-reverse but not forward.** The `upgrade()` adds nullable/defaulted columns, so it's safe to run against a populated DB. `downgrade()` drops both columns, which would lose any staleness data already captured — fine for a rollback test, not fine if you've been running the scraper for a while.
2. **`flask run-scrapers` is blocking and synchronous.** A full run against the live APIs takes ~10-20 seconds (6 sequential HTTP calls + ~1,300 DB writes). It's fine for a cron/Render-worker trigger but shouldn't be invoked from an HTTP handler.
3. **The runner commits once per scraper.** If `SIGTERM` arrives mid-run, completed scrapers' data is already durable; the in-flight scraper is lost. Resume semantics are "run again from scratch" — idempotent by design (see decision 7).
4. **`is_active=False` is a hint, not a hard filter.** The HTTP layer in [backend/app/blueprints/jobs/](backend/app/blueprints/jobs/) does not currently filter on `is_active` — doing that is a follow-up PR, intentionally out of scope here so the columns can be verified in isolation first.
5. **No scheduler yet.** This PR gives you the hand-crank (`flask run-scrapers`). Wiring it to a cron job, APScheduler, or a Render worker is deferred — matches the "scheduler task" hand-off point called out at the end of [feature-scrapers.md](feature-scrapers.md).

## Deferred to later tasks

- **Scheduling / cadence.** How often does this run? APScheduler in-process? Render cron? Dedicated worker dyno? Open question.
- **`is_active` consumption.** The jobs API needs to filter out `is_active=False` rows (probably with a `?include_inactive=1` override for admin debugging). One-line query change, but belongs with the consumer PR.
- **Metrics / observability.** Per-scraper stats (`fetched` / `inserted` / `updated` / `deactivated`) are returned from `run_all_scrapers()` but nothing consumes them yet. Once there's a scheduler, these should be surfaced (logs → Render, or a stats table for dashboards).
- **User-suggested companies.** Covered in depth in the "Future" section of [feature-scrapers.md](feature-scrapers.md) — the runner's per-scraper isolation already accommodates runtime-constructed scrapers, so that feature won't need runner changes.

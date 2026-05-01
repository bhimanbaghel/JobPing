# feature/jobs-schema

Branch notes for the `jobs` table work. Covers code changes, live-DB operations against the Render Postgres instance, and an inconsistency in the live DB that was discovered during this work.

## Goal

Add a `jobs` table that is the decoupling boundary between the (future) scraper and the recommendation engine: scraper writes, recommender reads, neither talks to the other directly.

## Schema decision

The original spec for this task was a normalized two-table design (`companies` + `jobs` with a FK, `external_id` for upsert dedup, `is_active` soft-delete flag, and an `embedding Vector(384)` column on `jobs`).

While generating the migration we discovered a parallel teammate branch chain (`origin/feature/recs-schema` → `recs-embeddings` → `recs-engine` → `recs-api` → `recs-frontend` → `recs-seed-and-tests` → `recs-docs`) that already creates a `jobs` table with a different, denormalized shape — `company` as a string column, no FK, no `external_id`, embedding lives in a separate `job_embeddings` table.

To avoid two competing schemas landing in the same DB, this branch's `Job` model now matches the teammate's shape exactly. The teammate's migration is guarded with `if "jobs" not in existing:` so whichever migration lands first wins; the other is a no-op for the `jobs` table.

## Code changes

### [backend/app/models.py](backend/app/models.py)

- Added module-level `_utcnow()` helper (replaces the inline `lambda` previously used as `User.created_at`'s default, so the new `Job` model can reuse it without duplication).
- Added `Job` model:
  - `__tablename__ = 'jobs'`
  - Columns: `id` (PK), `role` (String 255, indexed, NOT NULL), `company` (String 255, indexed, NOT NULL), `description` (Text, NOT NULL), `link` (String 2048), `city/state/country` (String 120 each), `salary_usd` (Numeric 12,2), `posted_at` (Date), `created_at` (DateTime tz-aware, default `_utcnow`, NOT NULL).
  - Comment on the class explains the schema-convergence decision so future readers understand why this doesn't match the original spec.
- `User` model unchanged in shape; only its `created_at` default was switched from a `lambda` to the new `_utcnow` helper.

### [backend/migrations/versions/1845a468133d_add_jobs_table.py](backend/migrations/versions/1845a468133d_add_jobs_table.py)

New Alembic migration. `down_revision = 'f3a9c2b101ef'` so the chain is now:

```
base → 72141e8076c0 (create users) → f3a9c2b101ef (users.name nullable) → 1845a468133d (add jobs table)
```

- `upgrade()`: creates the `jobs` table with the columns above and two indexes (`ix_jobs_role`, `ix_jobs_company`). Index ops are wrapped in `batch_alter_table` because [backend/app/__init__.py:28](backend/app/__init__.py#L28) initializes Flask-Migrate with `render_as_batch=True`.
- `downgrade()`: drops the two indexes, then drops the `jobs` table.

Note: the autogenerator initially also emitted `op.create_table('users', ...)` because the live Render DB does not contain a `users` table (see DB issue below). That spurious op was removed by hand — `users` belongs to migration `72141e8076c0`, not this one.

## Live-DB operations performed against Render

The Render Postgres instance referenced by `DATABASE_URL` in [backend/.env](backend/.env) was modified during this work.

### Alembic version stamp

When `flask db migrate` was first attempted it errored with:

```
ERROR [flask_migrate] Error: Can't locate revision identified by '9c2628e89ee4'
```

The `alembic_version` table on Render pointed at revision `9c2628e89ee4`, which does not exist in any branch in this repo (checked: `main`, all `origin/feature/*`). Someone had either run a migration from a deleted branch, manually `UPDATE`d `alembic_version`, or run a migration without committing the file.

To unblock autogenerate, `alembic_version` was force-updated:

```sql
UPDATE alembic_version SET version_num = 'f3a9c2b101ef';
```

This was done via psycopg2 (not raw psql). Result confirmed: 1 row updated, value transitioned `9c2628e89ee4` → `f3a9c2b101ef`.

### `flask db upgrade` was NOT run

The new migration file exists locally but has not been applied to any database. The Render DB still does not have a `jobs` table.

## Outstanding issue: Render DB has no `users` table

Discovered while investigating the autogenerate output. Inspection of the Render `public` schema returned only one table:

```
alembic_version
```

No `users`, no `jobs`, nothing. The previous `9c2628e89ee4` stamp was decoupled from any real schema — and stamping forward to `f3a9c2b101ef` inherited that fiction. Our local migration head now claims `users` exists with `name` nullable, but in reality nothing has ever been applied to this DB.

The auth endpoints in [backend/app/blueprints/auth/routes.py](backend/app/blueprints/auth/routes.py) will fail in production until this is resolved.

### Suggested fixes (not performed on this branch)

Option A — reset and replay everything:

```sql
DELETE FROM alembic_version;
```

Then `flask db upgrade` will apply all three migrations from base (`72141e8076c0` → `f3a9c2b101ef` → `1845a468133d`).

Option B — keep current alembic head, manually create `users`:

Apply the SQL equivalent of migrations `72141e8076c0` and `f3a9c2b101ef` by hand, then `flask db upgrade` to pick up only `1845a468133d`. Riskier; Option A is preferred.

The local SQLite at [backend/app.db](backend/app.db) is independent and was not touched.

## Verifying the migration locally

```bash
cd backend
FLASK_APP=wsgi.py .venv/bin/flask db heads      # should show 1845a468133d (head)
FLASK_APP=wsgi.py .venv/bin/flask db history    # should show the 3-migration chain
```

To apply against a fresh local SQLite (separate from the Render DB):

```bash
DATABASE_URL=sqlite:///dev.db FLASK_APP=wsgi.py .venv/bin/flask db upgrade
```

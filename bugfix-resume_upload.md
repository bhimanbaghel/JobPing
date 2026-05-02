# bugfix/resume-upload

Branch: `bugfix/resume-upload` (forked from `main`).

## TL;DR

The "preferences confirmation lock" feature shipped on `main` was a one-way door: every submit unconditionally locked the profile, no unlock affordance existed, and the locked state replaced the form with a static "Preferences have been locked." panel — making it impossible to upload a new resume after the first save. This branch removes the lock end-to-end and adds server-side cache invalidation so a re-uploaded resume actually changes the recommendations on the next page load. While testing, a separate latent bug was found in the migration that introduced `is_locked` (it's broken on SQLite); that was patched in the same branch to unblock local verification.

## Files changed

| File | Why |
| --- | --- |
| [backend/app/blueprints/profile/routes.py](backend/app/blueprints/profile/routes.py) | Drop the lock guard; invalidate cached recommendations on save |
| [frontend/src/views/PreferencesView.vue](frontend/src/views/PreferencesView.vue) | Drop the locked UI state and the unconditional `is_locked=true` form field; dedupe a duplicate function |
| [frontend/src/views/RecommendationsView.vue](frontend/src/views/RecommendationsView.vue) | Add a "Preferences" link to the nav so users can return to the input screen and re-upload (latent UX gap surfaced by manual testing) |
| [backend/test_profile_preferences.py](backend/test_profile_preferences.py) | Replace the lock-enforcement test with three new tests covering the new behaviour |
| [backend/migrations/versions/48b394868294_add_is_locked.py](backend/migrations/versions/48b394868294_add_is_locked.py) | Make the migration runnable on SQLite (latent bug, see below) |

## The bug, in detail

### What the user saw

Once a user clicked *Final Submit* on the preferences page, every subsequent visit showed a frozen screen with their saved values and the message "Preferences have been locked." The file input — the only way to upload a new resume — was no longer rendered. Re-attempts via direct API calls returned `403 Preferences are locked and cannot be modified.` There was no in-app way to unlock; the row in the DB had to be edited by hand.

### How it was reaching that state

Three pieces conspired:

1. **Backend `upsert_preferences` enforced the lock**: any POST returned 403 when `UserPreference.is_locked` was true.
2. **Frontend always set the lock**: `savePreferences()` appended `is_locked=true` to the form data on every submit. There was no checkbox or opt-in — every save was a permanent lock.
3. **Frontend rendered a terminal locked state**: `loadExistingStatus()` switched `uiState` to `'locked'`, which the template handled by replacing the form with a static read-only panel.

The combination meant the very first save irreversibly locked the user.

### Secondary bug: stale recommendations

Even if the lock had been opt-in, re-uploading a resume would not have visibly changed the recommendations:

- `GET /api/jobs/recommendations` returns cached `Recommendation` rows ([backend/app/blueprints/jobs/routes.py:46-52](backend/app/blueprints/jobs/routes.py#L46)) and only recomputes when the cache is empty *or* `?recompute=1` is passed.
- The frontend never sets `?recompute=1` on the navigation that follows a save — only the manual *Refresh* button does.
- Result: a freshly uploaded resume only takes effect after the user manually clicks Refresh, which is non-obvious and has no UI cue tying it to the upload.

## Design decisions

### Remove the lock entirely

Considered keeping `is_locked` as an opt-in toggle in the review step, but rejected: the existing `edit → review → submit` flow already provides confirmation UX, and the lock has no real product value without an unlock affordance, which doesn't exist and isn't planned. Removing the mechanism is simpler than half-fixing it.

### Invalidate cache server-side, not client-side

When `upsert_preferences` commits, it now deletes the user's rows from `recommendations`. Considered the alternative of having the frontend pass `recompute=1` after save, but server-side invalidation is preferable:

- Any client (web, future mobile) that hits the upload endpoint gets fresh data — the invariant is enforced at the system boundary, not duplicated at every caller.
- The `recommendations` table is purely a cache; deleting on prefs change is the natural "cache key changed → invalidate" pattern.
- The next `GET /api/jobs/recommendations` falls into the `if not recs` branch and runs `recommend_for_user()`, which rebuilds the resume embedding via `_compute_resume_vector()` ([backend/app/services/recommender.py:147-155](backend/app/services/recommender.py#L147)) — that function always re-embeds from the latest `Resume.parsed_text`, so no `resume_embeddings` invalidation is needed.

### Leave the `is_locked` column in the DB

The DB column stays. Removing it would require a destructive migration; with the code no longer reading or writing it, the column is harmless dead weight. A separate cleanup PR can drop it later — out of scope for a bugfix branch.

## Per-file changes

### `backend/app/blueprints/profile/routes.py`

- Added `Recommendation` to the model import.
- Removed the `if pref is not None and pref.is_locked: return 403` guard at the top of `upsert_preferences`. With this gone, any save is allowed regardless of the column's value (for new users it defaults to `False`; for users locked by prior code it stays `True` but is read by nothing).
- Removed the `is_locked` form field parsing — the frontend stopped sending it and there's no ingest path anymore.
- Removed `is_locked` from the `/preferences/status` JSON payload — clients have no reason to know about it now.
- After `db.session.commit()` of prefs/resume, added a delete of the user's `Recommendation` rows followed by a second commit. Two commits keep the operations independently durable: a partial failure leaves the prefs saved and only the cache wipe to retry, instead of rolling back the user's submitted prefs because of a cleanup-side hiccup.

### `frontend/src/views/PreferencesView.vue`

- Template: removed the `<div v-if="uiState === 'locked'">` block that rendered the static "Preferences have been locked." panel. Simplified the review-section condition from `uiState === 'review' || uiState === 'locked'` to just `uiState === 'review'`.
- Updated the `uiState` type comment from `'edit' | 'review' | 'locked'` to `'edit' | 'review'`.
- Removed the `if (body.is_locked) { uiState.value = 'locked' }` branch in `loadExistingStatus()` — there's no terminal state to enter anymore.
- Deleted `formData.append('is_locked', 'true')` in `savePreferences()`. This was the actual root cause of the one-way-door behaviour; even after the backend stops enforcing it, leaving this in would have kept setting the column to `True` every save.
- Deleted a duplicate `goToReview` function definition (the file had two byte-identical copies). Pure cleanup; behaviour was already determined by which one JS hoisted last.

### `frontend/src/views/RecommendationsView.vue`

Latent UX gap surfaced by manual verification: after the lock came off, there was no in-app navigation back to `/preferences` from the recommendations page. The top-right nav had only "Home" and "Sign out". Without a way back, the user could not exercise the re-upload flow we'd just unblocked.

Single-line addition: a `<router-link to="/preferences" class="recs-nav-link">Preferences</router-link>` between the existing Home link and the Sign-out button. No CSS or store changes needed; the link reuses the existing `recs-nav-link` styling.

### `backend/test_profile_preferences.py`

- Added `Recommendation` to imports.
- Deleted `test_lock_preferences_and_prevent_modification`. It encoded the broken behaviour (asserting the second POST returns 403); keeping it would have failed against the fixed code.
- Added `test_save_preferences_can_be_modified_after_first_save`: posts twice with different roles; asserts both succeed and the second value wins. Direct regression test for the user-visible bug.
- Added `test_save_preferences_invalidates_cached_recommendations`: seeds a `Recommendation` row to simulate a populated cache, posts new preferences, asserts the cache is empty afterward. Locks in the server-side invalidation contract.
- Added `test_preferences_status_does_not_expose_is_locked`: hits `/api/profile/preferences/status` and asserts `is_locked` is absent from the JSON. Guards against a future change accidentally re-exposing the deprecated field.

### `backend/migrations/versions/48b394868294_add_is_locked.py`

This was unplanned scope creep but unavoidable. The migration was autogenerated against Postgres and never run against SQLite; it had three SQLite-incompatible problems that surfaced the moment we tried to verify the resume-upload fix on a fresh local DB.

1. **Postgres-style auto-generated constraint names**: `drop_constraint(... 'resumes_user_id_key' / 'user_preferences_user_id_key' ...)`. Postgres labels unnamed `UniqueConstraint("user_id")` declarations with `<table>_<col>_key`; SQLite inlines the constraint without naming it. On SQLite, those drops fail with `No such constraint: 'resumes_user_id_key'`. Fix: wrapped both calls in `if is_postgres:`. The drops are no-ops on SQLite anyway because batch mode recreates the table from the new schema (which has unique *indexes* in place of the constraints).

2. **`is_locked` column added with `nullable=False` and no default**: safe against an empty table, but would fail if any rows existed. Fix: added `server_default=sa.false()` so the migration is non-destructive against any prior state.

3. **Unnamed unique constraint on `users.email`**: `create_unique_constraint(None, ['email'])`. SQLite's batch mode requires constraints to have names; this raised `Constraint must have a name`. Fix: gave it the name `uq_users_email` (matching alembic's standard naming convention) and updated `downgrade()` to drop by that name.

The `downgrade()` got symmetric treatment so up/down stays reversible on both dialects.

A safety note on editing this migration in-place: this is acceptable because the commit message and behaviour suggest the migration was *autogenerated* against a Postgres DB but never actually `db upgrade`d against any deployment. Modifying an already-applied migration would normally be unsafe (Alembic skips already-applied revisions per the `alembic_version` table, so the edit only affects fresh applies — but anyone with the old revision applied stays stuck on the old schema shape). If we later discover the original *was* applied somewhere, the right follow-up is a new revision that brings stragglers forward, not a re-edit.

## What was deliberately NOT changed

- The `UserPreference.is_locked` model attribute and DB column. Removing them requires a destructive schema migration and a model edit; out of scope. The column is now vestigial — code no longer reads or writes it.
- The `edit → review → submit` UX flow. The lock was the bug, not the multi-step confirmation. Users still see a review screen before final submission.
- The recommender, embedding service, scraper, and any other code outside the profile/preferences flow.
- A frontend "you have unsaved resume changes" indicator. Nice-to-have, not required.

## Verification

### Automated

```bash
cd backend
source .venv/bin/activate
pytest test_profile_preferences.py test_recommender.py -q
```

Expected: 34 passed (12 in profile prefs after the test refactor, 22 in recommender unchanged).

### Manual end-to-end

The run command sequence (the four `flask` commands) is identical regardless of which DB dialect you target — only the setup before them differs.

Two terminals:

```bash
# Terminal 1
cd backend
source .venv/bin/activate
pip install -r requirements.txt   # see "setup gotcha — Python deps" below
rm -f app.db                      # SQLite only; harmless on Postgres setups
flask --app wsgi.py db upgrade
flask --app wsgi.py run-scrapers
flask --app wsgi.py run

# Terminal 2
cd frontend
npm run dev
```

To target Postgres instead of SQLite, do the Postgres setup below and flip `DATABASE_URL` in `.env`. Re-running `flask db upgrade` against the new URL applies the same migration chain to the Postgres database. The four `flask` commands themselves don't change.

#### Setup gotcha — Python deps

The provided `.venv` was set up before `pypdf` and `sentence-transformers` made it into `requirements.txt` (or before someone re-installed). The PDF resume upload calls `pypdf`, and the recommender's SBERT path needs `sentence-transformers`. Without them, *Final Submit* on a PDF returns `PDF parsing dependency missing. Install backend requirements.` and the server logs `SBERT preload failed; falling back to lazy load`. Running `pip install -r requirements.txt` once after activating the venv pulls both. Activating the venv alone is not enough — that just points your shell at it; it doesn't install anything that wasn't already there.

#### Postgres validation (verified)

The migration patch was empirically verified against Postgres in addition to the SQLite test path. Setup steps that worked locally:

```bash
brew install postgresql@16 pgvector
brew services start postgresql@16
createdb jobping_dev
psql jobping_dev -c "CREATE EXTENSION vector;"

cd backend
source .venv/bin/activate
pip install "psycopg[binary]" pgvector

# In backend/.env, swap the SQLite line for:
#   DATABASE_URL=postgresql+psycopg://<your-mac-user>@localhost:5432/jobping_dev

flask --app wsgi.py db upgrade
```

Result: full migration chain runs cleanly through `48b394868294 add is_locked`. The `is_postgres` branches in the patched migration execute the original `drop_constraint` calls (Postgres has those auto-generated names) and produce the same final schema as SQLite. Confirms the patch is dialect-correct.

#### Setup gotcha — pgvector keg-only mismatch

If `psql ... -c "CREATE EXTENSION vector;"` fails with `extension "vector" is not available`, brew's `pgvector` formula was built against a different Postgres version than `postgresql@16`. The `@<version>` Postgres formulas are keg-only: brew doesn't symlink their binaries onto `PATH`, so the default `pg_config` (which `pgvector`'s formula uses at build time) points elsewhere. Fix by building pgvector from source against the matching Postgres:

```bash
cd /tmp
git clone --branch v0.8.0 https://github.com/pgvector/pgvector.git
cd pgvector
PG_CONFIG=/opt/homebrew/opt/postgresql@16/bin/pg_config make
PG_CONFIG=/opt/homebrew/opt/postgresql@16/bin/pg_config make install
```

Then re-run `psql jobping_dev -c "CREATE EXTENSION vector;"` — it should print `CREATE EXTENSION`.

In the browser:

1. Register a new user.
2. `/preferences`: pick a role that exists in the scraped data, attach **resume A**, *Review preferences* → *Final Submit*.
3. Note the top recommendations on `/recommendations`.
4. Navigate back to `/preferences`. **The form should be editable** (no "Preferences have been locked" screen).
5. Attach **resume B** (with clearly different content), *Review* → *Final Submit*.
6. On `/recommendations`, **the ordering should change without clicking Refresh**.

Step 4 proves the lock is gone (frontend + backend). Step 6 proves the cache invalidation actually flowed through to a re-embed and re-score.

### DB sanity probes

```bash
sqlite3 backend/app.db "SELECT user_id, length(parsed_text) FROM resumes;"
sqlite3 backend/app.db "SELECT user_id, job_id, similarity_score FROM recommendations;"
```

After step 5 the `recommendations` rows for your user should have different `job_id`s or `similarity_score`s than after step 2.

## Follow-ups

- Drop the `is_locked` column and its model attribute in a separate cleanup PR.
- If the original `48b394868294` revision turns out to have been applied to any production DB, write a no-op revision that matches the patched semantics so stragglers can converge.

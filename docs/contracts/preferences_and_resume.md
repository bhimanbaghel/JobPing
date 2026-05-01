# Contract — `user_preferences` and `resumes` tables (Preferences teammate)

The recommender (Bhiman) only **reads** these tables; the preferences
teammate **writes** them via the `profile` blueprint. As with the `jobs`
table, stubs ship in `backend/app/models.py` and the recommendations
migration only creates these tables when they do not already exist, so
the teammate's branch can be merged in either order.

When the real models land:

1. Delete the `UserPreference` and `Resume` stub classes in
   `backend/app/models.py` (look for the `# STUB: owned by the
   preferences teammate` markers).
2. Drop the corresponding `if "user_preferences" not in existing` and
   `if "resumes" not in existing` blocks from the migration.

## `user_preferences`

| Column      | Type            | Nullable | Notes                              |
|-------------|-----------------|----------|------------------------------------|
| `id`        | `INTEGER` PK    | no       |                                    |
| `user_id`   | `INTEGER` FK→`users.id` | no | Unique per user                    |
| `roles`     | `JSON` (array of strings) | no | At least one entry is required for FR6.1 |
| `companies` | `JSON` (array of strings) | no | Optional; empty list disables company filter |
| `locations` | `JSON` (array of strings) | no | Optional; used in the FR6.3 fallback query |
| `updated_at`| `TIMESTAMPTZ`   | no       | Auto-set on insert/update          |

### Behavioural notes

- The recommender treats role match as case-insensitive substring (e.g.
  preference `"Backend Engineer"` matches a job role of
  `"Senior Backend Engineer"`).
- Company match is case-insensitive substring, applied only when
  `companies` is non-empty.
- After every preferences update, the profile endpoint should call
  `POST /api/jobs/recommendations/recompute` (or instruct the client to)
  so cached `recommendations` rows refresh.

## `resumes`

| Column        | Type            | Nullable | Notes                              |
|---------------|-----------------|----------|------------------------------------|
| `id`          | `INTEGER` PK    | no       |                                    |
| `user_id`     | `INTEGER` FK→`users.id` | no | Unique per user                    |
| `parsed_text` | `TEXT`          | no       | Plain-text resume content          |
| `updated_at`  | `TIMESTAMPTZ`   | no       | Auto-set on insert/update          |

### Behavioural notes

- The recommender embeds `parsed_text` directly. Binary file storage
  (PDF/DOCX) and parsing live in the profile blueprint and are out of
  scope for the recommender.
- When `parsed_text` is missing or empty, the recommender falls back to
  a synthesized preferences string (FR6.3) and writes a
  `ResumeEmbedding` row with `source='preferences'` so the next read is
  warm.
- Replacing an existing resume should also trigger a recompute (same
  endpoint as for preferences).

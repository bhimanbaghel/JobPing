# Contract — `jobs` table (Lakshay / Table 1)

The recommender (Bhiman) reads from this table; the parser (Lakshay) writes
to it. To unblock recommender development, a **stub** model with the schema
below is currently shipped in `backend/app/models.py` and the migration
`backend/migrations/versions/a1b2c3d4e5f6_recommendations_schema.py` only
creates the table when one does not already exist.

When Lakshay's branch with the real `jobs` model lands:

1. Delete the `Job` stub class in `backend/app/models.py` (look for the
   `# STUB: owned by Lakshay` marker).
2. Import the real `Job` class wherever the recommender uses it.
3. Drop the `jobs` table-creation block from the migration above (the
   `if "jobs" not in existing` branch).

## Schema

| Column        | Type                  | Nullable | Notes                              |
|---------------|-----------------------|----------|------------------------------------|
| `id`          | `INTEGER` PK          | no       | Surrogate identifier               |
| `role`        | `VARCHAR(255)`        | no       | Indexed; case-insensitive filter   |
| `company`     | `VARCHAR(255)`        | no       | Indexed; case-insensitive filter   |
| `description` | `TEXT`                | no       | Embedded into 384-dim vector       |
| `link`        | `VARCHAR(2048)`       | yes      | External career page URL           |
| `city`        | `VARCHAR(120)`        | yes      |                                    |
| `state`       | `VARCHAR(120)`        | yes      |                                    |
| `country`     | `VARCHAR(120)`        | yes      |                                    |
| `salary_usd`  | `NUMERIC(12, 2)`      | yes      | Annual, USD                        |
| `posted_at`   | `DATE`                | yes      | Posting date                       |
| `created_at`  | `TIMESTAMPTZ`         | no       | Insertion time                     |

## Behavioural notes

- `description` should be the cleaned, plain-text description (no HTML).
  The recommender embeds it as-is; deduping markup keeps embeddings clean.
- When Lakshay's parser inserts/updates a row, the recommender will pick
  the change up on the next call to `recommend_for_user(...)` because
  `JobEmbedding` rows are computed lazily by `_ensure_job_vector(...)`.
- A future enhancement is to recompute the `JobEmbedding` whenever
  `description` changes (e.g. via a SQLAlchemy event listener); flagged
  as out-of-scope for the MVP.

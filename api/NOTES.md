# Notes

to start run uv run uvicorn app.main:app --reload --port 8000 in api directory

## Trade-offs made
- **Single assembled query with LATERAL JOIN** — slightly more complex SQL, but avoids N+1 queries and keeps variant selection in the database where it's most efficient.
- **In-memory progress summary computation on GET** — since we already fetch all blocks with progress

## With 2 more hours I would add
- **Structured logging** with correlation IDs per request for observability.
- **A health check endpoint** (`/health`) that verifies the Postgres connection.
- **Proper test suite** rather than relying on the manual execution of the curl_samples.sh
- **Database migrations**
- **Benchmark the assembled lesson query** with larger datasets to verify the LATERAL JOIN scales, and add a composite index on `block_variants(block_id, tenant_id)` if needed (one already exists in the provided schema)
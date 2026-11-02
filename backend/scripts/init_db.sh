#!/usr/bin/env bash
# Apply the schema (in order) and optionally the demo data.
#   DATABASE_URL=postgresql://user:pass@localhost:5432/advisor ./scripts/init_db.sh          # schema only
#   DATABASE_URL=... ./scripts/init_db.sh --seed                                             # schema + demo data
set -euo pipefail
cd "$(dirname "$0")/.."
: "${DATABASE_URL:?set DATABASE_URL first}"

for f in sql/schema.sql sql/schema_v2.sql sql/schema_v3.sql; do
  echo "applying $f"
  psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -q -f "$f"
done

if [[ "${1:-}" == "--seed" ]]; then
  echo "loading sql/seed.sql (demo data, password demo1234)"
  psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -q -f sql/seed.sql
fi
echo "done"
